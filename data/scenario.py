"""Lädt Missions-Szenarien aus JSON.

Ein Szenario beschreibt die Himmelskörper mit ihren Startzuständen, die
geplanten Manöver und -- optional -- historische Meilensteine, an denen sich
der Lauf messen lassen muss.

Alle Werte sind SI-Einheiten: Meter, Meter pro Sekunde, Kilogramm, Sekunden,
Newton. Positionen und Geschwindigkeiten sind zweidimensional in der
Bahnebene, weil die Simulation in 2D rechnet.

Körper dürfen sich über `relative_to` auf einen anderen Körper beziehen; ihre
Angaben werden dann als Versatz zu dessen Zustand verstanden. So bleibt etwa
die Mondbahn beschreibbar, ohne die Erdposition einzurechnen.
"""

import json
import os

import numpy as np

from data.constants import DIMENSIONS
from models.maneuver import Maneuver
from models.massive_object import DEFAULT_HISTORY_LENGTH, MassiveObject
from models.oblateness import Oblateness
from models.trigger import PeriapsisTrigger, trigger_from_config
from models.state import State

SCENARIO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios")


class ScenarioError(ValueError):
    """Das Szenario ist unvollständig oder widersprüchlich."""


class Milestone:
    """Ein überprüfbarer Punkt im Missionsverlauf.

    Prüft den Abstand von `body` zu `relative_to` zum Zeitpunkt `time`
    (Sekunden seit Simulationsbeginn) gegen `expected_distance` mit der
    angegebenen `tolerance` -- beide in Metern.

    `status` trennt zwei grundverschiedene Ansprüche:
    "verified"     -- das Szenario soll diesen Punkt treffen, Abweichung ist ein Fehler.
    "aspirational" -- historisch belegtes Ziel, das das Modell derzeit nicht
                      erreicht (etwa weil es in 2D rechnet). Wird berichtet,
                      aber nicht als Testfehler gewertet.
    """

    VALID_STATUS = ("verified", "aspirational")

    def __init__(self, name, time, body, relative_to, expected_distance, tolerance,
                 status="verified", date=None, note=None, source=None):
        if status not in self.VALID_STATUS:
            raise ScenarioError(
                f"Meilenstein {name!r}: 'status' muss eines von "
                f"{self.VALID_STATUS} sein, ist aber {status!r}"
            )
        self.name = name
        self.time = time
        self.body = body
        self.relative_to = relative_to
        self.expected_distance = expected_distance
        self.tolerance = tolerance
        self.status = status
        self.date = date
        self.note = note
        self.source = source

    def __repr__(self):
        return f"<Milestone {self.name!r} bei t={self.time}s>"


class Scenario:
    """Ein vollständiges Missions-Szenario."""

    def __init__(self, name, bodies, milestones, description=None, epoch=None,
                 time_step=60.0, source=None, limitations=()):
        self.name = name
        self.bodies = bodies
        self.milestones = milestones
        self.description = description
        self.epoch = epoch
        self.time_step = time_step
        self.source = source
        # Bekannte Grenzen des Modells -- gehören zum Szenario, damit ein
        # verfehlter Meilenstein einordbar bleibt.
        self.limitations = list(limitations)

    def body(self, name):
        """Liefert den Körper mit diesem Namen."""
        for body in self.bodies:
            if body.name == name:
                return body
        raise ScenarioError(f"Kein Körper namens {name!r} im Szenario {self.name!r}")

    def __repr__(self):
        return f"<Scenario {self.name!r}: {len(self.bodies)} Körper>"


def _require(mapping, key, context):
    if key not in mapping:
        raise ScenarioError(f"{context}: Pflichtfeld {key!r} fehlt")
    return mapping[key]


def _vector(raw, context):
    """Prüft und konvertiert einen Orts- oder Geschwindigkeitsvektor.

    Intern rechnet die Simulation dreikomponentig. Zweikomponentige Angaben
    bleiben zulässig und werden mit z = 0 aufgefüllt -- eine Bahn in der
    Ekliptik lässt sich so weiter kurz notieren.
    """
    if not isinstance(raw, (list, tuple)) or len(raw) not in (2, DIMENSIONS):
        raise ScenarioError(
            f"{context}: erwartet einen Vektor [x, y] oder [x, y, z], "
            f"bekam {raw!r}"
        )
    try:
        components = [float(value) for value in raw]
    except (TypeError, ValueError):
        raise ScenarioError(f"{context}: Vektor {raw!r} ist nicht numerisch")

    components += [0.0] * (DIMENSIONS - len(components))
    return np.array(components)


