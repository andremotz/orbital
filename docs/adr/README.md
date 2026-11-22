# Architecture Decision Records

Each record has the sections **Context**, **Decision** and **Consequences**.
Status is one of `Proposed`, `Accepted`, `Superseded by ADR-xxxx`.

ADRs 0002–0011 were written retroactively on 2026-11-22. They document
decisions that were already in the code; the date in each record is the date
of the commit that introduced the decision.

| # | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-simultaneous-fixed-step-rk4.md) | Integrate all bodies simultaneously with fixed-step RK4 | Accepted |
| [0003](0003-gravitational-parameters-instead-of-mass.md) | Use GM instead of G × mass | Accepted |
| [0004](0004-3d-state-in-ecliptic-j2000.md) | 3D state vectors in the ecliptic J2000 frame | Accepted |
| [0005](0005-scenarios-as-json-data.md) | Mission data lives in JSON scenarios, with provenance | Accepted |
| [0006](0006-optional-rust-kernel-python-reference.md) | Optional Rust kernel, Python as the reference implementation | Accepted |
| [0007](0007-horizons-as-ground-truth-with-offline-cache.md) | JPL Horizons as ground truth, cached for offline use | Accepted |
| [0008](0008-derive-burns-from-flown-trajectory.md) | Derive the burn profile from the flown trajectory | Accepted |
| [0009](0009-event-triggered-maneuvers.md) | Fire manoeuvres on orbital events, not by the clock | Accepted |
| [0010](0010-closed-loop-apoapsis-targeting.md) | Closed-loop targeting: burns name a target apoapsis | Accepted |
| [0011](0011-layered-verification.md) | Layered verification with verified and aspirational milestones | Accepted |
| [0012](0012-english-as-single-project-language.md) | English as the single project language | Proposed |
| [0013](0013-installable-package-and-single-cli.md) | Installable package with a single CLI | Proposed |
| [0014](0014-separate-scenario-definition-from-run-state.md) | Separate scenario definition from run state | Proposed |
| [0015](0015-adaptive-step-size-integration.md) | Adaptive step-size integration | Proposed |

## Template

```markdown
# ADR-NNNN: Title

- Status: Proposed | Accepted | Superseded by ADR-xxxx
- Date: YYYY-MM-DD

## Context
What forces are at play? What problem needs a decision?

## Decision
What we do, stated in the active voice.

## Consequences
What becomes easier, what becomes harder, what we now have to live with.
```
