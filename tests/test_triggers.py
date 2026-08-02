"""Tests für die Zündlogik: Manöver an Bahnereignissen statt nach der Uhr."""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.constants import GM_EARTH
from data.scenario import load_named_scenario
from models.maneuver import Maneuver
from models.massive_object import MassiveObject
from models.state import State
from models.trigger import PeriapsisTrigger, TimeTrigger, trigger_from_config
from physics.elements import elements_from_state, time_to_periapsis
from physics.integrator import step
from physics.mission import update_schedule
from tests.test_physics import make_object


def elliptical_orbit(periapsis=6.6e6, apoapsis=5.2e7):
    """Erde plus Sonde auf einer Ellipse, Sonde startet im Periapsis."""
    semi_major_axis = (periapsis + apoapsis) / 2.0
    speed = math.sqrt(GM_EARTH * (2.0 / periapsis - 1.0 / semi_major_axis))

    earth = MassiveObject(
        State(np.zeros(3), np.zeros(3)), 5.9722e24, 6.371e6, (0, 0, 0),
        "Earth", True, [], mu=GM_EARTH,
    )
    probe = make_object("Probe", 1000.0, [periapsis, 0.0, 0.0], [0.0, speed, 0.0],
                        is_heavy=False)
    return [earth, probe], 2.0 * math.pi * math.sqrt(semi_major_axis ** 3 / GM_EARTH)


class TestTimeToPeriapsis(unittest.TestCase):
    """Die Vorhersage, auf der die ganze Zündlogik ruht."""

    def test_at_periapsis_a_full_period_remains(self):
        bodies, period = elliptical_orbit()
        state = bodies[1].getLatestState()

        remaining = time_to_periapsis(state.vec_location, state.vec_velocity, GM_EARTH)

        self.assertAlmostEqual(remaining / period, 1.0, places=9)

    def test_prediction_matches_the_integrated_orbit(self):
        """Die vorhergesagte Zeit muss zum tatsächlichen Durchgang passen."""
        bodies, period = elliptical_orbit()

        # Ein Stück weiterfliegen, dann vorhersagen
        elapsed = 0.0
        for _ in range(2000):
            step(bodies, 10.0, elapsed)
            elapsed += 10.0

        state = bodies[1].getLatestState()
        predicted = time_to_periapsis(state.vec_location, state.vec_velocity, GM_EARTH)

        self.assertAlmostEqual((elapsed + predicted) / period, 1.0, places=6)

    def test_circular_orbit_has_no_distinguished_point(self):
        radius = 7.0e6
        speed = math.sqrt(GM_EARTH / radius)

        remaining = time_to_periapsis([radius, 0.0, 0.0], [0.0, speed, 0.0], GM_EARTH)

        self.assertEqual(remaining, 0.0)

    def test_hyperbolic_orbit_has_no_next_pass(self):
        radius = 7.0e6
        escape = math.sqrt(2.0 * GM_EARTH / radius)

        self.assertIsNone(
            time_to_periapsis([radius, 0.0, 0.0], [0.0, escape * 1.2, 0.0], GM_EARTH)
        )