def _build_oblateness(raw, context):
    """Liest die Abplattung eines Körpers, falls angegeben."""
    if raw is None:
        return None

    for key in ("j2", "equatorial_radius", "pole"):
        _require(raw, key, f"{context}.oblateness")

    return Oblateness(
        float(raw["j2"]),
        float(raw["equatorial_radius"]),
        _vector(raw["pole"], f"{context}.oblateness.pole"),
    )


def _resolve_order(raw_bodies):
    """Sortiert die Körper so, dass Bezugskörper vor ihren Bezugnehmern stehen.

    Meldet fehlende Bezüge und Zyklen, statt sie stillschweigend zu ignorieren.
    """
    by_name = {}
    for index, raw in enumerate(raw_bodies):
        name = _require(raw, "name", f"Körper #{index}")
        if name in by_name:
            raise ScenarioError(f"Körper {name!r} ist doppelt definiert")
        by_name[name] = raw

    ordered = []
    resolved = set()
    visiting = set()

    def visit(name, trail):
        if name in resolved:
            return
        if name in visiting:
            cycle = " -> ".join(trail + [name])
            raise ScenarioError(f"Zyklischer Bezug über 'relative_to': {cycle}")
        if name not in by_name:
            raise ScenarioError(f"'relative_to' verweist auf unbekannten Körper {name!r}")

        visiting.add(name)
        parent = by_name[name].get("relative_to")
        if parent is not None:
            visit(parent, trail + [name])
        visiting.discard(name)

        resolved.add(name)
        ordered.append(by_name[name])

    for raw in raw_bodies:
        visit(raw["name"], [])

    return ordered


def _build_bodies(raw_bodies, raw_maneuvers, history_length):
    """Erzeugt die MassiveObject-Instanzen inklusive ihrer Manöver."""
    maneuvers_by_body = {}
    for index, raw in enumerate(raw_maneuvers):
        context = f"Manöver #{index}"
        body_name = _require(raw, "body", context)
        direction = raw.get("direction")

        if ("force" in raw) == ("delta_v" in raw):
            raise ScenarioError(
                f"{context}: genau eines von 'force' und 'delta_v' angeben"
            )
        if ("time_start" in raw) == ("trigger" in raw):
            raise ScenarioError(
                f"{context}: genau eines von 'time_start' und 'trigger' angeben"
            )

        try:
            trigger = (trigger_from_config(raw["trigger"], context)
                       if "trigger" in raw else None)
        except ValueError as error:
            raise ScenarioError(str(error)) from error

        maneuvers_by_body.setdefault(body_name, []).append(
            Maneuver(
                time_start=(float(raw["time_start"]) if "time_start" in raw else None),
                time_duration=float(_require(raw, "duration", context)),
                force=float(raw["force"]) if "force" in raw else None,
                delta_v=float(raw["delta_v"]) if "delta_v" in raw else None,
                direction=_vector(direction, context) if direction is not None else None,
                relative_to=raw.get("relative_to"),
                trigger=trigger,
            )
        )

    built = {}
    for raw in _resolve_order(raw_bodies):
        name = raw["name"]
        context = f"Körper {name!r}"

        vec_location = _vector(_require(raw, "location", context), f"{context}.location")
        vec_velocity = _vector(_require(raw, "velocity", context), f"{context}.velocity")

        parent_name = raw.get("relative_to")
        if parent_name is not None:
            parent_state = built[parent_name].getLatestState()
            vec_location = vec_location + parent_state.vec_location
            vec_velocity = vec_velocity + parent_state.vec_velocity

        color = raw.get("color", [255, 255, 255])
        if not isinstance(color, (list, tuple)) or len(color) != 3:
            raise ScenarioError(f"{context}: 'color' erwartet [r, g, b], bekam {color!r}")

        built[name] = MassiveObject(
            State(vec_velocity, vec_location),
            float(_require(raw, "mass", context)),
            float(_require(raw, "radius", context)),
            tuple(int(channel) for channel in color),
            name,
            bool(raw.get("is_heavy", True)),
            maneuvers_by_body.pop(name, []),
            history_length,
            oblateness=_build_oblateness(raw.get("oblateness"), context),
            # GM ist genauer bekannt als Masse mal G; ohne Angabe wird es aus
            # der Masse gebildet.
            mu=float(raw["mu"]) if "mu" in raw else None,
        )

    if maneuvers_by_body:
        unknown = ", ".join(sorted(maneuvers_by_body))
        raise ScenarioError(f"Manöver verweisen auf unbekannte Körper: {unknown}")

    for body in built.values():
        for maneuver in body.list_maneuvers:
            if maneuver.relative_to is not None and maneuver.relative_to not in built:
                raise ScenarioError(
                    f"Manöver von {body.name!r}: 'relative_to' verweist auf "
                    f"unbekannten Körper {maneuver.relative_to!r}"
                )
            trigger = maneuver.trigger
            if isinstance(trigger, PeriapsisTrigger) and trigger.reference not in built:
                raise ScenarioError(
                    f"Manöver von {body.name!r}: Auslöser verweist auf "
                    f"unbekannten Körper {trigger.reference!r}"
                )

    # Reihenfolge der JSON-Datei beibehalten, nicht die Auflösungsreihenfolge
    return [built[raw["name"]] for raw in raw_bodies]


