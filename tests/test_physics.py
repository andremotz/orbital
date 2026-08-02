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

from data.constants import CONST_GRAVITY, DIMENSIONS, GM_EARTH, GM_SUN
from models.maneuver import Maneuver
from models.massive_object import MassiveObject
from models.oblateness import Oblateness
from models.state import State
from physics.gravity import (
    accelerations,
    get_acceleration,
    oblateness_accelerations,
)
from physics.integrator import step
from physics.mission import get_mission_acceleration

MASS_SUN = 1.989e30
AU = 1.5e11


def as_vector(values):
    """Ergänzt zwei- auf dreikomponentige Vektoren, wie der Szenario-Loader."""
    components = [float(value) for value in values]
    components += [0.0] * (DIMENSIONS - len(components))
    return np.array(components)


def make_object(name, mass, location, velocity, is_heavy=True):
    """Erzeugt einen Körper mit einem einzigen Anfangszustand."""
    state = State(as_vector(velocity), as_vector(location))
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
        np.zeros(DIMENSIONS),
    )


def total_angular_momentum(objects):
    """Drehimpuls Sigma m*(r x v) um den Ursprung.

    In 3D ist das ein Vektor: sein Betrag misst den Bahndrehimpuls, seine
    Richtung steht senkrecht auf der Bahnebene. Beides muss erhalten bleiben,
    denn eine driftende Richtung hiesse, dass sich die Bahnebene dreht.
    """
    total = np.zeros(DIMENSIONS)
    for obj in objects:
        state = obj.getLatestState()
        total += obj.mass * np.cross(state.vec_location, state.vec_velocity)
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
        mus = np.array([obj.mu for obj in objects])

        batch = accelerations(positions, mus)

        for index, obj in enumerate(objects):
            single = get_acceleration(obj, obj.getLatestState(), objects)
            np.testing.assert_allclose(batch[index], single, rtol=1e-12)


class TestGravitationalParameter(unittest.TestCase):
    """GM ist die maßgebliche Grösse, nicht Masse mal Gravitationskonstante."""

    def test_mu_defaults_to_mass_times_g(self):
        body = make_object("X", 1.0e24, [0.0, 0.0], [0.0, 0.0])
        self.assertAlmostEqual(body.mu, CONST_GRAVITY * 1.0e24, places=6)

    def test_explicit_mu_overrides_mass(self):
        """Ein angegebenes GM muss die Anziehung bestimmen, nicht die Masse."""
        state = State(np.zeros(DIMENSIONS), np.zeros(DIMENSIONS))
        body = MassiveObject(state, 1.0, 1.0, (0, 0, 0), "X", True, [], mu=GM_EARTH)

        self.assertEqual(body.mu, GM_EARTH)

        probe = make_object("P", 1.0, [7.0e6, 0.0], [0.0, 0.0], is_heavy=False)
        acceleration = get_acceleration(probe, probe.getLatestState(), [body, probe])

        self.assertAlmostEqual(
            float(np.linalg.norm(acceleration)) / (GM_EARTH / 7.0e6 ** 2), 1.0, places=9
        )

    def test_published_gm_differs_from_mass_times_g(self):
        """Die Abweichung ist der Grund für die Umstellung -- sie ist real."""
        mass_based = CONST_GRAVITY * 1.989e30
        relative = abs(mass_based - GM_SUN) / GM_SUN

        self.assertGreater(relative, 1e-4,
                           "Wenn beide übereinstimmen, ist die Begründung hinfällig")


class TestOblateness(unittest.TestCase):
    """Abplattung der Erde, die stärkste Störung im erdnahen Orbit."""

    def earth_and_probe(self, offset):
        state = State(np.zeros(DIMENSIONS), np.zeros(DIMENSIONS))
        earth = MassiveObject(state, 5.9722e24, 6.371e6, (0, 0, 0), "Earth", True, [],
                              mu=GM_EARTH, oblateness=Oblateness.earth())
        probe = make_object("Probe", 1000.0, offset, [0.0, 0.0, 0.0], is_heavy=False)
        return [earth, probe]

    def test_magnitude_matches_closed_form(self):
        """Im Äquator der Erde muss der Betrag der Formel 1.5*J2*mu*Re^2/r^4 folgen."""
        radius = 7.0e6
        # Senkrecht zur Polachse, damit der Anteil längs des Pols verschwindet
        pole = Oblateness.earth().pole
        equatorial = np.cross(pole, [0.0, 0.0, 1.0])
        equatorial = equatorial / np.linalg.norm(equatorial)

        bodies = self.earth_and_probe(equatorial * radius)
        positions = np.array([b.getLatestState().vec_location for b in bodies])

        extra = oblateness_accelerations(positions, bodies)

        expected = 1.5 * Oblateness.earth().j2 * GM_EARTH * \
            Oblateness.earth().equatorial_radius ** 2 / radius ** 4
        self.assertAlmostEqual(
            float(np.linalg.norm(extra[1])) / expected, 1.0, places=6
        )

    def test_falls_off_as_inverse_fourth_power(self):
        pole = Oblateness.earth().pole
        equatorial = np.cross(pole, [0.0, 0.0, 1.0])
        equatorial = equatorial / np.linalg.norm(equatorial)

        magnitudes = []
        for radius in (7.0e6, 1.4e7):
            bodies = self.earth_and_probe(equatorial * radius)
            positions = np.array([b.getLatestState().vec_location for b in bodies])
            magnitudes.append(float(np.linalg.norm(
                oblateness_accelerations(positions, bodies)[1]
            )))

        # Radius verdoppelt -> Beitrag auf ein Sechzehntel
        self.assertAlmostEqual(magnitudes[0] / magnitudes[1], 16.0, places=4)

    def test_acts_around_the_rotation_axis_not_the_ecliptic(self):
        """Auf der Polachse muss der Beitrag längs des Pols zeigen.

        Läge die Wulst fälschlich um die z-Achse der Ekliptik, zeigte er in
        eine um 23,44 Grad verdrehte Richtung.
        """
        pole = Oblateness.earth().pole
        bodies = self.earth_and_probe(pole * 7.0e6)
        positions = np.array([b.getLatestState().vec_location for b in bodies])

        extra = oblateness_accelerations(positions, bodies)[1]
        direction = extra / np.linalg.norm(extra)

        # Antiparallel zum Pol: über den Polen zieht die Wulst nach innen
        self.assertAlmostEqual(abs(float(np.dot(direction, pole))), 1.0, places=9)

    def test_spherical_bodies_contribute_nothing(self):
        objects, _ = circular_orbit_pair()
        positions = np.array([o.getLatestState().vec_location for o in objects])

        np.testing.assert_array_equal(
            oblateness_accelerations(positions, objects), np.zeros_like(positions)
        )


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

        drift = float(np.linalg.norm(total_angular_momentum(objects) - before))
        drift /= float(np.linalg.norm(before))
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


