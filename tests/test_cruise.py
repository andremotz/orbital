"""Tests für die adaptive Schrittweite und die interplanetare Reisephase.

Die Reisephase misst etwas anderes als die Mondmissionen: dort ging es um
Manöver und Zielsteuerung, hier allein um die Modellgüte über lange Zeit und
grosse Entfernungen.
"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.constants import GM_EARTH, GM_JUPITER_SYSTEM, GM_SUN, GM_VENUS
from data.horizons import load_cache
from data.scenario import load_named_scenario
from physics.adaptive import advance, characteristic_time, suggested_step
from tests.test_physics import make_object

AU = 1.496e11

# Ende der rein ballistischen Reise: der erste Venus-Vorbeiflug am
# 26. April 1998, 190 Tage nach dem Referenzbeginn.
BALLISTIC_SECONDS = 16_416_000.0


def cruise_run(until, minimum=2.0, maximum=86400.0, fraction=None):
    """Lässt die Reisephase bis `until` laufen und gibt Sonde und Schrittzahl."""
    from physics.adaptive import DEFAULT_FRACTION
    from rust_integration import RustAcceleratedIntegrator

    scenario = load_named_scenario("cassini_cruise")
    probe = scenario.body("Cassini")
    steps = advance(
        scenario.bodies, probe, until,
        RustAcceleratedIntegrator(use_rust=True),
        minimum=minimum, maximum=maximum,
        fraction=fraction or DEFAULT_FRACTION,
    )
    return probe, steps


class TestCharacteristicTime(unittest.TestCase):
    """Die Grösse, an der sich die Schrittweite bemisst."""

    def test_uses_the_strongest_attractor_not_the_nearest(self):
        """Im erdnahen Raum zählt die Erde, weiter draussen die Sonne.

        Massgeblich ist nicht, welcher Körper am nächsten steht, sondern
        welcher hier am stärksten zieht.
        """
        sun = make_object("Sun", 1.0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        sun.mu = GM_SUN
        earth = make_object("Earth", 1.0, [AU, 0.0, 0.0], [0.0, 0.0, 0.0])
        earth.mu = GM_EARTH

        near_earth = make_object("Probe", 1.0, [AU + 7.0e6, 0.0, 0.0],
                                 [0.0, 0.0, 0.0], is_heavy=False)
        bodies = [sun, earth, near_earth]

        # Rund 97 Minuten für einen erdnahen Orbit
        period = characteristic_time(bodies, near_earth)
        self.assertLess(period, 2.0 * 3600.0)
        self.assertGreater(period, 3600.0)

    def test_is_much_longer_in_interplanetary_space(self):
        sun = make_object("Sun", 1.0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        sun.mu = GM_SUN
        probe = make_object("Probe", 1.0, [3.0 * AU, 0.0, 0.0], [0.0, 0.0, 0.0],
                            is_heavy=False)

        period = characteristic_time([sun, probe], probe)

        # Ein Umlauf bei 3 AE dauert gut fünf Jahre
        self.assertGreater(period, 4.0 * 365.25 * 86400.0)

    def test_step_stays_inside_the_bounds(self):
        sun = make_object("Sun", 1.0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        sun.mu = GM_SUN
        probe = make_object("Probe", 1.0, [3.0 * AU, 0.0, 0.0], [0.0, 0.0, 0.0],
                            is_heavy=False)

        step = suggested_step([sun, probe], probe, minimum=2.0, maximum=3600.0)

        self.assertLessEqual(step, 3600.0)
        self.assertGreaterEqual(step, 2.0)

    def test_falls_back_to_the_maximum_without_attractors(self):
        lonely = make_object("Probe", 1.0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0],
                             is_heavy=False)

        self.assertEqual(
            suggested_step([lonely], lonely, minimum=2.0, maximum=1234.0), 1234.0
        )


class TestAdaptiveStepping(unittest.TestCase):
    """Die Anpassung muss Rechenzeit sparen, ohne Genauigkeit zu kosten."""

    def test_agrees_with_a_fixed_step_but_needs_fewer(self):
        """Der eigentliche Zweck, an der Reisephase gemessen.

        Auf einer Mondmission bringt die Anpassung nichts -- dort bestimmen
        die Perigäumsdurchgänge die Schrittweite ohnehin. Auf einer
        interplanetaren Bahn dagegen ändert sich über Stunden kaum etwas.
        """
        from rust_integration import RustAcceleratedIntegrator

        until = 6.0e6

        scenario = load_named_scenario("cassini_cruise")
        probe_fixed = scenario.body("Cassini")
        integrator = RustAcceleratedIntegrator(use_rust=True)
        elapsed, fixed_steps = 0.0, 0
        while elapsed < until:
            size = min(3600.0, until - elapsed)
            integrator.calculate_states_batch(scenario.bodies, size, elapsed)
            elapsed += size
            fixed_steps += 1

        probe_adaptive, adaptive_steps = cruise_run(until)

        self.assertLess(adaptive_steps, fixed_steps / 2.0,
                        "Anpassung spart weniger als die Hälfte der Schritte")

        difference = float(np.linalg.norm(
            probe_adaptive.getLatestState().vec_location
            - probe_fixed.getLatestState().vec_location
        ))
        scale = float(np.linalg.norm(probe_fixed.getLatestState().vec_location))
        self.assertLess(difference / scale, 1e-7,
                        "Anpassung verändert das Ergebnis merklich")

    def test_lands_exactly_on_the_requested_time(self):
        """Der letzte Schritt darf nicht über das Ziel hinausschiessen."""
        from rust_integration import RustAcceleratedIntegrator

        scenario = load_named_scenario("cassini_cruise")
        seen = []
        advance(scenario.bodies, scenario.body("Cassini"), 100_000.0,
                RustAcceleratedIntegrator(use_rust=True),
                observer=seen.append)

        self.assertAlmostEqual(seen[-1], 100_000.0, places=6)


class TestBallisticCruiseAccuracy(unittest.TestCase):
    """Wie weit trägt das Modell auf einer interplanetaren Bahn?"""

    def position_error(self, seconds):
        """Ortsfehler gegen die Ephemeride.

        Die Referenz ist auf den Schwerpunkt des Sonnensystems bezogen, und
        genau darauf sind auch die Startzustände der Simulation bezogen -- die
        absolute Position ist also direkt vergleichbar, ohne einen Bezugskörper
        abzuziehen.
        """
        truth = load_cache("cassini_truth")["records"]
        epoch = truth[0]["jd"]

        target = min(truth, key=lambda r: abs((r["jd"] - epoch) * 86400.0 - seconds))
        elapsed = (target["jd"] - epoch) * 86400.0

        probe, _ = cruise_run(elapsed)
        return float(np.linalg.norm(
            probe.getLatestState().vec_location - np.array(target["location"])
        )), float(np.linalg.norm(target["location"]))

    def test_tracks_the_real_trajectory_until_the_first_flyby(self):
        """190 Tage ballistisch, ohne Manöver, ohne Vorbeiflug.

        Das ist die Modellgüte selbst: gemessen wurden rund 87.600 km auf
        einer Bahn von 107 Millionen Kilometern, also 0,08 Prozent.
        """
        error, distance = self.position_error(BALLISTIC_SECONDS)

        self.assertLess(error / distance, 2.0e-3,
                        f"Reisebahn driftet um {error / distance:.2%}")
        self.assertLess(error, 2.0e8, "Ortsfehler über 200.000 km")

    def test_a_flyby_amplifies_the_error_by_more_than_an_order(self):
        """Warum eine Vorbeiflugkette nicht mit denselben Mitteln zu zielen ist.

        Der Venus-Vorbeiflug am 26. April 1998 vervielfacht den bis dahin
        angesammelten Fehler. Gemessen: von 87.600 km auf 4,06 Millionen km
        binnen zehn Tagen, also Faktor 46. Ein Modellfehler, der vor dem
        Vorbeiflug harmlos wirkt, entscheidet danach über Millionen Kilometer.
        """
        before, _ = self.position_error(BALLISTIC_SECONDS)
        after, _ = self.position_error(BALLISTIC_SECONDS + 10.0 * 86400.0)

        self.assertGreater(after / before, 10.0,
                           "Der Vorbeiflug verstärkt den Fehler kaum -- dann "
                           "wäre die Empfindlichkeit überschätzt")


class TestCruiseScenario(unittest.TestCase):
    """Aufbau des Reisephasen-Szenarios."""

    def test_carries_the_flyby_bodies(self):
        """Ohne Venus und Jupiter wäre die Bahn sinnlos -- sie lebt von ihnen."""
        scenario = load_named_scenario("cassini_cruise")
        names = {body.name for body in scenario.bodies}

        for required in ("Sun", "Venus", "Earth", "Jupiter", "Saturn", "Cassini"):
            with self.subTest(body=required):
                self.assertIn(required, names)

    def test_giant_planets_use_system_gravitational_parameters(self):
        """Deren Monde werden nicht geführt; aus der Ferne zählt die Summe."""
        scenario = load_named_scenario("cassini_cruise")

        self.assertAlmostEqual(
            scenario.body("Jupiter").mu / GM_JUPITER_SYSTEM, 1.0, places=9
        )
        self.assertAlmostEqual(scenario.body("Venus").mu / GM_VENUS, 1.0, places=9)

    def test_is_purely_ballistic(self):
        """Das Szenario prüft die Modellgüte, nicht die Missionsplanung."""
        scenario = load_named_scenario("cassini_cruise")

        for body in scenario.bodies:
            with self.subTest(body=body.name):
                self.assertEqual(body.list_maneuvers, [])

    def test_limitations_name_the_flyby_sensitivity(self):
        scenario = load_named_scenario("cassini_cruise")
        text = " ".join(scenario.limitations)

        self.assertIn("Vorbeiflug", text)


if __name__ == "__main__":
    unittest.main()
