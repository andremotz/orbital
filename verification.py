"""Schicht 2 der Verifikation: Missions-Szenarien gegen historische Meilensteine.

Anders als die Kernel-Verifikation in `tests/test_kernel_verification.py` misst
diese Schicht nicht das Integrationsverfahren, sondern das Gesamtmodell:
Startzustände, Manöverprofil und Physik zusammen. Ein verfehlter Meilenstein
sagt deshalb für sich genommen nichts über die Korrektheit des Kernels aus.

Meilensteine tragen dafür einen Status:
  verified     -- das Modell soll den Punkt treffen; Abweichung ist ein Fehler.
  aspirational -- historisch belegtes Ziel, das das Modell derzeit nicht
                  erreichen kann. Wird berichtet, nicht als Fehler gewertet.

Aufruf:  python verification.py [szenario]
"""

import math
import sys

import numpy as np

from data.scenario import available_scenarios, load_named_scenario
from physics.elements import elements_from_state


class MilestoneResult:
    """Was an einem Meilenstein tatsächlich herauskam."""

    def __init__(self, milestone, actual_distance, reached=True):
        self.milestone = milestone
        self.actual_distance = actual_distance
        # False, wenn der Lauf vorher abgebrochen ist -- dann ist der
        # gemessene Abstand nur der letzte gültige Zustand, kein Ergebnis.
        self.reached = reached

    @property
    def error(self):
        return abs(self.actual_distance - self.milestone.expected_distance)

    @property
    def within_tolerance(self):
        return self.reached and self.error <= self.milestone.tolerance

    @property
    def is_failure(self):
        """Nur ein verfehlter 'verified'-Meilenstein ist ein Fehler."""
        return self.milestone.status == "verified" and not self.within_tolerance


class Collision:
    """Zwei Körper sind einander näher gekommen als die Summe ihrer Radien.

    Die Simulation kennt keine Kollisionsantwort -- die Körper fliegen
    einfach weiter und werden an der 1/r^2-Singularität auf unphysikalische
    Geschwindigkeiten beschleunigt. Alles nach diesem Zeitpunkt ist wertlos,
    deshalb muss der Fall gemeldet und nicht überrechnet werden.
    """

    def __init__(self, time, name_a, name_b, distance):
        self.time = time
        self.name_a = name_a
        self.name_b = name_b
        self.distance = distance

    def __repr__(self):
        return (f"<Collision {self.name_a}/{self.name_b} bei t={self.time:.0f}s, "
                f"Abstand {self.distance:.0f} m>")


def find_collision(bodies, time):
    """Erster Körperdurchdringung im aktuellen Zustand, sonst None."""
    positions = np.array([body.getLatestState().vec_location for body in bodies])
    radii = np.array([body.radius for body in bodies])

    for i in range(len(bodies)):
        for j in range(i + 1, len(bodies)):
            distance = float(np.linalg.norm(positions[j] - positions[i]))
            if distance < radii[i] + radii[j]:
                return Collision(time, bodies[i].name, bodies[j].name, distance)
    return None


def _distance_between(scenario_bodies, name_a, name_b):
    by_name = {body.name: body for body in scenario_bodies}
    return float(np.linalg.norm(
        by_name[name_a].getLatestState().vec_location
        - by_name[name_b].getLatestState().vec_location
    ))


def verify_scenario(scenario, time_step=None, integrator=None):
    """Läuft das Szenario ab und wertet jeden Meilenstein aus."""
    if not scenario.milestones:
        return []

    time_step = time_step or scenario.time_step
    if integrator is None:
        from rust_integration import RustAcceleratedIntegrator

        integrator = RustAcceleratedIntegrator(use_rust=True)

    # Meilensteine der Reihe nach abarbeiten, damit ein Lauf genügt
    pending = sorted(scenario.milestones, key=lambda m: m.time)
    results = []
    collision = None

    simulation_time = 0.0
    for milestone in pending:
        while simulation_time < milestone.time and collision is None:
            integrator.calculate_states_batch(
                scenario.bodies, time_step, simulation_time
            )
            simulation_time += time_step
            collision = find_collision(scenario.bodies, simulation_time)

        results.append(MilestoneResult(
            milestone,
            _distance_between(scenario.bodies, milestone.body, milestone.relative_to),
            reached=collision is None,
        ))

    return results, collision


