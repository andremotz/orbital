# Specifications

A spec states what code or data must do, precisely enough to write a test
against it. The words MUST, SHOULD and MAY are used in the RFC 2119 sense.

| Spec | Status | Describes |
|---|---|---|
| [scenario-format.md](scenario-format.md) | Current | The JSON scenario file format as the loader accepts it today |
| [kernel-contract.md](kernel-contract.md) | Current | What an integrator step computes, and the Python ↔ Rust parity rule |
| [verification.md](verification.md) | Current | The verification layers, milestone semantics, report and exit codes |
| [simulation-run-api.md](simulation-run-api.md) | Draft | Proposed `Simulation` run API (ADR-0014) |
| [cli.md](cli.md) | Draft | Proposed single `orbital` command (ADR-0013) |

**Current** specs describe implemented behaviour; a difference between spec
and code is a bug in one of them. **Draft** specs describe intended behaviour
that is not implemented yet.
