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
from models.state import State
from rust_integration import RustAcceleratedIntegrator

# Laufzeit und Bildrate. 25 Bilder je Sekunde wirken flüssig, ohne dass die
# 500 Einzelbilder das GIF unnötig aufblähen.
DEFAULT_DURATION_SECONDS = 20.0
DEFAULT_FRAMES_PER_SECOND = 25


def timing(mission_key):
    """Laufzeit, Bildrate und Bildzahl einer Mission.

    Die Reisephase von Cassini laeuft laenger: sieben Jahre in zwanzig
    Sekunden liessen die Vorbeifluege vorbeihuschen. Dafuer genuegt dort eine
    kleinere Bildrate, weil sich zwischen den Begegnungen wenig bewegt -- das
    haelt zugleich das GIF in ertraeglicher Groesse.
    """
    mission = MISSIONS[mission_key]
    seconds = mission.get("runtime", DEFAULT_DURATION_SECONDS)
    fps = mission.get("fps", DEFAULT_FRAMES_PER_SECOND)
    return seconds, fps, int(round(seconds * fps))

# Die Bahn wird deutlich feiner abgetastet als Bilder gezeichnet werden. Sonst
# geriete der Bahnschweif zum Vieleck: Chandrayaans früher Orbit dauert rund
# 13,8 Stunden, bei 500 Bildern über 46 Tage entfielen darauf nur sechs Punkte.
SAMPLES_PER_FRAME = 12

# Sichtfeld: Rand um die bisher durchflogene Ausdehnung, und wie träge der
# Zoom nachzieht. Kleine Werte wirken ruhiger, brauchen aber länger, bis eine
# neu gewonnene Bahnhöhe ganz im Bild ist.
VIEW_MARGIN = 1.10
ZOOM_SMOOTHING = 0.05

# Die eingeblendeten Texte sind englisch, weil die Animationen in der README
# stehen und diese englisch ist. Kommentare und Dokumentation bleiben deutsch
# wie im übrigen Projekt.
# `center` ist der Körper, um den herum gezeichnet wird, `context` sind die
# Begleiter, deren Bahnen als Zusammenhang mitlaufen. `barycentric` sagt, dass
# die Referenzbahn absolut vorliegt statt relativ zum Mittelpunkt -- bei den
# Mondmissionen ist sie geozentrisch, bei Cassini auf den Schwerpunkt des
# Sonnensystems bezogen, und die beiden zu verwechseln kostet über eine
# Million Kilometer.
MISSIONS = {
    "chandrayaan2": {
        "body": "Chandrayaan-2",
        "truth": "chandrayaan2_truth_fine",
        "title": "Chandrayaan-2",
        "subtitle": "Orbit raising and lunar transfer, 22 July to 6 September 2019",
        "duration": 4_011_300.0,
        "center": "Earth",
        "context": ["Moon"],
        "barycentric": False,
        "scale": 1e6,
        "unit": "1000 km",
    },
    "artemis2": {
        "body": "Artemis II",
        "truth": "artemis2_truth_fine",
        "title": "Artemis II",
        "subtitle": "Crewed lunar flyby on a free-return trajectory, 2 to 11 April 2026",
        "duration": 769_380.0,
        "center": "Earth",
        "context": ["Moon"],
        "barycentric": False,
        "scale": 1e6,
        "unit": "1000 km",
    },
    "cassini_cruise": {
        "body": "Cassini",
        "truth": "cassini_truth_fine",
        "title": "Cassini-Huygens",
        "subtitle": "Seven years to Saturn: Venus, Venus, Earth, Jupiter",
        "duration": 210_000_000.0,
        "center": "Sun",
        "context": ["Venus", "Earth", "Jupiter", "Saturn"],
        "barycentric": True,
        "anchors": "cassini_anchors",
        "runtime": 60.0,
        "fps": 15,
        # Dreimal so viele Bilder wie bei den Mondmissionen; ohne schmaleres
        # GIF spraenge die Datei die Groesse, die in einer README zumutbar ist
        "gif_width": 440,
        "scale": 1.495978707e11,
        "unit": "AU",
    },
}


