import numpy as np
from data.constants import CONST_GRAVITY, DIMENSIONS


def accelerations(positions, mus):
    """Gravitative Beschleunigung aller Körper in m/s^2.

    `positions` ist ein (n, d)-Array, `mus` ein (n,)-Array der
    Standard-Gravitationsparameter GM; zurück kommt ein (n, d)-Array. Alle
    Körper werden in einem Rutsch ausgewertet, damit die RK4-Zwischenstufen
    einen konsistenten Systemzustand sehen -- eine körperweise Auswertung
    würde die übrigen Körper einfrieren.

    Es geht bewusst GM ein und nicht Masse mal Gravitationskonstante; die
    Begründung steht bei den Konstanten.

    Die Formulierung ist dimensionsfrei; die Simulation führt Zustände
    dreikomponentig, siehe DIMENSIONS.
    """
    # delta[i, j] ist der Vektor von Körper i zu Körper j
    delta = positions[np.newaxis, :, :] - positions[:, np.newaxis, :]
    distance = np.linalg.norm(delta, axis=2)

    # Schließt die Selbstanziehung aus, ohne durch null zu teilen
    np.fill_diagonal(distance, np.inf)

    factor = mus[np.newaxis, :] / distance ** 3
    return np.einsum('ij,ijk->ik', factor, delta)


def oblateness_accelerations(positions, bodies):
    """Zusatzbeschleunigung durch die Abplattung abgeplatteter Körper.

    Ein rotierender Planet ist keine Kugel, sondern am Äquator ausgebaucht.
    Der zweite zonale Koeffizient J2 erfasst den Hauptteil dieser Abweichung.
    Im erdnahen Orbit ist das die mit Abstand stärkste Störung: rund
    0,013 m/s^2 in 330 km Höhe, etwa vierhundertmal mehr als die dortige
    Anziehung des Mondes. Wer sie weglässt, kann eine reale Bahn nicht auf
    Metern pro Sekunde genau nachrechnen.

    Die Ausbuchtung liegt um die Rotationsachse des Körpers, nicht um die
    Normale der Ekliptik -- bei der Erde stehen die beiden 23,44 Grad
    auseinander. Deshalb trägt jeder abgeplattete Körper seine Polrichtung
    mit sich.
    """
    extra = np.zeros_like(positions)

    for index, body in enumerate(bodies):
        oblateness = getattr(body, "oblateness", None)
        if oblateness is None:
            continue

        pole = oblateness.pole
        offsets = positions - positions[index]
        distances = np.linalg.norm(offsets, axis=1)

        # Der Körper selbst und alles im Mittelpunkt bleiben aussen vor
        affected = distances > 0.0
        if not affected.any():
            continue

        scale = -1.5 * oblateness.j2 * body.mu * oblateness.equatorial_radius ** 2

        offsets_affected = offsets[affected]
        distances_affected = distances[affected][:, np.newaxis]

        # Zerlegung in Anteile längs und quer zur Polachse
        along_pole = offsets_affected @ pole
        perpendicular = offsets_affected - np.outer(along_pole, pole)
        ratio_squared = (along_pole[:, np.newaxis] / distances_affected) ** 2

        contribution = (
            (1.0 - 5.0 * ratio_squared) * perpendicular
            + (3.0 - 5.0 * ratio_squared) * np.outer(along_pole, pole)
        )
        extra[affected] += scale / distances_affected ** 5 * contribution

    return extra


def get_acceleration(massiveObject_current, massiveObject_state, list_massiveObject):
    """Gravitative Beschleunigung eines einzelnen Körpers in m/s^2.

    Die übrigen Körper werden mit ihrem jeweils letzten Zustand herangezogen.
    Für die Integration ist `accelerations` vorzuziehen; diese Funktion dient
    Einzelabfragen, etwa zur Anzeige im Cockpit.
    """
    vec_location = massiveObject_state.vec_location
    vec_acceleration = np.zeros(DIMENSIONS)

    for massiveObject_other in list_massiveObject:
        if massiveObject_other is massiveObject_current:
            continue

        vec_distance = massiveObject_other.getLatestState().vec_location - vec_location
        magnitude = np.linalg.norm(vec_distance)
        if magnitude == 0.0:
            continue

        vec_acceleration += massiveObject_other.mu * vec_distance / magnitude ** 3

    return vec_acceleration
