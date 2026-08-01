import numpy as np

from models.state import State
from .gravity import accelerations
from .mission import get_mission_acceleration


def step(list_massiveObject, time_step, time=0.0):
    """Integriert alle Körper mit RK4 um einen Zeitschritt weiter.

    Anders als eine körperweise Integration zieht diese Funktion das gesamte
    System gemeinsam durch die vier RK4-Stufen. Nur so sehen die
    Zwischenstufen einen konsistenten Zustand -- würde man Körper
    nacheinander fortschreiben, sähe der zweite Körper den ersten bereits im
    neuen Zeitschritt.

    `time` ist die verstrichene Simulationszeit in Sekunden und entscheidet,
    welche Manöver in diesem Schritt aktiv sind.
    """
    positions = np.array(
        [obj.getLatestState().vec_location for obj in list_massiveObject], dtype=float
    )
    velocities = np.array(
        [obj.getLatestState().vec_velocity for obj in list_massiveObject], dtype=float
    )
    masses = np.array([obj.mass for obj in list_massiveObject], dtype=float)

    # Schub wird einmal für den gesamten Schritt bestimmt: Manöver sind über
    # ihre Dauer konstant, und ein Zeitschritt ist kurz gegen die Brenndauer.
    thrust = np.array(
        [get_mission_acceleration(obj, time, list_massiveObject)
         for obj in list_massiveObject],
        dtype=float,
    )

    def derivatives(pos, vel):
        """Liefert (dx/dt, dv/dt) für den übergebenen Systemzustand."""
        return vel, accelerations(pos, masses) + thrust

    half_step = time_step / 2.0

    k1_location, k1_velocity = derivatives(positions, velocities)
    k2_location, k2_velocity = derivatives(
        positions + k1_location * half_step, velocities + k1_velocity * half_step
    )
    k3_location, k3_velocity = derivatives(
        positions + k2_location * half_step, velocities + k2_velocity * half_step
    )
    k4_location, k4_velocity = derivatives(
        positions + k3_location * time_step, velocities + k3_velocity * time_step
    )

    weight = time_step / 6.0
    positions_new = positions + weight * (
        k1_location + 2.0 * (k2_location + k3_location) + k4_location
    )
    velocities_new = velocities + weight * (
        k1_velocity + 2.0 * (k2_velocity + k3_velocity) + k4_velocity
    )

    for obj, vec_velocity, vec_location in zip(
        list_massiveObject, velocities_new, positions_new
    ):
        obj.addState(State(vec_velocity, vec_location))
