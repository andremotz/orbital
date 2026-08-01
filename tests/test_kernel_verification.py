"""Schicht 1 der Verifikation: der Kernel gegen analytisch bekannte Lösungen.

Hier wird ausschließlich der Integrator geprüft, gegen Probleme, deren exakte
Lösung bekannt ist. Jede Abweichung ist damit eindeutig dem Verfahren
zuzuschreiben -- anders als bei einem Missions-Szenario, wo Startwerte,
Manöverprofil und fehlende Physik als Fehlerquellen dazukommen.

Geprüft werden:
  * Kepler-Zweikörperproblem gegen die exakte Lösung der Kepler-Gleichung
  * Konvergenzordnung des Verfahrens (RK4 muss vierter Ordnung sein)
  * Figur-Acht-Choreografie, eine bekannte periodische Dreikörperlösung

Ausführen:  python -m unittest discover tests
"""

import math
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.constants import CONST_GRAVITY
from physics.integrator import step
from tests.test_physics import advance, make_object

MASS_SUN = 1.989e30
AU = 1.5e11


def solve_kepler_equation(mean_anomaly, eccentricity, tolerance=1e-14):
    """Löst E - e*sin(E) = M nach der exzentrischen Anomalie E.

    Newton-Verfahren; die Kepler-Gleichung ist transzendent und hat keine
    geschlossene Lösung.
    """
    eccentric_anomaly = mean_anomaly
    for _ in range(100):
        residual = eccentric_anomaly - eccentricity * math.sin(eccentric_anomaly) - mean_anomaly
        derivative = 1.0 - eccentricity * math.cos(eccentric_anomaly)
        delta = residual / derivative
        eccentric_anomaly -= delta
        if abs(delta) < tolerance:
            return eccentric_anomaly
    raise AssertionError("Kepler-Gleichung nicht konvergiert")


def kepler_position(semi_major_axis, eccentricity, mu, elapsed):
    """Exakte Position auf einer Keplerbahn, Start im Perihel bei t=0."""
    mean_motion = math.sqrt(mu / semi_major_axis ** 3)
    eccentric_anomaly = solve_kepler_equation(mean_motion * elapsed, eccentricity)
    return np.array([
        semi_major_axis * (math.cos(eccentric_anomaly) - eccentricity),
        semi_major_axis * math.sqrt(1.0 - eccentricity ** 2) * math.sin(eccentric_anomaly),
    ])


def kepler_pair(semi_major_axis=AU, eccentricity=0.5, satellite_mass=1000.0):
    """Zweikörpersystem, das im Perihel der gewünschten Bahn startet.

    Die Relativbewegung zweier Körper folgt exakt einer Keplerbahn mit
    mu = G*(M+m) -- deshalb ist der Vergleich streng und nicht genähert.
    """
    mu = CONST_GRAVITY * (MASS_SUN + satellite_mass)
    perihelion = semi_major_axis * (1.0 - eccentricity)
    speed = math.sqrt(mu * (1.0 + eccentricity) / (semi_major_axis * (1.0 - eccentricity)))

    central = make_object("Central", MASS_SUN, [0.0, 0.0], [0.0, 0.0])
    satellite = make_object("Satellite", satellite_mass, [perihelion, 0.0], [0.0, speed])
    return [central, satellite], mu


def relative_position(objects):
    """Position des Satelliten relativ zum Zentralkörper."""
    return (objects[1].getLatestState().vec_location
            - objects[0].getLatestState().vec_location)


