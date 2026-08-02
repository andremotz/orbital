import math

import numpy as np

# Schiefe der Ekliptik zu J2000: der Winkel zwischen Erdachse und der
# Normalen der Erdbahnebene.
OBLIQUITY_J2000 = math.radians(23.4392911)

# Erdachse in ekliptikalen Koordinaten. Die Simulation rechnet in der
# Ekliptik, die Abplattung liegt aber um die Rotationsachse -- ohne diese
# Drehung säße der Äquatorwulst in der falschen Ebene.
EARTH_POLE_ECLIPTIC = np.array([
    0.0,
    -math.sin(OBLIQUITY_J2000),
    math.cos(OBLIQUITY_J2000),
])

# Zweiter zonaler Koeffizient und Äquatorradius der Erde (WGS 84 / EGM96)
EARTH_J2 = 1.08262668e-3
EARTH_EQUATORIAL_RADIUS = 6.378137e6


class Oblateness:
    """Abplattung eines Körpers, beschrieben über den Koeffizienten J2.

    `pole` ist die Rotationsachse als Einheitsvektor im Bezugssystem der
    Simulation, also in der Ekliptik.
    """

    def __init__(self, j2, equatorial_radius, pole):
        self.j2 = float(j2)
        self.equatorial_radius = float(equatorial_radius)

        pole = np.asarray(pole, dtype=float)
        magnitude = np.linalg.norm(pole)
        if magnitude == 0.0:
            raise ValueError("Polrichtung darf nicht der Nullvektor sein")
        self.pole = pole / magnitude

    @classmethod
    def earth(cls):
        return cls(EARTH_J2, EARTH_EQUATORIAL_RADIUS, EARTH_POLE_ECLIPTIC)

    def __repr__(self):
        return f"<Oblateness J2={self.j2:.6e} Re={self.equatorial_radius:.0f}m>"
