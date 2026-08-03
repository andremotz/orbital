"""Animiert den Verlauf einer Mission -- als Vorschau oder als Datei.

Die Simulation wird einmal durchgerechnet und die Bahn dabei fein abgetastet;
erst danach wird gezeichnet. Vorschau und Export teilen sich denselben
Zeichenpfad, es kommt also genau das heraus, was die Vorschau zeigt.

Als Master entsteht ein MP4: H.264 komprimiert bei voller Qualität um ein
Vielfaches besser als GIF, das nur 256 Farben kennt. Das GIF für die README
wird daraus abgeleitet, mit einer auf den Inhalt zugeschnittenen Palette --
ffmpeg liefert damit kleinere und sauberere Ergebnisse als ein direkter
GIF-Export aus matplotlib.

Aufrufe:
    python make_animations.py --preview artemis2     # ansehen, nichts schreiben
    python make_animations.py                        # beide Missionen, MP4 + GIF
    python make_animations.py --no-gif chandrayaan2  # nur der MP4-Master
"""

import argparse
import os
import shutil
import subprocess
import sys

import numpy as np

from data.horizons import HorizonsError, load_cache
from data.scenario import load_named_scenario
from rust_integration import RustAcceleratedIntegrator

# Laufzeit und Bildrate. 25 Bilder je Sekunde wirken flüssig, ohne dass die
# 500 Einzelbilder das GIF unnötig aufblähen.
DURATION_SECONDS = 20.0
FRAMES_PER_SECOND = 25
FRAME_COUNT = int(DURATION_SECONDS * FRAMES_PER_SECOND)

# Die Bahn wird deutlich feiner abgetastet als Bilder gezeichnet werden. Sonst
# geriete der Bahnschweif zum Vieleck: Chandrayaans früher Orbit dauert rund
# 13,8 Stunden, bei 500 Bildern über 46 Tage entfielen darauf nur sechs Punkte.
SAMPLES_PER_FRAME = 12

# Sichtfeld: Rand um die bisher durchflogene Ausdehnung, und wie träge der
# Zoom nachzieht. Kleine Werte wirken ruhiger, brauchen aber länger, bis eine
# neu gewonnene Bahnhöhe ganz im Bild ist.
VIEW_MARGIN = 1.10
ZOOM_SMOOTHING = 0.05

MISSIONS = {
    "chandrayaan2": {
        "body": "Chandrayaan-2",
        "truth": "chandrayaan2_truth_fine",
        "title": "Chandrayaan-2",
        "subtitle": "Bahnanhebung und Mondtransfer, 22. Juli bis 6. September 2019",
        "duration": 4_011_300.0,
    },
    "artemis2": {
        "body": "Artemis II",
        "truth": "artemis2_truth_fine",
        "title": "Artemis II",
        "subtitle": "Bemannter Mondvorbeiflug auf freier Rückkehrbahn, 2. bis 11. April 2026",
        "duration": 769_380.0,
    },
}


def simulate(mission_key):
    """Rechnet die Mission durch und tastet Sonde und Mond fein ab.

    Zurück kommen erdrelative Bahnen sowie die Zeitpunkte, zu denen Manöver
    aktiv waren -- letztere, um die Zündungen im Bild markieren zu können.
    """
    mission = MISSIONS[mission_key]
    scenario = load_named_scenario(mission_key)
    integrator = RustAcceleratedIntegrator(use_rust=True)

    body = scenario.body(mission["body"])
    earth = scenario.body("Earth")
    moon = scenario.body("Moon")

    sample_count = FRAME_COUNT * SAMPLES_PER_FRAME
    sample_step = mission["duration"] / sample_count

    probe_track = np.zeros((sample_count, 2))
    moon_track = np.zeros((sample_count, 2))
    burning = np.zeros(sample_count, dtype=bool)
    times = np.zeros(sample_count)

    elapsed = 0.0
    for index in range(sample_count):
        target = index * sample_step
        while elapsed < target:
            integrator.calculate_states_batch(scenario.bodies, scenario.time_step, elapsed)
            elapsed += scenario.time_step

        origin = earth.getLatestState().vec_location
        probe_track[index] = (body.getLatestState().vec_location - origin)[:2]
        moon_track[index] = (moon.getLatestState().vec_location - origin)[:2]
        burning[index] = any(m.is_active(elapsed) for m in body.list_maneuvers)
        times[index] = elapsed

        if index % 1000 == 0:
            print(f"    {index}/{sample_count} Stützstellen", flush=True)

    return {
        "probe": probe_track,
        "moon": moon_track,
        "burning": burning,
        "times": times,
        "scenario": scenario,
    }


def reference_track(mission_key, duration):
    """Die tatsächlich geflogene Bahn, auf dasselbe Zeitraster gebracht."""
    try:
        cache = load_cache(MISSIONS[mission_key]["truth"])
    except HorizonsError:
        return None, None

    records = cache["records"]
    epoch = records[0]["jd"]
    seconds = np.array([(r["jd"] - epoch) * 86400.0 for r in records])
    positions = np.array([r["location"][:2] for r in records])

    # Nur den Abschnitt behalten, den auch die Simulation abdeckt
    inside = seconds <= duration
    return seconds[inside], positions[inside]


