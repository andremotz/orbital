import math
import numpy as np

def calc_days_from_time(time):
    """Konvertiert Zeit in Sekunden zu Tagen"""
    time_in_days = time / 86400
    time_in_days = round(time_in_days, 1)
    return time_in_days

def get_polar_coordinates(massiveObject1, massiveObject2):
    """Berechnet Polarkoordinaten zwischen zwei Objekten"""
    state_mo1_current = massiveObject1.getLatestState()
    state_mo2_current = massiveObject2.getLatestState()

    vec_mo1_location = state_mo1_current.vec_location
    vec_mo2_location = state_mo2_current.vec_location

    vec_distance = vec_mo2_location - vec_mo1_location
    magnitude = np.linalg.norm(vec_distance)
    distance_km = round(magnitude / 10**9, 0)

    x_mo1 = state_mo1_current.vec_location[0]
    x_mo2 = state_mo2_current.vec_location[0]

    x_distance = x_mo2 - x_mo1

    angle = round(math.acos(x_distance / magnitude), 2)
    print("r: %s mio km, φ: %s" % (distance_km, angle)) 