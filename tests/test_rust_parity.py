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

from data.constants import GM_EARTH
from models.maneuver import Maneuver
from models.massive_object import MassiveObject
from models.oblateness import Oblateness
from models.state import State
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
        make_object(
            "Moon",
            7.349e22,
            [0.0, AU + 3.5523395142e8, 3.1985027687e7],
            [29780.0 + 1015.9, 0.0, 91.4],
        ),
        make_object(
            "Probe",
            100.0,
            [0.0, AU + 4.5475e7, 6.0e6],
            [29780.0 + 2220.0, 0.0, -310.0],
            is_heavy=False,
        ),
    ]


def oblate_earth_with_satellite(oblateness=True):
    """An oblate Earth with a satellite in a low, inclined orbit.

    The four-body scenario above treats every body as a sphere, so it cannot
    see an error in the J2 term -- a kernel whose J2 was 1 % off passed every
    other parity test. Here J2 is the largest perturbation there is: at
    630 km altitude it is about a thousandth of central gravity. The orbit is
    inclined against Earth's equator, so the term has components along and
    across the pole.

    The system sits away from the origin and moves on purpose. The comparison
    is relative to each body's own position and velocity; an Earth at rest at
    the origin would only move by some 1e-14 m under the satellite's pull, and
    comparing rounding noise of that size relative to itself says nothing.
    """
    radius = 7.0e6
    speed = float(np.sqrt(GM_EARTH / radius))
    inclination = np.radians(51.6)
    offset = np.array([1.0e8, 0.0, 0.0])
    drift = np.array([1000.0, 0.0, 0.0])

    earth = MassiveObject(
        State(drift.copy(), offset.copy()),
        5.9722e24,
        6.371e6,
        (0, 255, 255),
        "Earth",
        True,
        [],
        mu=GM_EARTH,
        oblateness=Oblateness.earth() if oblateness else None,
    )
    satellite = MassiveObject(
        State(
            drift
            + np.array([0.0, speed * np.cos(inclination), speed * np.sin(inclination)]),
            offset + np.array([radius, 0.0, 0.0]),
        ),
        1000.0,
        5.0,
        (255, 255, 255),
        "Satellite",
        False,
        [],
    )
    return [earth, satellite]


REQUIRE_RUST = os.environ.get("ORBITAL_REQUIRE_RUST") == "1"


class TestKernelIsRequired(unittest.TestCase):
    """Turns a missing kernel into a failure where it must be present.

    Locally the parity tests are skipped without a kernel, so the suite stays
    usable with nothing but numpy. In CI that skip would hide a kernel that
    failed to build or import. Setting ORBITAL_REQUIRE_RUST=1 makes it fail.
    """

    @unittest.skipUnless(REQUIRE_RUST, "ORBITAL_REQUIRE_RUST is not set")
    def test_kernel_is_importable(self):
        self.assertTrue(
            RUST_AVAILABLE,
            "ORBITAL_REQUIRE_RUST=1, but orbital_rust_kernel cannot be imported",
        )


