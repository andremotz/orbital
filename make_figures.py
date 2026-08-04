"""Erzeugt die Abbildungen für die README.

Alle Abbildungen entstehen aus denselben Daten, mit denen die Simulation auch
geprüft wird -- den Ephemeriden aus dem Cache und Läufen des eigenen Kernels.
Es wird nichts nachgezeichnet oder geglättet.

Aufruf:  python make_figures.py [--outdir docs/figures]
"""

import argparse
import math
import os

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from data.constants import GM_EARTH
from data.horizons import load_cache
from data.scenario import load_named_scenario
from physics.elements import elements_from_state
from physics.integrator import step
from rendering.plotstyle import (
    ACCENT,
    BACKGROUND,
    FOREGROUND,
    GRID,
    REAL,
    SIMULATED,
    WARN,
    style_axes,
)
from rust_integration import RustAcceleratedIntegrator

KM = 1e3


def new_figure(width=10.0, height=6.0):
    figure, axes = plt.subplots(figsize=(width, height))
    figure.patch.set_facecolor(BACKGROUND)
    return figure, axes


def save(figure, path):
    figure.tight_layout()
    figure.savefig(path, dpi=140, facecolor=BACKGROUND)
    plt.close(figure)
    print(f"  {path}")


def run_scenario(name, truth_records, body_name):
    """Läuft ein Szenario ab und sammelt die Bahn an den Referenzzeitpunkten."""
    scenario = load_named_scenario(name)
    integrator = RustAcceleratedIntegrator(use_rust=True)
    body = scenario.body(body_name)
    earth = scenario.body("Earth")
    moon = scenario.body("Moon")

    epoch = truth_records[0]["jd"]
    simulated, moon_track = [], []
    elapsed = 0.0
    for record in truth_records:
        target = (record["jd"] - epoch) * 86400.0
        while elapsed < target:
            integrator.calculate_states_batch(scenario.bodies, 60.0, elapsed)
            elapsed += 60.0
        simulated.append((body.getLatestState().vec_location
                          - earth.getLatestState().vec_location).copy())
        moon_track.append((moon.getLatestState().vec_location
                           - earth.getLatestState().vec_location).copy())

    return np.array(simulated), np.array(moon_track)


def figure_artemis_trajectory(outdir):
    """Die Flugbahn von Artemis II, simuliert gegen real."""
    truth = load_cache("artemis2_truth")["records"]
    simulated, moon = run_scenario("artemis2", truth, "Artemis II")
    actual = np.array([record["location"] for record in truth])

    figure, axes = new_figure(9.0, 8.0)
    style_axes(axes,
               "Artemis II: freie Rückkehrbahn um den Mond\n"
               "Simulation gegen die tatsächlich geflogene Bahn",
               "x (1000 km, Ekliptik)", "y (1000 km, Ekliptik)")

    axes.plot(moon[:, 0] / 1e6, moon[:, 1] / 1e6, color=GRID, linewidth=1.2,
              linestyle="--", label="Mondbahn")
    axes.plot(actual[:, 0] / 1e6, actual[:, 1] / 1e6, color=REAL, linewidth=2.4,
              label="real (JPL Horizons)")
    axes.plot(simulated[:, 0] / 1e6, simulated[:, 1] / 1e6, color=SIMULATED,
              linewidth=2.0, linestyle="-", label="simuliert")

    axes.plot(0, 0, "o", color=ACCENT, markersize=9)
    axes.annotate("Erde", (0, 0), textcoords="offset points", xytext=(10, -14),
                  color=FOREGROUND, fontsize=9)

    furthest = int(np.argmax(np.linalg.norm(actual, axis=1)))
    axes.plot(moon[furthest, 0] / 1e6, moon[furthest, 1] / 1e6, "o",
              color=FOREGROUND, markersize=7)
    axes.annotate("Mond bei\ndichtester Annäherung",
                  (moon[furthest, 0] / 1e6, moon[furthest, 1] / 1e6),
                  textcoords="offset points", xytext=(-40, 18),
                  color=FOREGROUND, fontsize=8, ha="center")

    axes.set_aspect("equal")
    legend = axes.legend(facecolor=BACKGROUND, edgecolor=GRID, fontsize=9)
    for text in legend.get_texts():
        text.set_color(FOREGROUND)

    save(figure, os.path.join(outdir, "artemis2_trajectory.png"))