def view_limits(probe, moon, times, reference_seconds, reference_positions):
    """Sichtfeld je Bild: wächst mit der Bahn, zoomt aber nie zurück.

    Der Zoom folgt der bisher grössten durchflogenen Entfernung. Ohne
    Nachführung wären Chandrayaans frühe Erdumläufe unsichtbar -- zwischen
    Startbahn und Mondabstand liegt ein Faktor 63. Ohne Glättung dagegen
    ruckte das Bild bei jedem neuen Höchstwert.
    """
    extent = np.maximum.accumulate(np.max(np.abs(probe), axis=1))

    if reference_positions is not None:
        # Auch die reale Bahn soll ins Bild passen, sonst liefe sie heraus.
        # Sie hat ihr eigenes, gröberes Zeitraster und wird dafür auf das der
        # Simulation gebracht.
        reference_extent = np.maximum.accumulate(
            np.max(np.abs(reference_positions), axis=1)
        )
        extent = np.maximum(extent, np.interp(times, reference_seconds,
                                              reference_extent))

    # Mindestausdehnung, damit die ersten Bilder nicht auf einen Punkt zoomen.
    # Bewusst klein gehalten: an den Mondabstand gekoppelt wäre der Startorbit
    # von Chandrayaan-2 nur ein Fleck in der Bildmitte.
    extent = np.maximum(extent, 1.5e7)

    target = extent * VIEW_MARGIN
    smoothed = np.empty_like(target)
    smoothed[0] = target[0]
    for index in range(1, len(target)):
        follow = smoothed[index - 1] + ZOOM_SMOOTHING * (target[index] - smoothed[index - 1])
        # Nie zurückzoomen: ein schrumpfendes Bild wirkt wie ein Fehler
        smoothed[index] = max(smoothed[index - 1], follow)

    return smoothed


def build_animation(mission_key, data, reference_seconds, reference_positions):
    """Baut Figur und Zeichenfunktion. Vorschau und Export nutzen beides."""
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    from rendering.plotstyle import (
        ACCENT,
        BACKGROUND,
        FOREGROUND,
        GRID,
        REAL,
        SIMULATED,
        WARN,
        style_axes,
        style_legend,
    )

    mission = MISSIONS[mission_key]
    probe, moon = data["probe"], data["moon"]
    limits = view_limits(probe, moon, data["times"],
                         reference_seconds, reference_positions)

    figure, axes = plt.subplots(figsize=(8.0, 8.0))
    figure.patch.set_facecolor(BACKGROUND)
    style_axes(axes, f"{mission['title']}\n{mission['subtitle']}",
               "x (1000 km, Ekliptik)", "y (1000 km, Ekliptik)")
    axes.set_aspect("equal")

    scale = 1e6  # Meter -> 1000 km

    moon_path, = axes.plot([], [], color=GRID, linewidth=1.0, linestyle="--",
                           label="Mondbahn")
    real_path, = axes.plot([], [], color=REAL, linewidth=2.0,
                           label="real (JPL Horizons)")
    sim_path, = axes.plot([], [], color=SIMULATED, linewidth=1.8,
                          label="simuliert")
    probe_dot, = axes.plot([], [], "o", color=SIMULATED, markersize=6)
    moon_dot, = axes.plot([], [], "o", color=FOREGROUND, markersize=7)
    burn_dot, = axes.plot([], [], "o", color=WARN, markersize=13, alpha=0.75)

    axes.plot(0, 0, "o", color=ACCENT, markersize=8)
    axes.annotate("Erde", (0, 0), textcoords="offset points", xytext=(9, -14),
                  color=FOREGROUND, fontsize=9)

    clock = axes.text(0.02, 0.97, "", transform=axes.transAxes, va="top",
                      color=FOREGROUND, fontsize=11, family="monospace")
    event = axes.text(0.02, 0.05, "", transform=axes.transAxes,
                      color=WARN, fontsize=11)
    style_legend(axes, loc="upper right")

    def draw(frame):
        upto = min((frame + 1) * SAMPLES_PER_FRAME, len(probe))
        head = upto - 1
        moment = data["times"][head]

        sim_path.set_data(probe[:upto, 0] / scale, probe[:upto, 1] / scale)
        moon_path.set_data(moon[:upto, 0] / scale, moon[:upto, 1] / scale)
        probe_dot.set_data([probe[head, 0] / scale], [probe[head, 1] / scale])
        moon_dot.set_data([moon[head, 0] / scale], [moon[head, 1] / scale])

        if reference_positions is not None:
            visible = reference_seconds <= moment
            real_path.set_data(reference_positions[visible, 0] / scale,
                               reference_positions[visible, 1] / scale)

        if data["burning"][head]:
            burn_dot.set_data([probe[head, 0] / scale], [probe[head, 1] / scale])
            event.set_text("Triebwerk brennt")
        else:
            burn_dot.set_data([], [])
            event.set_text("")

        limit = limits[head] / scale
        axes.set_xlim(-limit, limit)
        axes.set_ylim(-limit, limit)

        distance = float(np.hypot(probe[head, 0], probe[head, 1]))
        clock.set_text(f"Tag {moment / 86400:5.2f}\n"
                       f"{distance / 1e3:8,.0f} km von der Erde".replace(",", "."))
        return [sim_path, moon_path, real_path, probe_dot, moon_dot, burn_dot,
                clock, event]

    animation = FuncAnimation(figure, draw, frames=FRAME_COUNT,
                              interval=1000.0 / FRAMES_PER_SECOND, blit=False)
    return figure, animation


