"""Tests für zielbasierte Manöver.

Geprüft wird die geschlossene Rechnung, nicht der Optimierer -- die Zielsuche
selbst dauert Minuten und schreibt Dateien. Ihr Ergebnis wird stattdessen als
Wert im Szenario geprüft.
"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.constants import GM_EARTH, GM_MOON
from data.scenario import ScenarioError, load_named_scenario, load_scenario
from models.maneuver import Maneuver
from physics.elements import elements_from_state, time_to_periapsis
from tests.test_scenario import MINIMAL_BODY, write_scenario


def circular_state(radius, mu=GM_EARTH):
    speed = math.sqrt(mu / radius)
    return np.array([radius, 0.0, 0.0]), np.array([0.0, speed, 0.0])


class TestVisVivaResolution(unittest.TestCase):
    """Das nötige Delta-v folgt aus dem Ist-Zustand, nicht aus einer Messung."""

    def test_matches_the_hohmann_transfer(self):
        """Von einer Kreisbahn aus ist der Wert analytisch bekannt."""
        radius, target = 7.0e6, 4.2e7
        location, velocity = circular_state(radius)

        maneuver = Maneuver(time_start=0.0, time_duration=100.0,
                            target_apoapsis=target, relative_to="Earth")
        resolved = maneuver.resolve(location, velocity, GM_EARTH)

        semi_major_axis = (radius + target) / 2.0
        expected = (math.sqrt(GM_EARTH * (2.0 / radius - 1.0 / semi_major_axis))
                    - math.sqrt(GM_EARTH / radius))
        self.assertAlmostEqual(resolved / expected, 1.0, places=12)

    def test_reaches_the_requested_apoapsis(self):
        """Nach dem aufgelösten Delta-v muss die Bahn das Ziel haben."""
        radius, target = 7.0e6, 4.2e7
        location, velocity = circular_state(radius)

        maneuver = Maneuver(time_start=0.0, time_duration=100.0,
                            target_apoapsis=target, relative_to="Earth")
        resolved = maneuver.resolve(location, velocity, GM_EARTH)

        direction = velocity / np.linalg.norm(velocity)
        elements = elements_from_state(location, velocity + direction * resolved,
                                       GM_EARTH)
        self.assertAlmostEqual(elements.apoapsis / target, 1.0, places=9)

    def test_a_lower_orbit_needs_more(self):
        """Das ist der Sinn der Sache: die Steuerung gleicht Abweichungen aus.

        Ein abgespieltes Delta-v täte auf beiden Bahnen dasselbe und liesse
        die zu tiefe zu tief.
        """
        target = 4.2e7
        deltas = []
        for radius in (6.6e6, 7.0e6):
            location, velocity = circular_state(radius)
            maneuver = Maneuver(time_start=0.0, time_duration=100.0,
                                target_apoapsis=target, relative_to="Earth")
            deltas.append(maneuver.resolve(location, velocity, GM_EARTH))

        self.assertGreater(deltas[0], deltas[1])

    def test_braking_resolves_to_a_negative_value(self):
        """Ein Einfang bremst; das Vorzeichen dreht die Schubrichtung um."""
        radius = 7.0e6
        location, velocity = circular_state(radius)

        maneuver = Maneuver(time_start=0.0, time_duration=100.0,
                            target_apoapsis=radius * 0.9, relative_to="Earth")
        resolved = maneuver.resolve(location, velocity, GM_EARTH)

        self.assertLess(resolved, 0.0)
        self.assertLess(maneuver.acceleration_magnitude(1000.0), 0.0)

    def test_target_below_the_current_radius_brakes(self):
        """Kein Fehler, sondern ein Bremsmanöver -- die Bahn wird abgesenkt."""
        radius = 7.0e6
        location, velocity = circular_state(radius)

        maneuver = Maneuver(time_start=0.0, time_duration=100.0,
                            target_apoapsis=radius * 0.5, relative_to="Earth")
        self.assertLess(maneuver.resolve(location, velocity, GM_EARTH), 0.0)

    def test_negative_target_is_rejected_when_built(self):
        """Ein negativer Radius ist keine Bahn, sondern ein Eingabefehler."""
        with self.assertRaises(ValueError):
            Maneuver(time_start=0.0, time_duration=100.0,
                     target_apoapsis=-1.0, relative_to="Earth")

    def test_unresolved_target_produces_no_thrust(self):
        """Vor dem Zünden ist das Delta-v unbekannt -- dann brennt nichts."""
        maneuver = Maneuver(time_start=0.0, time_duration=100.0,
                            target_apoapsis=4.2e7, relative_to="Earth")

        self.assertEqual(maneuver.acceleration_magnitude(1000.0), 0.0)

    def test_reset_clears_the_resolved_value(self):
        """Sonst liefe eine Zielsuche im zweiten Durchlauf mit alten Werten."""
        location, velocity = circular_state(7.0e6)
        maneuver = Maneuver(time_duration=100.0, target_apoapsis=4.2e7,
                            relative_to="Earth",
                            trigger=__import__("models.trigger", fromlist=["x"])
                            .TimeTrigger(0.0))
        maneuver.resolve(location, velocity, GM_EARTH)
        self.assertIsNotNone(maneuver.resolved_delta_v)

        maneuver.reset()
        self.assertIsNone(maneuver.resolved_delta_v)


class TestPeriapsisReferencedResolution(unittest.TestCase):
    """Ein Manöver ums Periapsis muss dort gerechnet werden, nicht am Zündpunkt."""

    def eccentric_state(self, periapsis=6.6e6, apoapsis=5.2e7, fraction=0.02):
        """Zustand kurz vor dem Periapsis einer Ellipse."""
        semi_major_axis = (periapsis + apoapsis) / 2.0
        eccentricity = (apoapsis - periapsis) / (apoapsis + periapsis)
        # Etwas vor dem Periapsis: kleiner negativer Winkel der wahren Anomalie
        angle = -fraction * math.pi
        radius = (semi_major_axis * (1 - eccentricity ** 2)
                  / (1 + eccentricity * math.cos(angle)))
        location = np.array([radius * math.cos(angle), radius * math.sin(angle), 0.0])
        speed = math.sqrt(GM_EARTH * (2.0 / radius - 1.0 / semi_major_axis))
        # Richtung grob tangential; für den Test zählt der Betrag
        tangent = np.cross([0.0, 0.0, 1.0], location)
        velocity = tangent / np.linalg.norm(tangent) * speed
        return location, velocity

    def test_periapsis_reference_needs_less_than_the_ignition_point(self):
        """Weiter draussen verlangt Vis-Viva mehr -- daher der Überschuss."""
        location, velocity = self.eccentric_state()
        target = 1.5e8

        at_ignition = Maneuver(time_start=0.0, time_duration=100.0,
                               target_apoapsis=target, relative_to="Earth")
        at_periapsis = Maneuver(time_start=0.0, time_duration=100.0,
                                target_apoapsis=target, relative_to="Earth")

        loose = at_ignition.resolve(location, velocity, GM_EARTH)
        tight = at_periapsis.resolve(location, velocity, GM_EARTH,
                                     at_periapsis=True)

        self.assertLess(tight, loose)

    def test_works_on_an_open_orbit(self):
        """Ein Einfang wird auf einer Hyperbel gerechnet -- er ist ja noch offen."""
        radius = 1.0e7
        escape = math.sqrt(2.0 * GM_MOON / radius)
        location = np.array([radius, 0.0, 0.0])
        velocity = np.array([0.0, escape * 1.1, 0.0])

        maneuver = Maneuver(time_start=0.0, time_duration=100.0,
                            target_apoapsis=1.8e7, relative_to="Moon")
        resolved = maneuver.resolve(location, velocity, GM_MOON,
                                    at_periapsis=True)

        self.assertLess(resolved, 0.0, "Einfang muss bremsen")


class TestHyperbolicPeriapsisPrediction(unittest.TestCase):
    """Ohne sie liesse sich ein Einfang gar nicht auslösen."""

    def approach(self, radius=1.0e8, factor=1.3):
        escape = math.sqrt(2.0 * GM_MOON / radius)
        location = np.array([radius, 0.0, 0.0])
        # Nach innen gerichtet, mit etwas Querkomponente
        velocity = np.array([-escape * factor * 0.9, escape * factor * 0.2, 0.0])
        return location, velocity

    def test_approaching_hyperbola_has_a_next_pass(self):
        location, velocity = self.approach()
        elements = elements_from_state(location, velocity, GM_MOON)
        self.assertGreater(elements.eccentricity, 1.0)

        remaining = time_to_periapsis(location, velocity, GM_MOON)

        self.assertIsNotNone(remaining, "Ohne Vorhersage kein Einfang")
        self.assertGreater(remaining, 0.0)

    def test_departing_hyperbola_has_none(self):
        location, velocity = self.approach()
        self.assertIsNone(time_to_periapsis(location, -velocity, GM_MOON))

    def test_prediction_is_consistent_with_the_elements(self):
        """Die Vorhersage muss zur Periapsisdistanz derselben Bahn passen."""
        location, velocity = self.approach()
        elements = elements_from_state(location, velocity, GM_MOON)
        remaining = time_to_periapsis(location, velocity, GM_MOON)

        # Grobe Gegenprobe über die mittlere Radialgeschwindigkeit
        travelled = float(np.linalg.norm(location)) - elements.periapsis
        radial_speed = abs(float(np.dot(location, velocity))
                           / np.linalg.norm(location))
        self.assertLess(remaining, travelled / radial_speed * 3.0)


class TestScenarioTargets(unittest.TestCase):
    """Die Ziele im Szenario und ihre Validierung."""

    def test_chandrayaan_targets_are_ordered_outwards(self):
        scenario = load_named_scenario("chandrayaan2")
        earth_burns = [m for m in scenario.body("Chandrayaan-2").list_maneuvers
                       if m.target_reference == "Earth"]

        targets = [m.target_apoapsis for m in earth_burns]
        self.assertEqual(targets, sorted(targets),
                         "Eine Bahnanhebung darf nicht nach innen zielen")

    def test_target_without_reference_is_rejected(self):
        path = write_scenario({
            "name": "X",
            "bodies": [dict(MINIMAL_BODY)],
            "maneuvers": [{"body": "Star", "time_start": 0, "duration": 10,
                           "target_apoapsis": 1.0e8}],
        })
        try:
            with self.assertRaises(ScenarioError) as context:
                load_scenario(path)
            self.assertIn("target_reference", str(context.exception))
        finally:
            os.unlink(path)

    def test_two_strengths_are_rejected(self):
        path = write_scenario({
            "name": "X",
            "bodies": [dict(MINIMAL_BODY)],
            "maneuvers": [{"body": "Star", "time_start": 0, "duration": 10,
                           "delta_v": 5, "target_apoapsis": 1.0e8,
                           "relative_to": "Star"}],
        })
        try:
            with self.assertRaises(ScenarioError):
                load_scenario(path)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
