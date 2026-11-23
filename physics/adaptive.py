"""Schrittweite, die sich der Umgebung anpasst.

Eine feste Schrittweite muss immer für den härtesten Moment der ganzen Bahn
taugen. Bei einem Erdorbit ist das der Perigäumsdurchgang, und 60 Sekunden
sind dafür angemessen. Auf einer interplanetaren Reise wäre dasselbe Mass
Verschwendung: zwischen zwei Vorbeiflügen ändert sich über Stunden kaum
etwas, und Cassinis Flug zum Saturn dauerte mit sieben Jahren rund 53-mal so
lange wie die gesamte Chandrayaan-2-Mission. Bei 60-Sekunden-Schritten wären
das dreieinhalb Millionen Schritte für einen einzigen Lauf.

Der Ausweg ist, die Schrittweite an der örtlichen charakteristischen Zeit zu
bemessen: der Umlaufzeit, die ein Körper an dieser Stelle um seinen
stärksten Anzieher hätte. Nahe an einem Planeten ist die kurz, im freien Raum
lang. Ein fester Bruchteil davon hält den Fehler je Schritt in etwa konstant.

Bewusst als Treiber über `physics.integrator.step` gebaut und nicht in den
Kern hinein: der Kern und seine Übereinstimmung mit dem Rust-Kernel sind
durch Tests abgesichert, und beides bleibt hier unberührt. Wer eine feste
Schrittweite will, ruft weiterhin `step` direkt auf.
"""

import numpy as np

# Bruchteil der örtlichen Umlaufzeit je Schritt. 1/2000 hält den Fehler eines
# RK4-Schritts weit unter dem, was die Bahn selbst an Unsicherheit mitbringt.
DEFAULT_FRACTION = 1.0 / 2000.0


def characteristic_time(bodies, subject):
    """Umlaufzeit, die `subject` um seinen stärksten Anzieher hätte.

    Massgeblich ist nicht der nächste Körper, sondern der, dessen Anziehung
    hier am stärksten wirkt -- im erdnahen Raum die Erde, wenige Millionen
    Kilometer weiter längst die Sonne.
    """
    location = subject.getLatestState().vec_location

    shortest = np.inf
    for body in bodies:
        if body is subject or body.mu <= 0.0:
            continue

        distance = float(np.linalg.norm(
            body.getLatestState().vec_location - location
        ))
        if distance <= 0.0:
            continue

        # Umlaufzeit einer Kreisbahn an dieser Stelle
        period = 2.0 * np.pi * np.sqrt(distance ** 3 / body.mu)
        shortest = min(shortest, period)

    return shortest


def suggested_step(bodies, subject, minimum, maximum,
                   fraction=DEFAULT_FRACTION):
    """Schrittweite für den aktuellen Zustand, begrenzt auf [minimum, maximum]."""
    period = characteristic_time(bodies, subject)
    if not np.isfinite(period):
        return maximum
    return float(np.clip(period * fraction, minimum, maximum))


def advance(bodies, subject, until, integrator=None, minimum=1.0,
            maximum=3600.0, fraction=DEFAULT_FRACTION, start=0.0,
            observer=None):
    """Rechnet bis `until` und passt die Schrittweite unterwegs an.

    `subject` ist der Körper, nach dem sich die Schrittweite richtet -- das
    Raumfahrzeug, nicht die Planeten. `observer` wird nach jedem Schritt mit
    der verstrichenen Zeit aufgerufen und erlaubt es, unterwegs zu messen.

    Zurück kommt die Zahl der ausgeführten Schritte; sie zeigt, was die
    Anpassung gegenüber einer festen Schrittweite einspart.
    """
    if integrator is None:
        from rust_integration import RustAcceleratedIntegrator

        integrator = RustAcceleratedIntegrator(use_rust=True)

    elapsed = float(start)
    steps = 0
    while elapsed < until:
        step_size = suggested_step(bodies, subject, minimum, maximum, fraction)
        # Nicht über das Ziel hinausschiessen
        step_size = min(step_size, until - elapsed)

        integrator.calculate_states_batch(bodies, step_size, elapsed)
        elapsed += step_size
        steps += 1

        if observer is not None:
            observer(elapsed)

    return steps
