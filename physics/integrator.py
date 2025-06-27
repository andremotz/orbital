from models.state import State
from models.derivative import Derivative
from .gravity import get_acceleration
from .mission import get_acceleration_by_mission

def calculate_state_new(massiveObject_current, list_massiveObject, time_step):
    """Berechnet den neuen Zustand eines Objekts mit RK4-Integration"""
    state_mo1_current = massiveObject_current.getLatestState()
    vec_mo1_velocity_current = state_mo1_current.vec_velocity
    vec_mo1_location_current = state_mo1_current.vec_location

    a = initial_derivative(massiveObject_current, list_massiveObject, time_step)
    b = next_derivative(massiveObject_current, list_massiveObject, a, time_step)
    c = next_derivative(massiveObject_current, list_massiveObject, b, time_step)
    d = next_derivative(massiveObject_current, list_massiveObject, c, time_step)

    vec_mo1_acceleration_new = 1/6 * (a.vec_acceleration
                                    + 2.0 *(b.vec_acceleration + c.vec_acceleration)
                                    + d.vec_acceleration)

    vec_mo1_acceleration_new += get_acceleration_by_mission(massiveObject_current, time_step)

    vec_mo1_velocity_new = vec_mo1_velocity_current + vec_mo1_acceleration_new

    vec_mo1_location_new = vec_mo1_location_current + vec_mo1_velocity_new * time_step

    state_mo1_new = State(vec_mo1_velocity_new, vec_mo1_location_new)
    return state_mo1_new

def initial_derivative(massiveObject_current, list_massiveObject, time_step):
    """Berechnet die initiale Ableitung für RK4"""
    state_mo1_current = massiveObject_current.getLatestState()
    vec_mo1_velocity = state_mo1_current.vec_velocity
    vec_mo1_acceleration = get_acceleration(massiveObject_current, state_mo1_current, list_massiveObject, time_step)

    return Derivative(vec_mo1_acceleration, vec_mo1_velocity)

def next_derivative(massiveObject_current, list_massiveObject, derivative, time_step):
    """Berechnet die nächste Ableitung für RK4"""
    state_mo1_current = massiveObject_current.getLatestState()

    vec_location_new = state_mo1_current.vec_location + derivative.vec_velocity + time_step
    vec_velocity_new = state_mo1_current.vec_velocity + derivative.vec_acceleration + time_step
    state_mo1_new = State(vec_velocity_new, vec_location_new)

    vec_mo1_acceleration = get_acceleration(massiveObject_current, state_mo1_new, list_massiveObject, time_step)

    return Derivative(vec_mo1_acceleration, state_mo1_new.vec_velocity) 