"""
Rust-Integration für die Orbital-Simulation

Bindet den Rust-Kernel für die RK4-Integration an. Der Kernel rechnet dieselbe
Physik wie `physics/integrator.py` -- inklusive Manöver-Schub, der als
Zusatzbeschleunigung übergeben wird. `tests/test_rust_parity.py` hält beide
Implementierungen aufeinander fest.
"""

import time
from typing import List

import numpy as np

from data.constants import DIMENSIONS
from models.state import State
from physics.integrator import step as python_step
from physics.mission import get_mission_acceleration

try:
    import orbital_rust_kernel

    RUST_AVAILABLE = True
except ImportError as e:
    print(f"⚠️  Rust-Kernel nicht verfügbar: {e}")
    print("   Führe './build_rust_kernel.sh' aus")
    RUST_AVAILABLE = False
    orbital_rust_kernel = None


def gather_arrays(massive_objects: List, time: float):
    """Sammelt alles, was der Kernel für einen Schritt braucht.

    Übergeben wird GM je Körper, nicht die Masse -- siehe die Begründung bei
    den Konstanten. Die Abplattung reist als drei parallele Arrays mit; ein
    j2 von null bedeutet, dass der Körper als Kugel gilt.
    """
    mus = np.array([obj.mu for obj in massive_objects], dtype=np.float64)
    positions = np.array(
        [obj.getLatestState().vec_location for obj in massive_objects], dtype=np.float64
    )
    velocities = np.array(
        [obj.getLatestState().vec_velocity for obj in massive_objects], dtype=np.float64
    )
    thrust = np.array(
        [get_mission_acceleration(obj, time, massive_objects) for obj in massive_objects],
        dtype=np.float64,
    )

    count = len(massive_objects)
    j2 = np.zeros(count, dtype=np.float64)
    equatorial_radii = np.zeros(count, dtype=np.float64)
    poles = np.zeros((count, DIMENSIONS), dtype=np.float64)
    for index, obj in enumerate(massive_objects):
        oblateness = getattr(obj, "oblateness", None)
        if oblateness is None:
            continue
        j2[index] = oblateness.j2
        equatorial_radii[index] = oblateness.equatorial_radius
        poles[index] = oblateness.pole

    return mus, positions, velocities, thrust, j2, equatorial_radii, poles


class RustAcceleratedIntegrator:
    """
    Beschleunigter Integrator mit Rust-Backend
    """

    def __init__(self, use_rust: bool = True):
        self.use_rust = use_rust and RUST_AVAILABLE
        if self.use_rust:
            print("🚀 Verwende Rust-beschleunigte RK4-Integration")
        else:
            print("🐍 Verwende Python RK4-Integration")

    def calculate_states_batch(self, massive_objects: List, time_step: float,
                               time: float = 0.0) -> None:
        """
        Berechnet neue Zustände für alle Objekte in einem Batch
        """
        if not self.use_rust or not massive_objects:
            self._calculate_states_python(massive_objects, time_step, time)
            return

        try:
            arrays = gather_arrays(massive_objects, time)
            mus, positions, velocities, thrust, j2, radii, poles = arrays

            new_positions, new_velocities = orbital_rust_kernel.rk4_step_python(
                mus, positions, velocities, thrust, j2, radii, poles, time_step
            )

            for obj, vec_location, vec_velocity in zip(
                massive_objects, new_positions, new_velocities
            ):
                obj.addState(State(vec_velocity, vec_location))

        except Exception as e:
            print(f"⚠️  Fehler im Rust-Kernel, verwende Python-Fallback: {e}")
            self._calculate_states_python(massive_objects, time_step, time)

    def _calculate_states_python(self, massive_objects: List, time_step: float,
                                 time: float = 0.0) -> None:
        """
        Python-Fallback-Implementierung
        """
        python_step(massive_objects, time_step, time)


class PerformanceBenchmark:
    """
    Benchmark-Tool zum Vergleich von Python vs Rust Performance
    """

    def __init__(self):
        self.rust_integrator = RustAcceleratedIntegrator(use_rust=True)
        self.python_integrator = RustAcceleratedIntegrator(use_rust=False)

    def benchmark_simulation(self, massive_objects: List, time_steps: int = 1000,
                             time_step: float = 60.0) -> dict:
        """
        Führt einen Performance-Benchmark durch
        """
        print(f"🔬 Benchmark: {time_steps} Zeitschritte mit {len(massive_objects)} Objekten")
        print("=" * 60)

        results = {}

        print("🐍 Python-Implementierung...")
        python_time = self._time_run(self.python_integrator, massive_objects,
                                     time_steps, time_step)
        results['python'] = {
            'time': python_time,
            'steps_per_second': time_steps / python_time,
            'objects': len(massive_objects),
        }
        print(f"   Zeit: {python_time:.3f}s")
        print(f"   Schritte/Sekunde: {time_steps/python_time:.1f}")

        if not RUST_AVAILABLE:
            print("\n⚠️  Rust-Kernel nicht verfügbar für Benchmark")
            return results

        print("\n🚀 Rust-Implementierung...")
        rust_time = self._time_run(self.rust_integrator, massive_objects,
                                   time_steps, time_step)
        results['rust'] = {
            'time': rust_time,
            'steps_per_second': time_steps / rust_time,
            'objects': len(massive_objects),
        }
        print(f"   Zeit: {rust_time:.3f}s")
        print(f"   Schritte/Sekunde: {time_steps/rust_time:.1f}")

        speedup = python_time / rust_time
        print(f"\n⚡ Speedup: {speedup:.2f}x")
        print(f"   Zeitersparnis: {((python_time - rust_time) / python_time * 100):.1f}%")
        results['speedup'] = speedup

        return results

    def _time_run(self, integrator, massive_objects: List, time_steps: int,
                  time_step: float) -> float:
        """Misst einen Lauf auf einer Kopie, damit beide gleich starten."""
        objects = self._copy_objects(massive_objects)

        simulation_time = 0.0
        start_time = time.perf_counter()
        for _ in range(time_steps):
            integrator.calculate_states_batch(objects, time_step, simulation_time)
            simulation_time += time_step
        return time.perf_counter() - start_time

    def _copy_objects(self, original_objects: List) -> List:
        """
        Erstellt eine unabhängige Kopie der Objekte für Benchmarking
        """
        return [obj.copy() for obj in original_objects]
