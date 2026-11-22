# ADR-0011: Layered verification with verified and aspirational milestones

- Status: Accepted
- Date: 2026-08-01 (commit `cedca41`), recorded 2026-11-22

## Context

"The probe misses the Moon" can mean the integrator is wrong, the force model
is incomplete, the initial state is off, or the guidance is poor. A single
end-to-end check cannot tell these apart, and a test suite that is red for a
known modelling gap gets ignored.

## Decision

Verification is split into layers that each answer one question:

1. **Kernel** — analytic checks of the integrator in isolation: conservation
   laws, convergence order against the exact Kepler solution
   (`tests/test_kernel_verification.py`, `tests/test_physics.py`).
2. **Mission milestones** — a scenario run checked against dated milestones
   (`verification.py`). Each milestone is either `verified` (missing it fails
   the run, exit code 1) or `aspirational` (historically documented, reported,
   not a failure).
3. **Tracking** — point-by-point comparison against the Horizons trajectory.
   Only the ballistic phase is a clean measure of the physics.

A body interpenetration aborts a run and is reported; everything after it is
unphysical and is not evaluated.

The details are specified in [specs/verification.md](../specs/verification.md).

## Consequences

- A failure points at a layer. Two real bugs were found when layer 1 was
  introduced.
- Known gaps are visible in every report instead of being hidden or
  permanently red.
- `aspirational` can become a parking lot. Each such milestone should name
  what is missing to promote it.
- Milestones check a single distance at a single time. With event-triggered
  burns, *when* something happens is itself uncertain, so tolerances have to
  be wide (± 6,000 km for lunar capture). Orbit-element or event-based
  milestones would be sharper (WI-017).
- Layer 3 is hard-wired to Chandrayaan-2 in `verification.py` (WI-009).
