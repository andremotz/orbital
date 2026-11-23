# Orbital — working notes for an agent

Everything an agent needs to work on this repository without rediscovering it.
Written to be pasted in as context.

The project simulates N-body gravitation and checks itself against the
trajectories real spacecraft actually flew, taken from JPL Horizons. Its
character is **measured claims over plausible ones**: every number in the
README was produced by a script in the repo, and every limitation is written
down next to the thing it limits.

---

## 1. Layout

```
physics/          integrator, gravity, orbital elements, manoeuvre scheduling
models/           MassiveObject, State, Maneuver, Trigger, Oblateness
data/             scenarios (JSON), Horizons client, cached ephemerides
rendering/        shared plot style, projection helpers, pygame renderer
rust_kernel/      Rust implementation of the RK4 step (PyO3)
tests/            157 unittest tests
docs/figures/     generated stills
docs/animations/  generated MP4 + GIF
```

Runnable entry points, all plain scripts — no agent needed:

```bash
python make_animations.py                  # MP4 + GIF for every mission
python make_animations.py --preview NAME   # watch it live, write nothing
python make_figures.py                     # the five README stills
python verification.py [scenario]          # milestone + tracking report
python detect_maneuvers.py --probe NAME    # recover burns from a real trajectory
python targeting.py chandrayaan2           # search a trans-lunar target
./build_rust_kernel.sh                     # build the Rust kernel
python -m unittest discover tests          # full suite, ~60 s
```

Interpreter is `.venv/bin/python`. `ffmpeg` must be on the PATH for animations.

---

## 2. Physics core — what is settled, and why

**The integrator is RK4 over the whole system at once.** All bodies are pulled
through the four stages together. Integrating them one after another lets the
second body see the first already advanced — that was a real bug once.

**Everything uses GM, never mass × G.** GM is determined from spacecraft
tracking to more than ten digits; G is known to about five, and a mass derived
as GM/G inherits that. Computing `G * 1.989e30` misses the Sun's true GM by
3e-4, which alone costs 0.038 m/s of Earth's velocity per six hours. Bodies
carry `mu`; mass survives only for `F = m·a`.

**States are three-dimensional.** The Moon's orbit is inclined 5.145° against
the ecliptic, so a lunar transfer is 3D by construction. Scenario vectors may
be written with two components and are padded with z = 0.

**Earth's J2 oblateness is modelled.** Near perigee it contributes about
0.013 m/s², roughly four hundred times the Moon's pull there. The bulge sits
around the rotation axis, which is tilted 23.4393° from the ecliptic the
simulation works in — bodies therefore carry a pole direction.

**Adaptive step size** (`physics/adaptive.py`) follows the local orbital
period: seconds near a planet, hours in cruise. Built as a driver *over*
`step()`, not inside it, so the core and its parity with Rust stay untouched.
It saves 3.5× on Cassini's cruise and **nothing** on a lunar mission, where
perigee passes set the pace regardless. Both are asserted.

**The Rust kernel must stay bit-identical to Python.** `tests/test_rust_parity.py`
holds them together: one step to 1e-12, 5000 steps to 1e-9. Without it a speed
comparison would be comparing two different algorithms — which it once was.

---

## 3. Scenarios

`data/scenarios/*.json`. All SI units. Top-level keys: `name`, `description`,
`epoch`, `time_step`, `source`, `provenance`, `limitations`, `bodies`,
`maneuvers`, `milestones`.

Bodies carry `mu`, `mass`, `radius`, `color`, `location`, `velocity`, and
optionally `relative_to` (state is an offset from another body) and
`oblateness`.

Manoeuvres specify **exactly one** of `force`, `delta_v`, `target_apoapsis`,
and **exactly one** of `time_start`, `trigger`.

- `target_apoapsis` is the one that self-corrects. A recorded Δv replayed onto
  a drifted orbit does something else than where it was measured; a target is
  flown to regardless of where you start. Δv is solved at ignition via
  vis-viva and then frozen — re-solving each step would make the burn chase a
  target it is itself moving.
- `trigger: {type: periapsis, reference, after, skip}` fires half a burn
  duration before periapsis, so thrust sits symmetrically around the pass.
  `skip` counts passes rather than trusting a time window: the simulated
  period differs from the real one, and after four orbits Chandrayaan-2's
  perigee sat three hours early — a one-hour window then fell *between* two
  passes and the burn fired a full orbit late.

Milestones carry `status`: `verified` must be met and fails the run;
`aspirational` records a historical target the model cannot currently reach
and is reported, not enforced.

`limitations` is not decoration. Every scenario states what it does not model.

---

## 4. Horizons

`data/horizons.py` wraps the JPL API, parses VECTORS output, converts to SI,
and caches to disk. Tests and normal runs read the cache; only an explicit
refresh goes online.

**Two traps, both of which cost real time:**

1. **Frames.** Horizons computes geocentric *spacecraft* coordinates from the
   Earth ephemeris bundled with the mission kernel, but chains to the
   barycentre through DE441. For Chandrayaan-2 the two differ by a constant
   **116 km** — enough to wreck a perigee pass. Take the spacecraft
   geocentrically and add it to your own Earth. The residual would not shrink
   with smaller integration steps, which is what ruled out numerical error.

2. **What is relative to what.** Lunar caches are geocentric; the Cassini one
   is barycentric. Treating one as the other is off by up to 1.5 million km. A
   milestone once failed by 441,000 km for this reason while the real position
   error was 87,600 km. The milestone tool compares two *bodies*; the
   barycentre is not a body, so measuring position error against the ephemeris
   directly is the right instrument there.

