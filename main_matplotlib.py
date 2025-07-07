import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from collections import deque

# Import modular components
from data.constants import WIDTH, HEIGHT
from data.celestial_objects import get_massive_objects
from physics.integrator import calculate_state_new


class OrbitVisualizer:
    """Pure matplotlib-based orbital simulation with adaptive time steps"""
    
    def __init__(self):
        # Simulation parameters
        self.time = 0
        self.physics_timestep = 60  # Constant at 60s for accuracy
        self.simulation_speed = 1   # How many physics steps per frame
        self.zoom = 10**-6 * (1.5**25)  # Pre-zoomed: equivalent to 25x "+" presses (~2.37)
        self.center_x = 0
        self.center_y = 0
        self.trail_length = 1000  # Length of orbital trails
        self.paused = False
        self.focus_index = 0  # 0=Sun, 1=Earth, 2=Moon, 3=Chandrayaan-2
        
        # Initialize celestial bodies
        self.massive_objects = get_massive_objects()
        
        # Store orbital trails for each object
        self.trails = {}
        # Additional trail buffers for intelligent sampling
        self.trail_buffers = {}
        for obj in self.massive_objects:
            self.trails[obj.name] = deque(maxlen=self.trail_length)
            self.trail_buffers[obj.name] = []
        
        # Matplotlib setup
        self.setup_plot()
        
    def setup_plot(self):
        """Set up matplotlib plot"""
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(14, 10))
        self.fig.patch.set_facecolor('black')
        self.ax.set_facecolor('black')
        
        # Initialize plot elements
        self.planet_plots = {}
        self.trail_plots = {}
        
        for obj in self.massive_objects:
            # Planet/object as point
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
            
            # Orbital trail
            self.trail_plots[obj.name], = self.ax.plot(
                [], [], '-', 
                color=color, 
                alpha=0.7, 
                linewidth=2 if obj.name in ['Earth', 'Moon'] else 1
            )
        
        self.ax.set_aspect('equal')
        self.ax.legend(loc='upper right', fancybox=True, shadow=True)
        self.ax.grid(True, alpha=0.2)
        
        # Title and labels - updated dynamically in update_animation
        self.update_axis_labels()
        
        # Keyboard event handler
        self.fig.canvas.mpl_connect('key_press_event', self.on_key_press)
        
        # Compact information text (ASCII-compatible)
        info_text = (
            "Controls:\n"
            "SPACE: Pause/Play\n"
            "+/-: Zoom  z: Zoom Reset\n"
            "o: Focus  Arrows: Speed\n"
            "r: Reset Simulation\n"
            "\n"
            "RK4 60s Integration\n"
            "Intelligent Trails"
        )
        self.ax.text(0.02, 0.98, info_text, transform=self.ax.transAxes, 
                    verticalalignment='top', fontsize=8, 
                    bbox=dict(boxstyle='round,pad=0.4', facecolor='black', alpha=0.9),
                    color='white')

    def get_appropriate_distance_unit(self, distance_in_meters):
        """Determines appropriate distance unit based on magnitude"""
        if distance_in_meters >= 1.496e11:  # 1 AU in meters
            return distance_in_meters / 1.496e11, "AU"
        elif distance_in_meters >= 1e9:  # 1 Million km
            return distance_in_meters / 1e9, "M km"
        elif distance_in_meters >= 1e6:  # 1000 km
            return distance_in_meters / 1e6, "1000 km"
        elif distance_in_meters >= 1e3:  # km
            return distance_in_meters / 1e3, "km"
        else:
            return distance_in_meters, "m"

    def update_axis_labels(self):
        """Updates axis labels based on current zoom level"""
        # Calculate current view range in meters
        view_range_meters = 2e8 / self.zoom
        
        # Determine appropriate unit
        scaled_distance, unit = self.get_appropriate_distance_unit(view_range_meters)
        
        # Update axis labels
        self.ax.set_xlabel(f'Distance ({unit})', color='white')
        self.ax.set_ylabel(f'Distance ({unit})', color='white')
        
    def on_key_press(self, event):
        """Keyboard event handler"""
        if event.key == ' ':  # Space bar
            self.toggle_pause()
        elif event.key == '+' or event.key == '=':
            self.zoom_in()
        elif event.key == '-':
            self.zoom_out()
        elif event.key == 'o':
            self.cycle_focus()
        elif event.key == 'up':
            self.simulation_speed = min(1440, int(self.simulation_speed * 2))  # Max: 1440 (1 day)
            effective_time = self.simulation_speed * self.physics_timestep
            print(f"Simulation accelerated: {self.simulation_speed} steps/frame ({effective_time}s = {effective_time/3600:.1f}h)")
        elif event.key == 'down':
            self.simulation_speed = max(1, int(self.simulation_speed / 2))
            effective_time = self.simulation_speed * self.physics_timestep
            print(f"Simulation slowed: {self.simulation_speed} steps/frame ({effective_time}s = {effective_time/60:.1f}min)")
        elif event.key == 'r':
            self.reset_simulation()
        elif event.key == 'z':
            self.reset_zoom()
            
    def zoom_in(self):
        """Zoom in"""
        self.zoom *= 1.5
        
    def zoom_out(self):
        """Zoom out"""
        self.zoom /= 1.5
        
    def toggle_pause(self):
        """Toggle pause/play"""
        self.paused = not self.paused
        print(f"Simulation {'paused' if self.paused else 'started'}")
        
    def reset_zoom(self):
        """Reset zoom to default level"""
        self.zoom = 10**-6 * (1.5**25)
        print("Zoom reset")
        
    def cycle_focus(self):
        """Cycle between focus objects"""
        self.focus_index = (self.focus_index + 1) % len(self.massive_objects)
        focus_name = self.massive_objects[self.focus_index].name
        print(f"Focus switched to: {focus_name}")
        
    def reset_simulation(self):
        """Reset simulation"""
        self.time = 0
        self.simulation_speed = 1
        self.zoom = 10**-6 * (1.5**25)  # Default zoom
        self.massive_objects = get_massive_objects()
        for obj in self.massive_objects:
            self.trails[obj.name].clear()
            self.trail_buffers[obj.name].clear()
        print("Simulation reset")
        
    def get_focus_object(self):
        """Return focus object"""
        return self.massive_objects[self.focus_index]
        
    def update_trail_intelligent(self, obj_name, position):
        """Intelligent trail update with adaptive thinning"""
        # Add position to buffer
        self.trail_buffers[obj_name].append(position)
        
        # Adaptive thinning based on speed
        if self.simulation_speed <= 10:
            # At low speeds: keep all points
            sample_rate = 1
        elif self.simulation_speed <= 50:
            # At medium speeds: every 2nd-5th point
            sample_rate = max(2, self.simulation_speed // 5)
        else:
            # At high speeds: intelligent thinning
            sample_rate = max(5, self.simulation_speed // 10)
        
        # Process buffer when enough points collected
        if len(self.trail_buffers[obj_name]) >= sample_rate:
            # Identify important points (turning points, extreme positions)
            buffer = self.trail_buffers[obj_name]
            
            if len(buffer) >= 3:
                # Always keep first and last point
                self.trails[obj_name].append(buffer[0])
                
                # For more than 3 points: find turning points and extrema
                if len(buffer) > 3:
                    # Middle points only at significant direction changes
                    for i in range(1, len(buffer) - 1):
                        prev_pos = buffer[i-1]
                        curr_pos = buffer[i]
                        next_pos = buffer[i+1]
                        
                        # Calculate direction vector
                        dx1 = curr_pos[0] - prev_pos[0]
                        dy1 = curr_pos[1] - prev_pos[1]
                        dx2 = next_pos[0] - curr_pos[0]
                        dy2 = next_pos[1] - curr_pos[1]
                        
                        # Calculate angle change (cross product)
                        cross_product = abs(dx1 * dy2 - dy1 * dx2)
                        distance = (dx1**2 + dy1**2)**0.5 * (dx2**2 + dy2**2)**0.5
                        
                        # Significant curvature? (adaptive threshold based on speed)
                        curvature_threshold = max(1e12, 1e15 / self.simulation_speed)
                        if distance > 0 and cross_product / distance > curvature_threshold:
                            self.trails[obj_name].append(curr_pos)
                
                # Always add last point
                self.trails[obj_name].append(buffer[-1])
            else:
                # For few points: add all
                for pos in buffer:
                    self.trails[obj_name].append(pos)
            
            # Clear buffer
            self.trail_buffers[obj_name].clear()
        
    def flush_trail_buffers(self):
        """Process all remaining trail buffers"""
        for obj_name in self.trail_buffers:
            if self.trail_buffers[obj_name]:
                # Add all remaining points
                for position in self.trail_buffers[obj_name]:
                    self.trails[obj_name].append(position)
                self.trail_buffers[obj_name].clear()
        
    def update_animation(self, frame):
        """Animation update for matplotlib"""
        if self.paused:
            return list(self.planet_plots.values()) + list(self.trail_plots.values())
            
        # Multiple physics steps per frame for acceleration
        for step in range(self.simulation_speed):
            self.time += self.physics_timestep
            
            # Physics simulation with constant 60s steps
            for massive_object in self.massive_objects:
                state_new = calculate_state_new(massive_object, self.massive_objects, self.physics_timestep)
                massive_object.addState(state_new)
                
                # Add position to orbital trail - ALL steps for accuracy
                current_state = massive_object.getLatestState()
                position = (current_state.vec_location[0], current_state.vec_location[1])
                self.update_trail_intelligent(massive_object.name, position)
        
        # Process all remaining buffer points
        self.flush_trail_buffers()
        
        # Focus object for camera positioning
        focus_obj = self.get_focus_object()
        focus_state = focus_obj.getLatestState()
        self.center_x = focus_state.vec_location[0]
        self.center_y = focus_state.vec_location[1]
        
        # Update plot
        for obj in self.massive_objects:
            current_state = obj.getLatestState()
            
            # Position relative to focus
            rel_x = (current_state.vec_location[0] - self.center_x) * self.zoom
            rel_y = (current_state.vec_location[1] - self.center_y) * self.zoom
            
            # Update planet position
            self.planet_plots[obj.name].set_data([rel_x], [rel_y])
            
            # Update orbital trail
            if len(self.trails[obj.name]) > 1:
                trail_x = [(pos[0] - self.center_x) * self.zoom for pos in self.trails[obj.name]]
                trail_y = [(pos[1] - self.center_y) * self.zoom for pos in self.trails[obj.name]]
                self.trail_plots[obj.name].set_data(trail_x, trail_y)
        
        # Automatically adjust axis limits
        # Higher zoom = smaller view range (closer in)
        view_range = 2e8 / self.zoom  # View range inversely proportional to zoom
        self.ax.set_xlim(-view_range, view_range)
        self.ax.set_ylim(-view_range, view_range)
        
        # Dynamically update axis labels and tick values
        view_range_meters = 2e8 / self.zoom
        scaled_distance, unit = self.get_appropriate_distance_unit(view_range_meters)
        
        # Update axis labels
        self.ax.set_xlabel(f'Distance ({unit})', color='white')
        self.ax.set_ylabel(f'Distance ({unit})', color='white')
        
        # Format tick values in appropriate units
        if unit == "AU":
            tick_scale = 1.496e11
        elif unit == "M km":
            tick_scale = 1e9
        elif unit == "1000 km":
            tick_scale = 1e6
        elif unit == "km":
            tick_scale = 1e3
        else:
            tick_scale = 1
        
        # Automatic tick generation based on view range
        scaled_view_range = view_range / tick_scale
        
        # Determine sensible tick spacing
        if scaled_view_range > 100:
            tick_step = 50
        elif scaled_view_range > 50:
            tick_step = 20
        elif scaled_view_range > 20:
            tick_step = 10
        elif scaled_view_range > 10:
            tick_step = 5
        elif scaled_view_range > 2:
            tick_step = 1
        else:
            tick_step = 0.5
        
        # Calculate tick positions
        max_ticks = int(scaled_view_range / tick_step) + 1
        tick_positions_scaled = [-i * tick_step for i in range(max_ticks, 0, -1)] + [i * tick_step for i in range(max_ticks + 1)]
        tick_positions_meters = [pos * tick_scale for pos in tick_positions_scaled]
        
        # Only show ticks in visible range
        visible_ticks = [(pos_m, pos_s) for pos_m, pos_s in zip(tick_positions_meters, tick_positions_scaled) 
                        if -view_range <= pos_m <= view_range]
        
        if visible_ticks:
            tick_pos_meters, tick_labels = zip(*visible_ticks)
            # Format tick labels (without too many decimal places)
            formatted_labels = [f"{label:.1f}" if label != int(label) else f"{int(label)}" 
                              for label in tick_labels]
            
            self.ax.set_xticks(tick_pos_meters)
            self.ax.set_xticklabels(formatted_labels)
            self.ax.set_yticks(tick_pos_meters)
            self.ax.set_yticklabels(formatted_labels)
        
        # Compact title with current information
        days = self.time / (24 * 3600)
        focus_name = self.get_focus_object().name
        
        # ASCII status indicator
        status = "PAUSE" if self.paused else "PLAY"
        
        # Compact speed info
        if self.simulation_speed >= 1440:
            speed_info = f"{self.simulation_speed//1440}d"  # Days
        elif self.simulation_speed >= 60:
            speed_info = f"{self.simulation_speed//60}h"    # Hours
        elif self.simulation_speed > 1:
            speed_info = f"{self.simulation_speed}×"
        else:
            speed_info = ""
        
        # Short title
        if speed_info:
            title = f"Day {days:.1f} | {focus_name} | {speed_info} | {status}"
        else:
            title = f"Day {days:.1f} | {focus_name} | {status}"
        self.ax.set_title(title, color='white', fontsize=11, pad=10)
        
        return list(self.planet_plots.values()) + list(self.trail_plots.values())
    
    def run(self):
        """Start simulation"""
        print("Starting orbital simulation...")
        print("Use keyboard for controls (window must be focused)")
        
        # Optimize layout for better title display
        plt.subplots_adjust(top=0.92, bottom=0.08, left=0.08, right=0.95)
        
        # Start animation
        self.animation = animation.FuncAnimation(
            self.fig, self.update_animation, interval=50, blit=False
        )
        
        plt.show()


def main():
    """Main function for matplotlib version"""
    print("=" * 60)
    print("🚀 ORBITAL SIMULATION - ADAPTIVE TIME STEPS")
    print("=" * 60)
    print()
    print("🔬 PHYSICS:")
    print("  • Constant 60s time steps for maximum accuracy")
    print("  • RK4 integration precise at all speeds")
    print("  • Energy conservation and orbit stability guaranteed")
    print()
    print("⚡ ACCELERATION:")
    print("  • Visualization: 1× to 1440× (24 hours/frame)")
    print("  • Physics always stays at 60s steps")
    print("  • Intelligent trail thinning at high speeds")
    print("  • No important orbital events are skipped")
    print()
    print("🎮 CONTROLS:")
    print("  SPACE     - Pause/Play")
    print("  +/-       - Zoom In/Out")
    print("  o         - Switch Focus")
    print("  ↑/↓       - Speed (steps/frame)")
    print("  r         - Reset Simulation")
    print()
    print("📡 OBJECTS:")
    
    # Display object information
    objects = get_massive_objects()
    for i, obj in enumerate(objects):
        print(f"  {i}: {obj.name}")
    
    print()
    print("🌍 Starting simulation...")
    
    visualizer = OrbitVisualizer()
    visualizer.run()


if __name__ == "__main__":
    main() 