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

import sys

import numpy as np

from data.scenario import available_scenarios, load_named_scenario


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

    if collision is not None:
        return 1
    return 1 if any(result.is_failure for result in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
