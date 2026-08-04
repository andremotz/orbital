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
from data.constants import GM_EARTH
from data.horizons import load_cache
from verification import (
    find_collision,
    format_report,
    track_against_truth,
    verify_scenario,
)

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
        self.assertEqual(len(scenario.milestones), 1)
        self.assertTrue(scenario.limitations, "Grenzen des Modells fehlen")

    def test_relative_positions_are_added_to_the_parent(self):
        """Die Sonde ist relativ zur Erde angegeben und muss versetzt landen.

        Horizons führt die Bahnlösung geozentrisch; im Szenario steht deshalb
        der geozentrische Vektor, den der Loader auf die Erdposition addiert.
        """
        scenario = load_named_scenario("chandrayaan2")
        earth = scenario.body("Earth")
        probe = scenario.body("Chandrayaan-2")

        separation = np.linalg.norm(
            probe.getLatestState().vec_location - earth.getLatestState().vec_location
        )
        # Zum Epochenzeitpunkt auf dem Weg zum Apogäum der ersten Parkbahn
        self.assertGreater(separation, 6.371e6, "Sonde läge innerhalb der Erde")
        self.assertLess(separation, 6.0e7)

    def test_moon_distance_is_physically_plausible(self):
        """Echte Ephemeride statt Kreisnäherung: der Abstand muss im Bereich liegen."""
        scenario = load_named_scenario("chandrayaan2")

        separation = np.linalg.norm(
            scenario.body("Moon").getLatestState().vec_location
            - scenario.body("Earth").getLatestState().vec_location
        )

        # Perigäum 363.300 km bis Apogäum 405.500 km, mit etwas Rand
        self.assertGreater(separation, 3.55e8)
        self.assertLess(separation, 4.10e8)

    def test_bodies_carry_published_gravitational_parameters(self):
        """GM kommt aus der Datei und wird nicht aus der Masse gebildet."""
        scenario = load_named_scenario("chandrayaan2")

        self.assertAlmostEqual(scenario.body("Earth").mu / GM_EARTH, 1.0, places=12)
        self.assertIsNotNone(scenario.body("Earth").oblateness)
        self.assertIsNone(scenario.body("Moon").oblateness)

    def test_burn_profile_is_loaded(self):
        """Die Manöver sind zielgesteuert, nicht als Delta-v abgespielt.

        Ein gemessenes Delta-v tut auf einer abgewichenen Bahn etwas anderes
        als dort, wo es gemessen wurde. Die fünf erdnahen Anhebungen, der
        trans-lunare Einschuss und der Mondorbit-Einschuss fliegen deshalb
        jeweils ein Ziel an.
        """
        scenario = load_named_scenario("chandrayaan2")

        probe = scenario.body("Chandrayaan-2")
        self.assertEqual(len(probe.list_maneuvers), 6)
        self.assertEqual(scenario.body("Earth").list_maneuvers, [])

        for maneuver in probe.list_maneuvers:
            with self.subTest(maneuver=maneuver):
                self.assertIsNotNone(maneuver.target_apoapsis)
                self.assertIsNone(maneuver.delta_v)
                self.assertIsNone(maneuver.force)
                self.assertIsNotNone(maneuver.target_reference)

    def test_lunar_insertion_is_referenced_to_the_moon(self):
        """Der Einfang muss mondrelativ gerechnet und ausgelöst werden."""
        scenario = load_named_scenario("chandrayaan2")
        insertion = scenario.body("Chandrayaan-2").list_maneuvers[-1]

        self.assertEqual(insertion.target_reference, "Moon")
        self.assertEqual(insertion.relative_to, "Moon")
        self.assertEqual(insertion.trigger.reference, "Moon")

    def test_maneuvers_are_in_chronological_order(self):
        scenario = load_named_scenario("chandrayaan2")
        # Ausgelöste Manöver haben keine feste Zeit; massgeblich ist der
        # früheste mögliche Zündzeitpunkt.
        starts = [m.earliest_time
                  for m in scenario.body("Chandrayaan-2").list_maneuvers]

        self.assertEqual(starts, sorted(starts))


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

    def test_lunar_capture_is_a_verified_milestone(self):
        """Der Einfang ist kein blosses Ziel mehr, sondern wird eingehalten.

        Seit die Manoever ihre Zielbahn anfliegen statt ein gemessenes Delta-v
        abzuspielen, erreicht die Sonde den Mond und wird gebunden. Das ist der
        erste Meilenstein des Projekts mit Status 'verified' -- er darf den
        Lauf scheitern lassen, wenn er verfehlt wird.
        """
        scenario = load_named_scenario("chandrayaan2")
        results, collision = verify_scenario(scenario)

        self.assertIsNone(collision, "Lauf endet unerwartet in einer Kollision")
        self.assertEqual(len(results), 1)

        capture = results[0]
        self.assertEqual(capture.milestone.status, "verified")
        self.assertTrue(capture.within_tolerance,
                        f"Einfang verfehlt: {capture.actual_distance/1e3:.0f} km")
        self.assertFalse(capture.is_failure)

    def test_ballistic_phase_tracks_the_real_trajectory(self):
        """Vor dem ersten Manöver muss die Bahn der realen eng folgen.

        Das ist die eigentliche Aussage über die Modellgüte: die Startwerte
        stammen aus Horizons, Schub wirkt noch keiner, also misst die
        Abweichung allein die Physik. Nach dem ersten Burn läuft die Bahn
        auseinander, weil die Manöver ohne Zielsteuerung zu fester
        Absolutzeit gezündet werden -- das prüft dieser Test bewusst nicht.
        """
        scenario = load_named_scenario("chandrayaan2")
        truth = load_cache("chandrayaan2_truth")["records"]
        first_burn = min(m.earliest_time
                         for m in scenario.body("Chandrayaan-2").list_maneuvers)

        epoch = truth[0]["jd"]
        ballistic = [record for record in truth
                     if (record["jd"] - epoch) * 86400.0 < first_burn]
        self.assertGreater(len(ballistic), 2, "Zu wenige Punkte vor dem ersten Burn")

        samples = track_against_truth(
            scenario, ballistic, "Chandrayaan-2", "Earth", GM_EARTH
        )

        self.assertAlmostEqual(samples[0].position_error, 0.0, delta=1.0,
                               msg="Startzustand weicht bereits ab")
        self.assertLess(max(s.position_error for s in samples), 1.0e6,
                        "Ballistische Phase driftet um mehr als 1000 km")

    def test_report_mentions_limitations(self):
        scenario = load_named_scenario("chandrayaan2")
        results, collision = verify_scenario(scenario)

        report = format_report(scenario, results, collision)

        self.assertIn("Bekannte Grenzen", report)
        self.assertIn("Mondeinfang", report)
        # Die Verschiebung der Aussage durch die Zielsteuerung muss im
        # Bericht stehen und nicht nur im Kommentar
        self.assertIn("Zielsteuerung", report)

    def test_moon_orbit_is_inclined(self):
        """Die Mondbahn ragt aus der Ekliptik heraus.

        Genau diese Neigung war der Grund, das Modell von 2D auf 3D zu heben.
        Der Wert schwankt um die mittleren 5,145 Grad, weil die Ephemeride die
        tatsaechliche Bahn abbildet und keine Kreisnaeherung.
        """
        scenario = load_named_scenario("chandrayaan2")

        offset = (scenario.body("Moon").getLatestState().vec_location
                  - scenario.body("Earth").getLatestState().vec_location)
        inclination = abs(np.degrees(np.arcsin(offset[2] / np.linalg.norm(offset))))

        self.assertGreater(inclination, 4.0)
        self.assertLess(inclination, 6.0)


