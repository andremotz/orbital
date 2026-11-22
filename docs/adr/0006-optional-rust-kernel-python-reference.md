# ADR-0006: Optional Rust kernel, Python as the reference implementation

- Status: Accepted
- Date: 2026-08-01 (commit `88bbe2f`), recorded 2026-11-22

## Context

A targeting search runs the same multi-week mission dozens of times. In pure
Python/NumPy one RK4 step for four bodies is dominated by interpreter
overhead. At the same time the project must stay runnable with nothing but
`pip install`, and the physics must stay readable.

## Decision

- The Python integrator (`physics/integrator.py`) is the reference. It defines
  the semantics.
- A Rust kernel (`rust_kernel/`, PyO3) implements the same RK4 step, including
  J2 and externally supplied thrust. It is optional: if the module cannot be
  imported, `RustAcceleratedIntegrator` falls back to Python.
- Mission logic (triggers, targeting, burn direction) stays in Python and is
  shared by both paths; the kernel receives thrust as a plain acceleration
  array.
- `tests/test_rust_parity.py` holds the two implementations together
  (relative tolerance 1e-12 for one step, 1e-9 over 5,000 steps).

The contract is specified in [specs/kernel-contract.md](../specs/kernel-contract.md).

## Consequences

- Measured ~7.4× speedup on four bodies.
- Every force model has to be implemented twice and kept in parity.
- The parity tests are skipped when the kernel is not built. Without CI that
  builds the kernel, the Rust path is effectively untested on a fresh clone
  (WI-001).
- The kernel is called once per step and copies every array on the way in and
  out. Most of the remaining cost is that boundary, not the arithmetic
  (WI-012).
- The build is a shell script that copies a `.so` into the repository root
  rather than a standard `maturin` build (WI-005).
- The fallback also triggers on *any* exception inside a step, which can hide
  a kernel bug behind a silently slower run (WI-008).
