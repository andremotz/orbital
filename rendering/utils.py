import math
import numpy as np

def calc_days_from_time(time):
    """Konvertiert Zeit in Sekunden zu Tagen"""
    time_in_days = time / 86400
    time_in_days = round(time_in_days, 1)
    return time_in_days


def project_to_ecliptic(vec_location):
    """Projiziert einen Zustandsvektor auf die Darstellungsebene.

    Die Simulation rechnet dreidimensional, die Darstellung ist flach. Alle
    Ansichten blicken senkrecht auf die Ekliptik, es fällt also die
    z-Komponente weg. `out_of_plane_distance` macht das Verworfene sichtbar.
    """
    return vec_location[0], vec_location[1]


def out_of_plane_distance(massiveObject, reference=None):
    """Abstand aus der Ekliptik heraus, in Metern.

    Ohne `reference` gilt der Abstand zur Ekliptik selbst, sonst der zur
    Ebene durch den Bezugskörper.
    """
    z = massiveObject.getLatestState().vec_location[2]
    if reference is not None:
        z -= reference.getLatestState().vec_location[2]
    return float(z)


def get_polar_coordinates(massiveObject1, massiveObject2):
    """Kugelkoordinaten von Objekt 2 aus Sicht von Objekt 1.

    Liefert Abstand, Azimut in der Ekliptik und Elevation darüber. Die
    Elevation ist die Grösse, die eine zweidimensionale Rechnung gar nicht
    darstellen könnte.
    """
    vec_distance = (massiveObject2.getLatestState().vec_location
                    - massiveObject1.getLatestState().vec_location)
    magnitude = float(np.linalg.norm(vec_distance))
    if magnitude == 0.0:
        return 0.0, 0.0, 0.0

    azimuth = math.atan2(vec_distance[1], vec_distance[0])
    elevation = math.asin(vec_distance[2] / magnitude)
    return magnitude, azimuth, elevation