"""Bahnelemente aus einem Zustandsvektor.

Ein Vergleich zweier Bahnen über den blossen Abstand der Positionen ist
irreführend: schon eine winzige Abweichung der Energie ändert die
Umlaufzeit, und nach einigen Umläufen laufen zwei ansonsten gleiche Bahnen
gegenphasig. Der Positionsabstand springt dann zwischen null und dem
doppelten Bahndurchmesser, ohne dass die Bahn selbst falsch wäre.

Grosse Halbachse, Exzentrizität und Neigung beschreiben dagegen die Bahn
unabhängig davon, wo auf ihr sich der Körper gerade befindet.
"""

import math

import numpy as np


class OrbitalElements:
    """Die klassischen Bahnelemente einer Keplerbahn."""

    def __init__(self, semi_major_axis, eccentricity, inclination,
                 periapsis, apoapsis, period):
        self.semi_major_axis = semi_major_axis
        self.eccentricity = eccentricity
        self.inclination = inclination
        self.periapsis = periapsis
        self.apoapsis = apoapsis
        self.period = period

    def __repr__(self):
        return (f"<a={self.semi_major_axis/1e3:.0f}km e={self.eccentricity:.4f} "
                f"i={math.degrees(self.inclination):.2f}deg>")


def elements_from_state(vec_location, vec_velocity, mu):
    """Bahnelemente aus Ort und Geschwindigkeit relativ zum Zentralkörper.

    `mu` ist der Gravitationsparameter GM des Zentralkörpers. Bei einer
    hyperbolischen Bahn ist die grosse Halbachse negativ und Apoapsis wie
    Umlaufzeit sind nicht definiert; beide werden dann als unendlich
    zurückgegeben.
    """
    vec_location = np.asarray(vec_location, dtype=float)
    vec_velocity = np.asarray(vec_velocity, dtype=float)

    distance = float(np.linalg.norm(vec_location))
    speed = float(np.linalg.norm(vec_velocity))
    if distance == 0.0:
        raise ValueError("Ort darf nicht der Nullvektor sein")

    # Spezifischer Drehimpuls: steht senkrecht auf der Bahnebene
    angular_momentum = np.cross(vec_location, vec_velocity)
    angular_momentum_magnitude = float(np.linalg.norm(angular_momentum))

    # Vis-Viva nach der grossen Halbachse aufgelöst
    specific_energy = speed ** 2 / 2.0 - mu / distance
    if specific_energy == 0.0:
        semi_major_axis = math.inf
    else:
        semi_major_axis = -mu / (2.0 * specific_energy)

    # Laplace-Runge-Lenz-Vektor zeigt zur Periapsis, sein Betrag ist e
    eccentricity_vector = (
        np.cross(vec_velocity, angular_momentum) / mu - vec_location / distance
    )
    eccentricity = float(np.linalg.norm(eccentricity_vector))

    if angular_momentum_magnitude == 0.0:
        inclination = 0.0
    else:
        inclination = math.acos(
            max(-1.0, min(1.0, angular_momentum[2] / angular_momentum_magnitude))
        )

    if eccentricity < 1.0 and semi_major_axis > 0.0:
        periapsis = semi_major_axis * (1.0 - eccentricity)
        apoapsis = semi_major_axis * (1.0 + eccentricity)
        period = 2.0 * math.pi * math.sqrt(semi_major_axis ** 3 / mu)
    else:
        periapsis = abs(semi_major_axis) * (eccentricity - 1.0)
        apoapsis = math.inf
        period = math.inf

    return OrbitalElements(semi_major_axis, eccentricity, inclination,
                           periapsis, apoapsis, period)
