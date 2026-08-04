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


def time_to_periapsis(vec_location, vec_velocity, mu):
    """Sekunden bis zum nächsten Periapsisdurchgang.

    Ein Bahnanhebungsmanöver wirkt fast nur im Periapsis, weil dort die
    Geschwindigkeit am höchsten ist und ein gegebenes Delta-v die meiste
    Energie einbringt. Um dort zünden zu können, muss man wissen, wann es so
    weit ist -- und zwar im Voraus, nicht erst beim Durchgang.

    Der Weg führt über die Kepler-Gleichung: aus dem Zustand folgt die
    exzentrische Anomalie, daraus die mittlere Anomalie und damit die
    verstrichene Zeit seit dem letzten Periapsis.

    Offene Bahnen sind mit erfasst, und das ist kein Beiwerk: eine Sonde, die
    auf einen Mond zufliegt, ist relativ zu ihm hyperbolisch: sie ist ja noch
    nicht eingefangen. Der Bremsschub, der sie einfängt, muss genau im
    Perizentrum dieser Hyperbel liegen. Ohne Vorhersage dafür liesse sich ein
    Einfang gar nicht auslösen. Bei einer offenen Bahn, deren Perizentrum
    schon hinter ihr liegt, kommt None zurück -- dort gibt es keinen nächsten
    Durchgang mehr.
    """
    vec_location = np.asarray(vec_location, dtype=float)
    vec_velocity = np.asarray(vec_velocity, dtype=float)

    elements = elements_from_state(vec_location, vec_velocity, mu)

    if elements.eccentricity >= 1.0:
        return _time_to_periapsis_open(vec_location, vec_velocity, mu, elements)

    distance = float(np.linalg.norm(vec_location))
    semi_major_axis = elements.semi_major_axis
    eccentricity = elements.eccentricity

    if eccentricity == 0.0:
        # Kreisbahn: jeder Punkt ist Periapsis, es gibt keinen ausgezeichneten
        return 0.0

    cosine = (1.0 - distance / semi_major_axis) / eccentricity
    sine = (float(np.dot(vec_location, vec_velocity))
            / (eccentricity * math.sqrt(mu * semi_major_axis)))
    eccentric_anomaly = math.atan2(sine, max(-1.0, min(1.0, cosine)))

    mean_anomaly = eccentric_anomaly - eccentricity * math.sin(eccentric_anomaly)
    mean_anomaly %= 2.0 * math.pi

    mean_motion = math.sqrt(mu / semi_major_axis ** 3)
    return (2.0 * math.pi - mean_anomaly) / mean_motion


def _time_to_periapsis_open(vec_location, vec_velocity, mu, elements):
    """Zeit bis zum Perizentrum auf einer hyperbolischen Bahn.

    Dieselbe Rechnung wie im geschlossenen Fall, nur mit hyperbolischen
    Funktionen: statt der exzentrischen Anomalie tritt die hyperbolische
    Anomalie H, statt der Kepler-Gleichung ihre Entsprechung
    M = e*sinh(H) - H.

    Eine Hyperbel wird nur einmal durchflogen. Liegt das Perizentrum bereits
    hinter dem Fahrzeug -- erkennbar an einer nach aussen gerichteten radialen
    Geschwindigkeit -- kommt None zurück.
    """
    distance = float(np.linalg.norm(vec_location))
    radial_speed = float(np.dot(vec_location, vec_velocity)) / distance
    if radial_speed >= 0.0:
        # Entfernt sich bereits; das Perizentrum ist passiert
        return None

    eccentricity = elements.eccentricity
    semi_major_axis = abs(elements.semi_major_axis)
    if eccentricity <= 1.0 or semi_major_axis == 0.0:
        return None

    cosh_anomaly = (distance / semi_major_axis + 1.0) / eccentricity
    if cosh_anomaly < 1.0:
        # Numerisch knapp am Perizentrum
        return 0.0

    hyperbolic_anomaly = math.acosh(cosh_anomaly)
    mean_anomaly = eccentricity * math.sinh(hyperbolic_anomaly) - hyperbolic_anomaly

    mean_motion = math.sqrt(mu / semi_major_axis ** 3)
    return mean_anomaly / mean_motion
