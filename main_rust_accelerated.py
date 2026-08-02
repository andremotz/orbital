import pygame
from collections import defaultdict
import time

# Import der modularen Komponenten
from data.constants import WIDTH, HEIGHT
from data.celestial_objects import get_massive_objects
from rendering.renderer import pygame_draw

# Import des Rust-Kernels
from rust_integration import RustAcceleratedIntegrator, PerformanceBenchmark


def main():
    """Hauptfunktion der Rust-beschleunigten Orbital-Simulation"""
    # initialize the pygame module
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    running = True
    
    #zoom = (10**-9) / 0.85 / 0.85 / 0.85 / 0.85 / 0.85 / 0.85 # Fokus Sun
    zoom = 10 ** -6 # Fokus Erde
    zoom = (10 ** -6) / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2 / 1.2  # Fokus Chandrayaan-2
    scroll_x = 0
    scroll_y = 0
    keysPressed = defaultdict(bool)

    list_massiveobjects = get_massive_objects()

    # Nicht 'time' nennen -- das verdeckt sonst das gleichnamige Modul
    simulation_time = 0
    time_step = 60

    # Initialisiere Rust-beschleunigten Integrator
    integrator = RustAcceleratedIntegrator(use_rust=True)
    
    # Performance-Monitoring
    frame_count = 0
    last_fps_time = time.time()
    fps = 0

    print("🚀 Rust-beschleunigte Orbital-Simulation gestartet!")
    print("   Drücke 'b' für Performance-Benchmark")
    print("   Drücke 'r' für Rust/Python-Umschaltung")

    while running:
        frame_start = time.time()
        frame_count += 1

        # Berechne neue Zustände für alle Objekte mit Rust-Kernel
        integrator.calculate_states_batch(list_massiveobjects, time_step, simulation_time)
        simulation_time += time_step

        # Event handling
        for event in pygame.event.get():
            # only do something if the event is of type QUIT
            if event.type == pygame.QUIT:
                # change the value to False, to exit the main loop
                running = False
            elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                keysPressed[event.key] = event.type == pygame.KEYDOWN

        # Keyboard controls
        if keysPressed[pygame.K_DOWN]:
            zoom /= 0.85
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_UP]:
            zoom /= 1.2
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_ESCAPE]:
            return False
        if keysPressed[pygame.K_w]:
            scroll_y += 10
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_s]:
            scroll_y -= 10
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_a]:
            scroll_x += 10
            screen.fill((0, 0, 0))
        if keysPressed[pygame.K_d]:
            scroll_x -= 10
            screen.fill((0, 0, 0))
        
        # Neue Tasten für Rust-Features
        if keysPressed[pygame.K_b]:
            print("\n🔬 Führe Performance-Benchmark durch...")
            benchmark = PerformanceBenchmark()
            results = benchmark.benchmark_simulation(list_massiveobjects, time_steps=1000)
            keysPressed[pygame.K_b] = False  # Verhindere wiederholte Ausführung
        
        if keysPressed[pygame.K_r]:
            integrator.use_rust = not integrator.use_rust
            print(f"🔄 Integrator umgeschaltet: {'Rust' if integrator.use_rust else 'Python'}")
            keysPressed[pygame.K_r] = False  # Verhindere wiederholte Ausführung

        # Rendering
        pygame_draw(list_massiveobjects, screen, zoom, scroll_x, scroll_y, simulation_time)
        
        # FPS-Berechnung
        current_time = time.time()
        if current_time - last_fps_time >= 1.0:  # Jede Sekunde
            fps = frame_count / (current_time - last_fps_time)
            frame_count = 0
            last_fps_time = current_time
            
            # Zeige Performance-Info in der Konsole
            integrator_type = "Rust" if integrator.use_rust else "Python"
            print(f"📊 FPS: {fps:.1f} | Integrator: {integrator_type} | Zeit: {simulation_time/3600:.2f}h")


def benchmark_mode():
    """Dedizierter Benchmark-Modus"""
    print("🔬 Performance-Benchmark-Modus")
    print("=" * 50)
    
    # Lade Objekte
    list_massiveobjects = get_massive_objects()
    
    # Führe verschiedene Benchmarks durch
    benchmark = PerformanceBenchmark()
    
    print("\n📊 Benchmark 1: Standard-Simulation (1000 Schritte)")
    results1 = benchmark.benchmark_simulation(list_massiveobjects, time_steps=1000)
    
    print("\n📊 Benchmark 2: Lange Simulation (10000 Schritte)")
    results2 = benchmark.benchmark_simulation(list_massiveobjects, time_steps=10000)
    
    print("\n📊 Benchmark 3: Hohe Frequenz (10000 Schritte, 1s Zeitschritt)")
    results3 = benchmark.benchmark_simulation(list_massiveobjects, time_steps=10000, time_step=1.0)
    
    print("\n✅ Benchmark abgeschlossen!")
    print("   Verwende 'python main_rust_accelerated.py' für die normale Simulation")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "benchmark":
        benchmark_mode()
    else:
        main()
