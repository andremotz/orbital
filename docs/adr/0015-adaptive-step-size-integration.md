# ADR-0015: Adaptive step-size integration

- Status: Proposed
- Date: 2026-11-22

## Context

The step is fixed at 60 s (ADR-0002). A spacecraft at a 170 km perigee moves
~470 km per step and sweeps several degrees of true anomaly; in the days-long
coast to the Moon the same step is far finer than needed. The fixed step also
quantises burn boundaries and trigger times (a 355 s burn becomes 360 s), and
the README notes "a few m/s per perigee pass" still unaccounted for — some of
that may be truncation error rather than missing physics, and today the two
cannot be told apart.

## Decision

Add an embedded Runge–Kutta pair with error control (Dormand–Prince 5(4)) as a
second integrator, selectable per scenario and per run, with:

- relative/absolute tolerances as parameters,
- step boundaries forced onto known discontinuities (burn start and end),
- dense output or root-finding to locate events (periapsis, closest approach)
  between steps.

Fixed-step RK4 stays as the simple reference and for the convergence tests.
Both the Python and the Rust path implement the new scheme, under the same
parity rule as ADR-0006.

Before committing to this, measure: rerun the ballistic tracking check at
60 s, 10 s and 1 s. If the 545 km / 3 days figure does not move, truncation
error is not the bottleneck and this ADR should be rejected in favour of
force-model work (WI-020).

## Consequences

- Accuracy becomes a stated tolerance instead of an implicit property of the
  step size; fewer steps on long coasts.
- Burn durations are honoured exactly.
- Step count varies between runs and backends, so parity tests have to compare
  states at fixed output times, and bit-level reproducibility between Python
  and Rust gets harder.
- History and animation sampling can no longer assume one sample per step.
- Twice the integrator code to keep in parity.

## Alternatives considered

- **Smaller fixed step.** Trivial, but costs linearly everywhere to fix a
  problem that exists only near perigee.
- **Symplectic integrator (e.g. Wisdom–Holman).** Better long-term energy
  behaviour, but awkward with thrust and close encounters — the wrong tool for
  mission-length runs with burns.
- **`scipy.integrate.solve_ivp`.** No new integrator code, but adds SciPy as a
  core dependency and leaves the Rust path without an equivalent.
