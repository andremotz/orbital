#!/usr/bin/env python3
"""
Test-Script für die Rust-Integration in matplotlib
Testet die Funktionalität der beschleunigten matplotlib-Version
"""

import sys
import os
import time
import numpy as np

# Füge den aktuellen Pfad hinzu
sys.path.insert(0, os.path.dirname(__file__))

def test_matplotlib_rust_import():
    """Testet ob die Rust-matplotlib-Integration importiert werden kann"""
    print("🧪 Teste Rust-matplotlib Import...")
    
    try:
        from main_matplotlib_rust import RustOrbitVisualizer
        print("✅ Rust-matplotlib-Integration erfolgreich importiert")
        return True
    except ImportError as e:
        print(f"❌ Import fehlgeschlagen: {e}")
        return False

def test_visualizer_creation():
    """Testet die Erstellung des Rust-Visualizers"""
    print("\n🧪 Teste Rust-Visualizer-Erstellung...")
    
    try:
        from main_matplotlib_rust import RustOrbitVisualizer
        
        # Teste beide Modi
        rust_visualizer = RustOrbitVisualizer(use_rust=True)
        python_visualizer = RustOrbitVisualizer(use_rust=False)
        
        print("✅ Rust-Visualizer erfolgreich erstellt")
        print(f"   Rust-Modus: {'Verfügbar' if rust_visualizer.use_rust else 'Nicht verfügbar'}")
        print(f"   Python-Modus: Verfügbar")
        return True
    except Exception as e:
        print(f"❌ Visualizer-Erstellung fehlgeschlagen: {e}")
        return False

def test_trail_optimizer():
    """Testet den Trail-Optimizer"""
    print("\n🧪 Teste Trail-Optimizer...")
    
    try:
        from rust_trail_optimizer import RustTrailOptimizer
        
        optimizer = RustTrailOptimizer(use_rust=True)
        optimizer.initialize_trails(["Earth", "Moon"], trail_length=100)
        
        # Teste Trail-Verarbeitung
        import math
        for i in range(100):
            angle = i * 0.1
            x = math.cos(angle) * 1e8
            y = math.sin(angle) * 1e8
            optimizer.add_position_to_buffer("Earth", (x, y))
        
        optimizer.process_trails_intelligent(simulation_speed=10)
        optimizer.flush_all_buffers()
        
        earth_trail = optimizer.get_trail_data("Earth")
        print(f"✅ Trail-Optimizer funktioniert: {len(earth_trail)} Punkte verarbeitet")
        return True
    except Exception as e:
        print(f"❌ Trail-Optimizer-Test fehlgeschlagen: {e}")
        return False

def test_performance_comparison():
    """Testet Performance-Vergleich zwischen Rust und Python"""
    print("\n🧪 Teste Performance-Vergleich...")
    
    try:
        from main_matplotlib_rust import RustOrbitVisualizer
        from data.celestial_objects import get_massive_objects
        
        objects = get_massive_objects()
        
        # Teste Python-Implementierung
        print("   Teste Python-Implementierung...")
        python_visualizer = RustOrbitVisualizer(use_rust=False)
        python_visualizer.massive_objects = objects.copy()
        
        start_time = time.time()
        for _ in range(100):
            python_visualizer.integrator.calculate_states_batch(python_visualizer.massive_objects, 60.0)
        python_time = time.time() - start_time
        
        print(f"   Python: {python_time:.3f}s für 100 Schritte")
        
        # Teste Rust-Implementierung (falls verfügbar)
        if python_visualizer.integrator.use_rust:
            print("   Teste Rust-Implementierung...")
            rust_visualizer = RustOrbitVisualizer(use_rust=True)
            rust_visualizer.massive_objects = objects.copy()
            
            start_time = time.time()
            for _ in range(100):
                rust_visualizer.integrator.calculate_states_batch(rust_visualizer.massive_objects, 60.0)
            rust_time = time.time() - start_time
            
            print(f"   Rust: {rust_time:.3f}s für 100 Schritte")
            
            if rust_time > 0:
                speedup = python_time / rust_time
                print(f"   Speedup: {speedup:.2f}x")
            else:
                print("   Rust-Timing nicht verfügbar")
        else:
            print("   Rust-Implementierung nicht verfügbar")
        
        return True
    except Exception as e:
        print(f"❌ Performance-Test fehlgeschlagen: {e}")
        return False

def test_controls():
    """Testet die neuen Tasten-Funktionen"""
    print("\n🧪 Teste neue Tasten-Funktionen...")
    
    try:
        from main_matplotlib_rust import RustOrbitVisualizer
        
        visualizer = RustOrbitVisualizer(use_rust=True)
        
        # Teste Integrator-Umschaltung
        original_use_rust = visualizer.use_rust
        visualizer.toggle_integrator()
        assert visualizer.use_rust != original_use_rust, "Integrator-Umschaltung funktioniert nicht"
        
        # Teste Reset
        visualizer.reset_simulation()
        assert visualizer.time == 0, "Reset funktioniert nicht"
        assert visualizer.simulation_speed == 1, "Reset funktioniert nicht"
        
        print("✅ Tasten-Funktionen funktionieren")
        return True
    except Exception as e:
        print(f"❌ Tasten-Test fehlgeschlagen: {e}")
        return False

