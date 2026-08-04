import math

import numpy as np

from data.constants import DIMENSIONS


class Maneuver:
    """Klasse repräsentiert ein Manöver eines Objekts.

    `time_start` und `time_duration` sind Sekunden Simulationszeit. Die Stärke
    lässt sich auf drei Arten angeben, aber nur auf eine je Manöver:

    `force`           -- Schub in Newton. Die Beschleunigung folgt aus F = m*a,
                         hängt also von der Masse ab.
    `delta_v`         -- Geschwindigkeitsänderung in m/s über die Brenndauer.
                         So werden Bahnmanöver üblicherweise beschrieben und
                         auch aus realen Bahnen gewonnen.
    `target_apoapsis` -- Radius der Gegenapside, den die Bahn nach dem Manöver
                         haben soll. Das nötige Delta-v wird erst beim Zünden
                         aus dem tatsächlichen Zustand bestimmt.

    Die dritte Form ist die einzige, die sich selbst korrigiert. Ein
    aufgezeichnetes Delta-v tut auf einer bereits abgewichenen Bahn etwas
    anderes als auf der, wo es gemessen wurde: liegt die Bahn zu tief, bleibt
    auch das Ergebnis zu tief, und der Fehler wächst mit jedem weiteren
    Manöver. Ein Ziel dagegen wird angeflogen, egal wo man startet.

    `direction` ist ein Richtungsvektor, der nicht normiert sein muss; ohne
    Angabe brennt das Triebwerk prograd. Das ist der Regelfall und meist
    besser als eine feste Richtung: über eine halbe Stunde am Perigäum dreht
    sich die Geschwindigkeit erheblich, und ein starr gehaltener Schub
    verschenkt dabei den Kosinusanteil. `relative_to` benennt den Körper, in
    dessen Bezugssystem "prograd" gemeint ist -- bei einem Erdorbit also
    "Earth". Ohne Angabe gilt das absolute System, was bei Bahnmanövern fast
    nie gewollt ist.
    """

    def __init__(self, time_start=None, time_duration=None, force=None,
                 direction=None, relative_to=None, delta_v=None, trigger=None,
                 target_apoapsis=None, target_reference=None):
        given = [value is not None for value in (force, delta_v, target_apoapsis)]
        if sum(given) != 1:
            raise ValueError(
                "Genau eines von 'force', 'delta_v' und 'target_apoapsis' "
                "muss angegeben sein"
            )
        if time_duration is None or time_duration <= 0:
            raise ValueError("'time_duration' muss positiv sein")
        if target_apoapsis is not None and target_apoapsis <= 0:
            raise ValueError("'target_apoapsis' muss ein positiver Radius sein")
        if (time_start is None) == (trigger is None):
            raise ValueError(
                "Genau eines von 'time_start' und 'trigger' muss angegeben sein"
            )

        self.time_start = time_start
        self.time_duration = time_duration
        self.force = force
        self.delta_v = delta_v
        self.target_apoapsis = target_apoapsis
        # Körper, auf den sich das Ziel bezieht; ohne Angabe derselbe, in
        # dessen System auch die Schubrichtung gemeint ist
        self.target_reference = target_reference or relative_to
        self.direction = _as_vector(direction)
        self.relative_to = relative_to

        # Ohne Auslöser zündet das Manöver zur festen Zeit; mit Auslöser wird
        # der Zündzeitpunkt erst im Lauf bestimmt und hier festgehalten.
        self.trigger = trigger
        self.activated_at = None if trigger is not None else time_start

        # Bei einem Zielmanöver erst zur Zündzeit bekannt, dann festgehalten
        self.resolved_delta_v = None

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
        """Setzt Zündzeitpunkt und aufgelöstes Delta-v zurück.

        Nötig, wenn dieselben Manöver in einem zweiten Lauf verwendet werden --
        sonst gälten sie als bereits gezündet und behielten das Delta-v des
        vorigen Laufs. Genau das braucht eine Zielsuche, die dasselbe Szenario
        hundertfach durchrechnet.
        """
        if self.trigger is not None:
            self.activated_at = None
        self.resolved_delta_v = None
        if hasattr(self.trigger, "reset"):
            self.trigger.reset()

    def resolve(self, vec_location, vec_velocity, mu, at_periapsis=False):
        """Bestimmt das Delta-v für ein Zielmanöver und hält es fest.

        Ort und Geschwindigkeit sind relativ zum Bezugskörper anzugeben, `mu`
        ist dessen Gravitationsparameter. Aufgelöst wird über den Vis-Viva-Satz:
        aus dem Radius und der gewünschten Gegenapside folgt die grosse
        Halbachse der Zielbahn und daraus die nötige Geschwindigkeit.

        `at_periapsis` rechnet nicht mit dem übergebenen Radius, sondern mit
        dem Periapsis der aktuellen Bahn. Das ist bei einem Manöver nötig, das
        um das Periapsis herum brennt: gezündet wird eine halbe Brenndauer
        davor, also weiter draussen, und dort verlangt Vis-Viva mehr Delta-v
        für dasselbe Ziel. Wirken tut der Schub aber überwiegend im Periapsis,
        wo er mehr ausrichtet -- ohne diese Korrektur schiesst das Manöver
        systematisch über, bei Chandrayaan-2 um vier bis achtzehn Prozent.

        Das Ergebnis ist vorzeichenbehaftet. Ein Bremsmanöver -- etwa der
        Einschuss in eine Mondumlaufbahn -- liefert einen negativen Wert und
        dreht damit die Schubrichtung von selbst um.
        """
        if self.target_apoapsis is None:
            return self.resolved_delta_v

        distance = float(np.linalg.norm(vec_location))
        speed = float(np.linalg.norm(vec_velocity))
        if distance <= 0.0:
            raise ValueError("Ort relativ zum Bezugskörper darf nicht null sein")

        if at_periapsis:
            # Auf das Periapsis der aktuellen Bahn zurückrechnen. Über die
            # Bahnelemente, weil die auch offene Bahnen abdecken -- der
            # Einfang an einem Mond ist genau dieser Fall.
            from physics.elements import elements_from_state

            current = elements_from_state(vec_location, vec_velocity, mu)
            distance = current.periapsis
            speed = math.sqrt(mu * (2.0 / distance
                                    - 1.0 / current.semi_major_axis))

        semi_major_axis = (distance + self.target_apoapsis) / 2.0
        required_squared = mu * (2.0 / distance - 1.0 / semi_major_axis)
        if required_squared <= 0.0:
            raise ValueError(
                f"Zielapoapsis {self.target_apoapsis:.3e} m ist von "
                f"r = {distance:.3e} m aus nicht erreichbar"
            )

        self.resolved_delta_v = math.sqrt(required_squared) - speed
        return self.resolved_delta_v

    def acceleration_magnitude(self, mass):
        """Beschleunigung in m/s^2 während der Brenndauer, vorzeichenbehaftet.

        Ein negativer Wert bedeutet Bremsen; die Richtung dreht sich dadurch
        beim Aufaddieren von selbst um.
        """
        if self.target_apoapsis is not None:
            if self.resolved_delta_v is None:
                # Noch nicht gezündet -- ohne Zustand gibt es kein Delta-v
                return 0.0
            return self.resolved_delta_v / self.time_duration

        if self.delta_v is not None:
            # Gleichmässig über die Brenndauer verteilt
            return self.delta_v / self.time_duration

        return self.force / mass

    def __repr__(self):
        if self.target_apoapsis is not None:
            strength = f"-> ra={self.target_apoapsis / 1e3:.0f}km"
        elif self.delta_v is not None:
            strength = f"dv={self.delta_v:.1f}m/s"
        else:
            strength = f"F={self.force:.0f}N"
        when = (f"t={self.time_start:.0f}s" if self.time_start is not None
                else f"@{self.trigger.describe()}")
        return f"<Maneuver {when} +{self.time_duration:.0f}s {strength}>"


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