class TestKeplerProblem(unittest.TestCase):
    """Vergleich gegen die exakte Lösung des Zweikörperproblems."""

    SEMI_MAJOR_AXIS = AU
    ECCENTRICITY = 0.5

    def period(self, mu):
        return 2.0 * math.pi * math.sqrt(self.SEMI_MAJOR_AXIS ** 3 / mu)

    def test_matches_analytic_solution_after_one_orbit(self):
        objects, mu = kepler_pair(self.SEMI_MAJOR_AXIS, self.ECCENTRICITY)
        period = self.period(mu)
        steps = 20000

        advance(objects, period / steps, steps)

        expected = kepler_position(self.SEMI_MAJOR_AXIS, self.ECCENTRICITY, mu, period)
        error = float(np.linalg.norm(relative_position(objects) - expected))
        self.assertLess(
            error / self.SEMI_MAJOR_AXIS, 1e-9,
            "Bahn weicht nach einem Umlauf von der Kepler-Lösung ab",
        )

    def test_matches_analytic_solution_along_the_way(self):
        """Auch zwischen den Apsiden muss die Bahn stimmen, nicht nur am Ende."""
        objects, mu = kepler_pair(self.SEMI_MAJOR_AXIS, self.ECCENTRICITY)
        period = self.period(mu)
        steps_per_orbit = 20000
        time_step = period / steps_per_orbit

        for fraction in (0.125, 0.25, 0.5, 0.75):
            objects, mu = kepler_pair(self.SEMI_MAJOR_AXIS, self.ECCENTRICITY)
            elapsed_steps = int(steps_per_orbit * fraction)
            advance(objects, time_step, elapsed_steps)

            expected = kepler_position(
                self.SEMI_MAJOR_AXIS, self.ECCENTRICITY, mu, elapsed_steps * time_step
            )
            error = float(np.linalg.norm(relative_position(objects) - expected))
            with self.subTest(fraction=fraction):
                self.assertLess(error / self.SEMI_MAJOR_AXIS, 1e-9)

    def test_high_eccentricity_still_tracks(self):
        """Bei e=0.9 wird das Perihel schnell durchlaufen -- der harte Fall."""
        eccentricity = 0.9
        objects, mu = kepler_pair(self.SEMI_MAJOR_AXIS, eccentricity)
        period = 2.0 * math.pi * math.sqrt(self.SEMI_MAJOR_AXIS ** 3 / mu)
        steps = 200000

        advance(objects, period / steps, steps)

        expected = kepler_position(self.SEMI_MAJOR_AXIS, eccentricity, mu, period)
        error = float(np.linalg.norm(relative_position(objects) - expected))
        self.assertLess(error / self.SEMI_MAJOR_AXIS, 1e-8)


class TestConvergenceOrder(unittest.TestCase):
    """RK4 muss vierter Ordnung sein: halbes dt bedeutet 1/16 des Fehlers."""

    def test_error_scales_with_fourth_power_of_step_size(self):
        semi_major_axis, eccentricity = AU, 0.3
        _, mu = kepler_pair(semi_major_axis, eccentricity)
        period = 2.0 * math.pi * math.sqrt(semi_major_axis ** 3 / mu)
        elapsed = period / 4.0

        errors = []
        for steps in (500, 1000, 2000):
            objects, mu = kepler_pair(semi_major_axis, eccentricity)
            advance(objects, elapsed / steps, steps)
            expected = kepler_position(semi_major_axis, eccentricity, mu, elapsed)
            errors.append(float(np.linalg.norm(relative_position(objects) - expected)))

        for coarse, fine in zip(errors, errors[1:]):
            order = math.log2(coarse / fine)
            with self.subTest(coarse=coarse, fine=fine):
                self.assertGreater(order, 3.7, f"Ordnung nur {order:.2f}, erwartet ~4")
                self.assertLess(order, 4.3, f"Ordnung {order:.2f}, unplausibel hoch")


class TestFigureEightChoreography(unittest.TestCase):
    """Drei gleich schwere Körper auf einer gemeinsamen Acht.

    Diese periodische Lösung des Dreikörperproblems (Chenciner und Montgomery,
    2000) ist ein scharfer Test: schon kleine Fehler im Kraftgesetz oder in der
    gemeinsamen Fortschreibung aller Körper lassen die Figur zerfallen.

    Die Startwerte gelten für G = 1 und Massen 1. Mit Masse 1/G wird daraus
    G*m = 1, sodass dieselbe Dynamik ohne Umskalierung der Zeit entsteht.
    """

    PERIOD = 6.32591398

    def make_system(self):
        mass = 1.0 / CONST_GRAVITY
        location = np.array([0.97000436, -0.24308753])
        velocity = np.array([-0.93240737, -0.86473146])

        return [
            make_object("A", mass, location, -velocity / 2.0),
            make_object("B", mass, -location, -velocity / 2.0),
            make_object("C", mass, [0.0, 0.0], velocity),
        ]

    def test_returns_to_start_after_one_period(self):
        objects = self.make_system()
        start = [obj.getLatestState().vec_location.copy() for obj in objects]
        steps = 200000

        advance(objects, self.PERIOD / steps, steps)

        for obj, expected in zip(objects, start):
            offset = float(np.linalg.norm(obj.getLatestState().vec_location - expected))
            with self.subTest(body=obj.name):
                self.assertLess(offset, 1e-6, "Figur-Acht schließt sich nicht")

    def test_bodies_stay_bound(self):
        """Über mehrere Perioden darf die Figur nicht auseinanderfliegen."""
        objects = self.make_system()
        steps = 200000

        advance(objects, 4.0 * self.PERIOD / steps, steps)

        for obj in objects:
            distance = float(np.linalg.norm(obj.getLatestState().vec_location))
            with self.subTest(body=obj.name):
                self.assertLess(distance, 2.0, "Körper hat die Choreografie verlassen")


if __name__ == "__main__":
    unittest.main()
