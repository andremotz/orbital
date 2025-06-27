class Maneuver:
    """Klasse repräsentiert ein Manöver eines Objekts"""
    def __init__(self, time_start, time_duration, force):
        self.time_start = time_start
        self.time_duration = time_duration
        self.force = force 