@unittest.skipUnless(RUST_AVAILABLE, "Rust-Kernel nicht gebaut")
class TestRustParity(unittest.TestCase):
    """Rust und Python müssen bis auf Rundung identische Ergebnisse liefern."""

    def assert_same_trajectory(
        self, objects_python, objects_rust, steps, time_step, rtol
    ):
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
                    rtol,
                    f"{expected.name}: Position",
                )
                self.assert_vectors_agree(
                    actual.getLatestState().vec_velocity,
                    expected.getLatestState().vec_velocity,
                    rtol,
                    f"{expected.name}: Geschwindigkeit",
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
            deviation / scale,
            rtol,
            f"{label}: Abweichung {deviation:.3e} bei Betrag {scale:.3e}",
        )

    def test_single_step_matches(self):
        """Ein Schritt muss bis auf Gleitkomma-Rundung exakt übereinstimmen."""
        self.assert_same_trajectory(
            scenario(), scenario(), steps=1, time_step=60.0, rtol=1e-12
        )

    def test_scenario_actually_leaves_the_ecliptic(self):
        """Absicherung: sonst prüften die Paritätstests die dritte Achse nicht."""
        for body in scenario()[2:]:
            with self.subTest(body=body.name):
                self.assertNotEqual(body.getLatestState().vec_location[2], 0.0)
                self.assertNotEqual(body.getLatestState().vec_velocity[2], 0.0)

    def test_out_of_plane_motion_matches(self):
        """Die z-Komponente muss in beiden Kernels gleich laufen."""
        objects_python, objects_rust = scenario(), scenario()
        self.assert_same_trajectory(
            objects_python, objects_rust, steps=2000, time_step=60.0, rtol=1e-9
        )

        # Und sie darf nicht bei null verharren, sonst ist der Test wertlos
        drift = abs(float(objects_rust[3].getLatestState().vec_location[2] - 6.0e6))
        self.assertGreater(drift, 1.0e5, "z-Komponente bewegt sich nicht")

    def test_long_run_matches(self):
        """Auch über viele Schritte darf nichts auseinanderlaufen."""
        self.assert_same_trajectory(
            scenario(), scenario(), steps=5000, time_step=60.0, rtol=1e-9
        )

    def test_oblateness_matches(self):
        """The J2 term must be computed identically in both kernels."""
        self.assert_same_trajectory(
            oblate_earth_with_satellite(),
            oblate_earth_with_satellite(),
            steps=1000,
            time_step=30.0,
            rtol=1e-9,
        )

    def test_oblateness_actually_changes_the_result(self):
        """Guard: if J2 had no effect, the test above would prove nothing."""
        with_j2 = oblate_earth_with_satellite(oblateness=True)
        without_j2 = oblate_earth_with_satellite(oblateness=False)

        integrator = RustAcceleratedIntegrator(use_rust=True)
        for index in range(1000):
            simulation_time = index * 30.0
            integrator.calculate_states_batch(with_j2, 30.0, simulation_time)
            integrator.calculate_states_batch(without_j2, 30.0, simulation_time)

        separation = np.linalg.norm(
            with_j2[1].getLatestState().vec_location
            - without_j2[1].getLatestState().vec_location
        )
        self.assertGreater(separation, 1e4, "J2 had no effect in the Rust kernel")

    def test_thrust_is_applied_identically(self):
        """Manöver-Schub muss im Rust-Kernel genauso wirken wie in Python."""
        objects_python = scenario()
        objects_rust = scenario()
        for objects in (objects_python, objects_rust):
            objects[3].list_maneuvers.append(
                Maneuver(time_start=0, time_duration=60_000, force=500.0)
            )

        self.assert_same_trajectory(
            objects_python, objects_rust, steps=500, time_step=60.0, rtol=1e-9
        )

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
        mus, positions, velocities, thrust, j2, radii, poles = gather_arrays(
            objects, 0.0
        )

        with self.assertRaises(ValueError):
            orbital_rust_kernel.rk4_step_python(
                mus, positions[:1], velocities, thrust, j2, radii, poles, 60.0
            )

    def test_rejects_mismatched_oblateness_length(self):
        objects, _ = circular_orbit_pair()
        mus, positions, velocities, thrust, j2, radii, poles = gather_arrays(
            objects, 0.0
        )

        with self.assertRaises(ValueError):
            orbital_rust_kernel.rk4_step_python(
                mus, positions, velocities, thrust, j2[:1], radii, poles, 60.0
            )

    def test_accepts_non_contiguous_input(self):
        """Ein Array-Slice darf keinen stillen Speicherfehler auslösen."""
        objects = scenario()
        mus, positions, velocities, thrust, j2, radii, poles = gather_arrays(
            objects, 0.0
        )

        # Jede zweite Zeile -- der zugrundeliegende Speicher ist nicht mehr zusammenhängend.
        # numpy meldet das als TypeError ("not contiguous or is misaligned").
        with self.assertRaises(TypeError):
            orbital_rust_kernel.rk4_step_python(
                mus[::2],
                positions[::2],
                velocities[::2],
                thrust[::2],
                j2[::2],
                radii[::2],
                poles[::2],
                60.0,
            )


if __name__ == "__main__":
    unittest.main()
