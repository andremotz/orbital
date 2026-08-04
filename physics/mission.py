import numpy as np

from data.constants import DIMENSIONS
from .elements import time_to_periapsis


class TriggerContext:
    """Was ein Auslöser über den aktuellen Zustand wissen muss."""

    def __init__(self, body, time, duration, all_bodies):
        self.body = body
        self.time = time
        self.duration = duration
        self.all_bodies = all_bodies

    def time_to_periapsis(self, reference_name):
        """Sekunden bis zum nächsten Periapsis um `reference_name`."""
        reference = _find_body(self.all_bodies, reference_name)
        if reference is None:
            return None

        state = self.body.getLatestState()
        reference_state = reference.getLatestState()
        return time_to_periapsis(
            state.vec_location - reference_state.vec_location,
            state.vec_velocity - reference_state.vec_velocity,
            reference.mu,
        )


def update_schedule(all_bodies, time):
    """Prüft für jedes noch nicht gezündete Manöver, ob es jetzt beginnt.

    Muss vor der Kraftberechnung eines Schritts laufen, damit ein in diesem
    Schritt ausgelöstes Manöver auch wirkt. `mission_accelerations` erledigt
    das; wer den Schub selbst zusammenstellt, muss es selbst aufrufen.
    """
    for body in all_bodies:
        for maneuver in body.list_maneuvers:
            if maneuver.activated_at is not None:
                continue

            if maneuver.trigger is not None:
                context = TriggerContext(body, time, maneuver.time_duration,
                                         all_bodies)
                if not maneuver.trigger.should_activate(context):
                    continue

            maneuver.activated_at = time
            _resolve_target(maneuver, body, all_bodies)


def _resolve_target(maneuver, body, all_bodies):
    """Legt das Delta-v eines Zielmanövers beim Zünden ein für alle Mal fest.

    Bewusst nur einmal und nicht in jedem Schritt: würde das Delta-v laufend
    neu bestimmt, verfolgte der Burn sein eigenes Ziel, das er gerade
    verschiebt -- er hörte nie auf, sich selbst nachzuregeln.
    """
    if maneuver.target_apoapsis is None:
        return

    reference = _find_body(all_bodies, maneuver.target_reference)
    if reference is None:
        raise ValueError(
            f"Zielmanöver braucht einen Bezugskörper; "
            f"'target_reference' ist {maneuver.target_reference!r}"
        )

    # Brennt das Manöver um das Periapsis herum, muss dort gerechnet werden --
    # nicht am Zündpunkt, der eine halbe Brenndauer weiter draussen liegt.
    trigger = maneuver.trigger
    at_periapsis = (getattr(trigger, "reference", None) == maneuver.target_reference
                    and trigger is not None
                    and hasattr(trigger, "reference"))

    state = body.getLatestState()
    reference_state = reference.getLatestState()
    maneuver.resolve(
        state.vec_location - reference_state.vec_location,
        state.vec_velocity - reference_state.vec_velocity,
        reference.mu,
        at_periapsis=at_periapsis,
    )


def mission_accelerations(all_bodies, time):
    """Schub aller Körper als (n, d)-Array, nach Aktualisierung der Auslöser."""
    update_schedule(all_bodies, time)
    return np.array(
        [get_mission_acceleration(body, time, all_bodies) for body in all_bodies],
        dtype=float,
    )


def get_mission_acceleration(massive_object, time, all_bodies=None):
    """Beschleunigung durch aktive Manöver in m/s^2.

    `time` ist die verstrichene Simulationszeit in Sekunden -- nicht die
    Schrittweite. Ein Manöver ist aktiv, solange `time` innerhalb von
    [Zündzeitpunkt, Zündzeitpunkt + time_duration) liegt.

    `all_bodies` wird gebraucht, wenn ein Manöver seine Richtung auf einen
    anderen Körper bezieht; ohne die Liste bleibt nur das absolute
    Bezugssystem.
    """
    vec_acceleration = np.zeros(DIMENSIONS)
    state = massive_object.getLatestState()

    for maneuver in massive_object.list_maneuvers:
        if not maneuver.is_active(time):
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
    Orbit). "Prograd" im absoluten System zeigt deshalb regelmässig in eine
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
