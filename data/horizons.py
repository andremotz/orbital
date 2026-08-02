"""Zugang zu den Ephemeriden von JPL Horizons.

Horizons liefert Zustandsvektoren realer Körper und Raumfahrzeuge -- für
Chandrayaan-2 sogar eine an DSN-Trackingdaten angepasste Bahn, also die
tatsächlich geflogene und nicht eine nachgerechnete. Damit lassen sich
Startzustände belegen statt schätzen, und die reale Bahn dient als
Referenz, gegen die sich das Modell messen lässt.

Alle abgerufenen Werte werden in SI umgerechnet: Meter und Meter pro
Sekunde. Bezugsebene ist die Ekliptik zu J2000, was der x-y-Ebene der
Simulation entspricht.

Abrufe werden auf Platte zwischengespeichert. Tests und der Normalbetrieb
laufen aus dem Cache und brauchen kein Netz; nur `refresh_cache` geht
tatsächlich online.
"""

import json
import os
import re
import urllib.parse
import urllib.request

import numpy as np

API_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "horizons_cache")

KM = 1000.0

# Horizons-Kennungen der Körper dieser Simulation. Negative Werte bezeichnen
# Raumfahrzeuge.
BODY_IDS = {
    "Sun": "10",
    "Earth": "399",
    "Moon": "301",
    "Chandrayaan-2": "-152",
    "Chandrayaan-2 Lander": "-153",
    "Artemis II": "-1024",
    "Artemis I": "-1023",
}

# Schwerpunkt des Sonnensystems. Als Bezugspunkt deutlich besser geeignet als
# der Sonnenmittelpunkt: die Sonne bewegt sich selbst um den Schwerpunkt, und
# die Simulation integriert sie als Körper mit.
SOLAR_SYSTEM_BARYCENTER = "500@0"
GEOCENTER = "500@399"

_RECORD_PATTERN = re.compile(
    r"(?P<jd>[\d.]+) = A\.D\. (?P<date>\S+ \S+).*?\n"
    r"\s*X\s*=\s*(?P<x>\S+)\s*Y\s*=\s*(?P<y>\S+)\s*Z\s*=\s*(?P<z>\S+)\s*\n"
    r"\s*VX\s*=\s*(?P<vx>\S+)\s*VY\s*=\s*(?P<vy>\S+)\s*VZ\s*=\s*(?P<vz>\S+)"
)


class HorizonsError(RuntimeError):
    """Der Abruf oder die Antwort von Horizons war nicht verwertbar."""


def _resolve_body(body):
    """Übersetzt einen Namen in die Horizons-Kennung."""
    return BODY_IDS.get(body, body)


def build_query(body, start_time, stop_time, step_size, center):
    """Baut die Abfrage-URL. Getrennt gehalten, damit sie prüfbar bleibt."""
    parameters = {
        "format": "text",
        "COMMAND": f"'{_resolve_body(body)}'",
        "OBJ_DATA": "'NO'",
        "MAKE_EPHEM": "'YES'",
        "EPHEM_TYPE": "'VECTORS'",
        "CENTER": f"'{center}'",
        "START_TIME": f"'{start_time}'",
        "STOP_TIME": f"'{stop_time}'",
        "STEP_SIZE": f"'{step_size}'",
        "VEC_TABLE": "'2'",
        "OUT_UNITS": "'KM-S'",
        "REF_PLANE": "'ECLIPTIC'",
    }
    return f"{API_URL}?{urllib.parse.urlencode(parameters)}"


def parse_vectors(payload):
    """Liest die VECTORS-Ausgabe und rechnet sie in SI um.

    Ergebnis ist eine Liste von Datensätzen mit Julianischem Datum, Datum als
    Text sowie Ort und Geschwindigkeit als Listen in Metern und m/s.
    """
    if "$$SOE" not in payload or "$$EOE" not in payload:
        message = payload.strip().splitlines()
        hint = message[-1] if message else "leere Antwort"
        raise HorizonsError(f"Keine Ephemeride in der Antwort: {hint}")

    body = payload.split("$$SOE", 1)[1].split("$$EOE", 1)[0]

    records = []
    for match in _RECORD_PATTERN.finditer(body):
        records.append({
            "jd": float(match.group("jd")),
            "date": match.group("date"),
            "location": [float(match.group(axis)) * KM for axis in ("x", "y", "z")],
            "velocity": [float(match.group(axis)) * KM for axis in ("vx", "vy", "vz")],
        })

    if not records:
        raise HorizonsError("Ephemeride enthielt keine lesbaren Datensätze")

    return records


def fetch_vectors(body, start_time, stop_time, step_size,
                  center=SOLAR_SYSTEM_BARYCENTER, timeout=60):
    """Holt Zustandsvektoren direkt von Horizons. Braucht eine Netzverbindung."""
    url = build_query(body, start_time, stop_time, step_size, center)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except OSError as error:
        raise HorizonsError(f"Horizons nicht erreichbar: {error}") from error

    return parse_vectors(payload)


def cache_path(name):
    return os.path.join(CACHE_DIR, f"{name}.json")


def save_cache(name, payload):
    """Legt einen Abruf im Cache ab."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(cache_path(name), "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def load_cache(name):
    """Lädt einen zwischengespeicherten Abruf."""
    path = cache_path(name)
    if not os.path.exists(path):
        raise HorizonsError(
            f"Kein Cache namens {name!r}. Mit 'python -m data.horizons' neu holen."
        )
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def available_caches():
    if not os.path.isdir(CACHE_DIR):
        return []
    return sorted(
        os.path.splitext(entry)[0]
        for entry in os.listdir(CACHE_DIR)
        if entry.endswith(".json")
    )


def state_arrays(record):
    """Gibt Ort und Geschwindigkeit eines Datensatzes als Arrays zurück."""
    return (np.array(record["location"], dtype=float),
            np.array(record["velocity"], dtype=float))
