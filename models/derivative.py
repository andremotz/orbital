import numpy as np

class Derivative:
    """Klasse repräsentiert eine Ableitung eines States"""
    def __init__(self, vec_acceleration, vec_velocity):
        self.vec_acceleration = vec_acceleration
        self.vec_velocity = vec_velocity 