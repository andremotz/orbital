import numpy as np
import pygame
from collections import defaultdict
import math


CONST_GRAVITY = 6.6743 * 10 ** -11
# The window size
WIDTH, HEIGHT = 900, 900
WIDTHD2, HEIGHTD2 = WIDTH/2., HEIGHT/2.


class MassiveObject:

    def __init__(self, state_new, mass, radius, color, name, is_heavy, list_maneuvers):
        self.mass = mass
        self.listStates = []
        self.addState(state_new)
        self.radius = radius
        self.color = color
        self.name = name
        self.is_heavy = is_heavy
        self.list_maneuvers = list_maneuvers

    def addState(self, state_new):
        self.listStates.append(state_new)

    def getLatestState(self):
        currentCount = len(self.listStates)
        return self.listStates[currentCount - 1]


# Klasse repräsentiert einen Zustand eines Körpers
class State:
    def __init__(self, vec_velocity, vec_location):
        self.vec_velocity = vec_velocity
        self.vec_location = vec_location


# Klasse repräsentiert eine Ableitung eines States
class Derivative:
    def __init__(self, vec_acceleration, vec_velocity):
        self.vec_acceleration = vec_acceleration
        self.vec_velocity = vec_velocity


# Klasse repräsentiert ein Manöver eines Objekts
class Maneuver:
    def __init__(self, time_start, time_duration, force):
        self.time_start = time_start
        self.time_duration = time_duration
        self.force = force


def calculate_state_new(massiveObject_current, list_massiveObject, time_step):
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

    #vec_mo1_acceleration_new = a.vec_acceleration

    vec_mo1_velocity_new = vec_mo1_velocity_current + vec_mo1_acceleration_new
    #vec_mo1_velocity_new = 1/6 * (a.vec_velocity
    #                              + 2.0 * (b.vec_velocity + c.vec_velocity)
    #                              + d.vec_velocity) + vec_mo1_acceleration_new

    vec_mo1_location_new = vec_mo1_location_current + vec_mo1_velocity_new * time_step

    state_mo1_new = State(vec_mo1_velocity_new,
                                    vec_mo1_location_new)
    return state_mo1_new


# Füge Beschleunigung durch Missionsdaten hinzu
def get_acceleration_by_mission(massive_object, time_step):
    force_extra = 0.0

    list_maneuvers = massive_object.list_maneuvers

    if massive_object.name == "Chandrayaan-2":
        test = 1

    if len(list_maneuvers) > 0:
        test = 1

        for maneuver in list_maneuvers:
            if time_step > maneuver.time_start and time_step < maneuver.time_duration:
                force_extra += maneuver.force
                print("adding extra force: %s", force_extra)

    return force_extra


def initial_derivative(massiveObject_current, list_massiveObject, time_step):
    state_mo1_current = massiveObject_current.getLatestState()
    vec_mo1_velocity = state_mo1_current.vec_velocity
    vec_mo1_acceleration = get_acceleration(massiveObject_current, state_mo1_current, list_massiveObject, time_step)

    return Derivative(vec_mo1_acceleration, vec_mo1_velocity)


def next_derivative(massiveObject_current, list_massiveObject, derivative, time_step):
    state_mo1_current = massiveObject_current.getLatestState()

    vec_location_new = state_mo1_current.vec_location + derivative.vec_velocity + time_step
    vec_velocity_new = state_mo1_current.vec_velocity + derivative.vec_acceleration + time_step
    state_mo1_new = State(vec_velocity_new, vec_location_new)

    # * 1.65
    vec_mo1_acceleration = get_acceleration(massiveObject_current, state_mo1_new, list_massiveObject, time_step )

    return Derivative(vec_mo1_acceleration, state_mo1_new.vec_velocity)


def get_acceleration(massiveObject_current, massiveObject_state, list_massiveObject, time_step):
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

            #if (massiveObject_current.name == "Sun" and massiveObject_other.name == "Earth"):
            #    get_polar_coordinates(massiveObject_current, massiveObject_other)

    return vec_mo1_acceleration_final


def get_gravity(mass1, mass2, distance):
    return CONST_GRAVITY * mass1 * mass2 / distance**3


def pygame_draw(listMassiveObjects, surface, zoom, scroll_x, scroll_y, time):
    currentMassiveObject_id = 0

    for currentMassiveObject in listMassiveObjects:
        if currentMassiveObject.name == "Earth":
            state_latest = currentMassiveObject.getLatestState()
            x = state_latest.vec_location[0]
            y = state_latest.vec_location[1]

            x_converted = WIDTHD2 + zoom * WIDTHD2 * (x - WIDTHD2) / WIDTHD2
            y_converted = HEIGHTD2 + zoom * HEIGHTD2 * (y - HEIGHTD2) / HEIGHTD2

            scroll_x = - (x_converted - WIDTHD2)
            scroll_y = - (y_converted - HEIGHTD2)

    for currentMassiveObject in listMassiveObjects: # loop through list of Objects

        state_latest = currentMassiveObject.getLatestState()
        x = state_latest.vec_location[0]
        y = state_latest.vec_location[1]


        x_converted = scroll_x + WIDTHD2 + zoom * WIDTHD2 * (x-WIDTHD2) / WIDTHD2
        y_converted = scroll_y + HEIGHTD2 + zoom * HEIGHTD2 * (y-HEIGHTD2) / HEIGHTD2


        radius_converted = currentMassiveObject.radius * zoom

        color = currentMassiveObject.color

        pygame.draw.circle(surface, color,
                           (int(x_converted),
                            int(y_converted)),
                           int(radius_converted), 0)

        currentMassiveObject_id += 1

    pygame.display.flip()
    pygame.display.set_caption("days: %s, zoom: %s, time %s" %
                               (calc_days_from_time(time),
                                round(zoom, 20),
                                time)
                               )


def calc_days_from_time(time):
    time_in_days = time / 86400
    time_in_days = round(time_in_days, 1)
    return time_in_days


def main():
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

    time = 0
    time_step = 60

    while running:

        time += time_step

        for massiveObject_1 in list_massiveobjects:
            state_new = calculate_state_new(massiveObject_1, list_massiveobjects, time_step)
            massiveObject_1.addState(state_new)

        # event handling, gets all event from the event queue
        for event in pygame.event.get():
            # only do something if the event is of type QUIT
            if event.type == pygame.QUIT:
                # change the value to False, to exit the main loop
                running = False
            elif event.type in [pygame.KEYDOWN, pygame.KEYUP]:
                keysPressed[event.key] = event.type == pygame.KEYDOWN

            # update zoom factor (numeric keypad +/- keys)
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

        pygame_draw(list_massiveobjects, screen, zoom, scroll_x, scroll_y, time)


def get_polar_coordinates(massiveObject1, massiveObject2):
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

    angle = round(math.acos(x_distance / magnitude),2)
    print("r: %s mio km, φ: %s" % (distance_km, angle))


def get_massive_objects():
    # es werde Licht
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
    #vec_earth_velocity = np.array([0, 0])
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


if __name__ == "__main__":
    main()
