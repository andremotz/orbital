# ADR-0009: Fire manoeuvres on orbital events, not by the clock

- Status: Accepted
- Date: 2026-08-02 (commit `fe80688`), recorded 2026-11-22

## Context

An orbit-raising burn is effective almost only at periapsis, where speed is
highest. Burns scheduled at absolute times stop hitting periapsis as soon as
the simulated orbit drifts from the real one. For Chandrayaan-2 the period
error was 2,072 s per revolution; after four revolutions the simulated perigee
was almost three hours early, and one burn ended up firing 13.6 hours late.
For Artemis II, a clock-timed TLI left the apogee 140,000 km short.

## Decision

A manoeuvre has either a fixed `time_start` or a `trigger`, never both.

`PeriapsisTrigger(reference, after, skip)` ignites half a burn duration before
the periapsis pass around `reference`, so the burn is centred on it. `after`
is an earliest time; `skip` counts passes after that. Counting passes — rather
than gating by time alone — is what keeps the intended pass selected when its
timing has shifted.

Triggers are evaluated once per step, before forces are computed
(`physics.mission.update_schedule`). Once fired, the ignition time is latched.

## Consequences

- Burns land on the pass they were meant for, even on a drifted orbit.
- Time to periapsis is computed from osculating two-body elements, which is an
  approximation under perturbations; ignition is additionally quantised to the
  step size.
- Triggers and manoeuvres hold run state (`activated_at`, pass counters).
  A scenario object can therefore not be run twice without `reset()`, and
  copies share that state. See ADR-0014.
- Only two trigger kinds exist (`time`, `periapsis`). Apoapsis, node crossing
  and sphere-of-influence entry are obvious next ones (WI-018).
