import numpy as np
from models.state import State
from models.massive_object import MassiveObject
from models.maneuver import Maneuver

def get_massive_objects():
    """Erstellt und gibt eine Liste aller Himmelskörper zurück"""
    list_massiveobjects = []

    # __Sun
    mass_sun = 1.989 * 10 ** 30  # https://de.wikipedia.org/wiki/Sonnenmasse
    radius_sun = 6.96342 * 10 ** 8  # https://de.wikipedia.org/wiki/Sonnenradius
    vec_sun_location = np.array([0., 0.])
    vec_sun_velocity = np.array([0., 0.])
    state_sun_current = State(vec_sun_velocity, vec_sun_location)
    is_heavy = True
    list_maneuver_sun = []
    list_massiveobjects.append(MassiveObject(
        state_sun_current, mass_sun, radius_sun, (255, 255, 0), "Sun", is_heavy, list_maneuver_sun
    ))

    # __Earth
    mass_earth = 5.9722 * 10 ** 24  # https://de.wikipedia.org/wiki/Erdmasse
    radius_earth = 6371000  # 6371 km
    vec_earth_velocity = np.array([29780, 0])  # 29.78 km/s = 29.780 m/s
    # 150 mio km - https://www.universetoday.com/14437/how-far-is-earth-from-the-sun/
    vec_earth_location = np.array([0, 15 * 10 ** 10])
    state_earth_current = State(vec_earth_velocity, vec_earth_location)
    is_heavy = True
    list_maneuver_earth = []
    list_massiveobjects.append(MassiveObject(
        state_earth_current, mass_earth, radius_earth, (0, 255, 255), "Earth", is_heavy, list_maneuver_earth
    ))

    # __Moon
    # 356671 km ...https://www.timeanddate.de/astronomie/mond/entfernung
    mass_moon = 7.349 * 10 ** 22  # https://de.wikipedia.org/wiki/Mond
    radius_moon = 1737000  # https://frag-doch-mich.de/natur-umwelt/mond-mondumfang-mondradius/
    vec_moon_velocity = np.array(
        [1020., 0.]) + vec_earth_velocity  # .https://www.astronews.com/frag/antworten/1/frage1480.html
    vec_moon_location = np.array([0., 356671000.]) + vec_earth_location
    state_moon_current = State(vec_moon_velocity, vec_moon_location)
    is_heavy = True
    list_maneuver_moon = []
    list_massiveobjects.append(MassiveObject(
        state_moon_current, mass_moon, radius_moon, (255, 255, 255), "Moon", is_heavy, list_maneuver_moon
    ))

    # __ Chandrayaan-2
    mass_chandrayaan = 100 # todo proof
    radius_chandrayaan = 10
    vec_chandrayaan_velocity = np.array( # todo proof
        [2220., 0.]) + vec_earth_velocity
    vec_chandrayaan_location = np.array([0., 45475000.]) + vec_earth_location
    state_chandrayaan_current = State(vec_chandrayaan_velocity, vec_chandrayaan_location)
    is_heavy = False

    list_maneuvers_chandrayaan = []
    maneuver_chandrayan = Maneuver(60*10, 1000, 10)
    list_maneuvers_chandrayaan.append(maneuver_chandrayan)

    list_massiveobjects.append(MassiveObject(
        state_chandrayaan_current,
        mass_chandrayaan,
        radius_chandrayaan,
        (255, 255, 0),
        "Chandrayaan-2",
        is_heavy,
        list_maneuvers_chandrayaan
    ))

    return list_massiveobjects 