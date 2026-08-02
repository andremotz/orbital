"""Tests für den Szenario-Loader und die Missions-Verifikation (Schicht 2)."""

import json
import os
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.scenario import (
    ScenarioError,
    available_scenarios,
    load_named_scenario,
    load_scenario,
)
from physics.mission import get_mission_acceleration
from tests.test_physics import make_object
from verification import find_collision, format_report, verify_scenario

MINIMAL_BODY = {
    "name": "Star",
    "mass": 1.989e30,
    "radius": 6.96e8,
    "location": [0, 0],
    "velocity": [0, 0],
}


def write_scenario(payload):
    """Schreibt ein Szenario in eine temporäre Datei und gibt den Pfad zurück."""
    handle = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(payload, handle)
    handle.close()
    return handle.name


class TestScenarioLoading(unittest.TestCase):
    """Das mitgelieferte Szenario muss vollständig und stimmig laden."""

    def test_chandrayaan_scenario_is_available(self):
        self.assertIn("chandrayaan2", available_scenarios())

    def test_bodies_and_milestones_are_loaded(self):
        scenario = load_named_scenario("chandrayaan2")

        self.assertEqual(
            [body.name for body in scenario.bodies],
            ["Sun", "Earth", "Moon", "Chandrayaan-2"],
        )
        self.assertEqual(len(scenario.milestones), 2)
        self.assertTrue(scenario.limitations, "Grenzen des Modells fehlen")

    def test_relative_positions_are_added_to_the_parent(self):
        """Der Mond ist relativ zur Erde angegeben und muss versetzt landen."""
        scenario = load_named_scenario("chandrayaan2")
        earth = scenario.body("Earth")
        moon = scenario.body("Moon")

        separation = np.linalg.norm(
            moon.getLatestState().vec_location - earth.getLatestState().vec_location
        )
        self.assertAlmostEqual(separation / 3.56671e8, 1.0, places=9)

        # Auch die Geschwindigkeit ist relativ gemeint
        relative_speed = np.linalg.norm(
            moon.getLatestState().vec_velocity - earth.getLatestState().vec_velocity
        )
        self.assertAlmostEqual(relative_speed, 1020.0, places=6)

    def test_maneuver_is_attached_to_its_body(self):
        scenario = load_named_scenario("chandrayaan2")

        probe = scenario.body("Chandrayaan-2")
        self.assertEqual(len(probe.list_maneuvers), 1)
        self.assertEqual(probe.list_maneuvers[0].relative_to, "Earth")
        self.assertEqual(scenario.body("Earth").list_maneuvers, [])


