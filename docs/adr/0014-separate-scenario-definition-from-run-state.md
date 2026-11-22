# ADR-0014: Separate scenario definition from run state

- Status: Proposed
- Date: 2026-11-22

## Context

A loaded scenario is both the mission definition and the mutable state of one
run:

- `Maneuver` stores `activated_at` and `resolved_delta_v`;
  `PeriapsisTrigger` stores its pass counter.
- `MassiveObject` stores its own state history in a bounded deque.
- `MassiveObject.copy()` copies the manoeuvre *list* but shares the manoeuvre
  objects, so two "independent" copies share ignition state. The benchmark
  runs Python and Rust on such copies.
- `targeting.py` works around this by reloading the JSON file for every
  evaluation and by overwriting manoeuvre fields in place to disable later
  burns.
- The run loop (`step`, advance time, check for collision, sample something)
  is written out separately in `verification.py`, `targeting.py`,
  `make_animations.py`, `make_figures.py` and each viewer.
- Physics state is an array-of-objects that is gathered into NumPy arrays and
  scattered back on every step.

## Decision

Split the two concerns:

- **Definition** — `Scenario`, `Body`, `Maneuver`, `Trigger` become immutable
  descriptions (frozen dataclasses). Loading a scenario has no side effects
  and the result can be shared and reused.
- **Run** — a `Simulation` owns everything that changes: time, an `(n, 3)`
  position and velocity array, per-manoeuvre ignition records, trigger
  counters, and an optional recorder for history. It exposes
  `step()`, `run_until(t)`, and an event stream (ignition, burnout, collision,
  closest approach).
- Variations for a search are expressed as overrides on the definition
  (`scenario.with_maneuver(index, target_apoapsis=...)`,
  `scenario.truncated_after(index)`), not as in-place mutation.

The intended API is sketched in
[specs/simulation-run-api.md](../specs/simulation-run-api.md).

## Consequences

- A scenario can be run any number of times, also in parallel — which makes
  the targeting grid trivially parallelisable.
- `reset()` and the reload-per-evaluation workaround disappear; the shared
  state bug in `copy()` cannot occur.
- One run loop instead of five; collision handling and recording behave the
  same everywhere.
- State lives in arrays, which is the natural input for a multi-step Rust call
  (WI-012).
- Touches nearly every module and most tests. Should follow ADR-0013 rather
  than be mixed with it.
