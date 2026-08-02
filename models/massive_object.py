from collections import deque

from data.constants import CONST_GRAVITY

from .state import State

# Wie viele Zustände je Körper vorgehalten werden. Die Simulation selbst
# braucht nur den letzten; die Historie dient Auswertung und Darstellung.
# Unbeschränktes Wachstum wäre bei 60s-Schritten über Monate Simulationszeit
# ein Speicherleck -- ein Umlauf der Erde sind bereits ~525.000 Zustände.
DEFAULT_HISTORY_LENGTH = 1000


class MassiveObject:
    """Klasse repräsentiert ein massives Objekt im Weltraum"""

    def __init__(self, state_new, mass, radius, color, name, is_heavy,
                 list_maneuvers, history_length=DEFAULT_HISTORY_LENGTH,
                 oblateness=None, mu=None):
        self.mass = mass
        # Standard-Gravitationsparameter GM. Er, nicht die Masse, bestimmt die
        # Anziehung; siehe die Erläuterung in data/constants.py. Ohne Angabe
        # wird er aus der Masse gebildet, was die Genauigkeit von G erbt.
        self.mu = float(mu) if mu is not None else CONST_GRAVITY * mass
        self.listStates = deque(maxlen=history_length)
        self.addState(state_new)
        self.radius = radius
        self.color = color
        self.name = name
        self.is_heavy = is_heavy
        self.list_maneuvers = list_maneuvers
        # Abplattung; None bedeutet, der Körper wird als Kugel gerechnet
        self.oblateness = oblateness

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
            self.oblateness,
            self.mu,
        )
