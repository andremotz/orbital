"""Validierungs-Tests für den Physik-Kern.

Diese Tests prüfen Erhaltungsgrößen, die für jedes korrekte N-Body-Verfahren
gelten müssen: Beschleunigungs-Dimension, Impuls, Drehimpuls, Energie und das
Schließen einer Kreisbahn. Sie sind bewusst unabhängig von der Aufruf-Mechanik
formuliert -- die gesamte Kopplung an den Integrator steckt in `advance()`.
Ändert sich die Integrator-API, wird nur dieser Adapter angepasst.

Ausführen:  python -m unittest discover tests
"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.constants import CONST_GRAVITY
from models.maneuver import Maneuver
from models.massive_object import MassiveObject
from models.state import State
from physics.gravity import accelerations, get_acceleration
from physics.integrator import step
from physics.mission import get_mission_acceleration

MASS_SUN = 1.989e30
AU = 1.5e11


def make_object(name, mass, location, velocity, is_heavy=True):
    """Erzeugt einen Körper mit einem einzigen Anfangszustand."""
    state = State(np.array(velocity, dtype=float), np.array(location, dtype=float))
    return MassiveObject(state, mass, 1.0, (255, 255, 255), name, is_heavy, [])


def advance(objects, time_step, steps):
    """Adapter auf den Integrator -- die einzige API-abhängige Stelle im Modul."""
    time = 0.0
    for _ in range(steps):
        step(objects, time_step, time)
        time += time_step


def total_momentum(objects):
    """Gesamtimpuls Sigma m*v -- ohne äußere Kräfte eine Erhaltungsgröße."""
    return sum(
        (obj.mass * obj.getLatestState().vec_velocity for obj in objects),
        np.zeros(2),
    )


def total_angular_momentum(objects):
    """Drehimpuls Sigma m*(x*vy - y*vx) um den Ursprung."""
    total = 0.0
    for obj in objects:
        state = obj.getLatestState()
        x, y = state.vec_location
        vx, vy = state.vec_velocity
        total += obj.mass * (x * vy - y * vx)
    return total


def total_energy(objects):
    """Gesamtenergie: kinetisch plus potenziell über alle Paare."""
    kinetic = sum(
        0.5 * obj.mass * float(np.dot(obj.getLatestState().vec_velocity,
                                      obj.getLatestState().vec_velocity))
        for obj in objects
    )
    potential = 0.0
    for i, obj_a in enumerate(objects):
        for obj_b in objects[i + 1:]:
            distance = np.linalg.norm(
                obj_a.getLatestState().vec_location - obj_b.getLatestState().vec_location
            )
            potential -= CONST_GRAVITY * obj_a.mass * obj_b.mass / distance
    return kinetic + potential


def circular_orbit_pair(radius=AU, satellite_mass=1000.0):
    """Sonne plus leichter Satellit auf exakter Kreisbahn bei `radius`."""
    speed = math.sqrt(CONST_GRAVITY * MASS_SUN / radius)
    sun = make_object("Sun", MASS_SUN, [0.0, 0.0], [0.0, 0.0])
    satellite = make_object("Satellite", satellite_mass, [radius, 0.0], [0.0, speed])
    return [sun, satellite], speed


class TestAcceleration(unittest.TestCase):
    """get_acceleration muss eine Beschleunigung in m/s^2 liefern."""

    def test_acceleration_has_si_magnitude(self):
        objects, _ = circular_orbit_pair()
        satellite = objects[1]

        acceleration = get_acceleration(
            satellite, satellite.getLatestState(), objects
        )

        expected = CONST_GRAVITY * MASS_SUN / AU ** 2  # ~5.9e-3 m/s^2
        self.assertAlmostEqual(
            float(np.linalg.norm(acceleration)) / expected, 1.0, places=3,
            msg="Beschleunigung weicht um mehr als 0.1%% vom analytischen Wert ab",
        )

    def test_vectorised_matches_single_body(self):
        """`accelerations` und `get_acceleration` müssen übereinstimmen."""
        objects, _ = circular_orbit_pair()
        positions = np.array([obj.getLatestState().vec_location for obj in objects])
        masses = np.array([obj.mass for obj in objects])

        batch = accelerations(positions, masses)

        for index, obj in enumerate(objects):
            single = get_acceleration(obj, obj.getLatestState(), objects)
            np.testing.assert_allclose(batch[index], single, rtol=1e-12)


class TestConservation(unittest.TestCase):
    """Erhaltungsgrößen über eine längere Integration."""

    TIME_STEP = 3600.0
    STEPS = 2000

    def test_momentum_is_conserved(self):
        objects, _ = circular_orbit_pair()
        before = total_momentum(objects)
        scale = objects[1].mass * math.sqrt(CONST_GRAVITY * MASS_SUN / AU)

        advance(objects, self.TIME_STEP, self.STEPS)

        drift = float(np.linalg.norm(total_momentum(objects) - before)) / scale
        self.assertLess(drift, 1e-6, "Gesamtimpuls driftet")

    def test_angular_momentum_is_conserved(self):
        objects, _ = circular_orbit_pair()
        before = total_angular_momentum(objects)

        advance(objects, self.TIME_STEP, self.STEPS)

        drift = abs(total_angular_momentum(objects) - before) / abs(before)
        self.assertLess(drift, 1e-8, "Drehimpuls driftet")

    def test_energy_is_conserved(self):
        objects, _ = circular_orbit_pair()
        before = total_energy(objects)

        advance(objects, self.TIME_STEP, self.STEPS)

        drift = abs(total_energy(objects) - before) / abs(before)
        self.assertLess(drift, 1e-6, "Gesamtenergie driftet")


class TestOrbitGeometry(unittest.TestCase):
    """Geometrische Eigenschaften einer bekannten Bahn."""

    def test_circular_orbit_keeps_radius(self):
        """Auf einer Kreisbahn muss der Bahnradius konstant bleiben."""
        objects, _ = circular_orbit_pair()
        satellite = objects[1]

        advance(objects, 3600.0, 500)

        radius = float(np.linalg.norm(satellite.getLatestState().vec_location))
        self.assertAlmostEqual(
            radius / AU, 1.0, places=3,
            msg="Bahnradius weicht um mehr als 0.1%% ab",
        )

    def test_circular_orbit_closes_after_one_period(self):
        """Nach einem vollen Umlauf muss der Satellit am Start ankommen."""
        objects, speed = circular_orbit_pair()
        satellite = objects[1]
        start = satellite.getLatestState().vec_location.copy()

        # Schrittweite aus der Periode ableiten, damit die Schritte den Umlauf
        # exakt abdecken -- sonst misst der Test Rundung statt Integration.
        period = 2.0 * math.pi * AU / speed
        steps = 8800
        advance(objects, period / steps, steps)

        offset = float(np.linalg.norm(satellite.getLatestState().vec_location - start))
        self.assertLess(
            offset / AU, 1e-6,
            "Bahn schließt sich nicht -- Abweichung > 1e-6 des Radius",
        )


class TestManeuvers(unittest.TestCase):
    """Manöver müssen zur richtigen Simulationszeit und Richtung wirken."""

    def make_probe(self, maneuver):
        probe = make_object("Probe", 100.0, [AU, 0.0], [0.0, 1000.0], is_heavy=False)
        probe.list_maneuvers.append(maneuver)
        return probe

    def test_maneuver_fires_inside_its_window(self):
        probe = self.make_probe(Maneuver(time_start=600, time_duration=1000, force=500.0))

        acceleration = get_mission_acceleration(probe, time=900.0)

        # Prograd, also entlang +y, mit a = F/m = 500/100
        np.testing.assert_allclose(acceleration, [0.0, 5.0], atol=1e-12)

    def test_maneuver_is_silent_outside_its_window(self):
        probe = self.make_probe(Maneuver(time_start=600, time_duration=1000, force=500.0))

        for time in (0.0, 599.0, 1600.0, 5000.0):
            with self.subTest(time=time):
                np.testing.assert_allclose(
                    get_mission_acceleration(probe, time), [0.0, 0.0], atol=1e-12
                )

    def test_maneuver_respects_explicit_direction(self):
        probe = self.make_probe(
            Maneuver(time_start=0, time_duration=100, force=500.0, direction=[3.0, 4.0])
        )

        acceleration = get_mission_acceleration(probe, time=50.0)

        # Richtung wird normiert: (3,4)/5 * 5.0
        np.testing.assert_allclose(acceleration, [3.0, 4.0], atol=1e-12)

    def test_maneuver_raises_orbit(self):
        """Ein prograder Burn muss den Bahnradius messbar anheben."""
        objects, _ = circular_orbit_pair(satellite_mass=100.0)
        satellite = objects[1]
        satellite.list_maneuvers.append(
            Maneuver(time_start=0, time_duration=3600 * 24, force=500.0)
        )

        advance(objects, 3600.0, 500)

        radius = float(np.linalg.norm(satellite.getLatestState().vec_location))
        self.assertGreater(radius, AU * 1.001, "Burn hebt die Bahn nicht an")


if __name__ == "__main__":
    unittest.main()
