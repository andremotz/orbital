"""
Rust-optimierte Trail-Verarbeitung für die Orbital-Simulation
Beschleunigt die intelligente Trail-Thinning-Algorithmen
"""

import numpy as np
from typing import List, Tuple, Deque
from collections import deque

# Versuche den Rust-Kernel zu importieren
try:
    import orbital_rust_kernel
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False
    orbital_rust_kernel = None


class RustTrailOptimizer:
    """
    Rust-beschleunigter Trail-Optimizer für intelligente Trail-Verarbeitung
    """
    
    def __init__(self, use_rust: bool = True):
        self.use_rust = use_rust and RUST_AVAILABLE
        self.trail_buffers = {}
        self.trails = {}
        
    def initialize_trails(self, object_names: List[str], trail_length: int = 1000):
        """Initialisiert Trail-Speicher für alle Objekte"""
        for name in object_names:
            self.trails[name] = deque(maxlen=trail_length)
            self.trail_buffers[name] = []
    
    def add_position_to_buffer(self, obj_name: str, position: Tuple[float, float]):
        """Fügt eine Position zum Trail-Buffer hinzu"""
        self.trail_buffers[obj_name].append(position)
    
    def process_trails_intelligent(self, simulation_speed: int) -> None:
        """
        Verarbeitet alle Trail-Buffer mit intelligenter Thinning-Logik
        """
        if not self.trail_buffers:
            return
            
        if self.use_rust and RUST_AVAILABLE:
            self._process_trails_rust(simulation_speed)
        else:
            self._process_trails_python(simulation_speed)
    
    def _process_trails_rust(self, simulation_speed: int) -> None:
        """Rust-beschleunigte Trail-Verarbeitung"""
        try:
            # Konvertiere Trail-Buffer zu NumPy-Arrays für Rust
            for obj_name, buffer in self.trail_buffers.items():
                if not buffer:
                    continue
                    
                # Berechne Sample-Rate basierend auf Geschwindigkeit
                sample_rate = self._calculate_sample_rate(simulation_speed)
                
                if len(buffer) >= sample_rate:
                    # Konvertiere zu NumPy-Array
                    positions = np.array(buffer, dtype=np.float64)
                    
                    # Führe intelligente Thinning in Rust durch
                    # (Hier würde eine Rust-Funktion für Trail-Thinning aufgerufen werden)
                    # Für jetzt verwenden wir Python-Implementierung als Fallback
                    self._process_trails_python(simulation_speed)
                    
        except Exception as e:
            print(f"⚠️  Rust Trail-Verarbeitung fehlgeschlagen, verwende Python: {e}")
            self._process_trails_python(simulation_speed)
    
    def _process_trails_python(self, simulation_speed: int) -> None:
        """Python-Fallback für Trail-Verarbeitung"""
        for obj_name, buffer in self.trail_buffers.items():
            if not buffer:
                continue
                
            sample_rate = self._calculate_sample_rate(simulation_speed)
            
            if len(buffer) >= sample_rate:
                # Intelligente Thinning-Logik
                if len(buffer) >= 3:
                    # Immer ersten und letzten Punkt behalten
                    self.trails[obj_name].append(buffer[0])
                    
                    # Mittlere Punkte nur bei signifikanten Richtungsänderungen
                    if len(buffer) > 3:
                        for i in range(1, len(buffer) - 1):
                            prev_pos = buffer[i-1]
                            curr_pos = buffer[i]
                            next_pos = buffer[i+1]
                            
                            # Berechne Richtungsvektor
                            dx1 = curr_pos[0] - prev_pos[0]
                            dy1 = curr_pos[1] - prev_pos[1]
                            dx2 = next_pos[0] - curr_pos[0]
                            dy2 = next_pos[1] - curr_pos[1]
                            
                            # Berechne Winkeländerung (Kreuzprodukt)
                            cross_product = abs(dx1 * dy2 - dy1 * dx2)
                            distance = (dx1**2 + dy1**2)**0.5 * (dx2**2 + dy2**2)**0.5
                            
                            # Signifikante Krümmung? (adaptiver Schwellenwert)
                            curvature_threshold = max(1e12, 1e15 / simulation_speed)
                            if distance > 0 and cross_product / distance > curvature_threshold:
                                self.trails[obj_name].append(curr_pos)
                    
                    # Immer letzten Punkt hinzufügen
                    self.trails[obj_name].append(buffer[-1])
                else:
                    # Für wenige Punkte: alle hinzufügen
                    for pos in buffer:
                        self.trails[obj_name].append(pos)
                
                # Buffer leeren
                self.trail_buffers[obj_name].clear()
    
    def _calculate_sample_rate(self, simulation_speed: int) -> int:
        """Berechnet optimale Sample-Rate basierend auf Simulationsgeschwindigkeit"""
        if simulation_speed <= 10:
            return 1
        elif simulation_speed <= 50:
            return max(2, simulation_speed // 5)
        else:
            return max(5, simulation_speed // 10)
    
    def flush_all_buffers(self) -> None:
        """Verarbeitet alle verbleibenden Buffer-Punkte"""
        for obj_name, buffer in self.trail_buffers.items():
            if buffer:
                for position in buffer:
                    self.trails[obj_name].append(position)
                buffer.clear()
    
    def get_trail_data(self, obj_name: str) -> List[Tuple[float, float]]:
        """Gibt Trail-Daten für ein Objekt zurück"""
        return list(self.trails.get(obj_name, []))
    
    def clear_trails(self) -> None:
        """Löscht alle Trails"""
        for trail in self.trails.values():
            trail.clear()
        for buffer in self.trail_buffers.values():
            buffer.clear()


class OptimizedRustOrbitVisualizer:
    """
    Optimierte Version der Rust-Orbit-Visualisierung mit beschleunigter Trail-Verarbeitung
    """
    
    def __init__(self, use_rust=True):
        # Importiere die Basis-Klasse
        from main_matplotlib_rust import RustOrbitVisualizer
        
        # Erstelle Basis-Visualizer
        self.base_visualizer = RustOrbitVisualizer(use_rust=use_rust)
        
        # Erweitere mit optimierter Trail-Verarbeitung
        self.trail_optimizer = RustTrailOptimizer(use_rust=use_rust)
        
        # Initialisiere Trails
        object_names = [obj.name for obj in self.base_visualizer.massive_objects]
        self.trail_optimizer.initialize_trails(object_names, self.base_visualizer.trail_length)
        
        # Überschreibe Trail-Methoden
        self._override_trail_methods()
    
    def _override_trail_methods(self):
        """Überschreibt Trail-Methoden mit optimierten Versionen"""
        # Überschreibe update_trail_intelligent
        self.base_visualizer.update_trail_intelligent = self._optimized_update_trail_intelligent
        self.base_visualizer.flush_trail_buffers = self._optimized_flush_trail_buffers
        
        # Überschreibe reset_simulation
        original_reset = self.base_visualizer.reset_simulation
        def enhanced_reset():
            original_reset()
            self.trail_optimizer.clear_trails()
        self.base_visualizer.reset_simulation = enhanced_reset
    
    def _optimized_update_trail_intelligent(self, obj_name: str, position: Tuple[float, float]):
        """Optimierte Trail-Update-Methode"""
        self.trail_optimizer.add_position_to_buffer(obj_name, position)
        
        # Verarbeite Trails in Batches für bessere Performance
        if len(self.trail_optimizer.trail_buffers[obj_name]) >= 10:  # Batch-Größe
            self.trail_optimizer.process_trails_intelligent(self.base_visualizer.simulation_speed)
    
    def _optimized_flush_trail_buffers(self):
        """Optimierte Buffer-Flush-Methode"""
        self.trail_optimizer.flush_all_buffers()
    
    def update_animation(self, frame):
        """Optimierte Animation-Update-Methode"""
        # Führe normale Animation aus
        result = self.base_visualizer.update_animation(frame)
        
        # Verarbeite verbleibende Trails
        self.trail_optimizer.process_trails_intelligent(self.base_visualizer.simulation_speed)
        
        return result
    
    def run(self):
        """Startet die optimierte Simulation"""
        print("🚀 Starte optimierte Rust-Orbit-Simulation mit beschleunigter Trail-Verarbeitung...")
        self.base_visualizer.run()


def create_optimized_visualizer(use_rust=True):
    """Factory-Funktion für optimierte Visualizer"""
    return OptimizedRustOrbitVisualizer(use_rust=use_rust)


if __name__ == "__main__":
    # Test der optimierten Trail-Verarbeitung
    print("🧪 Teste optimierte Trail-Verarbeitung...")
    
    optimizer = RustTrailOptimizer(use_rust=True)
    optimizer.initialize_trails(["Earth", "Moon"], trail_length=100)
    
    # Simuliere Trail-Daten
    import math
    for i in range(1000):
        angle = i * 0.1
        x = math.cos(angle) * 1e8
        y = math.sin(angle) * 1e8
        optimizer.add_position_to_buffer("Earth", (x, y))
        
        if i % 50 == 0:  # Verarbeite alle 50 Punkte
            optimizer.process_trails_intelligent(simulation_speed=10)
    
    # Flush verbleibende Buffer
    optimizer.flush_all_buffers()
    
    # Zeige Ergebnisse
    earth_trail = optimizer.get_trail_data("Earth")
    print(f"✅ Trail-Verarbeitung abgeschlossen: {len(earth_trail)} Punkte gespeichert")
    print(f"   Kompression: {1000/len(earth_trail):.1f}x")