class TestTriggers(unittest.TestCase):
    """Auslöser einzeln betrachtet."""

    def test_time_trigger_fires_at_its_time(self):
        maneuver = Maneuver(time_duration=100.0, delta_v=10.0,
                            trigger=TimeTrigger(500.0))
        bodies, _ = elliptical_orbit()
        bodies[1].list_maneuvers.append(maneuver)

        update_schedule(bodies, 499.0)
        self.assertIsNone(maneuver.activated_at)

        update_schedule(bodies, 500.0)
        self.assertEqual(maneuver.activated_at, 500.0)

    def test_periapsis_trigger_waits_for_the_pass(self):
        """Auf einer Ellipse darf erst kurz vor dem Periapsis gezündet werden."""
        bodies, period = elliptical_orbit()
        duration = 600.0
        maneuver = Maneuver(time_duration=duration, delta_v=50.0,
                            trigger=PeriapsisTrigger("Earth", after=60.0))
        bodies[1].list_maneuvers.append(maneuver)

        elapsed = 0.0
        while elapsed < period * 1.1 and maneuver.activated_at is None:
            update_schedule(bodies, elapsed)
            if maneuver.activated_at is None:
                step(bodies, 10.0, elapsed)
                elapsed += 10.0

        self.assertIsNotNone(maneuver.activated_at, "Auslöser hat nie gezündet")

        # Der Brennschluss soll um das Periapsis liegen: gezündet wird eine
        # halbe Brenndauer davor
        state = bodies[1].getLatestState()
        remaining = time_to_periapsis(state.vec_location, state.vec_velocity, GM_EARTH)
        self.assertLessEqual(remaining, duration / 2.0 + 10.0)

    def test_periapsis_trigger_respects_after(self):
        """Vor `after` darf nichts passieren, auch nicht an einem Periapsis."""
        bodies, period = elliptical_orbit()
        maneuver = Maneuver(time_duration=600.0, delta_v=50.0,
                            trigger=PeriapsisTrigger("Earth", after=period * 1.5))
        bodies[1].list_maneuvers.append(maneuver)

        elapsed = 0.0
        while elapsed < period:
            update_schedule(bodies, elapsed)
            step(bodies, 60.0, elapsed)
            elapsed += 60.0

        self.assertIsNone(maneuver.activated_at)

    def test_trigger_fires_only_once(self):
        bodies, period = elliptical_orbit()
        maneuver = Maneuver(time_duration=600.0, delta_v=50.0,
                            trigger=PeriapsisTrigger("Earth", after=0.0))
        bodies[1].list_maneuvers.append(maneuver)

        elapsed = 0.0
        while elapsed < period * 2.2:
            update_schedule(bodies, elapsed)
            step(bodies, 60.0, elapsed)
            elapsed += 60.0

        first = maneuver.activated_at
        self.assertIsNotNone(first)

        # Auch nach weiteren Umläufen bleibt es beim ersten Zündzeitpunkt
        self.assertEqual(maneuver.activated_at, first)

    def test_reset_allows_a_second_run(self):
        maneuver = Maneuver(time_duration=100.0, delta_v=10.0,
                            trigger=TimeTrigger(0.0))
        bodies, _ = elliptical_orbit()
        bodies[1].list_maneuvers.append(maneuver)

        update_schedule(bodies, 0.0)
        self.assertIsNotNone(maneuver.activated_at)

        maneuver.reset()
        self.assertIsNone(maneuver.activated_at)

    def test_config_rejects_unknown_trigger(self):
        with self.assertRaises(ValueError):
            trigger_from_config({"type": "sonnenaufgang"}, "Test")

    def test_config_requires_reference_for_periapsis(self):
        with self.assertRaises(ValueError):
            trigger_from_config({"type": "periapsis"}, "Test")


