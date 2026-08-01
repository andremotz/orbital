"""Zugang zu den Himmelskörpern der Simulation.

Die Daten liegen nicht mehr im Code, sondern als Szenario unter
`data/scenarios/`. Diese Modul-Ebene bleibt bestehen, damit die bestehenden
Einstiegspunkte unverändert `get_massive_objects()` aufrufen können.
"""

from .scenario import available_scenarios, load_named_scenario

DEFAULT_SCENARIO = "chandrayaan2"


def get_massive_objects(scenario_name=DEFAULT_SCENARIO):
    """Erstellt und gibt eine Liste aller Himmelskörper zurück"""
    return load_named_scenario(scenario_name).bodies


def get_scenario(scenario_name=DEFAULT_SCENARIO):
    """Gibt das vollständige Szenario samt Manövern und Meilensteinen zurück"""
    return load_named_scenario(scenario_name)


__all__ = ["get_massive_objects", "get_scenario", "available_scenarios",
           "DEFAULT_SCENARIO"]
