import numpy as np

from data.constants import DIMENSIONS


def get_mission_acceleration(massive_object, time, all_bodies=None):
    """Beschleunigung durch aktive Manöver in m/s^2.

    `time` ist die verstrichene Simulationszeit in Sekunden -- nicht die
    Schrittweite. Ein Manöver ist aktiv, solange `time` innerhalb von
    [time_start, time_start + time_duration) liegt.

    `all_bodies` wird gebraucht, wenn ein Manöver seine Richtung auf einen
    anderen Körper bezieht; ohne die Liste bleibt nur das absolute
    Bezugssystem.
    """
    vec_acceleration = np.zeros(DIMENSIONS)
    state = massive_object.getLatestState()

    for maneuver in massive_object.list_maneuvers:
        if not maneuver.time_start <= time < maneuver.time_start + maneuver.time_duration:
            continue

        vec_direction = _burn_direction(maneuver, state, all_bodies)
        if vec_direction is None:
            continue

        vec_acceleration += vec_direction * maneuver.acceleration_magnitude(
            massive_object.mass
        )

    return vec_acceleration


def _burn_direction(maneuver, state, all_bodies):
    """Einheitsvektor des Schubs, oder None wenn er unbestimmt ist.

    Ohne explizite Richtung brennt das Triebwerk prograd, also entlang der
    Geschwindigkeit. Entscheidend ist dabei das Bezugssystem: bei einer
    Erdumlaufbahn ist die absolute Geschwindigkeit von der Bahngeschwindigkeit
    der Erde um die Sonne dominiert (rund 29,8 km/s gegenüber einigen km/s im
    Orbit). "Prograd" im absoluten System zeigt deshalb regelmäßig in eine
    ganz andere Richtung als prograd im Orbit -- ein Bahnanhebungsmanöver
    würde so zur Bremsung. `maneuver.relative_to` benennt den Bezugskörper.
    """
    vec_direction = maneuver.direction

    if vec_direction is None:
        vec_direction = state.vec_velocity

        reference = _find_body(all_bodies, maneuver.relative_to)
        if reference is not None:
            vec_direction = vec_direction - reference.getLatestState().vec_velocity

    vec_direction = np.asarray(vec_direction, dtype=float)
    magnitude = np.linalg.norm(vec_direction)
    if magnitude == 0.0:
        return None

    return vec_direction / magnitude


def _find_body(all_bodies, name):
    if not name or not all_bodies:
        return None

    for body in all_bodies:
        if body.name == name:
            return body

    raise ValueError(f"Manöver bezieht sich auf unbekannten Körper {name!r}")
