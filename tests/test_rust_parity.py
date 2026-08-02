"""Hält Rust-Kernel und Python-Integrator aufeinander fest.

Der Rust-Kernel ist nur dann ein Beschleuniger, wenn er dieselbe Physik
rechnet wie Python. Weicht er ab, ist der Geschwindigkeitsvergleich wertlos,
weil er zwei verschiedene Verfahren vergleicht. Diese Tests werden
übersprungen, solange der Kernel nicht gebaut ist.

Ausführen:  python -m unittest discover tests
"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.maneuver import Maneuver
from physics.integrator import step
from rust_integration import RUST_AVAILABLE, RustAcceleratedIntegrator, gather_arrays
from tests.test_physics import AU, MASS_SUN, circular_orbit_pair, make_object

if RUST_AVAILABLE:
    import orbital_rust_kernel


def scenario():
    """Vier Körper mit deutlich verschiedenen Massen und Abständen.

    Mond und Sonde stehen bewusst ausserhalb der Ekliptik: liefe die Parität
    nur mit z = 0, bliebe eine Abweichung in der dritten Komponente
    unentdeckt.
    """
    return [
        make_object("Sun", MASS_SUN, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]),
        make_object("Earth", 5.9722e24, [0.0, AU, 0.0], [29780.0, 0.0, 0.0]),
        make_object("Moon", 7.349e22,
                    [0.0, AU + 3.5523395142e8, 3.1985027687e7],
                    [29780.0 + 1015.9, 0.0, 91.4]),
        make_object("Probe", 100.0,
                    [0.0, AU + 4.5475e7, 6.0e6],
                    [29780.0 + 2220.0, 0.0, -310.0],
                    is_heavy=False),
    ]


@unittest.skipUnless(RUST_AVAILABLE, "Rust-Kernel nicht gebaut")
class TestRustParity(unittest.TestCase):
    """Rust und Python müssen bis auf Rundung identische Ergebnisse liefern."""

    def assert_same_trajectory(self, objects_python, objects_rust, steps, time_step,
                               rtol):
        integrator = RustAcceleratedIntegrator(use_rust=True)
        self.assertTrue(integrator.use_rust, "Rust-Pfad wurde nicht verwendet")

        simulation_time = 0.0
        for _ in range(steps):
            step(objects_python, time_step, simulation_time)
            integrator.calculate_states_batch(objects_rust, time_step, simulation_time)
            simulation_time += time_step

        for expected, actual in zip(objects_python, objects_rust):
            with self.subTest(body=expected.name):
                self.assert_vectors_agree(
                    actual.getLatestState().vec_location,
                    expected.getLatestState().vec_location,
                    rtol, f"{expected.name}: Position",
                )
                self.assert_vectors_agree(
                    actual.getLatestState().vec_velocity,
                    expected.getLatestState().vec_velocity,
                    rtol, f"{expected.name}: Geschwindigkeit",
                )

    def assert_vectors_agree(self, actual, expected, rtol, label):
        """Vergleicht am Betrag der Abweichung, nicht Komponente für Komponente.

        Eine komponentenweise Relativtoleranz bestraft kleine Komponenten
        unverhältnismässig: die z-Komponente einer fast ebenen Bahn ist um
        Grössenordnungen kleiner als x und y, sodass dort schon
        Rundungsrauschen als grosse relative Abweichung erscheint, obwohl der
        absolute Fehler im Millimeterbereich liegt.
        """
        deviation = float(np.linalg.norm(np.asarray(actual) - np.asarray(expected)))
        scale = float(np.linalg.norm(expected))
        self.assertLessEqual(
            deviation / scale, rtol,
            f"{label}: Abweichung {deviation:.3e} bei Betrag {scale:.3e}",
        )

    def test_single_step_matches(self):
        """Ein Schritt muss bis auf Gleitkomma-Rundung exakt übereinstimmen."""
        self.assert_same_trajectory(scenario(), scenario(), steps=1,
                                    time_step=60.0, rtol=1e-12)

    def test_scenario_actually_leaves_the_ecliptic(self):
        """Absicherung: sonst prüften die Paritätstests die dritte Achse nicht."""
        for body in scenario()[2:]:
            with self.subTest(body=body.name):
                self.assertNotEqual(body.getLatestState().vec_location[2], 0.0)
                self.assertNotEqual(body.getLatestState().vec_velocity[2], 0.0)

    def test_out_of_plane_motion_matches(self):
        """Die z-Komponente muss in beiden Kernels gleich laufen."""
        objects_python, objects_rust = scenario(), scenario()
        self.assert_same_trajectory(objects_python, objects_rust, steps=2000,
                                    time_step=60.0, rtol=1e-9)

        # Und sie darf nicht bei null verharren, sonst ist der Test wertlos
        drift = abs(float(objects_rust[3].getLatestState().vec_location[2] - 6.0e6))
        self.assertGreater(drift, 1.0e5, "z-Komponente bewegt sich nicht")

    def test_long_run_matches(self):
        """Auch über viele Schritte darf nichts auseinanderlaufen."""
        self.assert_same_trajectory(scenario(), scenario(), steps=5000,
                                    time_step=60.0, rtol=1e-9)

    def test_thrust_is_applied_identically(self):
        """Manöver-Schub muss im Rust-Kernel genauso wirken wie in Python."""
        objects_python = scenario()
        objects_rust = scenario()
        for objects in (objects_python, objects_rust):
            objects[3].list_maneuvers.append(
                Maneuver(time_start=0, time_duration=60_000, force=500.0)
            )

        self.assert_same_trajectory(objects_python, objects_rust, steps=500,
                                    time_step=60.0, rtol=1e-9)

    def test_thrust_actually_changes_the_result(self):
        """Absicherung: ohne wirksamen Schub wäre der Test oben wertlos."""
        objects_with = scenario()
        objects_with[3].list_maneuvers.append(
            Maneuver(time_start=0, time_duration=60_000, force=500.0)
        )
        objects_without = scenario()

        integrator = RustAcceleratedIntegrator(use_rust=True)
        for index in range(500):
            simulation_time = index * 60.0
            integrator.calculate_states_batch(objects_with, 60.0, simulation_time)
            integrator.calculate_states_batch(objects_without, 60.0, simulation_time)

        separation = np.linalg.norm(
            objects_with[3].getLatestState().vec_location
            - objects_without[3].getLatestState().vec_location
        )
        self.assertGreater(separation, 1e6, "Schub blieb im Rust-Kernel wirkungslos")


@unittest.skipUnless(RUST_AVAILABLE, "Rust-Kernel nicht gebaut")
class TestRustKernelContract(unittest.TestCase):
    """Der Kernel muss fehlerhafte Eingaben zurückweisen statt zu raten."""

    def test_rejects_mismatched_shapes(self):
        objects, _ = circular_orbit_pair()
        mus, positions, velocities, thrust, j2, radii, poles = gather_arrays(objects, 0.0)

        with self.assertRaises(ValueError):
            orbital_rust_kernel.rk4_step_python(
                mus, positions[:1], velocities, thrust, j2, radii, poles, 60.0
            )

    def test_rejects_mismatched_oblateness_length(self):
        objects, _ = circular_orbit_pair()
        mus, positions, velocities, thrust, j2, radii, poles = gather_arrays(objects, 0.0)

        with self.assertRaises(ValueError):
            orbital_rust_kernel.rk4_step_python(
                mus, positions, velocities, thrust, j2[:1], radii, poles, 60.0
            )

    def test_accepts_non_contiguous_input(self):
        """Ein Array-Slice darf keinen stillen Speicherfehler auslösen."""
        objects = scenario()
        mus, positions, velocities, thrust, j2, radii, poles = gather_arrays(objects, 0.0)

        # Jede zweite Zeile -- der zugrundeliegende Speicher ist nicht mehr zusammenhängend
        with self.assertRaises(Exception):
            orbital_rust_kernel.rk4_step_python(
                mus[::2], positions[::2], velocities[::2], thrust[::2],
                j2[::2], radii[::2], poles[::2], 60.0
            )


if __name__ == "__main__":
    unittest.main()