def figure_artemis_distance(outdir):
    """Erdabstand über die Mission, mit dem veröffentlichten Höchstwert."""
    truth = load_cache("artemis2_truth")["records"]
    simulated, _ = run_scenario("artemis2", truth, "Artemis II")
    actual = np.array([record["location"] for record in truth])
    epoch = truth[0]["jd"]
    days = np.array([(record["jd"] - epoch) for record in truth])

    figure, axes = new_figure()
    style_axes(axes,
               "Artemis II: Abstand zur Erde\n"
               "größte Entfernung real 413.146 km, simuliert 418.745 km (1,4 % Abweichung)",
               "Tage seit dem 2. April 2026, 02:10 UTC", "Abstand zur Erde (1000 km)")

    axes.plot(days, np.linalg.norm(actual, axis=1) / 1e6, color=REAL,
              linewidth=2.4, label="real (JPL Horizons)")
    axes.plot(days, np.linalg.norm(simulated, axis=1) / 1e6, color=SIMULATED,
              linewidth=2.0, label="simuliert")
    axes.axhline(413.1462, color=ACCENT, linewidth=1.0, linestyle=":",
                 label="NASA: 413.146,2 km")

    scenario = load_named_scenario("artemis2")
    for maneuver in scenario.body("Artemis II").list_maneuvers:
        if maneuver.delta_v < 100.0:
            continue
        moment = maneuver.earliest_time / 86400.0
        axes.axvline(moment, color=WARN, linewidth=1.0, linestyle="--")
        axes.annotate(f"TLI, {maneuver.delta_v:.0f} m/s", (moment, 300),
                      textcoords="offset points", xytext=(8, 0),
                      color=WARN, fontsize=9)

    legend = axes.legend(facecolor=BACKGROUND, edgecolor=GRID, fontsize=9)
    for text in legend.get_texts():
        text.set_color(FOREGROUND)

    save(figure, os.path.join(outdir, "artemis2_distance.png"))


def figure_burn_detection(outdir):
    """Wie das Brennprofil aus der realen Bahn gewonnen wird."""
    detection = load_cache("artemis2_maneuvers")
    maneuvers = detection["maneuvers"]

    figure, axes = new_figure()
    style_axes(axes,
               "Manöver aus der geflogenen Bahn gewinnen\n"
               "zwischen den Burns ist die Bewegung ballistisch -- was übrig bleibt, ist Schub",
               "Manöver (Reihenfolge im Missionsverlauf)",
               "unerklärte Geschwindigkeitsänderung (m/s)")

    labels = [entry["start"][5:17] for entry in maneuvers]
    values = [entry["delta_v"] for entry in maneuvers]
    colors = [ACCENT if value > 100 else SIMULATED for value in values]

    positions = np.arange(len(values))
    axes.bar(positions, values, color=colors, width=0.55)
    axes.set_yscale("log")
    axes.set_xticks(positions)
    axes.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)

    median = detection["quiet_residual_median"]
    axes.axhline(median, color=REAL, linewidth=1.0, linestyle=":",
                 label=f"Grundrauschen ohne Manöver: {median:.4f} m/s")

    for index, entry in enumerate(maneuvers):
        if entry["delta_v"] > 100:
            axes.annotate("TLI\nNASA: 388 m/s\nerkannt: 388,3 m/s",
                          (index, entry["delta_v"]), textcoords="offset points",
                          xytext=(0, 12), ha="center", color=ACCENT, fontsize=9)
        elif abs(entry["delta_v"] - 3.0) < 0.3:
            axes.annotate("OTC-3\nNASA: 3 m/s\nerkannt: 3,0 m/s",
                          (index, entry["delta_v"]), textcoords="offset points",
                          xytext=(0, 12), ha="center", color=FOREGROUND, fontsize=8)

    legend = axes.legend(facecolor=BACKGROUND, edgecolor=GRID, fontsize=9,
                         loc="upper left")
    for text in legend.get_texts():
        text.set_color(FOREGROUND)

    save(figure, os.path.join(outdir, "burn_detection.png"))


