# Spec (draft): Simulation run API

- Status: Draft — not implemented
- Related: ADR-0014, ADR-0006

## 1. Goal

One object owns a run. Scenario definitions are immutable and reusable. Every
consumer (verification, targeting, figures, animations, viewers) uses the same
loop.

## 2. Definition objects

`Scenario`, `Body`, `Maneuver`, `Trigger`, `Milestone` are frozen dataclasses.
They hold no run state.

```python
scenario = load_scenario("chandrayaan2")

variant = scenario.with_maneuver(4, target_apoapsis=4.8e8)  # new object
variant = variant.truncated_after(4)  # drop later burns
```

- `with_maneuver(index, **changes)` MUST return a new scenario and leave the
  original untouched.
- Two scenarios loaded from the same file MUST compare equal.

## 3. Simulation

```python
sim = Simulation(scenario, backend="auto", time_step=None, record=Recorder(every=10))

sim.step()  # one step
sim.run_until(2.9e6)  # stops early on collision
sim.time  # seconds since epoch
sim.positions, sim.velocities  # (n, 3) float64 views, read-only
sim.state_of("Moon")  # (position, velocity)
sim.relative_state("Chandrayaan-2", "Earth")
sim.events  # list of Event, in time order
sim.backend  # "python" | "rust" — what is actually in use
```

Requirements:

- `Simulation(scenario)` MUST NOT mutate `scenario`. Running the same scenario
  twice MUST give identical results.
- `backend="auto"` uses Rust if importable, else Python. `backend="rust"` MUST
  raise if the kernel is unavailable. A kernel error MUST propagate; there is
  no silent mid-run fallback.
- The backend MUST NOT print. Which backend is in use is available as
  `sim.backend` and logged at INFO.
- `run_until(t)` MUST stop at the first collision and record it as an event.
- Simulations MUST be independent of each other, so that several can run in
  separate processes.

## 4. Events

```python
Event(time, kind, body, detail)
```

| `kind` | Emitted when | `detail` |
|---|---|---|
| `ignition` | a manoeuvre starts | manoeuvre index, resolved Δv |
| `burnout` | a manoeuvre ends | achieved apsides relative to its reference |
| `periapsis` / `apoapsis` | a body with manoeuvres passes an apsis of its dominant body | radius |
| `closest_approach` | a tracked pair passes a local distance minimum | distance |
| `collision` | two bodies interpenetrate | pair, distance |

Events are the basis for sharper milestones (WI-017) and replace ad-hoc
bookkeeping in `targeting.py` and `make_animations.py`.

## 5. Recording

History is opt-in. A `Recorder(every=k, bodies=None)` stores time, positions
and velocities every k steps in pre-allocated arrays. Bodies no longer carry
their own history deque.

## 6. Multi-step backend call

Between two points where Python has to act — a trigger check that could fire,
a burn boundary, a recorder sample — the backend MAY advance several steps in
one call. Results MUST equal single-stepping within the parity tolerance of
[kernel-contract.md](kernel-contract.md).

To keep that valid with per-step trigger checks, either triggers are evaluated
inside the kernel, or the batch length is bounded by the earliest time a
trigger could fire (a periapsis trigger cannot fire before `after`, nor while
time-to-periapsis exceeds half the burn duration plus the batch length).

## 7. Migration

1. Introduce `Simulation` as a wrapper around today's objects; port
   `verification.py` to it.
2. Port `targeting.py`; delete the reload-per-evaluation workaround.
3. Port figures, animations and viewers.
4. Make definitions frozen; move run state out of `Maneuver` and `Trigger`;
   remove `MassiveObject.copy()` and `reset()`.
5. Add the multi-step backend call.

Each step keeps the full test suite green.
