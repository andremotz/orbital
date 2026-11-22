# ADR-0003: Use GM instead of G × mass

- Status: Accepted
- Date: 2026-08-02 (commit `72d1e77`), recorded 2026-11-22

## Context

The standard gravitational parameter GM of a body is known from orbit
observations to more than ten significant digits. The gravitational constant G
is only measured to about five. Published masses are derived as GM / G and
inherit that uncertainty. Computing G × M with M = 1.989e30 kg misses the
Sun's true GM by 3e-4, which puts Earth's orbit off by almost 0.04 m/s within
six hours.

## Decision

Every body carries `mu` (GM, in m³/s²). Gravity is computed from `mu` only.
Values come from JPL DE440 and are stored per body in the scenario file.
`mass` is kept, but used solely to convert a thrust given in newtons into an
acceleration. If a scenario omits `mu`, it is derived as G × mass as a
fallback.

## Consequences

- The ballistic phase tracks the real Chandrayaan-2 trajectory to 545 km after
  three days.
- Scenario files carry two partly redundant numbers per body (`mu`, `mass`).
- The G × mass fallback silently reintroduces the error this ADR removes. A
  loader warning for massive bodies without `mu` would close that gap
  (WI-014).