def load_anchors(mission_key, epoch_jd):
    """Zeitpunkte und Zustände, an denen die reale Bahn neu eingesetzt wird.

    Über eine Vorbeiflugkette lässt sich nicht durchrechnen: eine Begegnung
    verstärkt den bis dahin angesammelten Fehler um mehr als das Zehnfache,
    beim ersten Venus-Vorbeiflug gemessen um das 46-fache. Wer trotzdem die
    ganze Reise zeigen will, muss die Wirklichkeit zwischendurch nachreichen.

    Verankert wird jeweils kurz *nach* einem Ereignis. Jede Etappe dazwischen
    ist damit reine Reisephase und für sich genommen ein ehrlicher Test des
    Modells.
    """
    name = MISSIONS[mission_key].get("anchors")
    if not name:
        return []

    entries = load_cache(name)["anchors"]
    return [
        {
            "label": entry["label"],
            "time": (entry["jd"] - epoch_jd) * 86400.0,
            "location": np.array(entry["location"], dtype=float),
            "velocity": np.array(entry["velocity"], dtype=float),
        }
        for entry in sorted(entries, key=lambda e: e["jd"])
    ]


def simulate(mission_key):
    """Rechnet die Mission durch und tastet die Bahnen fein ab.

    Zurück kommen Bahnen relativ zum Mittelpunkt der Darstellung, die
    Zeitpunkte aktiver Manöver und die gesetzten Verankerungen.
    """
    mission = MISSIONS[mission_key]
    scenario = load_named_scenario(mission_key)
    integrator = RustAcceleratedIntegrator(use_rust=True)

    body = scenario.body(mission["body"])
    center = scenario.body(mission["center"])
    context = [scenario.body(name) for name in mission["context"]]

    truth = load_cache(mission["truth"])["records"]
    anchors = load_anchors(mission_key, truth[0]["jd"])
    pending = list(anchors)

    _, _, frame_count = timing(mission_key)
    sample_count = frame_count * SAMPLES_PER_FRAME
    sample_step = mission["duration"] / sample_count

    probe_track = np.zeros((sample_count, 2))
    context_tracks = np.zeros((len(context), sample_count, 2))
    # Absolute Bahn des Mittelpunkts: nötig, um eine absolut vorliegende
    # Referenzbahn in dieselbe Darstellung zu bringen
    center_track = np.zeros((sample_count, 2))
    burning = np.zeros(sample_count, dtype=bool)
    times = np.zeros(sample_count)
    anchored = []
    fired = []
    fired_seen = set()

    elapsed = 0.0
    for index in range(sample_count):
        target = index * sample_step
        while elapsed < target:
            integrator.calculate_states_batch(scenario.bodies, scenario.time_step, elapsed)
            elapsed += scenario.time_step

            # Ist eine Verankerung fällig, tritt der reale Zustand an die
            # Stelle des gerechneten -- und der Fehler der Etappe endet hier.
            while pending and elapsed >= pending[0]["time"]:
                entry = pending.pop(0)
                body.addState(State(entry["velocity"].copy(),
                                    entry["location"].copy()))
                anchored.append({"index": index, "time": elapsed,
                                 "label": entry["label"]})

        origin = center.getLatestState().vec_location
        center_track[index] = origin[:2]
        probe_track[index] = (body.getLatestState().vec_location - origin)[:2]
        for slot, companion in enumerate(context):
            context_tracks[slot, index] = (
                companion.getLatestState().vec_location - origin
            )[:2]
        burning[index] = any(m.is_active(elapsed) for m in body.list_maneuvers)
        times[index] = elapsed

        # Gezuendete Manoever festhalten. Bei einem Zielmanoever steht das
        # Delta-v erst nach dem Zuenden fest, deshalb hier und nicht vorab.
        for maneuver in body.list_maneuvers:
            if maneuver.activated_at is None or maneuver in fired_seen:
                continue
            fired_seen.add(maneuver)
            magnitude = maneuver.resolved_delta_v
            if magnitude is None:
                magnitude = maneuver.delta_v
            fired.append({
                "index": index,
                "time": maneuver.activated_at,
                "label": maneuver.label or "burn",
                "delta_v": abs(magnitude) if magnitude is not None else None,
            })

        if index % 1000 == 0:
            print(f"    {index}/{sample_count} Stützstellen", flush=True)

    return {
        "probe": probe_track,
        "context": context_tracks,
        "burning": burning,
        "times": times,
        "anchors": anchored,
        "burns": fired,
        "center": center_track,
        "scenario": scenario,
    }