def format_report(scenario, results, collision=None):
    """Baut einen lesbaren Bericht über einen Verifikationslauf."""
    lines = [
        f"Szenario: {scenario.name}",
        "=" * 70,
    ]
    if scenario.description:
        lines += ["", scenario.description]

    if collision is not None:
        lines += [
            "",
            "ABBRUCH: Körperdurchdringung",
            "-" * 70,
            f"  {collision.name_a} und {collision.name_b} bei t={collision.time:,.0f}s"
            f" ({collision.time/86400:.2f} Tage), Abstand {collision.distance/1e3:,.1f} km.",
            "  Die Simulation kennt keine Kollisionsantwort. Alle Werte nach",
            "  diesem Zeitpunkt sind unphysikalisch und werden nicht bewertet.",
        ]

    lines += ["", "Meilensteine", "-" * 70]
    for result in results:
        milestone = result.milestone
        if not result.reached:
            mark = "n/a"
        elif milestone.status == "verified":
            mark = "OK" if result.within_tolerance else "FEHLER"
        else:
            mark = "OK" if result.within_tolerance else "offen"

        lines.append(
            f"[{mark:6}] {milestone.name}  ({milestone.date or 't=%.0fs' % milestone.time})"
        )
        lines.append(
            f"           erwartet {milestone.expected_distance/1e3:14,.1f} km"
            f"  +/- {milestone.tolerance/1e3:,.1f} km"
        )
        if result.reached:
            lines.append(
                f"           gemessen {result.actual_distance/1e3:14,.1f} km"
                f"  Abweichung {result.error/1e3:,.1f} km"
            )
        else:
            lines.append("           nicht ausgewertet -- Lauf vorher abgebrochen")
        if milestone.status == "aspirational":
            lines.append("           Status: historisches Ziel, vom Modell nicht erreichbar")
        if milestone.note:
            lines.append(f"           {milestone.note}")
        lines.append("")

    if scenario.limitations:
        lines += ["Bekannte Grenzen des Modells", "-" * 70]
        for limitation in scenario.limitations:
            lines.append(f"  * {limitation}")
        lines.append("")

    failures = [result for result in results if result.is_failure]
    if collision is not None:
        lines.append("ERGEBNIS: Lauf wegen Körperdurchdringung abgebrochen")
    elif failures:
        lines.append(f"ERGEBNIS: {len(failures)} von {len(results)} Meilensteinen verfehlt")
    else:
        verified = sum(1 for r in results if r.milestone.status == "verified")
        lines.append(
            f"ERGEBNIS: alle {verified} pruefbaren Meilensteine eingehalten "
            f"({len(results) - verified} als historisches Ziel vermerkt)"
        )

    return "\n".join(lines)


class TrackingSample:
    """Ein Vergleichspunkt zwischen Simulation und realer Bahn."""

    def __init__(self, elapsed, date, position_error, simulated, actual):
        self.elapsed = elapsed
        self.date = date
        self.position_error = position_error
        self.simulated = simulated
        self.actual = actual

    @property
    def apoapsis_error(self):
        if math.isinf(self.actual.apoapsis) or math.isinf(self.simulated.apoapsis):
            return math.inf
        return abs(self.simulated.apoapsis - self.actual.apoapsis)

    @property
    def periapsis_error(self):
        return abs(self.simulated.periapsis - self.actual.periapsis)


