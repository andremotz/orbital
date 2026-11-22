# ADR-0008: Derive the burn profile from the flown trajectory

- Status: Accepted
- Date: 2026-08-02 (commit `dad086c`), recorded 2026-11-22

## Context

Burn times and magnitudes from press releases are rounded, incomplete and
given in inconsistent time systems. They also come from a different source
than the trajectory the model is later verified against.

## Decision

`detect_maneuvers.py` recovers burns from the reference ephemeris itself:
propagate ballistically from one ephemeris sample to the next with this
project's own kernel, and book the unexplained velocity change as Δv.
A spike whose contributions cancel over neighbouring samples is a bad
ephemeris sample, not a burn, and is discarded.

Published figures are used only to cross-check the result.

## Consequences

- All six published ISRO manoeuvres for Chandrayaan-2 are recovered to within
  minutes; Artemis II's TLI comes out at 388.3 m/s against a published
  388 m/s, at a noise floor of 0.0001 m/s.
- Detected Δv contains the model's own error: any force the model lacks shows
  up as a small "burn". The method is only as good as the force model.
- Time resolution is limited by the sample spacing (ten minutes for
  Artemis II), so detected burn durations are too long — only the TLI uses the
  published 355 s.
- Of 30 detected Chandrayaan-2 manoeuvres only 6 are modelled; the 24 trim
  burns (~158 m/s in total) are omitted.
- Launch date, mission end and probe are hard-coded for Chandrayaan-2 in the
  script (WI-009).
