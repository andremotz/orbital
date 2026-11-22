# ADR-0002: Integrate all bodies simultaneously with fixed-step RK4

- Status: Accepted
- Date: 2026-08-01 (commit `a70a2a7`), recorded 2026-11-22

## Context

The original integrator advanced bodies one after another. Within a single
step the second body then saw the first already at its new position, and the
RK4 intermediate stages saw the other bodies frozen. The scheme was no longer
RK4 and did not converge at fourth order.

## Decision

`physics.integrator.step` advances the whole system as one state vector
through the four classical RK4 stages. Gravity for all bodies is evaluated in
one vectorised call (`physics.gravity.accelerations`) per stage. The step size
is fixed and comes from the scenario (`time_step`, default 60 s).

Thrust is evaluated once per step and held constant over the four stages;
position-dependent forces (gravity, J2) are re-evaluated in each stage.

## Consequences

- Measured fourth-order convergence against the exact Kepler solution
  (`tests/test_kernel_verification.py`, `docs/figures/convergence.png`).
- Cost per step is O(n²) in the number of bodies — irrelevant for the 4-body
  scenarios here.
- A fixed step is wasteful far from any body and coarse at a low perigee. See
  ADR-0015.
- Burn start and end are quantised to the step size: a 355 s burn at a 60 s
  step effectively lasts 360 s. See work item WI-011.
- RK4 is not symplectic; energy drifts slowly over very long runs. Acceptable
  for missions of weeks, not for long-term solar-system dynamics.
