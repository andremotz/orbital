#!/usr/bin/env python3
"""
Test-Script für die Rust-Integration
Testet die Funktionalität ohne vollständige Simulation
"""

import sys
import os
import time
import numpy as np

# Füge den aktuellen Pfad hinzu
sys.path.insert(0, os.path.dirname(__file__))

def test_rust_import():
    """Testet ob der Rust-Kernel importiert werden kann"""
    print("🧪 Teste Rust-Kernel Import...")
    
    try:
        from rust_integration import RustAcceleratedIntegrator, PerformanceBenchmark
        print("✅ Rust-Integration erfolgreich importiert")
        return True
    except ImportError as e:
        print(f"❌ Import fehlgeschlagen: {e}")
        print("   Stelle sicher, dass der Rust-Kernel kompiliert ist:")
        print("   ./build_rust_kernel.sh")
        return False

def test_integrator_creation():
    """Testet die Erstellung des Integrators"""
    print("\n🧪 Teste Integrator-Erstellung...")
    
    try:
        from rust_integration import RustAcceleratedIntegrator
        
        # Teste beide Modi
        rust_integrator = RustAcceleratedIntegrator(use_rust=True)
        python_integrator = RustAcceleratedIntegrator(use_rust=False)
        
        print("✅ Integratoren erfolgreich erstellt")
        print(f"   Rust-Integrator: {'Verfügbar' if rust_integrator.use_rust else 'Nicht verfügbar'}")
        print(f"   Python-Integrator: Verfügbar")
        return True
    except Exception as e:
        print(f"❌ Integrator-Erstellung fehlgeschlagen: {e}")
        return False

def test_benchmark_creation():
    """Testet die Erstellung des Benchmarks"""
    print("\n🧪 Teste Benchmark-Erstellung...")
    
    try:
        from rust_integration import PerformanceBenchmark
        
        benchmark = PerformanceBenchmark()
        print("✅ Benchmark erfolgreich erstellt")
        return True
    except Exception as e:
        print(f"❌ Benchmark-Erstellung fehlgeschlagen: {e}")
        return False

def test_simulation_data():
    """Testet ob Simulationsdaten geladen werden können"""
    print("\n🧪 Teste Simulationsdaten...")
    
    try:
        from data.celestial_objects import get_massive_objects
        
        objects = get_massive_objects()
        print(f"✅ {len(objects)} Himmelskörper geladen:")
        
        for i, obj in enumerate(objects):
            state = obj.getLatestState()
            print(f"   {i+1}. {obj.name}: Masse={obj.mass:.2e}kg, Position=({state.vec_location[0]:.2e}, {state.vec_location[1]:.2e})")
        
        return True
    except Exception as e:
        print(f"❌ Simulationsdaten-Ladung fehlgeschlagen: {e}")
        return False

def test_rust_kernel_direct():
    """Testet den Rust-Kernel direkt (falls verfügbar)"""
    print("\n🧪 Teste Rust-Kernel direkt...")
    
    try:
        import orbital_rust_kernel
        
        # Erstelle Testdaten
        masses = np.array([1.989e30, 5.972e24], dtype=np.float64)  # Sonne, Erde
        # Zustände sind dreikomponentig: [x, y, z]
        positions = np.array([[0.0, 0.0, 0.0], [1.496e11, 0.0, 0.0]], dtype=np.float64)
        velocities = np.array([[0.0, 0.0, 0.0], [0.0, 29780.0, 0.0]], dtype=np.float64)
        # Manöver-Schub in m/s^2, hier für beide Körper null
        thrust = np.zeros((2, 3), dtype=np.float64)
        time_step = 60.0

        # Führe RK4-Berechnung aus
        new_positions, new_velocities = orbital_rust_kernel.rk4_step_python(
            masses, positions, velocities, thrust, time_step
        )
        
        print("✅ Rust-Kernel funktioniert!")
        print(f"   Neue Positionen: {new_positions}")
        print(f"   Neue Geschwindigkeiten: {new_velocities}")
        return True
    except ImportError:
        print("⚠️  Rust-Kernel nicht verfügbar (nicht kompiliert)")
        return False
    except Exception as e:
        print(f"❌ Rust-Kernel-Test fehlgeschlagen: {e}")
        return False

def run_performance_test():
    """Führt einen einfachen Performance-Test durch"""
    print("\n🧪 Führe Performance-Test durch...")
    
    try:
        from rust_integration import RustAcceleratedIntegrator
        from data.celestial_objects import get_massive_objects
        
        objects = get_massive_objects()
        integrator = RustAcceleratedIntegrator(use_rust=True)
        
        # Teste 100 Schritte
        start_time = time.time()
        for _ in range(100):
            integrator.calculate_states_batch(objects, 60.0)
        end_time = time.time()
        
        duration = end_time - start_time
        steps_per_second = 100 / duration
        
        print(f"✅ Performance-Test abgeschlossen")
        print(f"   100 Schritte in {duration:.3f}s")
        print(f"   {steps_per_second:.1f} Schritte/Sekunde")
        
        return True
    except Exception as e:
        print(f"❌ Performance-Test fehlgeschlagen: {e}")
        return False

def main():
    """Hauptfunktion für alle Tests"""
    print("🚀 Rust-Integration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Rust-Import", test_rust_import),
        ("Integrator-Erstellung", test_integrator_creation),
        ("Benchmark-Erstellung", test_benchmark_creation),
        ("Simulationsdaten", test_simulation_data),
        ("Rust-Kernel direkt", test_rust_kernel_direct),
        ("Performance-Test", run_performance_test),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} fehlgeschlagen mit Exception: {e}")
            results.append((test_name, False))
    
    # Zusammenfassung
    print("\n" + "=" * 50)
    print("📊 Test-Zusammenfassung:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nErgebnis: {passed}/{len(results)} Tests bestanden")
    
    if passed == len(results):
        print("🎉 Alle Tests bestanden! Rust-Integration ist bereit.")
    else:
        print("⚠️  Einige Tests fehlgeschlagen. Prüfe die Fehlermeldungen oben.")
        print("\n🔧 Nächste Schritte:")
        print("   1. Installiere Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh")
        print("   2. Kompiliere Kernel: ./build_rust_kernel.sh")
        print("   3. Führe Tests erneut aus: python test_rust_integration.py")

if __name__ == "__main__":
    main()
