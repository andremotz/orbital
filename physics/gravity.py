import numpy as np
from data.constants import CONST_GRAVITY

def get_gravity(mass1, mass2, distance):
    """Berechnet die Gravitationskraft zwischen zwei Objekten"""
    return CONST_GRAVITY * mass1 * mass2 / distance**3

def get_acceleration(massiveObject_current, massiveObject_state, list_massiveObject, time_step):
    """Berechnet die Beschleunigung eines Objekts durch Gravitationskräfte"""
    vec_mo_current_location = massiveObject_state.vec_location

    vec_mo1_acceleration_final = np.array([0., 0.])

    for massiveObject_other in list_massiveObject:
        if massiveObject_current == massiveObject_other:
            continue
        else:
            mo_other_state = massiveObject_other.getLatestState()
            mo_other_vec_location = mo_other_state.vec_location

            vec_distance = mo_other_vec_location - vec_mo_current_location
            magnitude = np.linalg.norm(vec_distance)

            # force between objects
            vec_force = vec_distance * get_gravity(massiveObject_current.mass,
                                                   massiveObject_other.mass,
                                                   magnitude)

            vec_mo1_acceleration_current = time_step * vec_force / massiveObject_current.mass
            vec_mo1_acceleration_final += vec_mo1_acceleration_current

    return vec_mo1_acceleration_final 