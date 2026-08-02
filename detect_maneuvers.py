"""Leitet das Brennprofil einer Mission aus ihrer tatsächlich geflogenen Bahn ab.

Zwischen zwei Manövern bewegt sich ein Raumfahrzeug rein ballistisch -- es
folgt allein der Schwerkraft. Rechnet man also von einem realen Zustand aus
mit dem eigenen Kernel weiter und vergleicht mit dem nächsten realen Zustand,
bleibt die Abweichung klein, solange kein Triebwerk lief. Wo sie sprunghaft
ansteigt, hat ein Manöver stattgefunden, und die Differenz der
Geschwindigkeiten ist dessen Delta-v.

Das ist belastbarer, als Brennzeiten aus Pressemitteilungen zu übernehmen:
die Manöver werden aus derselben Bahn gewonnen, gegen die das Modell später
geprüft wird.

Aufruf:  python detect_maneuvers.py [--step 30m] [--threshold 5]
"""

import argparse
import sys

import numpy as np

from data.constants import CONST_GRAVITY, GM_EARTH, GM_MOON, GM_SUN
from data.horizons import (
    GEOCENTER,
    SOLAR_SYSTEM_BARYCENTER,
    fetch_vectors,
    save_cache,
)
from models.massive_object import MassiveObject
from models.oblateness import Oblateness
from models.state import State
from physics.integrator import step as integrate

# Gravitationsparameter und Radien der begleitenden Körper. GM statt Masse --
# der Unterschied macht in dieser Rechnung den Ausschlag, siehe Konstanten.
SYSTEM_BODIES = [
    ("Sun", GM_SUN, 6.96342e8),
    ("Earth", GM_EARTH, 6.371e6),
    ("Moon", GM_MOON, 1.737e6),
]

# Nur die Erde wird abgeplattet gerechnet: im erdnahen Teil der Mission ist
# ihre Abplattung die stärkste Störung überhaupt.
OBLATE_BODIES = {"Earth": Oblateness.earth}
PROBE_MASS = 3850.0
PROBE_RADIUS = 10.0

LAUNCH = "2019-07-22 09:35"
MISSION_END = "2019-09-07 00:00"


def fetch_system(probe, start_time, stop_time, step_size):
    """Holt die Zustände aller Körper im selben Raster.

    Die Himmelskörper kommen bezogen auf den Schwerpunkt des Sonnensystems,
    das Raumfahrzeug dagegen geozentrisch. Der Grund steckt in den
    Ephemeriden: Horizons rechnet geozentrische Raumfahrzeug-Koordinaten mit
    der Erd-Ephemeride aus dem Missions-Kernel, die Kette zum Schwerpunkt
    aber über DE441. Beide Wege unterscheiden sich für Chandrayaan-2 um
    konstante 116 km -- genug, um eine Perigäumsdurchgang unbrauchbar zu
    machen. Die geozentrische Angabe ist die belastbare, weil die Bahnlösung
    in diesem Bezug bestimmt wurde.
    """
    series = {}
    for name, _, _ in SYSTEM_BODIES:
        print(f"  hole {name} ...", flush=True)
        series[name] = fetch_vectors(name, start_time, stop_time, step_size,
                                     center=SOLAR_SYSTEM_BARYCENTER)

    print(f"  hole {probe} (geozentrisch) ...", flush=True)
    series[probe] = fetch_vectors(probe, start_time, stop_time, step_size,
                                  center=GEOCENTER)

    lengths = {name: len(records) for name, records in series.items()}
    if len(set(lengths.values())) != 1:
        raise SystemExit(f"Ungleiche Datensatzzahlen je Körper: {lengths}")

    return series


def build_system(series, probe, index, use_oblateness=True):
    """Baut die Körper aus den realen Zuständen an Stützstelle `index`."""
    bodies = []
    for name, mu, radius in SYSTEM_BODIES:
        record = series[name][index]
        factory = OBLATE_BODIES.get(name) if use_oblateness else None
        bodies.append(MassiveObject(
            State(np.array(record["velocity"]), np.array(record["location"])),
            mu / CONST_GRAVITY, radius, (255, 255, 255), name, True, [],
            oblateness=factory() if factory else None, mu=mu,
        ))

    # Geozentrische Sondenangabe auf denselben Bezug wie die Körper heben
    earth = series["Earth"][index]
    record = series[probe][index]
    bodies.append(MassiveObject(
        State(np.array(record["velocity"]) + np.array(earth["velocity"]),
              np.array(record["location"]) + np.array(earth["location"])),
        PROBE_MASS, PROBE_RADIUS, (255, 128, 0), probe, False, [],
    ))
    return bodies


def probe_state_in_system(series, probe, index):
    """Realer Sondenzustand im Bezugssystem der Simulation."""
    earth = series["Earth"][index]
    record = series[probe][index]
    return (np.array(record["location"]) + np.array(earth["location"]),
            np.array(record["velocity"]) + np.array(earth["velocity"]))