def track_against_truth(scenario, truth_records, body_name, center_name,
                        center_mu, time_step=None, integrator=None):
    """Vergleicht einen Lauf mit der real geflogenen Bahn.

    Die Referenz stammt aus JPL Horizons und ist relativ zu `center_name`
    angegeben. Verglichen wird beides: der Abstand der Positionen und die
    Bahnelemente. Letztere sind aussagekräftiger, sobald sich die Bahnen
    zeitlich verschieben -- zwei identische Bahnen, die nur gegenphasig
    durchlaufen werden, zeigen einen riesigen Positionsabstand bei
    identischen Elementen.
    """
    time_step = time_step or scenario.time_step
    if integrator is None:
        from rust_integration import RustAcceleratedIntegrator

        integrator = RustAcceleratedIntegrator(use_rust=True)

    body = scenario.body(body_name)
    center = scenario.body(center_name)
    epoch_jd = truth_records[0]["jd"]

    samples = []
    simulation_time = 0.0
    for record in truth_records:
        target = (record["jd"] - epoch_jd) * 86400.0
        while simulation_time < target:
            integrator.calculate_states_batch(scenario.bodies, time_step, simulation_time)
            simulation_time += time_step

        relative_location = (body.getLatestState().vec_location
                             - center.getLatestState().vec_location)
        relative_velocity = (body.getLatestState().vec_velocity
                             - center.getLatestState().vec_velocity)

        actual_location = np.array(record["location"])
        samples.append(TrackingSample(
            elapsed=target,
            date=record["date"][:17],
            position_error=float(np.linalg.norm(relative_location - actual_location)),
            simulated=elements_from_state(relative_location, relative_velocity, center_mu),
            actual=elements_from_state(actual_location, record["velocity"], center_mu),
        ))

    return samples


def format_tracking_report(samples, maneuver_times=()):
    """Bericht über die Übereinstimmung mit der realen Bahn."""
    lines = [
        "Vergleich mit der real geflogenen Bahn (JPL Horizons)",
        "=" * 78,
        "",
        f"{'Zeitpunkt':<18}{'verstrichen':>12}{'Ortsfehler':>14}"
        f"{'Perigaeum sim/ist':>22}{'Apogaeum sim/ist':>24}",
        "-" * 90,
    ]

    first_burn = min(maneuver_times) if maneuver_times else None
    marked_burn = False

    for sample in samples:
        if first_burn is not None and not marked_burn and sample.elapsed >= first_burn:
            lines.append(
                f"{'':>18}--- ab hier wirken Manoever "
                f"(erstes bei t={first_burn/86400:.2f} d) ---"
            )
            marked_burn = True

        apoapsis = (f"{sample.simulated.apoapsis/1e3:>10.0f}/"
                    f"{sample.actual.apoapsis/1e3:<10.0f}"
                    if not math.isinf(sample.actual.apoapsis) else f"{'hyperbolisch':>21}")
        lines.append(
            f"{sample.date:<18}{sample.elapsed/86400:>10.2f} d"
            f"{sample.position_error/1e3:>12.0f} km"
            f"{sample.simulated.periapsis/1e3:>11.0f}/"
            f"{sample.actual.periapsis/1e3:<10.0f}"
            f"{apoapsis:>24}"
        )

    ballistic = [s for s in samples
                 if first_burn is None or s.elapsed < first_burn]
    if ballistic:
        worst = max(s.position_error for s in ballistic)
        lines += [
            "",
            f"Rein ballistische Phase ({len(ballistic)} Vergleichspunkte bis zum "
            f"ersten Manoever):",
            f"  groesster Ortsfehler {worst/1e3:.1f} km nach "
            f"{ballistic[-1].elapsed/86400:.2f} Tagen",
        ]

    return "\n".join(lines)


def main(argv):
    scenario_name = argv[1] if len(argv) > 1 else None
    if scenario_name is None:
        names = available_scenarios()
        if not names:
            print("Keine Szenarien gefunden.")
            return 1
        scenario_name = names[0]

    scenario = load_named_scenario(scenario_name)
    results, collision = verify_scenario(scenario)
    print(format_report(scenario, results, collision))

    _print_tracking_if_available(scenario_name)

    if collision is not None:
        return 1
    return 1 if any(result.is_failure for result in results) else 0


def _print_tracking_if_available(scenario_name):
    """Hängt den Vergleich mit der realen Bahn an, falls Referenzdaten da sind."""
    from data.constants import GM_EARTH
    from data.horizons import HorizonsError, load_cache

    try:
        truth = load_cache(f"{scenario_name}_truth")
    except HorizonsError:
        return

    scenario = load_named_scenario(scenario_name)
    samples = track_against_truth(
        scenario, truth["records"], "Chandrayaan-2", "Earth", GM_EARTH
    )
    maneuver_times = [
        maneuver.time_start
        for body in scenario.bodies
        for maneuver in body.list_maneuvers
    ]

    print()
    print(format_tracking_report(samples[::6], maneuver_times))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