def figure_trigger_effect(outdir):
    """Zielsteuerung gegen abgespieltes Delta-v.

    Die Abbildung endet mit dem Mondeinfang. Danach umkreist die Sonde den
    Mond, und ein *geozentrisches* Apogäum sagt über ihre Bahn nichts mehr aus
    -- es zu zeichnen ergäbe nur Zacken.
    """
    import json

    from data.scenario import SCENARIO_DIR

    truth = load_cache("chandrayaan2_truth")["records"]
    epoch = truth[0]["jd"]

    # Bis kurz nach dem Mondtransfer. Danach zerfaellt im Replay-Lauf die
    # Bahn vollends, was nur noch Zacken erzeugt statt etwas zu zeigen.
    until_day = 25.5
    records = [r for r in truth if (r["jd"] - epoch) <= until_day]
    days = np.array([record["jd"] - epoch for record in records])

    with open(os.path.join(SCENARIO_DIR, "chandrayaan2.json"), encoding="utf-8") as f:
        raw_maneuvers = json.load(f)["maneuvers"]

    def apoapsis_track(replay):
        """Bahnverlauf, wahlweise zielgesteuert oder als Delta-v abgespielt."""
        scenario = load_named_scenario("chandrayaan2")
        probe = scenario.body("Chandrayaan-2")
        earth = scenario.body("Earth")

        if replay:
            # Den früheren Stand nachstellen: das gemessene Delta-v zur
            # geplanten Zeit, ohne Ziel und ohne Auslöser.
            for maneuver, entry in zip(probe.list_maneuvers, raw_maneuvers):
                if "measured_delta_v" not in entry or "planned_at" not in entry:
                    continue
                maneuver.target_apoapsis = None
                maneuver.delta_v = entry["measured_delta_v"]
                maneuver.time_start = entry["planned_at"]
                maneuver.trigger = None
                maneuver.activated_at = entry["planned_at"]

        integrator = RustAcceleratedIntegrator(use_rust=True)
        elapsed = 0.0
        track = []
        for record in records:
            target = (record["jd"] - epoch) * 86400.0
            while elapsed < target:
                integrator.calculate_states_batch(scenario.bodies, 60.0, elapsed)
                elapsed += 60.0
            elements = elements_from_state(
                probe.getLatestState().vec_location - earth.getLatestState().vec_location,
                probe.getLatestState().vec_velocity - earth.getLatestState().vec_velocity,
                GM_EARTH,
            )
            track.append(min(elements.apoapsis, 5.0e8))
        return np.array(track)

    actual = np.array([
        min(elements_from_state(r["location"], r["velocity"], GM_EARTH).apoapsis, 5.0e8)
        for r in records
    ])

    figure, axes = new_figure()
    style_axes(axes,
               "Ein gemessenes Delta-v abzuspielen genügt nicht\n"
               "Chandrayaan-2: Anhebung des Apogäums bis zum Mondtransfer",
               "Tage seit dem Start", "Apogäum (1000 km)")

    axes.plot(days, actual / 1e6, color=REAL, linewidth=2.6,
              label="real (JPL Horizons)")
    axes.plot(days, apoapsis_track(replay=False) / 1e6, color=ACCENT,
              linewidth=2.0, label="Zielsteuerung: jeder Burn fliegt sein Ziel an")
    axes.plot(days, apoapsis_track(replay=True) / 1e6, color=WARN,
              linewidth=2.0, linestyle="--",
              label="abgespielt: gemessenes Delta-v zur geplanten Zeit")

    axes.set_ylim(0, 460)
    legend = axes.legend(facecolor=BACKGROUND, edgecolor=GRID, fontsize=9)
    for text in legend.get_texts():
        text.set_color(FOREGROUND)

    save(figure, os.path.join(outdir, "trigger_effect.png"))


def figure_convergence(outdir):
    """Die gemessene Konvergenzordnung des Integrators."""
    import sys

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from tests.test_kernel_verification import kepler_pair, kepler_position, relative_position
    from tests.test_physics import advance

    semi_major_axis, eccentricity = 1.5e11, 0.3
    _, mu = kepler_pair(semi_major_axis, eccentricity)
    period = 2.0 * math.pi * math.sqrt(semi_major_axis ** 3 / mu)
    elapsed = period / 4.0

    steps = [250, 500, 1000, 2000, 4000]
    sizes, errors = [], []
    for count in steps:
        objects, mu = kepler_pair(semi_major_axis, eccentricity)
        advance(objects, elapsed / count, count)
        expected = kepler_position(semi_major_axis, eccentricity, mu, elapsed)
        errors.append(float(np.linalg.norm(relative_position(objects) - expected)))
        sizes.append(elapsed / count)

    figure, axes = new_figure(8.0, 6.0)
    style_axes(axes,
               "Der Integrator ist vierter Ordnung\n"
               "Fehler gegen die exakte Lösung der Kepler-Gleichung",
               "Schrittweite (s)", "Ortsfehler nach einem Viertelumlauf (m)")

    axes.loglog(sizes, errors, "o-", color=SIMULATED, linewidth=2.0,
                markersize=7, label="gemessen")

    reference = np.array(errors[0]) * (np.array(sizes) / sizes[0]) ** 4
    axes.loglog(sizes, reference, "--", color=ACCENT, linewidth=1.4,
                label="ideale vierte Ordnung")

    for size, error in zip(sizes, errors):
        axes.annotate(f"{error:.1e}", (size, error), textcoords="offset points",
                      xytext=(8, -12), color=FOREGROUND, fontsize=8)

    legend = axes.legend(facecolor=BACKGROUND, edgecolor=GRID, fontsize=9)
    for text in legend.get_texts():
        text.set_color(FOREGROUND)

    save(figure, os.path.join(outdir, "convergence.png"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", default=os.path.join("docs", "figures"))
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    print("Erzeuge Abbildungen:")

    figure_artemis_trajectory(args.outdir)
    figure_artemis_distance(args.outdir)
    figure_burn_detection(args.outdir)
    figure_trigger_effect(args.outdir)
    figure_convergence(args.outdir)


if __name__ == "__main__":
    main()
