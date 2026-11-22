# ADR-0004: 3D state vectors in the ecliptic J2000 frame

- Status: Accepted
- Date: 2026-08-02 (commit `877aca7`), recorded 2026-11-22

## Context

The simulation started in 2D. The Moon's orbit is inclined 5.145° against the
ecliptic, so a lunar transfer necessarily has out-of-plane components. A 2D
model cannot represent real trajectories and cannot be compared against real
ephemerides.

## Decision

All state vectors have three components (`data.constants.DIMENSIONS = 3`).
The frame is ecliptic J2000 with the origin at the solar-system barycentre;
the simulation's x-y plane is the ecliptic. The Sun is integrated as a body
like any other.

Two-component vectors remain valid in scenario files and manoeuvre directions
and are padded with z = 0.

Body-fixed quantities are rotated into this frame when loaded. Earth's pole,
needed for J2, is stored as a unit vector in ecliptic coordinates (tilted by
the 23.44° obliquity).

## Consequences

- States from JPL Horizons can be used directly as initial conditions and as
  ground truth.
- All views still project onto the ecliptic; a real 3D view is open (WI-019).
- Some docstrings still describe the 2D model (`data/scenario.py`). They are
  wrong and must be fixed (WI-003).
