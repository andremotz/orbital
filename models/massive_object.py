from .state import State

class MassiveObject:
    """Klasse repräsentiert ein massives Objekt im Weltraum"""
    
    def __init__(self, state_new, mass, radius, color, name, is_heavy, list_maneuvers):
        self.mass = mass
        self.listStates = []
        self.addState(state_new)
        self.radius = radius
        self.color = color
        self.name = name
        self.is_heavy = is_heavy
        self.list_maneuvers = list_maneuvers

    def addState(self, state_new):
        """Fügt einen neuen Zustand zur Zustandsliste hinzu"""
        self.listStates.append(state_new)

    def getLatestState(self):
        """Gibt den aktuellsten Zustand zurück"""
        currentCount = len(self.listStates)
        return self.listStates[currentCount - 1] 