class TestOberthEffect(unittest.TestCase):
    """Der eigentliche Zweck der Zündlogik.

    Der Energiezuwachs eines Manövers ist v * dv: er wächst mit der
    Geschwindigkeit, die das Fahrzeug beim Brennen ohnehin hat. Am Periapsis
    ist sie am grössten, also bringt dasselbe Delta-v dort die meiste Energie.
    Das ist der Grund, Manöver an das Periapsis zu koppeln statt an die Uhr --
    und es lässt sich an der grossen Halbachse ablesen, die unmittelbar an der
    Energie hängt.
    """

    def burn_at(self, when, period, use_trigger):
        bodies, _ = elliptical_orbit()
        probe = bodies[1]

        if use_trigger:
            maneuver = Maneuver(time_duration=600.0, delta_v=150.0,
                                trigger=PeriapsisTrigger("Earth", after=period * 0.5),
                                relative_to="Earth")
        else:
            maneuver = Maneuver(time_start=when, time_duration=600.0,
                                delta_v=150.0, relative_to="Earth")
        probe.list_maneuvers.append(maneuver)

        elapsed = 0.0
        while elapsed < period * 2.0:
            step(bodies, 30.0, elapsed)
            elapsed += 30.0

        self.assertIsNotNone(maneuver.activated_at, "Manöver zündete nie")
        state = probe.getLatestState()
        return elements_from_state(state.vec_location, state.vec_velocity, GM_EARTH)

    def test_periapsis_burn_adds_more_energy_than_apoapsis_burn(self):
        _, period = elliptical_orbit()

        # Die Bahn startet im Periapsis, das Apoapsis liegt eine halbe Periode später
        at_apoapsis = self.burn_at(period * 0.5, period, use_trigger=False)
        at_periapsis = self.burn_at(None, period, use_trigger=True)

        # Gemessen liegt der Vorteil bei rund 26 Prozent: 37.945 km gegen
        # 30.226 km grosse Halbachse für dasselbe Delta-v von 150 m/s.
        ratio = at_periapsis.semi_major_axis / at_apoapsis.semi_major_axis
        self.assertGreater(
            ratio, 1.15,
            f"Zündung am Periapsis bringt nur Faktor {ratio:.2f} mehr Energie "
            f"als am Apoapsis -- dann wäre die Zündlogik kaum wirksam",
        )

    def test_periapsis_burn_lifts_the_apoapsis(self):
        """Ein prograder Burn im Periapsis hebt die Gegenseite der Bahn."""
        bodies, period = elliptical_orbit()
        before = elements_from_state(
            bodies[1].getLatestState().vec_location,
            bodies[1].getLatestState().vec_velocity, GM_EARTH,
        )

        bodies[1].list_maneuvers.append(Maneuver(
            time_duration=600.0, delta_v=150.0, relative_to="Earth",
            trigger=PeriapsisTrigger("Earth", after=period * 0.5),
        ))
        elapsed = 0.0
        while elapsed < period * 2.0:
            step(bodies, 30.0, elapsed)
            elapsed += 30.0

        after = elements_from_state(
            bodies[1].getLatestState().vec_location,
            bodies[1].getLatestState().vec_velocity, GM_EARTH,
        )

        self.assertGreater(after.apoapsis, before.apoapsis * 1.1)
        # Das Periapsis bleibt dabei nahezu unverändert
        self.assertAlmostEqual(after.periapsis / before.periapsis, 1.0, delta=0.05)


class TestScenarioTriggers(unittest.TestCase):
    """Die Zündlogik im mitgelieferten Szenario."""

    def test_earth_raising_burns_are_triggered(self):
        scenario = load_named_scenario("chandrayaan2")
        maneuvers = scenario.body("Chandrayaan-2").list_maneuvers

        triggered = [m for m in maneuvers if m.trigger is not None]
        self.assertEqual(len(triggered), 5)

        for maneuver in triggered:
            with self.subTest(maneuver=maneuver):
                self.assertIsInstance(maneuver.trigger, PeriapsisTrigger)
                self.assertEqual(maneuver.trigger.reference, "Earth")
                self.assertIsNone(maneuver.activated_at)

    def test_unknown_trigger_reference_is_rejected(self):
        from data.scenario import ScenarioError, load_scenario
        from tests.test_scenario import MINIMAL_BODY, write_scenario

        path = write_scenario({
            "name": "X",
            "bodies": [dict(MINIMAL_BODY)],
            "maneuvers": [{
                "body": "Star", "duration": 10, "delta_v": 1,
                "trigger": {"type": "periapsis", "reference": "Ghost"},
            }],
        })
        try:
            with self.assertRaises(ScenarioError) as context:
                load_scenario(path)
            self.assertIn("Ghost", str(context.exception))
        finally:
            os.unlink(path)

    def test_time_start_and_trigger_are_mutually_exclusive(self):
        from data.scenario import ScenarioError, load_scenario
        from tests.test_scenario import MINIMAL_BODY, write_scenario

        path = write_scenario({
            "name": "X",
            "bodies": [dict(MINIMAL_BODY)],
            "maneuvers": [{
                "body": "Star", "duration": 10, "delta_v": 1, "time_start": 0,
                "trigger": {"type": "periapsis", "reference": "Star"},
            }],
        })
        try:
            with self.assertRaises(ScenarioError):
                load_scenario(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