class TestThreeDimensionalMotion(unittest.TestCase):
    """Bewegung ausserhalb der Ekliptik.

    Ohne diese Tests bliebe unbemerkt, wenn die dritte Komponente überall
    null wäre -- die übrigen Tests liefen dann weiter, obwohl das Modell in
    Wahrheit zweidimensional rechnete.
    """

    def inclined_orbit(self, inclination_degrees=30.0, radius=AU):
        """Kreisbahn, deren Ebene um `inclination_degrees` gekippt ist."""
        angle = math.radians(inclination_degrees)
        speed = math.sqrt(CONST_GRAVITY * MASS_SUN / radius)

        sun = make_object("Sun", MASS_SUN, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
        # Ortsvektor entlang x, Geschwindigkeit in der gekippten Ebene
        satellite = make_object(
            "Satellite", 1000.0,
            [radius, 0.0, 0.0],
            [0.0, speed * math.cos(angle), speed * math.sin(angle)],
        )
        return [sun, satellite], angle

    def test_inclined_orbit_leaves_the_ecliptic(self):
        objects, _ = self.inclined_orbit()
        satellite = objects[1]

        advance(objects, 3600.0, 2000)

        out_of_plane = abs(float(satellite.getLatestState().vec_location[2]))
        self.assertGreater(out_of_plane, 0.1 * AU,
                           "Bahn bleibt in der Ekliptik -- z wird nicht integriert")

    def test_inclination_is_preserved(self):
        """Ohne Störung darf sich die Bahnebene nicht drehen."""
        objects, angle = self.inclined_orbit()

        before = total_angular_momentum(objects)
        advance(objects, 3600.0, 2000)
        after = total_angular_momentum(objects)

        # Winkel zwischen den Drehimpulsvektoren -- er misst die Drehung der Ebene
        cosine = float(np.dot(before, after) / (np.linalg.norm(before) * np.linalg.norm(after)))
        self.assertAlmostEqual(cosine, 1.0, places=12, msg="Bahnebene kippt")

        # Und die Neigung entspricht der vorgegebenen
        normal = before / np.linalg.norm(before)
        measured = math.acos(abs(float(normal[2])))
        self.assertAlmostEqual(measured, angle, places=9)

    def test_planar_orbit_stays_planar(self):
        """Die Umkehrung: eine Bahn in der Ebene darf z nicht entwickeln."""
        objects, _ = circular_orbit_pair()

        advance(objects, 3600.0, 2000)

        for obj in objects:
            with self.subTest(body=obj.name):
                self.assertEqual(obj.getLatestState().vec_location[2], 0.0)
                self.assertEqual(obj.getLatestState().vec_velocity[2], 0.0)

    def test_energy_is_conserved_on_an_inclined_orbit(self):
        objects, _ = self.inclined_orbit()
        before = total_energy(objects)

        advance(objects, 3600.0, 2000)

        drift = abs(total_energy(objects) - before) / abs(before)
        self.assertLess(drift, 1e-6, "Gesamtenergie driftet ausserhalb der Ebene")


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
        np.testing.assert_allclose(acceleration, [0.0, 5.0, 0.0], atol=1e-12)

    def test_maneuver_is_silent_outside_its_window(self):
        probe = self.make_probe(Maneuver(time_start=600, time_duration=1000, force=500.0))

        for time in (0.0, 599.0, 1600.0, 5000.0):
            with self.subTest(time=time):
                np.testing.assert_allclose(
                    get_mission_acceleration(probe, time), np.zeros(DIMENSIONS),
                    atol=1e-12,
                )

    def test_maneuver_respects_explicit_direction(self):
        probe = self.make_probe(
            Maneuver(time_start=0, time_duration=100, force=500.0, direction=[3.0, 4.0])
        )

        acceleration = get_mission_acceleration(probe, time=50.0)

        # Richtung wird normiert: (3,4,0)/5 * 5.0
        np.testing.assert_allclose(acceleration, [3.0, 4.0, 0.0], atol=1e-12)

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