if __name__ == "__main__":
    unittest.main()


class TestArtemisScenario(unittest.TestCase):
    """Das Artemis-II-Szenario aus echten Horizons-Daten."""

    def test_scenario_is_available(self):
        self.assertIn("artemis2", available_scenarios())

    def test_tli_matches_the_published_delta_v(self):
        """NASA nennt 388 m/s; die Erkennung darf davon kaum abweichen."""
        scenario = load_named_scenario("artemis2")
        burns = [m for m in scenario.body("Artemis II").list_maneuvers
                 if m.delta_v > 100.0]

        self.assertEqual(len(burns), 1, "Genau ein grosser Burn erwartet: der TLI")
        self.assertAlmostEqual(burns[0].delta_v, 388.0, delta=2.0)

    def test_tli_fires_at_perigee_with_the_published_duration(self):
        """Beides zusammen bringt erst die richtige Bahnhoehe."""
        scenario = load_named_scenario("artemis2")
        tli = [m for m in scenario.body("Artemis II").list_maneuvers
               if m.delta_v > 100.0][0]

        self.assertIsNotNone(tli.trigger)
        self.assertEqual(tli.trigger.reference, "Earth")
        self.assertAlmostEqual(tli.time_duration, 355.0, places=6)

    def test_reaches_the_published_maximum_distance(self):
        """Der weiteste Punkt, den Menschen je von der Erde entfernt waren."""
        scenario = load_named_scenario("artemis2")
        results, collision = verify_scenario(scenario)
        self.assertIsNone(collision, "Lauf endet unerwartet in einer Kollision")

        distance = [r for r in results if r.milestone.name == "Groesste Erdentfernung"]
        self.assertEqual(len(distance), 1)

        # NASA: 413.146,2 km. Ohne Zielsteuerung sind wenige Prozent zu erwarten.
        relative = distance[0].error / distance[0].milestone.expected_distance
        self.assertLess(relative, 0.03,
                        f"Groesste Erdentfernung weicht um {relative:.1%} ab")
