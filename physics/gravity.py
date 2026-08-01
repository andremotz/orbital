import numpy as np
from data.constants import CONST_GRAVITY


def accelerations(positions, masses):
    """Gravitative Beschleunigung aller Körper in m/s^2.

    `positions` ist ein (n, 2)-Array, `masses` ein (n,)-Array; zurück kommt ein
    (n, 2)-Array. Alle Körper werden in einem Rutsch ausgewertet, damit die
    RK4-Zwischenstufen einen konsistenten Systemzustand sehen -- eine
    körperweise Auswertung würde die übrigen Körper einfrieren.
    """
    # delta[i, j] ist der Vektor von Körper i zu Körper j
    delta = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    distance = np.linalg.norm(delta, axis=2)

    # Schließt die Selbstanziehung aus, ohne durch null zu teilen
    np.fill_diagonal(distance, np.inf)

    factor = CONST_GRAVITY * masses[np.newaxis, :] / distance ** 3
    return np.einsum('ij,ijk->ik', factor, delta)


def get_acceleration(massiveObject_current, massiveObject_state, list_massiveObject):
    """Gravitative Beschleunigung eines einzelnen Körpers in m/s^2.

    Die übrigen Körper werden mit ihrem jeweils letzten Zustand herangezogen.
    Für die Integration ist `accelerations` vorzuziehen; diese Funktion dient
    Einzelabfragen, etwa zur Anzeige im Cockpit.
    """
    vec_location = massiveObject_state.vec_location
    vec_acceleration = np.zeros(2)

    for massiveObject_other in list_massiveObject:
        if massiveObject_other is massiveObject_current:
            continue

        vec_distance = massiveObject_other.getLatestState().vec_location - vec_location
        magnitude = np.linalg.norm(vec_distance)
        if magnitude == 0.0:
            continue

        vec_acceleration += CONST_GRAVITY * massiveObject_other.mass * vec_distance / magnitude ** 3

    return vec_acceleration
