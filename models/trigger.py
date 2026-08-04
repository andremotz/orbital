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

    `after` gibt die Freigabe, `skip` überspringt danach noch so viele
    Durchgänge. Gezündet wird eine halbe Brenndauer vor dem Durchgang, sodass
    der Schub symmetrisch um das Periapsis liegt -- so wird ein realer Burn
    geflogen.

    Warum es `skip` braucht und eine blosse Zeitschranke nicht genügt: die
    Umlaufzeit der Simulation weicht von der wirklichen ab, und der Fehler
    summiert sich über die Umläufe. Bei Chandrayaan-2 waren es 2072 s je
    Umlauf; nach vier Umläufen lag das simulierte Periapsis fast drei Stunden
    vor dem wirklichen. Eine Freigabe, die auf den geplanten Zeitpunkt
    gerechnet ist, fällt dann zwischen zwei Durchgänge -- der richtige liegt
    davor und wird ausgeschlossen, gezündet wird ein voller Umlauf später.
    Wer stattdessen zählt, trifft den gemeinten Durchgang auch dann, wenn er
    sich zeitlich verschoben hat.
    """

    def __init__(self, reference, after=0.0, skip=0):
        self.reference = reference
        self.after = float(after)
        self.skip = int(skip)
        self._seen = 0
        self._previous_remaining = None

    def reset(self):
        """Verwirft die gezählten Durchgänge für einen erneuten Lauf."""
        self._seen = 0
        self._previous_remaining = None

    def should_activate(self, context):
        remaining = context.time_to_periapsis(self.reference)
        if remaining is None:
            return False

        # Ein Durchgang ist überschritten, wenn die Restzeit springt: kurz
        # davor geht sie gegen null, unmittelbar danach steht wieder ein
        # ganzer Umlauf aus.
        if (self._previous_remaining is not None
                and remaining > self._previous_remaining):
            self._seen += 1
        self._previous_remaining = remaining

        if context.time < self.after:
            # Vor der Freigabe zählt nichts; erst ab hier wird gezählt
            self._seen = 0
            return False

        if self._seen < self.skip:
            return False

        return remaining <= context.duration / 2.0

    def describe(self):
        if self.skip:
            return (f"{self.skip + 1}. Periapsis um {self.reference} "
                    f"nach t = {self.after:.0f}s")
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
        return PeriapsisTrigger(raw["reference"], raw.get("after", 0.0),
                                raw.get("skip", 0))

    raise ValueError(
        f"{context}: unbekannter Ausloeser {kind!r}, erlaubt sind "
        f"'time' und 'periapsis'"
    )