def propagate(bodies, duration, time_step=60.0):
    """Rechnet das System ballistisch um `duration` Sekunden weiter."""
    elapsed = 0.0
    while elapsed < duration:
        current_step = min(time_step, duration - elapsed)
        integrate(bodies, current_step, elapsed)
        elapsed += current_step
    return bodies[-1].getLatestState()


def residual_delta_v(series, probe, index, time_step=60.0):
    """Unerklärte Geschwindigkeitsänderung über ein Intervall, in m/s."""
    start_record = series[probe][index]
    end_record = series[probe][index + 1]

    duration = (end_record["jd"] - start_record["jd"]) * 86400.0
    predicted = propagate(build_system(series, probe, index), duration, time_step)

    _, actual_velocity = probe_state_in_system(series, probe, index + 1)
    return (float(np.linalg.norm(actual_velocity - predicted.vec_velocity)),
            actual_velocity - predicted.vec_velocity,
            duration)


def detect(series, probe, threshold, time_step=60.0):
    """Findet alle Intervalle, deren Restabweichung die Schwelle übersteigt."""
    residuals = []
    count = len(series[probe]) - 1

    for index in range(count):
        magnitude, vector, duration = residual_delta_v(series, probe, index, time_step)
        residuals.append({
            "index": index,
            "start": series[probe][index]["date"],
            "end": series[probe][index + 1]["date"],
            "jd_start": series[probe][index]["jd"],
            "duration": duration,
            "delta_v": magnitude,
            "delta_v_vector": vector.tolist(),
        })
        if (index + 1) % 200 == 0:
            print(f"  {index + 1}/{count} Intervalle geprüft", flush=True)

    return residuals


def summarise(residuals, threshold):
    """Fasst zusammenhängende Intervalle über der Schwelle zu Manövern zusammen."""
    maneuvers = []
    current = None

    for entry in residuals:
        if entry["delta_v"] < threshold:
            if current is not None:
                maneuvers.append(current)
                current = None
            continue

        if current is None:
            current = dict(entry)
            current["intervals"] = 1
        else:
            # Ein Manöver kann über mehrere Stützstellen reichen
            current["end"] = entry["end"]
            current["duration"] += entry["duration"]
            current["delta_v"] += entry["delta_v"]
            current["delta_v_vector"] = (
                np.array(current["delta_v_vector"]) + np.array(entry["delta_v_vector"])
            ).tolist()
            current["intervals"] += 1

    if current is not None:
        maneuvers.append(current)

    return maneuvers


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", default="Chandrayaan-2")
    parser.add_argument("--start", default=LAUNCH)
    parser.add_argument("--stop", default=MISSION_END)
    parser.add_argument("--step", default="30m",
                        help="Abtastschritt der Ephemeride")
    parser.add_argument("--threshold", type=float, default=5.0,
                        help="Delta-v-Schwelle in m/s, ab der ein Burn gilt")
    parser.add_argument("--time-step", type=float, default=60.0,
                        help="Integrationsschrittweite in Sekunden")
    parser.add_argument("--cache", default="chandrayaan2_maneuvers")
    args = parser.parse_args(argv)

    print(f"Hole Ephemeriden {args.start} .. {args.stop} im Raster {args.step}")
    series = fetch_system(args.probe, args.start, args.stop, args.step)
    print(f"  {len(series[args.probe])} Stützstellen je Körper\n")

    print("Vergleiche ballistische Rechnung mit der realen Bahn ...")
    residuals = detect(series, args.probe, args.threshold, args.time_step)

    quiet = [entry["delta_v"] for entry in residuals if entry["delta_v"] < args.threshold]
    print(f"\nRestabweichung ohne Manöver: Median {np.median(quiet):.4f} m/s, "
          f"Maximum {max(quiet):.4f} m/s")

    maneuvers = summarise(residuals, args.threshold)
    print(f"\n{len(maneuvers)} Manöver oberhalb {args.threshold} m/s erkannt:\n")
    print(f"{'Beginn':<26} {'Dauer':>9} {'Delta-v':>12}")
    print("-" * 50)
    for maneuver in maneuvers:
        print(f"{maneuver['start']:<26} {maneuver['duration']:>8.0f}s "
              f"{maneuver['delta_v']:>10.1f} m/s")

    save_cache(args.cache, {
        "probe": args.probe,
        "start": args.start,
        "stop": args.stop,
        "step": args.step,
        "threshold": args.threshold,
        "quiet_residual_median": float(np.median(quiet)),
        "quiet_residual_max": float(max(quiet)),
        "maneuvers": maneuvers,
    })
    print(f"\nErgebnis im Cache abgelegt: {args.cache}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
