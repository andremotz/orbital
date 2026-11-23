# Spec: Verification

- Status: Current (describes commit `83718a0`)
- Related: ADR-0007, ADR-0011

## 1. Layers

| Layer | Question | Where | Runs in |
|---|---|---|---|
| 1 Kernel | Is the integrator correct? | `tests/test_kernel_verification.py`, `tests/test_physics.py` | unit tests |
| 1b Parity | Does Rust compute what Python computes? | `tests/test_rust_parity.py` | unit tests, only if the kernel is built |
| 2 Milestones | Does the whole model fly the mission? | `verification.py`, `tests/test_scenario.py` | unit tests and CLI |
| 3 Tracking | How far is the run from the real trajectory? | `verification.py` (`track_against_truth`) | CLI report |

A failure in a higher layer says nothing about a lower one. Lower layers MUST
NOT depend on scenario files or Horizons data.

All tests MUST run offline; Horizons data is read from `data/horizons_cache/`.

## 2. Milestones

A milestone compares the centre-to-centre distance between `body` and
`relative_to` at simulation time `time` with `expected_distance`.

- It **holds** if the run reached `time` and
  |actual − expected| ≤ `tolerance`.
- `verified`: not holding is a failure.
- `aspirational`: reported as open, never a failure. It documents a
  historically attested value the model cannot reach yet.

Milestones are evaluated in time order within a single run. The distance is
sampled at the first step boundary at or after `time`.

## 3. Collisions

After every step, all pairs of bodies are checked. If the distance between two
centres is smaller than the sum of their radii, the run stops. Milestones not
yet reached are reported as not evaluated (`n/a`) and count as not holding.

## 4. Report and exit code

`python verification.py [scenario]` verifies one scenario — without an
argument the alphabetically first one, not all of them. It prints the
description, a collision notice if any, each milestone with expected and
measured value, the scenario's `limitations`, and a one-line result.

Exit code is 1 if a run was aborted by a collision or any `verified`
milestone does not hold; otherwise 0. An unknown scenario name ends in an
uncaught `ScenarioError`.

## 5. Tracking

`track_against_truth` runs the scenario and, at each reference sample,
records the position error and the osculating apoapsis and periapsis of the
simulated and the real state relative to a centre body.

- The position error during the **ballistic phase** (before the first burn) is
  the model's intrinsic accuracy. Reference value: 545 km after three days for
  Chandrayaan-2.
- After the first targeted burn the run deliberately leaves the recorded
  trajectory (ADR-0010); position error is then not a quality measure. Apsis
  errors remain meaningful.

## 6. Current verified claims

| Scenario | Milestone | Status |
|---|---|---|
| chandrayaan2 | Lunar capture: 17,000 km ± 6,000 km from the Moon at t = 2,484,000 s | verified |
| artemis2 | Closest lunar approach: 8,282 km ± 500 km from the Moon | aspirational |
| artemis2 | Maximum distance from Earth: 413,146.2 km ± 500 km | aspirational |
| artemis2 | Entry interface: 6,493 km ± 100 km from Earth's centre | aspirational |

Artemis II therefore has no `verified` milestone: its verification run can
only fail on a collision.

## 7. Known gaps

- Tracking assumes a geocentric cache named `<scenario>_truth` and tracks
  the first body with manoeuvres (WI-009).
- The README's numbers are asserted only loosely: the ballistic phase to
  < 1,000 km (README: 545 km), the Artemis II maximum distance to < 3 %
  (README: 1.4 %). The detected TLI is checked to ± 2 m/s. The closest lunar
  approach (16,266 km) is checked only through the ± 6,000 km capture
  milestone. A regression inside those bounds goes unnoticed (WI-010).
- A milestone can only express "distance at a time". It cannot express
  "is in a bound orbit", "periapsis below x" or "event happened by t"
  (WI-017).
- The report is German-only (ADR-0012) and has no machine-readable form.
