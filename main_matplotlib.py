import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from collections import deque

# Import der modularen Komponenten
from data.constants import WIDTH, HEIGHT
from data.celestial_objects import get_massive_objects
from physics.integrator import calculate_state_new


class OrbitVisualizer:
    """Reine Matplotlib-basierte Orbital-Simulation"""
    
    def __init__(self):
        # Simulation Parameter
        self.time = 0
        self.time_step = 60  # Sekunden
        self.zoom = 10**-6  # Fokus auf Erde
        self.center_x = 0
        self.center_y = 0
        self.trail_length = 1000  # Länge der Bahnspuren
        self.paused = False
        self.focus_index = 1  # 0=Sun, 1=Earth, 2=Moon, 3=Chandrayaan-2
        
        # Himmelskörper initialisieren
        self.massive_objects = get_massive_objects()
        
        # Bahnspuren für jedes Objekt speichern
        self.trails = {}
        for obj in self.massive_objects:
            self.trails[obj.name] = deque(maxlen=self.trail_length)
        
        # Matplotlib Setup
        self.setup_plot()
        
    def setup_plot(self):
        """Matplotlib Plot einrichten"""
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(12, 10))
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
        
        # Informationstext
        info_text = (
            "Steuerung:\n"
            "SPACE - Pause/Play\n"
            "+ - Zoom In\n"
            "- - Zoom Out\n"
            "o - Fokus wechseln\n"
            "↑/↓ - Geschwindigkeit\n"
            "r - Reset"
        )
        self.ax.text(0.02, 0.98, info_text, transform=self.ax.transAxes, 
                    verticalalignment='top', fontsize=9, 
                    bbox=dict(boxstyle='round', facecolor='black', alpha=0.8),
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
            self.time_step = min(86400, self.time_step * 10.5)  # Maximum: 1 Tag pro Frame
            print(f"Geschwindigkeit erhöht: {self.time_step:.1f}s/Frame (×{self.time_step/60:.1f})")
        elif event.key == 'down':
            self.time_step = max(1, self.time_step / 10.5)
            print(f"Geschwindigkeit reduziert: {self.time_step:.1f}s/Frame (×{self.time_step/60:.1f})")
        elif event.key == 'r':
            self.reset_simulation()
            
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
        
    def cycle_focus(self):
        """Zwischen Fokus-Objekten wechseln"""
        self.focus_index = (self.focus_index + 1) % len(self.massive_objects)
        focus_name = self.massive_objects[self.focus_index].name
        print(f"Fokus gewechselt zu: {focus_name}")
        
    def reset_simulation(self):
        """Simulation zurücksetzen"""
        self.time = 0
        self.massive_objects = get_massive_objects()
        for obj in self.massive_objects:
            self.trails[obj.name].clear()
        print("Simulation zurückgesetzt")
        
    def get_focus_object(self):
        """Fokus-Objekt zurückgeben"""
        return self.massive_objects[self.focus_index]
        
    def update_animation(self, frame):
        """Animation-Update für matplotlib"""
        if self.paused:
            return list(self.planet_plots.values()) + list(self.trail_plots.values())
            
        self.time += self.time_step
        
        # Physik-Simulation
        for massive_object in self.massive_objects:
            state_new = calculate_state_new(massive_object, self.massive_objects, self.time_step)
            massive_object.addState(state_new)
            
            # Position zur Bahnspur hinzufügen
            current_state = massive_object.getLatestState()
            self.trails[massive_object.name].append(
                (current_state.vec_location[0], current_state.vec_location[1])
            )
        
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
        
        # Titel mit aktueller Information
        days = self.time / (24 * 3600)
        focus_name = self.get_focus_object().name
        speed_info = f"×{self.time_step/60:.1f}" if self.time_step != 60 else ""
        status = "⏸ PAUSIERT" if self.paused else "▶ LÄUFT"
        
        title = f"Orbital Simulation - Tag {days:.1f} | Fokus: {focus_name} {speed_info} | {status}"
        self.ax.set_title(title, color='white', fontsize=12)
        
        return list(self.planet_plots.values()) + list(self.trail_plots.values())
    
    def run(self):
        """Simulation starten"""
        print("Starte Orbital-Simulation...")
        print("Verwende Tastatur für Steuerung (Fenster muss fokussiert sein)")
        
        # Animation starten
        self.animation = animation.FuncAnimation(
            self.fig, self.update_animation, interval=50, blit=False
        )
        
        plt.tight_layout()
        plt.show()


def main():
    """Hauptfunktion für matplotlib-Version"""
    print("=" * 50)
    print("🚀 ORBITAL SIMULATION - MATPLOTLIB VERSION")
    print("=" * 50)
    print()
    print("STEUERUNG:")
    print("  SPACE     - Pause/Play")
    print("  +/-       - Zoom In/Out")
    print("  f         - Fokus wechseln")
    print("  ↑/↓       - Geschwindigkeit ändern")
    print("  r         - Simulation zurücksetzen")
    print()
    print("OBJEKTE:")
    
    # Objekt-Informationen anzeigen
    objects = get_massive_objects()
    for i, obj in enumerate(objects):
        print(f"  {i}: {obj.name}")
    
    print()
    print("Starte Simulation...")
    
    visualizer = OrbitVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main() 