class TestScenarioValidation(unittest.TestCase):
    """Fehlerhafte Szenarien müssen klar scheitern, nicht stillschweigend laden."""

    def load_and_expect_error(self, payload, expected_fragment):
        path = write_scenario(payload)
        try:
            with self.assertRaises(ScenarioError) as context:
                load_scenario(path)
            self.assertIn(expected_fragment, str(context.exception))
        finally:
            os.unlink(path)

    def test_missing_required_field(self):
        body = dict(MINIMAL_BODY)
        del body["mass"]
        self.load_and_expect_error({"name": "X", "bodies": [body]}, "mass")

    def test_malformed_vector(self):
        body = dict(MINIMAL_BODY, location=[0, 0, 0, 0])
        self.load_and_expect_error({"name": "X", "bodies": [body]}, "[x, y, z]")

    def test_two_component_vector_is_padded_to_three(self):
        """Zweikomponentige Angaben bleiben zulässig und meinen z = 0."""
        path = write_scenario({
            "name": "X",
            "bodies": [dict(MINIMAL_BODY, location=[1.0, 2.0], velocity=[3.0, 4.0])],
        })
        try:
            scenario = load_scenario(path)
        finally:
            os.unlink(path)

        state = scenario.body("Star").getLatestState()
        np.testing.assert_allclose(state.vec_location, [1.0, 2.0, 0.0])
        np.testing.assert_allclose(state.vec_velocity, [3.0, 4.0, 0.0])

    def test_unknown_relative_to(self):
        body = dict(MINIMAL_BODY, relative_to="Nowhere")
        self.load_and_expect_error({"name": "X", "bodies": [body]}, "unbekannten Körper")

    def test_cyclic_relative_to(self):
        payload = {
            "name": "X",
            "bodies": [
                dict(MINIMAL_BODY, name="A", relative_to="B"),
                dict(MINIMAL_BODY, name="B", relative_to="A"),
            ],
        }
        self.load_and_expect_error(payload, "Zyklischer Bezug")

    def test_duplicate_body_names(self):
        payload = {"name": "X", "bodies": [dict(MINIMAL_BODY), dict(MINIMAL_BODY)]}
        self.load_and_expect_error(payload, "doppelt definiert")

    def test_maneuver_on_unknown_body(self):
        payload = {
            "name": "X",
            "bodies": [dict(MINIMAL_BODY)],
            "maneuvers": [
                {"body": "Ghost", "time_start": 0, "duration": 10, "force": 1}
            ],
        }
        self.load_and_expect_error(payload, "unbekannte Körper")

    def test_maneuver_with_unknown_reference_frame(self):
        payload = {
            "name": "X",
            "bodies": [dict(MINIMAL_BODY)],
            "maneuvers": [
                {"body": "Star", "time_start": 0, "duration": 10, "force": 1,
                 "relative_to": "Ghost"}
            ],
        }
        self.load_and_expect_error(payload, "relative_to")

    def test_invalid_milestone_status(self):
        payload = {
            "name": "X",
            "bodies": [dict(MINIMAL_BODY)],
            "milestones": [
                {"name": "M", "time": 1, "body": "Star", "relative_to": "Star",
                 "expected_distance": 0, "tolerance": 1, "status": "vielleicht"}
            ],
        }
        self.load_and_expect_error(payload, "status")

    def test_empty_scenario_is_rejected(self):
        self.load_and_expect_error({"name": "X", "bodies": []}, "keine Körper")


class TestBurnReferenceFrame(unittest.TestCase):
    """Das Bezugssystem eines Manövers entscheidet über die Schubrichtung."""

    def make_orbit(self):
        """Sonde im Erdorbit, Erde selbst schnell um die Sonne unterwegs."""
        earth = make_object("Earth", 5.9722e24, [0.0, 1.5e11], [29780.0, 0.0])
        # Sonde bewegt sich relativ zur Erde entgegen deren Bahnrichtung
        probe = make_object("Probe", 1000.0, [0.0, 1.5e11 + 7.0e6],
                            [29780.0 - 7500.0, 0.0], is_heavy=False)
        return [earth, probe]

    def test_prograde_without_frame_follows_absolute_velocity(self):
        bodies = self.make_orbit()
        from models.maneuver import Maneuver

        bodies[1].list_maneuvers.append(Maneuver(0, 100, 1000.0))
        acceleration = get_mission_acceleration(bodies[1], 50.0, bodies)

        # Absolut bewegt sich die Sonde mit +x (Erdbahn dominiert)
        self.assertGreater(acceleration[0], 0.0)

    def test_prograde_with_frame_follows_orbital_velocity(self):
        """Mit Erdbezug muss der Schub in die andere Richtung zeigen."""
        bodies = self.make_orbit()
        from models.maneuver import Maneuver

        bodies[1].list_maneuvers.append(
            Maneuver(0, 100, 1000.0, relative_to="Earth")
        )
        acceleration = get_mission_acceleration(bodies[1], 50.0, bodies)

        # Relativ zur Erde bewegt sich die Sonde mit -x
        self.assertLess(acceleration[0], 0.0)

    def test_unknown_reference_frame_is_reported(self):
        bodies = self.make_orbit()
        from models.maneuver import Maneuver

        bodies[1].list_maneuvers.append(Maneuver(0, 100, 1000.0, relative_to="Mars"))

        with self.assertRaises(ValueError):
            get_mission_acceleration(bodies[1], 50.0, bodies)


