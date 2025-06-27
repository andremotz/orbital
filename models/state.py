import numpy as np

class State:
    """Klasse repräsentiert einen Zustand eines Körpers"""
    def __init__(self, vec_velocity, vec_location):
        self.vec_velocity = vec_velocity
        self.vec_location = vec_location 