def test_animation_components():
    """Testet die Animationskomponenten"""
    print("\n🧪 Teste Animationskomponenten...")
    
    try:
        from main_matplotlib_rust import RustOrbitVisualizer
        
        visualizer = RustOrbitVisualizer(use_rust=True)
        
        # Teste Trail-Verarbeitung
        visualizer.update_trail_intelligent("Earth", (1e8, 2e8))
        assert "Earth" in visualizer.trail_buffers, "Trail-Buffer nicht erstellt"
        
        # Teste Focus-Wechsel
        original_focus = visualizer.focus_index
        visualizer.cycle_focus()
        assert visualizer.focus_index != original_focus, "Focus-Wechsel funktioniert nicht"
        
        # Teste Zoom-Funktionen
        original_zoom = visualizer.zoom
        visualizer.zoom_in()
        assert visualizer.zoom > original_zoom, "Zoom-In funktioniert nicht"
        
        zoom_after_zoom_in = visualizer.zoom
        visualizer.zoom_out()
        assert visualizer.zoom < zoom_after_zoom_in, "Zoom-Out funktioniert nicht"
        
        print("✅ Animationskomponenten funktionieren")
        return True
    except Exception as e:
        print(f"❌ Animations-Test fehlgeschlagen: {e}")
        return False

def test_benchmark_integration():
    """Testet die Benchmark-Integration"""
    print("\n🧪 Teste Benchmark-Integration...")
    
    try:
        from main_matplotlib_rust import RustOrbitVisualizer
        from rust_integration import PerformanceBenchmark
        
        visualizer = RustOrbitVisualizer(use_rust=True)
        benchmark = PerformanceBenchmark()
        
        # Teste ob Benchmark ausgeführt werden kann
        # (Ohne tatsächliche Ausführung, da das zu lange dauern würde)
        assert hasattr(visualizer, 'run_benchmark'), "Benchmark-Methode nicht gefunden"
        assert hasattr(benchmark, 'benchmark_simulation'), "Benchmark-Klasse nicht korrekt"
        
        print("✅ Benchmark-Integration funktioniert")
        return True
    except Exception as e:
        print(f"❌ Benchmark-Test fehlgeschlagen: {e}")
        return False

def run_quick_simulation_test():
    """Führt einen schnellen Simulations-Test durch"""
    print("\n🧪 Führe schnellen Simulations-Test durch...")
    
    try:
        from main_matplotlib_rust import RustOrbitVisualizer
        
        visualizer = RustOrbitVisualizer(use_rust=True)
        
        # Simuliere einige Zeitschritte
        for _ in range(10):
            visualizer.integrator.calculate_states_batch(visualizer.massive_objects, 60.0)
            visualizer.time += 60.0
        
        # Prüfe ob Objekte sich bewegt haben
        initial_positions = []
        for obj in visualizer.massive_objects:
            state = obj.getLatestState()
            initial_positions.append((state.vec_location[0], state.vec_location[1]))
        
        # Führe weitere Schritte aus
        for _ in range(10):
            visualizer.integrator.calculate_states_batch(visualizer.massive_objects, 60.0)
            visualizer.time += 60.0
        
        # Prüfe ob sich Positionen geändert haben
        positions_changed = False
        for i, obj in enumerate(visualizer.massive_objects):
            state = obj.getLatestState()
            current_pos = (state.vec_location[0], state.vec_location[1])
            if current_pos != initial_positions[i]:
                positions_changed = True
                break
        
        assert positions_changed, "Objekte bewegen sich nicht"
        
        print("✅ Simulation funktioniert korrekt")
        print(f"   Zeit: {visualizer.time/3600:.2f} Stunden")
        print(f"   Objekte: {len(visualizer.massive_objects)}")
        
        return True
    except Exception as e:
        print(f"❌ Simulations-Test fehlgeschlagen: {e}")
        return False

def main():
    """Hauptfunktion für alle Tests"""
    print("🚀 Rust-matplotlib Integration Test Suite")
    print("=" * 60)
    
    tests = [
        ("Rust-matplotlib Import", test_matplotlib_rust_import),
        ("Visualizer-Erstellung", test_visualizer_creation),
        ("Trail-Optimizer", test_trail_optimizer),
        ("Performance-Vergleich", test_performance_comparison),
        ("Tasten-Funktionen", test_controls),
        ("Animationskomponenten", test_animation_components),
        ("Benchmark-Integration", test_benchmark_integration),
        ("Simulations-Test", run_quick_simulation_test),
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
    print("\n" + "=" * 60)
    print("📊 Test-Zusammenfassung:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\nErgebnis: {passed}/{len(results)} Tests bestanden")
    
    if passed == len(results):
        print("🎉 Alle Tests bestanden! Rust-matplotlib-Integration ist bereit.")
        print("\n🚀 Nächste Schritte:")
        print("   1. Starte die beschleunigte Simulation: python main_matplotlib_rust.py")
        print("   2. Teste die neuen Tasten: 't' (Toggle), 'b' (Benchmark)")
        print("   3. Vergleiche Performance zwischen Rust und Python")
    else:
        print("⚠️  Einige Tests fehlgeschlagen. Prüfe die Fehlermeldungen oben.")
        print("\n🔧 Mögliche Lösungen:")
        print("   1. Stelle sicher, dass der Rust-Kernel kompiliert ist")
        print("   2. Prüfe alle Dependencies: pip install matplotlib numpy")
        print("   3. Führe Tests erneut aus: python test_matplotlib_rust.py")

if __name__ == "__main__":
    main()
