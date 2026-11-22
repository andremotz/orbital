# Spec: Integrator kernel contract

- Status: Current (describes commit `83718a0`)
- Related: ADR-0002, ADR-0003, ADR-0006

There are two implementations of one integration step: Python
(`physics.integrator.step`, the reference) and Rust
(`orbital_rust_kernel.rk4_step_python`). This spec states what both MUST
compute.

## 1. Inputs

For a system of n bodies:

| Name | Shape | Unit | Meaning |
|---|---|---|---|
| `mus` | (n,) | m³/s² | GM per body |
| `positions` | (n, 3) | m | |
| `velocities` | (n, 3) | m/s | |
| `thrust` | (n, 3) | m/s² | Non-gravitational acceleration per body, constant over the step |
| `j2` | (n,) | – | Zonal coefficient per body; 0 means "treat as a sphere" |
| `equatorial_radii` | (n,) | m | Used only where `j2` ≠ 0 |
| `poles` | (n, 3) | – | Unit rotation axis per body in the simulation frame |
| `time_step` | scalar | s | |

All arrays are float64. The Rust entry point MUST reject arrays whose shapes
do not match n with a `ValueError`.

## 2. Acceleration

For body i:

```
a_i = thrust_i
    + Σ_{j≠i} mu_j · (r_j − r_i) / |r_j − r_i|³
    + Σ_{s: j2_s≠0, s≠i} J2_s(r_i − r_s)
```

with, for an oblate source s, offset d = r_i − r_s, r = |d|, pole p̂,
z = d · p̂, d⊥ = d − z p̂:

```
J2_s(d) = −(3/2) · j2_s · mu_s · R_s² / r⁵ · [ (1 − 5 z²/r²) d⊥ + (3 − 5 z²/r²) z p̂ ]
```

- Self-interaction MUST be excluded without dividing by zero.
- The J2 term acts on the other bodies only; the reaction on the oblate body
  itself is neglected.
- No softening, no collision handling. Two *distinct* bodies at exactly the
  same position are not specified: Python produces non-finite values, Rust
  skips the pair. Detecting a collision before that happens is the caller's
  job.

## 3. Step

One classical RK4 step for the first-order system (ṙ = v, v̇ = a(r)) applied
to **all bodies simultaneously**: each stage evaluates `a` from the stage
positions of every body. Gravity and J2 are re-evaluated in each of the four
stages; `thrust` is the same in all four.

Outputs are new `positions` and `velocities`, shape (n, 3). Inputs MUST NOT be
modified.

## 4. Mission logic stays outside

Triggers, target resolution and burn direction are evaluated in Python by
`physics.mission.mission_accelerations` **once per step, before the step**,
and reach either kernel only as the `thrust` array. A caller that assembles
thrust itself MUST call `update_schedule` first, or triggered burns never
fire.

## 5. Parity

For identical inputs, the two implementations MUST agree to:

| Case | Relative tolerance |
|---|---|
| single step | 1e-12 |
| 5,000 steps of 60 s, with and without thrust, in and out of the ecliptic | 1e-9 |
| 1,000 steps of 30 s, oblate Earth with a low, inclined satellite | 1e-9 |

measured per body as |Δ| / max(|expected|, scale). This is enforced by
`tests/test_rust_parity.py`. Each case has a guard test showing that the
effect under test (thrust, out-of-plane motion, J2) actually changes the
result — the J2 case was added after a kernel with J2 off by 1 % passed every
other parity test.

The parity tests are skipped when the kernel is not importable. With
`ORBITAL_REQUIRE_RUST=1`, as CI sets it, a missing kernel is a failure.

Note: the two are *not* bit-identical — summation order differs between the
vectorised NumPy and the scalar Rust code, and Rust exploits Newton's third
law to visit each pair once.

Any new force term or integrator MUST be added to both implementations and to
the parity tests in the same change.

## 6. Kernel verification

Independently of parity, the reference implementation MUST satisfy
(`tests/test_kernel_verification.py`, `tests/test_physics.py`):

- global error order 4: halving the step divides the error against the exact
  two-body solution by ≈ 16;
- conservation of energy, linear and angular momentum in an isolated system
  within the bounds stated in the tests;
- the J2 acceleration matches its closed form in magnitude, falls off as
  1/r⁴, acts around the body's rotation axis rather than the ecliptic normal,
  and vanishes for spherical bodies.

Not yet covered: a check of J2's integrated effect (nodal regression rate
against the analytic secular rate), which would test the term end to end.

## 7. Known gaps

- The Rust entry point copies every input array and builds the outputs row by
  row; there is no multi-step call (WI-012).
- The fallback in `RustAcceleratedIntegrator` catches every exception from the
  kernel and continues in Python (WI-008).
