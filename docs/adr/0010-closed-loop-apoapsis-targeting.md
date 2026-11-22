# ADR-0010: Closed-loop targeting — burns name a target apoapsis

- Status: Accepted
- Date: 2026-08-04 (commit `d5070ac`), recorded 2026-11-22

## Context

Replaying a Δv measured on the flown trajectory is open-loop control. On an
orbit that has already drifted, the same Δv does something else, and the
error compounds: the first Chandrayaan-2 burn fell 15 % short, which shortened
the period, which walked later perigee passes out of their windows. The
replayed mission stalled at an apogee of about 94,000 km.

## Decision

A manoeuvre's strength is given in exactly one of three ways: `force`,
`delta_v`, or `target_apoapsis` (with a `target_reference` body).

For a target manoeuvre the Δv is solved from vis-viva **once, at ignition**,
from the state actually found, and then held for the burn. It is not
re-solved during the burn — a burn that keeps chasing a target it is itself
moving never settles.

When the burn is centred on periapsis (ADR-0009), the Δv is computed for the
periapsis radius of the current orbit, not for the ignition point half a burn
earlier; otherwise the burn overshoots by 4–18 %. The result is signed, so a
capture burn brakes without special handling.

The target of the trans-lunar injection is not copied from the flown
trajectory but searched (`targeting.py`): a coarse grid over the target
apoapsis to escape local minima, then bounded scalar refinement on the closest
approach to the Moon.

## Consequences

- Chandrayaan-2 reaches the Moon and is captured: closest approach 16,266 km
  (189,063 km before), bound orbit 16,445 × 17,878 km.
- The simulation no longer replays the recorded mission; it flies its own
  mission to the same target orbits. Verification now answers "can the model
  fly a mission", not "can it reproduce a given trajectory". The ballistic
  phase remains the measure of raw model accuracy.
- The solve is impulsive; a finite burn falls short of it. That is why the
  searched TLI target (479,873 km) sits above the apogee actually flown
  (416,513 km) — the target value compensates for a modelling gap and is not a
  physical quantity.
- Only apoapsis is targeted, one parameter per search. Phasing, inclination
  and periapsis at arrival are not controlled, hence the wide captured orbit.
- Artemis II still replays measured Δv (WI-016).
- `scipy` is needed for the search only.
