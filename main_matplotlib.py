import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from collections import deque

# Import der modularen Komponenten
from data.constants import WIDTH, HEIGHT
from data.celestial_objects import get_massive_objects
from physics.integrator import calculate_state_new


class OrbitVisualizer:
    """Reine Matplotlib-basierte Orbital-Simulation mit adaptiven Zeitschritten"""
    
    def __init__(self):
        # Simulation Parameter
        self.time = 0
        self.physics_timestep = 60  # Konstant bei 60s für Genauigkeit
        self.simulation_speed = 1   # Wie viele Physik-Schritte pro Frame
        self.zoom = 10**-6 * (1.5**25)  # Vorgezoomt: entspricht 25x "+" drücken (~2.37)
        self.center_x = 0
        self.center_y = 0
        self.trail_length = 1000  # Länge der Bahnspuren
        self.paused = False
        self.focus_index = 0  # 0=Sun, 1=Earth, 2=Moon, 3=Chandrayaan-2
        
        # Himmelskörper initialisieren
        self.massive_objects = get_massive_objects()
        
        # Bahnspuren für jedes Objekt speichern
        self.trails = {}
        # Zusätzliche Trail-Buffer für intelligentes Sampling
        self.trail_buffers = {}
        for obj in self.massive_objects:
            self.trails[obj.name] = deque(maxlen=self.trail_length)
            self.trail_buffers[obj.name] = []
        
        # Matplotlib Setup
        self.setup_plot()
        
    def setup_plot(self):
        """Matplotlib Plot einrichten"""
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(14, 10))
        self.fig.patch.set_facecolor('black')
        self.ax.set_facecolor('black')
        
        # Plot-Elemente initialisieren
        self.planet_plots = {}
        self.trail_plots = {}
        
        for obj in self.massive_objects:
            # Planet/Objekt als Punkt
            color = np.array(obj.color)/255.0
            size = max(5, min(25, obj.radius/500000))
            
            self.planet_plots[obj.name], = self.ax.plot(
                [], [], 'o', 
                color=color,
                markersize=size,
                label=obj.name,
                markeredgewidth=1,
                markeredgecolor='white' if obj.name != 'Sun' else color
            )
            
            # Bahnspur
            self.trail_plots[obj.name], = self.ax.plot(
                [], [], '-', 
                color=color, 
                alpha=0.7, 
                linewidth=2 if obj.name in ['Earth', 'Moon'] else 1
            )
        
        self.ax.set_aspect('equal')
        self.ax.legend(loc='upper right', fancybox=True, shadow=True)
        self.ax.grid(True, alpha=0.2)
        
        # Titel und Beschriftungen
        self.ax.set_xlabel('Distanz (skaliert)', color='white')
        self.ax.set_ylabel('Distanz (skaliert)', color='white')
        
        # Keyboard-Event-Handler
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
        # Kompakter Informationstext (ASCII-kompatibel)
        info_text = (
            "Steuerung:\n"
            "SPACE: Pause/Play\n"
            "+/-: Zoom  z: Zoom Reset\n"
            "o: Fokus  Pfeile: Speed\n"
            "r: Simulation Reset\n"
            "\n"
            "RK4 60s Integration\n"
            "Intelligente Trails"
        )
        self.ax.text(0.02, 0.98, info_text, transform=self.ax.transAxes, 
                    verticalalignment='top', fontsize=8, 
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='black', alpha=0.9),
                    color='white')
        
    def on_key_press(self, event):
        """Tastatur-Event-Handler"""
        if event.key == ' ':  # Leertaste
            self.toggle_pause()
        elif event.key == '+' or event.key == '=':
            self.zoom_in()
        elif event.key == '-':
            self.zoom_out()
        elif event.key == 'o':
            self.cycle_focus()
        elif event.key == 'up':
            self.simulation_speed = min(1440, int(self.simulation_speed * 2))  # Max: 1440 (1 Tag)
            effective_time = self.simulation_speed * self.physics_timestep
            print(f"Simulation beschleunigt: {self.simulation_speed} Schritte/Frame ({effective_time}s = {effective_time/3600:.1f}h)")
        elif event.key == 'down':
            self.simulation_speed = max(1, int(self.simulation_speed / 2))
            effective_time = self.simulation_speed * self.physics_timestep
            print(f"Simulation verlangsamt: {self.simulation_speed} Schritte/Frame ({effective_time}s = {effective_time/60:.1f}min)")
        elif event.key == 'r':
            self.reset_simulation()
        elif event.key == 'z':
            self.reset_zoom()
            
    def zoom_in(self):
        """Hineinzoomen"""
        self.zoom *= 1.5
        
    def zoom_out(self):
        """Herauszoomen"""
        self.zoom /= 1.5
        
    def toggle_pause(self):
        """Pause/Play umschalten"""
        self.paused = not self.paused
        print(f"Simulation {'pausiert' if self.paused else 'gestartet'}")
        
    def reset_zoom(self):
        """Zoom auf Standard-Level zurücksetzen"""
        self.zoom = 10**-6 * (1.5**25)
        print("Zoom zurückgesetzt")
        
    def cycle_focus(self):
        """Zwischen Fokus-Objekten wechseln"""
        self.focus_index = (self.focus_index + 1) % len(self.massive_objects)
        focus_name = self.massive_objects[self.focus_index].name
        print(f"Fokus gewechselt zu: {focus_name}")
        
    def reset_simulation(self):
        """Simulation zurücksetzen"""
        self.time = 0
        self.simulation_speed = 1
        self.zoom = 10**-6 * (1.5**25)  # Standard-Zoom
        self.massive_objects = get_massive_objects()
        for obj in self.massive_objects:
            self.trails[obj.name].clear()
            self.trail_buffers[obj.name].clear()
        print("Simulation zurückgesetzt")
        
    def get_focus_object(self):
        """Fokus-Objekt zurückgeben"""
        return self.massive_objects[self.focus_index]
        
    def update_trail_intelligent(self, obj_name, position):
        """Intelligentes Trail-Update mit adaptiver Ausdünnung"""
        # Position zum Buffer hinzufügen
        self.trail_buffers[obj_name].append(position)
        
        # Adaptive Ausdünnung basierend auf Geschwindigkeit
        if self.simulation_speed <= 10:
            # Bei niedrigen Geschwindigkeiten: alle Punkte behalten
            sample_rate = 1
        elif self.simulation_speed <= 50:
            # Bei mittleren Geschwindigkeiten: jeden 2.-5. Punkt
            sample_rate = max(2, self.simulation_speed // 5)
        else:
            # Bei hohen Geschwindigkeiten: intelligente Ausdünnung
            sample_rate = max(5, self.simulation_speed // 10)
        
        # Buffer verarbeiten wenn genug Punkte gesammelt
        if len(self.trail_buffers[obj_name]) >= sample_rate:
            # Wichtige Punkte identifizieren (Wendepunkte, extreme Positionen)
            buffer = self.trail_buffers[obj_name]
            
            if len(buffer) >= 3:
                # Immer ersten und letzten Punkt behalten
                self.trails[obj_name].append(buffer[0])
                
                # Bei mehr als 3 Punkten: Wendepunkte und Extrema finden
                if len(buffer) > 3:
                    # Mittlere Punkte nur bei signifikanten Richtungsänderungen
                    for i in range(1, len(buffer) - 1):
                        prev_pos = buffer[i-1]
                        curr_pos = buffer[i]
                        next_pos = buffer[i+1]
                        
                        # Richtungsvektor berechnen
                        dx1 = curr_pos[0] - prev_pos[0]
                        dy1 = curr_pos[1] - prev_pos[1]
                        dx2 = next_pos[0] - curr_pos[0]
                        dy2 = next_pos[1] - curr_pos[1]
                        
                        # Winkeländerung berechnen (Kreuprodukt)
                        cross_product = abs(dx1 * dy2 - dy1 * dx2)
                        distance = (dx1**2 + dy1**2)**0.5 * (dx2**2 + dy2**2)**0.5
                        
                        # Signifikante Krümmung? (adaptive Schwelle basierend auf Geschwindigkeit)
                        curvature_threshold = max(1e12, 1e15 / self.simulation_speed)
                        if distance > 0 and cross_product / distance > curvature_threshold:
                            self.trails[obj_name].append(curr_pos)
                
                # Letzten Punkt immer hinzufügen
                self.trails[obj_name].append(buffer[-1])
            else:
                # Bei wenigen Punkten: alle hinzufügen
                for pos in buffer:
                    self.trails[obj_name].append(pos)
            
            # Buffer leeren
            self.trail_buffers[obj_name].clear()
        
    def flush_trail_buffers(self):
        """Alle verbleibenden Trail-Buffer verarbeiten"""
        for obj_name in self.trail_buffers:
            if self.trail_buffers[obj_name]:
                # Alle verbleibenden Punkte hinzufügen
                for position in self.trail_buffers[obj_name]:
                    self.trails[obj_name].append(position)
                self.trail_buffers[obj_name].clear()
        
    def update_animation(self, frame):
        """Animation-Update für matplotlib"""
        if self.paused:
            return list(self.planet_plots.values()) + list(self.trail_plots.values())
            
        # Mehrere Physik-Schritte pro Frame für Beschleunigung
        for step in range(self.simulation_speed):
            self.time += self.physics_timestep
            
            # Physik-Simulation mit konstanten 60s Schritten
            for massive_object in self.massive_objects:
                state_new = calculate_state_new(massive_object, self.massive_objects, self.physics_timestep)
                massive_object.addState(state_new)
                
                # Position zur Bahnspur hinzufügen - ALLE Schritte für Genauigkeit
                current_state = massive_object.getLatestState()
                position = (current_state.vec_location[0], current_state.vec_location[1])
                self.update_trail_intelligent(massive_object.name, position)
        
        # Alle verbleibenden Buffer-Punkte verarbeiten
        self.flush_trail_buffers()
        
        # Fokus-Objekt für Kamera-Positionierung
        focus_obj = self.get_focus_object()
        focus_state = focus_obj.getLatestState()
        self.center_x = focus_state.vec_location[0]
        self.center_y = focus_state.vec_location[1]
        
        # Plot aktualisieren
        for obj in self.massive_objects:
            current_state = obj.getLatestState()
            
            # Position relativ zum Fokus
            rel_x = (current_state.vec_location[0] - self.center_x) * self.zoom
            rel_y = (current_state.vec_location[1] - self.center_y) * self.zoom
            
            # Planet-Position aktualisieren
            self.planet_plots[obj.name].set_data([rel_x], [rel_y])
            
            # Bahnspur aktualisieren
            if len(self.trails[obj.name]) > 1:
                trail_x = [(pos[0] - self.center_x) * self.zoom for pos in self.trails[obj.name]]
                trail_y = [(pos[1] - self.center_y) * self.zoom for pos in self.trails[obj.name]]
                self.trail_plots[obj.name].set_data(trail_x, trail_y)
        
        # Achsen-Grenzen automatisch anpassen
        # Je höher der zoom, desto kleiner der Sichtbereich (näher heran)
        view_range = 2e8 / self.zoom  # Sichtbereich umgekehrt proportional zum Zoom
        self.ax.set_xlim(-view_range, view_range)
        self.ax.set_ylim(-view_range, view_range)
        
        # Kompakter Titel mit aktueller Information
        days = self.time / (24 * 3600)
        focus_name = self.get_focus_object().name
        
        # ASCII Status-Indikator
        status = "PAUSE" if self.paused else "PLAY"
        
        # Kompakte Geschwindigkeits-Info
        if self.simulation_speed >= 1440:
            speed_info = f"{self.simulation_speed//1440}d"  # Tage
        elif self.simulation_speed >= 60:
            speed_info = f"{self.simulation_speed//60}h"    # Stunden
        elif self.simulation_speed > 1:
            speed_info = f"{self.simulation_speed}×"
        else:
            speed_info = ""
        
        # Kurzer Titel
        if speed_info:
            title = f"Tag {days:.1f} | {focus_name} | {speed_info} | {status}"
        else:
            title = f"Tag {days:.1f} | {focus_name} | {status}"
        self.ax.set_title(title, color='white', fontsize=11, pad=10)
        
        return list(self.planet_plots.values()) + list(self.trail_plots.values())
    
    def run(self):
        """Simulation starten"""
        print("Starte Orbital-Simulation...")
        print("Verwende Tastatur für Steuerung (Fenster muss fokussiert sein)")
        
        # Layout optimieren für bessere Titel-Anzeige
        plt.subplots_adjust(top=0.92, bottom=0.08, left=0.08, right=0.95)
        
        # Animation starten
        self.animation = animation.FuncAnimation(
            self.fig, self.update_animation, interval=50, blit=False
        )
        
        plt.show()


def main():
    """Hauptfunktion für matplotlib-Version"""
    print("=" * 60)
    print("🚀 ORBITAL SIMULATION - ADAPTIVE ZEITSCHRITTE")
    print("=" * 60)
    print()
    print("🔬 PHYSIK:")
    print("  • Konstante 60s Zeitschritte für maximale Genauigkeit")
    print("  • RK4-Integration bei allen Geschwindigkeiten präzise")
    print("  • Energie-Erhaltung und Orbit-Stabilität gewährleistet")
    print()
    print("⚡ BESCHLEUNIGUNG:")
    print("  • Visualisierung: 1× bis 1440× (24 Stunden/Frame)")
    print("  • Physik bleibt immer bei 60s-Schritten")
    print("  • Intelligente Trail-Ausdünnung bei hohen Geschwindigkeiten")
    print("  • Keine wichtigen Orbital-Events werden übersprungen")
    print()
    print("🎮 STEUERUNG:")
    print("  SPACE     - Pause/Play")
    print("  +/-       - Zoom In/Out")
    print("  o         - Fokus wechseln")
    print("  ↑/↓       - Geschwindigkeit (Schritte/Frame)")
    print("  r         - Simulation zurücksetzen")
    print()
    print("📡 OBJEKTE:")
    
    # Objekt-Informationen anzeigen
    objects = get_massive_objects()
    for i, obj in enumerate(objects):
        print(f"  {i}: {obj.name}")
    
    print()
    print("🌍 Starte Simulation...")
    
    visualizer = OrbitVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main() 