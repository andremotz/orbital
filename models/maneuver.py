import numpy as np

from data.constants import DIMENSIONS


class Maneuver:
    """Klasse repräsentiert ein Manöver eines Objekts.

    `time_start` und `time_duration` sind Sekunden Simulationszeit. Die Stärke
    lässt sich auf zwei Arten angeben, aber nur auf eine je Manöver:

    `force`   -- Schub in Newton. Die Beschleunigung folgt aus F = m*a, hängt
                 also von der Masse ab.
    `delta_v` -- Geschwindigkeitsänderung in m/s über die gesamte Brenndauer.
                 So werden Bahnmanöver üblicherweise beschrieben und auch aus
                 realen Bahnen gewonnen; die Masse spielt dann keine Rolle.

    `direction` ist ein Richtungsvektor, der nicht normiert sein muss; ohne
    Angabe brennt das Triebwerk prograd. `relative_to` benennt den Körper, in
    dessen Bezugssystem "prograd" gemeint ist -- bei einem Erdorbit also
    "Earth". Ohne Angabe gilt das absolute System, was bei Bahnmanövern fast
    nie gewollt ist.
    """

    def __init__(self, time_start=None, time_duration=None, force=None,
                 direction=None, relative_to=None, delta_v=None, trigger=None):
        if (force is None) == (delta_v is None):
            raise ValueError(
                "Genau eines von 'force' und 'delta_v' muss angegeben sein"
            )
        if time_duration is None or time_duration <= 0:
            raise ValueError("'time_duration' muss positiv sein")
        if (time_start is None) == (trigger is None):
            raise ValueError(
                "Genau eines von 'time_start' und 'trigger' muss angegeben sein"
            )

        self.time_start = time_start
        self.time_duration = time_duration
        self.force = force
        self.delta_v = delta_v
        self.direction = _as_vector(direction)
        self.relative_to = relative_to

        # Ohne Auslöser zündet das Manöver zur festen Zeit; mit Auslöser wird
        # der Zündzeitpunkt erst im Lauf bestimmt und hier festgehalten.
        self.trigger = trigger
        self.activated_at = None if trigger is not None else time_start

    @property
    def earliest_time(self):
        """Frühester Zeitpunkt, zu dem das Manöver zünden kann.

        Bei fester Zeit ist das der Zündzeitpunkt selbst, bei einem Auslöser
        die Sperrfrist davor. Erlaubt es, Manöver zu ordnen und einzuplanen,
        ohne den Lauf schon zu kennen.
        """
        if self.time_start is not None:
            return self.time_start
        return getattr(self.trigger, "after", 0.0)

    def is_active(self, time):
        """Läuft das Triebwerk zu diesem Zeitpunkt?"""
        if self.activated_at is None:
            return False
        return self.activated_at <= time < self.activated_at + self.time_duration

    def reset(self):
        """Setzt einen ausgelösten Zündzeitpunkt zurück.

        Nötig, wenn dieselben Manöver in einem zweiten Lauf verwendet werden --
        sonst gälten sie als bereits gezündet.
        """
        if self.trigger is not None:
            self.activated_at = None

    def acceleration_magnitude(self, mass):
        """Betrag der Beschleunigung in m/s^2 während der Brenndauer."""
        if self.delta_v is not None:
            # Gleichmässig über die Brenndauer verteilt
            return self.delta_v / self.time_duration
        return self.force / mass

    def __repr__(self):
        strength = (f"dv={self.delta_v:.1f}m/s" if self.delta_v is not None
                    else f"F={self.force:.0f}N")
        return (f"<Maneuver t={self.time_start:.0f}s "
                f"+{self.time_duration:.0f}s {strength}>")


def _as_vector(direction):
    """Bringt eine Richtungsangabe auf volle Komponentenzahl.

    Zweikomponentige Angaben meinen eine Richtung in der Ekliptik und werden
    mit z = 0 aufgefüllt -- sonst bräche die Addition zur Beschleunigung.
    """
    if direction is None:
        return None

    components = [float(value) for value in direction]
    if len(components) > DIMENSIONS:
        raise ValueError(
            f"Schubrichtung hat {len(components)} Komponenten, erlaubt sind "
            f"hoechstens {DIMENSIONS}"
        )

    components += [0.0] * (DIMENSIONS - len(components))
    return np.array(components)