class TestCollisionDetection(unittest.TestCase):
    """Körperdurchdringungen müssen erkannt werden."""

    def test_detects_overlapping_bodies(self):
        bodies = [
            make_object("Big", 1e24, [0.0, 0.0], [0.0, 0.0]),
            make_object("Small", 1e3, [0.0, 0.0], [0.0, 0.0]),
        ]
        bodies[0].radius = 6.371e6
        bodies[1].radius = 10.0

        collision = find_collision(bodies, time=42.0)

        self.assertIsNotNone(collision)
        self.assertEqual({collision.name_a, collision.name_b}, {"Big", "Small"})
        self.assertEqual(collision.time, 42.0)

    def test_ignores_well_separated_bodies(self):
        bodies = [
            make_object("Big", 1e24, [0.0, 0.0], [0.0, 0.0]),
            make_object("Small", 1e3, [1.0e9, 0.0], [0.0, 0.0]),
        ]
        bodies[0].radius = 6.371e6
        bodies[1].radius = 10.0

        self.assertIsNone(find_collision(bodies, time=0.0))


class TestMissionVerification(unittest.TestCase):
    """Die Auswertung von Meilensteinen (Schicht 2)."""

    def test_aspirational_milestone_is_not_a_failure(self):
        """Ein historisches Ziel darf den Lauf nicht scheitern lassen."""
        scenario = load_named_scenario("chandrayaan2")
        results, collision = verify_scenario(scenario)

        self.assertIsNone(collision, "Szenario endet unerwartet in einer Kollision")
        self.assertEqual(len(results), 2)
        for result in results:
            with self.subTest(milestone=result.milestone.name):
                self.assertEqual(result.milestone.status, "aspirational")
                self.assertFalse(result.is_failure)

    def test_probe_stays_bound_to_earth(self):
        """Regression: ohne Erdbezug beim Burn entkam die Sonde früher.

        Der Schub wirkte im absoluten System und bremste die Sonde, worauf sie
        in die Erde stürzte und an der Singularität herauskatapultiert wurde.
        """
        scenario = load_named_scenario("chandrayaan2")
        verify_scenario(scenario)

        earth = scenario.body("Earth")
        probe = scenario.body("Chandrayaan-2")
        distance = np.linalg.norm(
            probe.getLatestState().vec_location - earth.getLatestState().vec_location
        )

        # Hill-Sphäre der Erde: rund 1,5 Millionen km
        self.assertLess(distance, 1.5e9, "Sonde hat den Erdeinfluss verlassen")
        self.assertGreater(distance, earth.radius, "Sonde ist in der Erde gelandet")

    def test_report_mentions_limitations(self):
        scenario = load_named_scenario("chandrayaan2")
        results, collision = verify_scenario(scenario)

        report = format_report(scenario, results, collision)

        self.assertIn("Bekannte Grenzen", report)
        self.assertIn("Vikram-Absturz", report)
        self.assertIn("historisches Ziel", report)

    def test_moon_orbit_is_inclined(self):
        """Die Mondbahn muss aus der Ekliptik herausragen.

        Genau diese Neigung war der Grund, das Modell von 2D auf 3D zu heben.
        """
        scenario = load_named_scenario("chandrayaan2")
        earth = scenario.body("Earth")
        moon = scenario.body("Moon")

        offset = (moon.getLatestState().vec_location
                  - earth.getLatestState().vec_location)
        inclination = np.degrees(np.arcsin(offset[2] / np.linalg.norm(offset)))

        self.assertAlmostEqual(inclination, 5.145, places=3)


if __name__ == "__main__":
    unittest.main()
