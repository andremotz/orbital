# Work items

Backlog as of 2026-11-24. WI-001 (CI), WI-002 (`pyproject.toml`), WI-003
(statements that were no longer true) and WI-004 (ruff) are done. Items are ordered by
priority within each group. Sizes: **S** ≤ half a day, **M** 1–2 days,
**L** more.

A work item is done when its acceptance criteria hold and the test suite is
green. Done items are removed from this file; the commit message carries the
ID.

| ID | Title | Size | Depends on |
|---|---|---|---|
| **Next — structure** | | | |
| [WI-005](#wi-005-package-layout-and-maturin-build) | Package layout and maturin build | L | – |
| [WI-006](#wi-006-single-cli-remove-duplicate-entry-points) | Single CLI, remove duplicate entry points | M | WI-005 |
| [WI-007](#wi-007-simulation-run-object) | `Simulation` run object | L | WI-005 |
| [WI-008](#wi-008-no-silent-backend-fallback-no-prints-in-library-code) | No silent backend fallback, no prints in library code | S | – |
| [WI-009](#wi-009-make-tools-mission-agnostic) | Make tools mission-agnostic | M | – |
| [WI-010](#wi-010-pin-the-readmes-numbers-with-tests) | Pin the README's numbers with tests | M | WI-009 |
| [WI-011](#wi-011-honour-burn-durations-exactly) | Honour burn durations exactly | M | – |
| [WI-012](#wi-012-make-mission-runs-fast) | Make mission runs fast | M | WI-007 |
| [WI-013](#wi-013-translate-to-english) | Translate to English | M | ADR-0012 accepted |
| [WI-014](#wi-014-scenario-schema-and-format-version) | Scenario schema and format version | S | – |
| [WI-015](#wi-015-horizons-fetch-command-and-cache-provenance) | Horizons fetch command and cache provenance | S | – |
| **Later — physics and features** | | | |
| [WI-016](#wi-016-targeting-for-artemis-ii) | Targeting for Artemis II | M | WI-007 |
| [WI-017](#wi-017-event--and-orbit-based-milestones) | Event- and orbit-based milestones | M | WI-007 |
| [WI-018](#wi-018-multi-parameter-targeting-and-low-lunar-orbit) | Multi-parameter targeting and low lunar orbit | L | WI-016, WI-017 |
| [WI-019](#wi-019-cockpit-and-3d-view) | Cockpit and 3D view | L | WI-006 |
| [WI-020](#wi-020-error-budget-and-further-perturbations) | Error budget and further perturbations | L | WI-010 |
| [WI-021](#wi-021-collision-response) | Collision response | S | WI-007 |
| [WI-022](#wi-022-repository-hygiene) | Repository hygiene | S | – |

---

## Next — structure

### WI-005: Package layout and maturin build

**Why / what.** ADR-0013, points 1 and 4. Move-only: no behaviour change.
`pyproject.toml` exists, but has package discovery switched off — it only
declares dependencies, because the top-level packages are named `data`,
`models`, `physics`, `rendering`. This item gives them a real package.

**Acceptance.** Tests run from any directory with no `sys.path` manipulation
(11 files do it today). `pip install .` builds the kernel when a Rust
toolchain is present and installs a working pure-Python package when not. No
build artefact lands in the repository root.

### WI-006: Single CLI, remove duplicate entry points

**Why.** Four viewers (`main.py`, `main_rust_accelerated.py`,
`main_matplotlib.py`, `main_matplotlib_rust.py`), the last two near-duplicates
of ~450–525 lines. `test_rust_integration.py` and `test_matplotlib_rust.py`
in the root look like tests but are demo scripts. `main.py` has a hard-coded
zoom chain and German comments.

**What.** Implement [specs/cli.md](specs/cli.md). One matplotlib viewer with
the backend as an option. Decide whether the pygame viewer is kept (as an
extra) or dropped. Delete the root scripts as their subcommands land.
`rust_trail_optimizer.py`: keep only if a measurement shows it helps. Its
"Rust" path calls no Rust, and runs the whole Python trail processing once
per trail buffer instead of once per call.

**Acceptance.** The repository root contains no `.py` files. Every command in
the README is an `orbital …` command.

### WI-007: `Simulation` run object

**Why / what.** ADR-0014 and [specs/simulation-run-api.md](specs/simulation-run-api.md),
migration steps 1–4.

A concrete bug this removes: `MassiveObject.copy()` shares `Maneuver` objects
between copies, so the Python and the Rust run of the benchmark share ignition
state.

**Acceptance.** `targeting.py` no longer reloads the JSON per evaluation.
A test runs the same scenario object twice and gets identical results. A test
shows two simulations of one scenario do not influence each other. `reset()`
and `copy()` are gone.

### WI-008: No silent backend fallback, no prints in library code

**Why.** `RustAcceleratedIntegrator.calculate_states_batch` catches every
exception from the kernel, prints a warning and continues in Python — for the
rest of that step only, on every step. A kernel bug becomes a slow run with
plausible output. `rust_integration.py` also prints at import time and on
every integrator construction (visible as noise in the test output).

**What.** Fall back only at construction time, only on `ImportError`. Let
kernel errors propagate. Replace `print` with `logging`. Expose which backend
is active.

**Acceptance.** Test: a kernel call that raises makes the step raise. Test
output is free of backend banners.

### WI-009: Make tools mission-agnostic

**Why.** Adding a third mission currently needs code changes:
`verification.py` assumes a geocentric reference in `<scenario>_truth` and
tracks "the first body with manoeuvres"; `detect_maneuvers.py` hard-codes launch date, mission end, probe
mass and system bodies; `targeting.py` defaults to manoeuvre index 4 and
lunar bounds, and picks "the first body with manoeuvres" as the probe;
`BODY_IDS` in `data/horizons.py` is a fixed table.

**What.** Move these into the scenario: a `spacecraft` key, a `reference`
block (Horizons id, centre, time span, cache names), and per-manoeuvre search
bounds. Tools read them from there.

**Acceptance.** Adding a mission requires a scenario file and cache files
only. (`verification.py artemis2` already prints a tracking section.)

### WI-010: Pin the README's numbers with tests

**Why.** The headline results — 545 km after three days ballistic, Artemis II
apogee 1.4 % off, TLI detected at 388.3 m/s, closest approach 16,266 km — are
asserted only loosely, if at all: < 1,000 km, < 3 %, ± 2 m/s, and the closest
approach only through a ± 6,000 km milestone. A change can make them markedly
worse without failing anything, and nothing updates them when a change makes
them better.

**What.** Regression tests with explicit bounds for each number. Emit the
numbers as JSON from the verification run and generate the README table from
it (or at least have a test compare the two). Promote Artemis II's
maximum-distance milestone to `verified` with a tolerance that reflects the
1.4 %; today the scenario has no `verified` milestone at all.

**Acceptance.** Worsening the model (e.g. disabling J2) fails a named test.

### WI-011: Honour burn durations exactly

**Why.** Thrust is sampled at the start of a step and held for the step, so
burns last a whole number of steps: the published 355 s TLI runs for 360 s
(+1.4 % Δv for a `delta_v` burn). Trigger times are quantised the same way.

**What.** Either split the step at burn boundaries (two sub-steps), or scale
the thrust in the first and last step by the covered fraction. Make the
choice in both kernels' callers, since thrust is assembled in Python.

**Acceptance.** Test: a `delta_v` burn of 355 s at a 60 s step delivers its Δv
to within 0.1 % in free space. Parity tests still pass.

### WI-012: Make mission runs fast

**Why.** The Rust step is 5.8× faster than Python, about 15× with J2, but a
Chandrayaan-2 run with its six manoeuvres gains only 1.8× (3.25 s → 1.79 s for
20,000 steps, freshly loaded scenario per run). Before every step Python
checks every pending periapsis trigger — osculating elements and time to
periapsis — at roughly 85 µs per step against 4.5 µs for the Rust step; a
profile puts ~93 % of the run there. The array gathering and copying at the
boundary come second.

**What.**

1. Make the trigger check cheap: skip a trigger before its `after` time
   (today the elements are computed from t = 0 to count passes), and compute
   elements once per step and reference body, not once per trigger.
2. Then the boundary: borrow the NumPy arrays (`PyReadonlyArray`) instead of
   copying, write into caller-provided arrays, and add `rk4_steps(…, n)` for
   coasts between trigger windows, per
   [specs/simulation-run-api.md](specs/simulation-run-api.md) §6.
3. A benchmark command that loads the scenario afresh for every run, with
   results recorded in `RUST_INTEGRATION.md`. (`PerformanceBenchmark` runs on
   copies that share manoeuvre objects, so the second run finds them already
   fired.)

**Acceptance.** A Chandrayaan-2 mission run gains at least 4× over pure
Python. Parity tolerances unchanged. A full targeting search is measurably
faster.

### WI-013: Translate to English

**Why / what.** ADR-0012. Docstrings, comments, error messages, CLI output,
scenario `note`/`limitations`/`description`, `RUST_INTEGRATION.md`,
`requirements.txt` comments, `.gitignore` comments. Long historical
explanations move to the matching ADR instead of being translated in place.

**Acceptance.** No German text outside quoted sources. Translation commits
contain no functional change and are listed in `.git-blame-ignore-revs`.

### WI-014: Scenario schema and format version

**Why.** Unknown keys are silently ignored, so `"durration"` on an optional
key or `"targetApoapsis"` goes unnoticed. There is no version to migrate from.
A massive body without `mu` silently falls back to G × mass (ADR-0003).

**What.** `format_version` at top level. A JSON Schema generated from, or
checked against, [specs/scenario-format.md](specs/scenario-format.md).
Documentation-only keys move under a `meta` object per element so everything
outside `meta` can be validated strictly. Warn when a body with other bodies
orbiting it has no `mu`. Parse `epoch` into a real time value.

**Acceptance.** A scenario with an unknown key outside `meta` is rejected with
the key's path. Both shipped scenarios validate.

### WI-015: Horizons fetch command and cache provenance

**Why.** The cache is committed, but the code path that produced it is gone:
`data/horizons.py` mentions `refresh_cache` and `python -m data.horizons`,
neither of which exists. Cache files record `source` and `step` but not the
query, the fetch date, or the Horizons solution id — so a cache cannot be
reproduced or checked for staleness.

**What.** A `fetch` command that rebuilds every cache file a scenario needs.
Store query parameters, retrieval timestamp and the response's solution/
ephemeris header in each file. Add a timeout and a clear error for network
failures.

**Acceptance.** Deleting `data/horizons_cache/` and running the fetch command
restores files that make the test suite pass.

---

## Later — physics and features

### WI-016: Targeting for Artemis II

**Why.** Artemis II still replays measured Δv (ADR-0010) and ends 1.4 % off
in maximum distance; non-TLI burns are smeared over ten-minute detection
windows.

**What.** Give the TLI a target and search it. A free return is not an
apoapsis problem — target perilune distance (8,282 km) or entry-interface
radius instead, which needs WI-017's events.

**Acceptance.** Closest-approach and maximum-distance milestones are
`verified`.

### WI-017: Event- and orbit-based milestones

**Why.** A milestone is "distance d at time t". With event-triggered burns the
time itself is uncertain, which forces tolerances like ± 6,000 km on a
17,000 km capture orbit — it cannot distinguish a good capture from a poor
one.

**What.** Milestone kinds on top of the event stream: closest approach to a
body (distance, within a time window), bound orbit around a body with
periapsis/apoapsis ranges, maximum distance, time of event. Keep the existing
kind for compatibility.

**Acceptance.** Chandrayaan-2 capture is asserted as "bound around the Moon,
apsides within x". The three Artemis II milestones are expressed as events.

### WI-018: Multi-parameter targeting and low lunar orbit

**Why.** The captured orbit is 16,445 × 17,878 km against 114 × 18,072 km
flown. One parameter (TLI apoapsis) cannot control both arrival distance and
phasing, and the lunar-orbit lowering burns are not modelled.

**What.** Target periapsis as well as apoapsis; add triggers for apoapsis and
sphere-of-influence entry; a differential-correction (shooting) solver over
several manoeuvre parameters with a B-plane or perilune target; model the
four lunar-bound burns. Replace the "searched TLI apoapsis" stand-in with a
physical target. Parallelise the grid stage.

**Acceptance.** Perilune after LOI within 500 km of flown; final orbit within
10 % of 114 × 18,072 km → later 100 km circular.

### WI-019: Cockpit and 3D view

**Why.** README "in progress" since the first commits: zoom and focus control,
distances, polar coordinates; and every view still projects onto the ecliptic
although the simulation is 3D.

**What.** One viewer: focus on any body, body-centred and rotating
(Earth–Moon) frames, time-warp control, a panel with osculating elements,
distances and next-burn countdown, a 3D or switchable-plane view, markers for
events. Overlay of the reference trajectory.

**Acceptance.** Following Chandrayaan-2 from launch to capture is possible
without editing code.

### WI-020: Error budget and further perturbations

**Why.** "A few m/s per perigee pass are still unaccounted for". Before adding
physics, find out what the 545 km / 3 days is made of.

**What.**

1. Step-size study (60 s / 10 s / 1 s) on the ballistic phase — separates
   truncation from modelling error and decides ADR-0015.
2. Estimate each missing term's magnitude along the real trajectory: J3/J4
   and tesseral terms, drag at the ~170 km perigee, solar radiation pressure,
   Jupiter and Venus, lunar J2, relativistic correction.
3. Implement in order of size, each in both kernels with parity tests.
4. Check Earth's pole: a fixed J2000 pole ignores precession/nutation since
   2000 — quantify.

**Acceptance.** A table in the docs: term, magnitude, effect on the 3-day
error. The ballistic error drops, and the bound in WI-010 is tightened.

### WI-021: Collision response

**Why.** Impacts are detected and stop the run in `verification.py`, but the
viewers keep integrating through the singularity.

**What.** Handle a collision in the run object: stop, or mark the smaller body
as landed/destroyed and remove it from the integration. Emit an event.
Detect between steps as well (a fast body can tunnel through a small one in
60 s).

**Acceptance.** A probe aimed at the Moon ends with a `collision` event in
every front end, with no non-finite states.

### WI-022: Repository hygiene

- **Binary assets.** `docs/animations/` is 13 MB and every regeneration adds
  another copy to history. Commit only the GIFs shown in the README, or move
  media to Git LFS / release assets.
- **`.gitignore`** is the generic Python template (Django, Flask, Scrapy,
  Celery …). Trim it; add `rust_kernel/target/`, `.venv/`, `.ruff_cache/`.
- **LICENSE** is the full GPL text; state the licence and SPDX id in the
  README and in `pyproject.toml`/`Cargo.toml`.
- **CONTRIBUTING.md**: setup, how to run the layers of verification, how to
  add a scenario, commit conventions, the ADR/spec/work-item workflow.
- **CHANGELOG.md** and a first tag (`v0.1.0`) now that WI-001–WI-003 are in.
- **CITATION / data attribution**: JPL Horizons and DE440/441 as data sources.
- **README**: put result and animation first, setup second, the derivations
  after; link to `docs/`.
- **Dependabot** (or Renovate) for pip, cargo and GitHub Actions.
- **Type hints** on the public API and a `mypy`/`pyright` job, once WI-007 has
  settled the shapes.
- **Move to `pytest`**: parametrised tests, markers for slow tests (the suite
  takes ~40 s, most of it full mission runs) and for tests needing the kernel.
