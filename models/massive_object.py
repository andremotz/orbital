from collections import deque

from .state import State

# Wie viele Zustände je Körper vorgehalten werden. Die Simulation selbst
# braucht nur den letzten; die Historie dient Auswertung und Darstellung.
# Unbeschränktes Wachstum wäre bei 60s-Schritten über Monate Simulationszeit
# ein Speicherleck -- ein Umlauf der Erde sind bereits ~525.000 Zustände.
DEFAULT_HISTORY_LENGTH = 1000


class MassiveObject:
    """Klasse repräsentiert ein massives Objekt im Weltraum"""

    def __init__(self, state_new, mass, radius, color, name, is_heavy,
                 list_maneuvers, history_length=DEFAULT_HISTORY_LENGTH):
        self.mass = mass
        self.listStates = deque(maxlen=history_length)
        self.addState(state_new)
        self.radius = radius
        self.color = color
        self.name = name
        self.is_heavy = is_heavy
        self.list_maneuvers = list_maneuvers

    def addState(self, state_new):
        """Fügt einen neuen Zustand hinzu; der älteste fällt heraus"""
        self.listStates.append(state_new)

    def getLatestState(self):
        """Gibt den aktuellsten Zustand zurück"""
        return self.listStates[-1]

    def copy(self):
        """Unabhängige Kopie, die nur den aktuellen Zustand übernimmt.

        Nötig, damit etwa ein Benchmark zwei Läufe von identischen
        Startbedingungen aus vergleichen kann, ohne das Original zu verändern.
        """
        state_latest = self.getLatestState()
        return MassiveObject(
            State(state_latest.vec_velocity.copy(), state_latest.vec_location.copy()),
            self.mass,
            self.radius,
            self.color,
            self.name,
            self.is_heavy,
            list(self.list_maneuvers),
            self.listStates.maxlen,
        )
