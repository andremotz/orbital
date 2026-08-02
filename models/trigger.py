"""Auslöser, die bestimmen, wann ein Manöver zündet.

Ein Manöver zu fester Absolutzeit zu zünden ist die einfachste, aber
schlechteste Wahl. Eine Bahnanhebung wirkt fast ausschliesslich im Periapsis,
wo die Geschwindigkeit am höchsten ist: dasselbe Delta-v bringt dort ein
Vielfaches der Energie ein wie sonstwo auf der Bahn. Driftet die Bahn auch nur
leicht, trifft ein Manöver nach der Uhr das Periapsis nicht mehr, und die
Anhebung bleibt aus -- genau daran scheiterte der offene Nachflug der
Chandrayaan-2-Mission.

Echte Missionen zünden an Bahnereignissen und korrigieren laufend nach. Diese
Auslöser bilden den ersten Teil davon ab.
"""


class Trigger:
    """Gemeinsame Schnittstelle aller Auslöser."""

    def should_activate(self, context):
        """True, wenn das Manöver in diesem Schritt beginnen soll."""
        raise NotImplementedError

    def describe(self):
        raise NotImplementedError


class TimeTrigger(Trigger):
    """Zündet zu einer festen Zeit seit Simulationsbeginn."""

    def __init__(self, time_start):
        self.time_start = float(time_start)

    def should_activate(self, context):
        return context.time >= self.time_start

    def describe(self):
        return f"t = {self.time_start:.0f}s"


class PeriapsisTrigger(Trigger):
    """Zündet so, dass der Brennschluss um das Periapsis herum liegt.

    `after` verhindert, dass gleich der erste Durchgang genommen wird -- die
    Manöver einer Bahnanhebungskampagne folgen typischerweise im Abstand
    mehrerer Umläufe. `reference` benennt den Körper, um den die Bahn
    betrachtet wird.

    Gezündet wird eine halbe Brenndauer vor dem Durchgang, sodass der Schub
    symmetrisch um das Periapsis liegt. So wird ein realer Burn geflogen.
    """

    def __init__(self, reference, after=0.0):
        self.reference = reference
        self.after = float(after)

    def should_activate(self, context):
        if context.time < self.after:
            return False

        remaining = context.time_to_periapsis(self.reference)
        if remaining is None:
            return False

        return remaining <= context.duration / 2.0

    def describe(self):
        return f"Periapsis um {self.reference} nach t = {self.after:.0f}s"


def trigger_from_config(raw, context):
    """Baut einen Auslöser aus der Szenario-Angabe."""
    kind = raw.get("type")
    if kind == "time":
        if "time_start" not in raw:
            raise ValueError(f"{context}: 'time' braucht 'time_start'")
        return TimeTrigger(raw["time_start"])

    if kind == "periapsis":
        if "reference" not in raw:
            raise ValueError(f"{context}: 'periapsis' braucht 'reference'")
        return PeriapsisTrigger(raw["reference"], raw.get("after", 0.0))

    raise ValueError(
        f"{context}: unbekannter Ausloeser {kind!r}, erlaubt sind "
        f"'time' und 'periapsis'"
    )