def write_gif(source, target, width=640):
    """Leitet aus dem MP4-Master ein GIF mit eigener Palette ab.

    Ein GIF kennt nur 256 Farben. Wer sie aus dem Inhalt bestimmt statt aus
    einer festen Tabelle, spart deutlich Platz und vermeidet Streifen in den
    Verläufen -- deshalb der Umweg über palettegen und paletteuse.
    """
    palette = target + ".palette.png"
    chain = f"fps={FRAMES_PER_SECOND},scale={width}:-1:flags=lanczos"

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", source,
         "-vf", f"{chain},palettegen=stats_mode=diff", palette],
        check=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", source, "-i", palette,
         "-lavfi", f"{chain}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3",
         target],
        check=True,
    )
    os.remove(palette)


def render(mission_key, outdir, make_gif=True):
    """Rechnet, rendert den MP4-Master und leitet daraus das GIF ab."""
    from matplotlib.animation import FFMpegWriter

    print(f"  {mission_key}: Simulation ...", flush=True)
    data = simulate(mission_key)
    seconds, positions = reference_track(mission_key, MISSIONS[mission_key]["duration"])

    figure, animation = build_animation(mission_key, data, seconds, positions)

    video = os.path.join(outdir, f"{mission_key}.mp4")
    print(f"  {mission_key}: {FRAME_COUNT} Bilder -> {video}", flush=True)
    animation.save(video, writer=FFMpegWriter(
        fps=FRAMES_PER_SECOND, bitrate=4000,
        extra_args=["-pix_fmt", "yuv420p"],
    ))

    import matplotlib.pyplot as plt
    plt.close(figure)

    if make_gif:
        gif = os.path.join(outdir, f"{mission_key}.gif")
        write_gif(video, gif)
        print(f"  {mission_key}: -> {gif} "
              f"({os.path.getsize(gif) / 1e6:.1f} MB)", flush=True)


def preview(mission_key):
    """Spielt die Animation einmal ab, ohne etwas zu schreiben."""
    import matplotlib.pyplot as plt

    print(f"  {mission_key}: Simulation ...", flush=True)
    data = simulate(mission_key)
    seconds, positions = reference_track(mission_key, MISSIONS[mission_key]["duration"])

    figure, animation = build_animation(mission_key, data, seconds, positions)
    print(f"  {DURATION_SECONDS:.0f} Sekunden Laufzeit, Fenster schliessen zum Beenden")
    plt.show()
    return animation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    # Kein `choices`: argparse prüft bei nargs="*" auch den Vorgabewert
    # dagegen, sodass sich "alle Missionen" nicht als Default ausdrücken lässt.
    parser.add_argument("missions", nargs="*", default=[],
                        help=f"Welche Missionen ({', '.join(MISSIONS)}); "
                             f"ohne Angabe alle")
    parser.add_argument("--preview", action="store_true",
                        help="Live ansehen statt exportieren")
    parser.add_argument("--no-gif", action="store_true",
                        help="Nur den MP4-Master schreiben")
    parser.add_argument("--outdir", default=os.path.join("docs", "animations"))
    args = parser.parse_args(argv)

    missions = args.missions or list(MISSIONS)
    unknown = [name for name in missions if name not in MISSIONS]
    if unknown:
        parser.error(f"Unbekannte Mission: {', '.join(unknown)}. "
                     f"Bekannt sind: {', '.join(MISSIONS)}")

    if args.preview:
        # Vorschau braucht ein Fenster; ein erzwungenes Agg würde sie
        # stillschweigend zu einer Rechnung ohne Bild machen.
        import matplotlib

        if matplotlib.get_backend().lower() == "agg":
            print("Kein interaktives Backend verfügbar -- Vorschau nicht möglich.")
            return 1
        for mission_key in missions:
            preview(mission_key)
        return 0

    import matplotlib

    matplotlib.use("Agg")

    if shutil.which("ffmpeg") is None:
        print("ffmpeg nicht gefunden. Es wird für MP4 und GIF gebraucht.")
        return 1

    os.makedirs(args.outdir, exist_ok=True)
    print("Erzeuge Animationen:")
    for mission_key in missions:
        render(mission_key, args.outdir, make_gif=not args.no_gif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