Spacecraft available: Chandrayaan-2 `-152`, its lander `-153`, Artemis II
`-1024`, Artemis I `-1023`, Cassini `-82`, Huygens `-150`.

---

## 5. Recovering burns from a flown trajectory

`detect_maneuvers.py`. Between manoeuvres a spacecraft coasts, so propagating
from one ephemeris sample to the next with this project's own kernel and
booking the unexplained velocity change as Δv finds the burns. Better than
transcribing press releases: the manoeuvres come from the same trajectory the
model is later checked against.

It recovers Artemis II's TLI at **388.3 m/s against a published 388**, and
OTC-3 at **3.0 against a published 3**, over a noise floor of 0.0001 m/s.

**Not every spike is a burn.** A single bad ephemeris sample produces two
consecutive residuals that cancel — the velocity jumps and returns while the
position runs smoothly through. `summarise` measures that coherence
(|vector sum| ÷ sum of magnitudes) and discards the rest. Seven of fourteen
Artemis candidates were artefacts; one would have been booked as a 1,063 m/s
manoeuvre.

---

## 6. Verification, in layers

Kept apart on purpose — conflating them makes a failure uninterpretable.

1. **Analytic** (`tests/test_kernel_verification.py`) — Kepler's equation
   including e = 0.9, measured convergence order (must land between 3.7 and
   4.3), and the figure-eight three-body choreography. Setting each mass to
   1/G makes G·m = 1, so the published initial conditions apply directly.
   Any deviation here is unambiguously the integrator's.
2. **Mission milestones** (`verification.py`) — with the verified/aspirational
   split above.
3. **Against the flown trajectory** — position error and orbital elements.
   Elements matter once the runs drift apart in *phase*: a tiny energy error
   changes the period, and the position error then swings between zero and two
   orbit diameters while the orbit itself is fine.

Collision detection stops a run and reports it rather than integrating through
the 1/r² singularity — a probe once fell through the Earth and was flung out
at 132 km/s.

---

## 7. Measured results, as of now

| | |
|---|---|
| angular momentum drift | 2.3e-15 |
| convergence | error ÷16 per halved step — fourth order |
| Rust speedup | 7.0× plain, 12.2× with J2 |
| Chandrayaan-2, ballistic phase | 545 km after three days |
| Chandrayaan-2, closest lunar approach | 16,266 km, captured into 16,445 × 17,878 km |
| Artemis II, max distance from Earth | 418,745 km against 413,146.2 published — 1.4 % |
| Cassini, 190 days ballistic | 87,600 km on 107 million km — 0.08 % |
| Cassini, across one Venus flyby | 4.06 million km — a factor of 46 |

That last row is why a flyby chain cannot be targeted with what got
Chandrayaan-2 to the Moon. An error that looks harmless going into an
encounter decides millions of kilometres coming out, and Cassini flew four in
series.

---

## 8. Animations

`make_animations.py`. `MISSIONS` at the top is the only place a mission is
configured: runtime, fps, centre body, context bodies, scale, unit, whether
the reference is barycentric, and optional anchors.

Preview and export share one drawing path — what the window shows is what gets
written. The master is MP4; the GIF is derived from it with a palette computed
from the content, which is smaller and cleaner than exporting GIF directly.

**Three lessons that are easy to repeat:**

- **The reference must be sampled finely.** At 12-hour steps Chandrayaan-2's
  13.8-hour orbit gets six points and the ellipse draws as a hexagon. Hence
  the `*_truth_fine` caches, and 12 trajectory samples per frame.
- **Moving labels do not survive more than one companion.** They overlap near
  the centre, cover the trajectory and run off the edge. A fixed legend plus
  one colour per body (`rendering/plotstyle.py`) replaces them. No body may
  take the blue or orange belonging to the trajectories — a body mistaken for
  part of the path is worse than two similar planets. Asserted.
- **Two overlapping solid lines average to grey.** REAL (77,163,255) and
  SIMULATED (255,157,77) are near-complementary; anti-aliased together they
  render as neutral grey and the picture looks like it holds a single grey
  curve. The simulated line is therefore dashed, so the two never paint the
  same pixels.

The view follows the largest distance flown so far, smoothed, and never zooms
back in — a shrinking frame reads as a fault rather than as intent.

Cassini's cruise is **anchored**: shortly after each encounter the real state
replaces the computed one, because nothing propagates cleanly across a flyby.
Anchors are drawn as crosses and named in the log, so they cannot be mistaken
for accuracy.

---

## 9. Conventions

- **Comments and docstrings are German.** On-screen text in the animations is
  English, because the README is.
- Docstrings explain *why*, not what. The reasoning behind a choice belongs
  next to it.
- Tests assert the reason, not just the behaviour — including negative results
  (adaptive stepping saving nothing on lunar missions is asserted).
- Names are spelled out: `massiveObject_current`, not `mo`.
- Nothing is claimed that was not measured. If a number appears in the README
  or a commit message, a script in the repo produced it.

---

## 10. Open items

- **Targeting a flyby chain** — not a matter of more effort; four coupled
  gravity assists at this sensitivity is a research problem.
- Artemis II still replays measured Δv; the same targeting treatment should
  close its remaining 1.4 %.
- The captured lunar orbit is 16,445 × 17,878 km against 114 × 18,072 km
  actually achieved. Capture works; the descent to a low orbit is not modelled.
- Solar radiation pressure, the remaining planets, higher terms of Earth's
  gravity field. A few m/s per perigee pass are still unaccounted for.
- A 3D view — the simulation is 3D, every view still projects onto the ecliptic.
- Fetching a new mission's ephemerides is still a manual step; a
  `fetch_mission.py` would make a new mission one command plus a scenario file.