def reference_track(mission_key, duration, center_track=None):
    """Die tatsächlich geflogene Bahn, auf dasselbe Zeitraster gebracht.

    `center_track` wird gebraucht, wenn die Referenz absolut vorliegt, die
    Darstellung aber um einen Körper herum aufgebaut ist -- dann muss dessen
    Bahn abgezogen werden. Bei den Mondmissionen ist die Referenz schon
    geozentrisch und es entfällt.
    """
    mission = MISSIONS[mission_key]
    try:
        cache = load_cache(mission["truth"])
    except HorizonsError:
        return None, None

    records = cache["records"]
    epoch = records[0]["jd"]
    seconds = np.array([(r["jd"] - epoch) * 86400.0 for r in records])
    positions = np.array([r["location"][:2] for r in records])

    if mission.get("barycentric") and center_track is not None:
        # Die Bahn des Mittelpunkts auf das Raster der Referenz bringen
        offsets = np.column_stack([
            np.interp(seconds, center_track["times"], center_track["positions"][:, axis])
            for axis in (0, 1)
        ])
        positions = positions - offsets

    # Nur den Abschnitt behalten, den auch die Simulation abdeckt
    inside = seconds <= duration
    return seconds[inside], positions[inside]


def view_limits(probe, context, times, reference_seconds, reference_positions,
                minimum_extent=1.5e7):
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
    extent = np.maximum(extent, minimum_extent)

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
        body_colour,
        style_axes,
        style_legend,
    )

    mission = MISSIONS[mission_key]
    probe, context = data["probe"], data["context"]
    scale = mission["scale"]
    unit = mission["unit"]

    # Auf interplanetarer Skala waeren 15.000 km Mindestausdehnung sinnlos
    minimum_extent = max(1.5e7, scale * 0.05)
    limits = view_limits(probe, context, data["times"],
                         reference_seconds, reference_positions,
                         minimum_extent=minimum_extent)

    figure, axes = plt.subplots(figsize=(8.0, 8.0))
    figure.patch.set_facecolor(BACKGROUND)
    style_axes(axes, f"{mission['title']}\n{mission['subtitle']}",
               f"x ({unit}, ecliptic)", f"y ({unit}, ecliptic)")
    axes.set_aspect("equal")

    # Jeder Körper in eigener Farbe, Bahn und Punkt gleich eingefärbt. Die
    # Legende benennt sie einmal fest, statt Namen durchs Bild wandern zu
    # lassen -- mitlaufende Beschriftungen überlappen sich, verdecken die Bahn
    # und laufen am Rand aus dem Diagramm.
    #
    # Kontextbahnen zuerst, damit sie hinter allem liegen -- und deutlich
    # zurueckgenommen: sie geben Zusammenhang, sind aber nicht der Gegenstand.
    context_paths = [
        axes.plot([], [], color=body_colour(name), linewidth=0.8,
                  linestyle="--", alpha=0.3)[0]
        for name in mission["context"]
    ]

    # Die simulierte Bahn gestrichelt ueber die durchgezogene reale. Zwei
    # deckungsgleiche Volllinien sind nicht nur ununterscheidbar, sie mitteln
    # sich weg: REAL und SIMULATED liegen sich im Farbkreis fast gegenueber,
    # und die Kantenglaettung macht aus (77,163,255) und (255,157,77) ein
    # neutrales Grau. Gemessen waren es 7380 graue gegen 659 farbige Pixel --
    # das Bild sah aus, als gaebe es nur eine einzige, graue Bahn.
    #
    # Gestrichelt teilen sich beide keine Pixel mehr: in den Luecken bleibt
    # Blau blau, auf den Strichen Orange orange.
    real_path, = axes.plot([], [], color=REAL, linewidth=2.6,
                           label="actually flown (JPL Horizons)")
    sim_path, = axes.plot([], [], color=SIMULATED, linewidth=1.9,
                          linestyle=(0, (5, 5)), label="simulated")

    # Koerper danach, damit sie in der Legende hinter den Bahnen stehen:
    # erst worum es geht, dann was mitlaeuft.
    context_dots = [
        axes.plot([], [], "o", color=body_colour(name), markersize=6,
                  label=name)[0]
        for name in mission["context"]
    ]
    probe_dot, = axes.plot([], [], "o", color=SIMULATED, markersize=6,
                           label=mission["body"])
    burn_dot, = axes.plot([], [], "o", color=WARN, markersize=13, alpha=0.75)
    # Verankerungen bleiben als Marker stehen: sie sind Stellen, an denen die
    # Wirklichkeit nachgereicht wurde, und duerfen nicht als Modellguete
    # durchgehen.
    anchor_dots, = axes.plot([], [], "x", color=ACCENT, markersize=10,
                             markeredgewidth=2.0,
                             label="real state re-injected" if data["anchors"] else None)

    axes.plot(0, 0, "o", color=body_colour(mission["center"]), markersize=9,
              label=f"{mission['center']} (centre)")

    clock = axes.text(0.02, 0.97, "", transform=axes.transAxes, va="top",
                      color=FOREGROUND, fontsize=11, family="monospace")
    # Was bisher gezuendet wurde, bleibt stehen -- so laesst sich am Ende
    # ablesen, aus welchen Manoevern die Bahn entstanden ist.
    logbook = axes.text(0.02, 0.30, "", transform=axes.transAxes, va="top",
                        color=FOREGROUND, fontsize=8.5, family="monospace")
    event = axes.text(0.02, 0.05, "", transform=axes.transAxes,
                      color=WARN, fontsize=11)
    # Bewusst einspaltig: zweispaltig waechst die Legende in die Breite und
    # schiebt sich ueber die Anzeige oben links. Hoch und schmal stoert nicht.
    style_legend(axes, loc="upper right",
                 fontsize=7.5 if len(mission["context"]) > 2 else 9)

    def draw(frame):
        upto = min((frame + 1) * SAMPLES_PER_FRAME, len(probe))
        head = upto - 1
        moment = data["times"][head]

        sim_path.set_data(probe[:upto, 0] / scale, probe[:upto, 1] / scale)
        probe_dot.set_data([probe[head, 0] / scale], [probe[head, 1] / scale])
        for slot, path in enumerate(context_paths):
            path.set_data(context[slot, :upto, 0] / scale,
                          context[slot, :upto, 1] / scale)
        for slot, dot in enumerate(context_dots):
            dot.set_data([context[slot, head, 0] / scale],
                         [context[slot, head, 1] / scale])

        reached = [a for a in data["anchors"] if a["index"] <= head]
        if reached:
            anchor_dots.set_data(
                [probe[a["index"], 0] / scale for a in reached],
                [probe[a["index"], 1] / scale for a in reached],
            )

        offset = None
        if reference_positions is not None:
            visible = reference_seconds <= moment
            real_path.set_data(reference_positions[visible, 0] / scale,
                               reference_positions[visible, 1] / scale)
            here = np.array([
                np.interp(moment, reference_seconds, reference_positions[:, axis])
                for axis in (0, 1)
            ])
            offset = float(np.hypot(*(probe[head] - here)))

        if data["burning"][head]:
            burn_dot.set_data([probe[head, 0] / scale], [probe[head, 1] / scale])
            event.set_text("engine burning")
        else:
            burn_dot.set_data([], [])
            event.set_text("")

        # Kurz nach einer Verankerung benennen, was gerade passiert ist
        for entry in data["anchors"]:
            if 0 <= head - entry["index"] < SAMPLES_PER_FRAME * 12:
                event.set_text(f"{entry['label']}: real state re-injected")

        limit = limits[head] / scale
        axes.set_xlim(-limit, limit)
        axes.set_ylim(-limit, limit)

        distance = float(np.hypot(probe[head, 0], probe[head, 1]))
        if unit == "AU":
            reading = f"{distance / scale:8.3f} AU from {mission['center']}"
        else:
            reading = f"{distance / 1e3:8,.0f} km from {mission['center']}"
        lines = [f"day {moment / 86400:6.1f}", reading]
        if offset is not None:
            lines.append(f"{offset / 1e3:8,.0f} km off the real track")
        clock.set_text("\n".join(lines))

        entries = []
        for burn in data["burns"]:
            if burn["index"] > head:
                continue
            strength = ("" if burn["delta_v"] is None
                        else f"  {burn['delta_v']:6.1f} m/s")
            entries.append(f"  day {burn['time'] / 86400:6.1f}  "
                           f"{burn['label']:<14}{strength}")
        for anchor in data["anchors"]:
            if anchor["index"] > head:
                continue
            entries.append(f"  day {anchor['time'] / 86400:6.1f}  "
                           f"{anchor['label']:<14}  real state")
        if entries:
            title = ("manoeuvres executed" if data["burns"]
                     else "trajectory re-anchored")
            logbook.set_text(title + "\n" + "\n".join(entries))
        return ([sim_path, real_path, probe_dot, burn_dot, anchor_dots,
                 clock, event, logbook] + context_paths + context_dots)

    runtime, fps, frame_count = timing(mission_key)
    animation = FuncAnimation(figure, draw, frames=frame_count,
                              interval=1000.0 / fps, blit=False)
    return figure, animation


