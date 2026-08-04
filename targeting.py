"""Sucht Manöverziele, mit denen eine Mission ihr Reiseziel trifft.

Ein Ziel-Apogäum aus der geflogenen Bahn zu übernehmen genügt nicht, um den
Mond zu erreichen. Zum einen brennt ein Manöver über eine endliche Dauer und
bleibt dadurch hinter der Rechnung für einen Momentanschub zurück; zum anderen
ist die Bahnhöhe nur die halbe Aufgabe. Die Sonde muss ankommen, *wenn der
Mond dort ist* -- Apogäum und Phasenlage sind zwei verschiedene Dinge, und ein
Modell, das nicht auf den Meter genau rechnet, verfehlt die zweite.

Deshalb wird das Ziel gesucht statt übernommen: das Apogäum des trans-lunaren
Einschusses wird variiert, bis die dichteste Annäherung an den Mond so klein
wie möglich ist. Das ist dasselbe, was eine Missionsplanung tut, nur mit
weniger Parametern.

Aufruf:
    python targeting.py chandrayaan2            # sucht und zeigt das Ergebnis
    python targeting.py chandrayaan2 --apply    # schreibt es ins Szenario
"""

import argparse
import json
import os
import sys

import numpy as np

from data.scenario import SCENARIO_DIR, load_named_scenario
from rust_integration import RustAcceleratedIntegrator

# Ausserhalb dieses Abstands gilt ein Lauf als Fehlflug. Der Wert liegt weit
# über der Hill-Sphäre des Mondes von 61.524 km, damit die Suche auch aus
# einem schlechten Startpunkt heraus noch ein Gefälle sieht.
MISS_PENALTY = 1.0e9


def closest_approach(scenario_name, target_apoapsis, maneuver_index,
                     until, time_step=60.0, chaser="Moon"):
    """Dichteste Annäherung an `chaser`, wenn das Manöver dieses Ziel bekommt.

    Das Szenario wird für jeden Aufruf frisch geladen -- Manöver merken sich
    ihren Zündzeitpunkt und das aufgelöste Delta-v, ein zweiter Lauf auf
    denselben Objekten liefe also mit den Werten des ersten.
    """
    scenario = load_named_scenario(scenario_name)
    integrator = RustAcceleratedIntegrator(use_rust=True)

    probe = _probe(scenario)
    target = scenario.body(chaser)
    probe.list_maneuvers[maneuver_index].target_apoapsis = float(target_apoapsis)

    # Manöver nach dem gesuchten abschalten: sie sind auf eine Bahn ausgelegt,
    # die es in diesem Zwischenstand noch nicht gibt, und würden die Suche
    # verfälschen.
    for maneuver in probe.list_maneuvers[maneuver_index + 1:]:
        maneuver.time_duration = 1e-9
        maneuver.delta_v = 0.0
        maneuver.force = None
        maneuver.target_apoapsis = None

    smallest = MISS_PENALTY
    moment = 0.0
    elapsed = 0.0
    while elapsed < until:
        integrator.calculate_states_batch(scenario.bodies, time_step, elapsed)
        elapsed += time_step

        separation = float(np.linalg.norm(
            probe.getLatestState().vec_location - target.getLatestState().vec_location
        ))
        if separation < smallest:
            smallest, moment = separation, elapsed

        if separation < target.radius:
            # Aufschlag: näher geht nicht, und weiterrechnen wäre unphysikalisch
            break

    return smallest, moment


def solve(scenario_name, maneuver_index, bounds, until, samples=13,
          tolerance=1.0e6):
    """Sucht das Ziel-Apogäum mit der dichtesten Mondannäherung.

    Erst ein grobes Raster, dann eine Verfeinerung um den besten Punkt. Das
    Raster ist nicht Bequemlichkeit: die Zielgrösse hat mehrere lokale Minima,
    weil jeder Vorbeiflug an einer anderen Mondposition eines ist. Ein
    Verfahren, das nur bergab läuft, bliebe im erstbesten hängen.
    """
    from scipy.optimize import minimize_scalar

    lower, upper = bounds
    grid = np.linspace(lower, upper, samples)

    print(f"  Raster über {samples} Werte von {lower/1e3:,.0f} bis "
          f"{upper/1e3:,.0f} km:")
    scores = []
    for value in grid:
        distance, moment = closest_approach(scenario_name, value, maneuver_index,
                                            until)
        scores.append(distance)
        print(f"    ra = {value/1e3:>9,.0f} km  ->  {distance/1e3:>10,.0f} km "
              f"bei Tag {moment/86400:5.2f}", flush=True)

    best = int(np.argmin(scores))
    left = grid[max(0, best - 1)]
    right = grid[min(len(grid) - 1, best + 1)]
    print(f"  bestes Rasterfeld: {grid[best]/1e3:,.0f} km, verfeinere in "
          f"[{left/1e3:,.0f}, {right/1e3:,.0f}] km")

    result = minimize_scalar(
        lambda value: closest_approach(scenario_name, value, maneuver_index,
                                       until)[0],
        bracket=None, bounds=(left, right), method="bounded",
        options={"xatol": tolerance},
    )

    distance, moment = closest_approach(scenario_name, result.x, maneuver_index,
                                        until)
    return float(result.x), distance, moment


def _probe(scenario):
    """Der Körper, der Manöver ausführt -- das Raumfahrzeug."""
    for body in scenario.bodies:
        if body.list_maneuvers:
            return body
    raise ValueError("Kein Körper mit Manövern im Szenario")


def apply_to_scenario(scenario_name, maneuver_index, target_apoapsis, note):
    """Schreibt das gefundene Ziel in die Szenario-Datei."""
    path = os.path.join(SCENARIO_DIR, f"{scenario_name}.json")
    with open(path, encoding="utf-8") as handle:
        raw = json.load(handle)

    maneuver = raw["maneuvers"][maneuver_index]
    maneuver["target_apoapsis"] = round(float(target_apoapsis), 1)
    maneuver["target_source"] = note

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(raw, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"  Ziel in {path} eingetragen")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", default="chandrayaan2", nargs="?")
    parser.add_argument("--maneuver", type=int, default=4,
                        help="Index des zu lösenden Manövers (Vorgabe: TLI)")
    parser.add_argument("--lower", type=float, default=3.8e8)
    parser.add_argument("--upper", type=float, default=6.0e8)
    parser.add_argument("--until", type=float, default=2.9e6,
                        help="Wie weit gerechnet wird, in Sekunden")
    parser.add_argument("--apply", action="store_true",
                        help="Ergebnis ins Szenario schreiben")
    args = parser.parse_args(argv)

    print(f"Zielsuche für {args.scenario}, Manöver {args.maneuver}:")
    target, distance, moment = solve(
        args.scenario, args.maneuver, (args.lower, args.upper), args.until
    )

    print()
    print(f"  Ziel-Apogäum      {target/1e3:,.0f} km")
    print(f"  Mondannäherung    {distance/1e3:,.0f} km bei Tag {moment/86400:.2f}")
    print(f"  Hill-Radius Mond  61,524 km")

    if args.apply:
        apply_to_scenario(
            args.scenario, args.maneuver, target,
            "Aus einer Zielsuche auf die dichteste Mondannäherung, nicht aus "
            "der geflogenen Bahn gemessen -- siehe targeting.py",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