def _build_milestones(raw_milestones, known_names):
    milestones = []
    for index, raw in enumerate(raw_milestones):
        context = f"Meilenstein #{index}"
        for key in ("body", "relative_to"):
            name = _require(raw, key, context)
            if name not in known_names:
                raise ScenarioError(
                    f"{context}: {key!r} verweist auf unbekannten Körper {name!r}"
                )

        milestones.append(
            Milestone(
                name=_require(raw, "name", context),
                time=float(_require(raw, "time", context)),
                body=raw["body"],
                relative_to=raw["relative_to"],
                expected_distance=float(_require(raw, "expected_distance", context)),
                tolerance=float(_require(raw, "tolerance", context)),
                status=raw.get("status", "verified"),
                date=raw.get("date"),
                note=raw.get("note"),
                source=raw.get("source"),
            )
        )
    return milestones


def load_scenario(path, history_length=None):
    """Lädt ein Szenario aus einer JSON-Datei."""
    with open(path, encoding="utf-8") as handle:
        try:
            raw = json.load(handle)
        except json.JSONDecodeError as error:
            raise ScenarioError(f"{path} ist kein gültiges JSON: {error}") from error

    name = _require(raw, "name", os.path.basename(path))
    raw_bodies = _require(raw, "bodies", name)
    if not raw_bodies:
        raise ScenarioError(f"Szenario {name!r} enthält keine Körper")

    if history_length is None:
        history_length = DEFAULT_HISTORY_LENGTH

    bodies = _build_bodies(raw_bodies, raw.get("maneuvers", []), history_length)
    milestones = _build_milestones(
        raw.get("milestones", []), {body.name for body in bodies}
    )

    return Scenario(
        name=name,
        bodies=bodies,
        milestones=milestones,
        description=raw.get("description"),
        epoch=raw.get("epoch"),
        time_step=float(raw.get("time_step", 60.0)),
        source=raw.get("source"),
        limitations=raw.get("limitations", []),
    )


def load_named_scenario(scenario_name, history_length=None):
    """Lädt ein Szenario aus dem mitgelieferten Szenario-Verzeichnis."""
    path = os.path.join(SCENARIO_DIR, f"{scenario_name}.json")
    if not os.path.exists(path):
        raise ScenarioError(
            f"Unbekanntes Szenario {scenario_name!r}. Verfügbar: "
            f"{', '.join(available_scenarios()) or 'keine'}"
        )
    return load_scenario(path, history_length)


def available_scenarios():
    """Namen aller mitgelieferten Szenarien."""
    if not os.path.isdir(SCENARIO_DIR):
        return []
    return sorted(
        os.path.splitext(entry)[0]
        for entry in os.listdir(SCENARIO_DIR)
        if entry.endswith(".json")
    )