def write_gif(source, target, fps, width=560):
    """Leitet aus dem MP4-Master ein GIF mit eigener Palette ab.

    Ein GIF kennt nur 256 Farben. Wer sie aus dem Inhalt bestimmt statt aus
    einer festen Tabelle, spart deutlich Platz und vermeidet Streifen in den
    Verläufen -- deshalb der Umweg über palettegen und paletteuse.
    """
    palette = target + ".palette.png"
    chain = f"fps={fps},scale={width}:-1:flags=lanczos"

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
    seconds, positions = reference_track(
        mission_key, MISSIONS[mission_key]["duration"],
        {"times": data["times"], "positions": data["center"]},
    )

    figure, animation = build_animation(mission_key, data, seconds, positions)

    video = os.path.join(outdir, f"{mission_key}.mp4")
    runtime, fps, frame_count = timing(mission_key)
    print(f"  {mission_key}: {frame_count} Bilder, {runtime:.0f} s -> {video}", flush=True)
    animation.save(video, writer=FFMpegWriter(
        fps=fps, bitrate=4000,
        extra_args=["-pix_fmt", "yuv420p"],
    ))

    import matplotlib.pyplot as plt
    plt.close(figure)

    if make_gif:
        gif = os.path.join(outdir, f"{mission_key}.gif")
        write_gif(video, gif, fps,
                  width=MISSIONS[mission_key].get("gif_width", 560))
        print(f"  {mission_key}: -> {gif} "
              f"({os.path.getsize(gif) / 1e6:.1f} MB)", flush=True)


def preview(mission_key):
    """Spielt die Animation einmal ab, ohne etwas zu schreiben."""
    import matplotlib.pyplot as plt

    print(f"  {mission_key}: Simulation ...", flush=True)
    data = simulate(mission_key)
    seconds, positions = reference_track(
        mission_key, MISSIONS[mission_key]["duration"],
        {"times": data["times"], "positions": data["center"]},
    )

    figure, animation = build_animation(mission_key, data, seconds, positions)
    print(f"  {timing(mission_key)[0]:.0f} Sekunden Laufzeit, Fenster schliessen zum Beenden")
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
