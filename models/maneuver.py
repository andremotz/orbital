class Maneuver:
    """Klasse repräsentiert ein Manöver eines Objekts.

    `time_start` und `time_duration` sind Sekunden Simulationszeit, `force`
    ist der Schub in Newton. `direction` ist ein Richtungsvektor, der nicht
    normiert sein muss; ohne Angabe brennt das Triebwerk prograd.

    `relative_to` benennt den Körper, in dessen Bezugssystem "prograd"
    gemeint ist -- bei einem Erdorbit also "Earth". Ohne Angabe gilt das
    absolute System, was bei Bahnmanövern fast nie gewollt ist.
    """

    def __init__(self, time_start, time_duration, force, direction=None,
                 relative_to=None):
        self.time_start = time_start
        self.time_duration = time_duration
        self.force = force
        self.direction = direction
        self.relative_to = relative_to
