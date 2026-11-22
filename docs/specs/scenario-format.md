# Spec: Scenario file format

- Status: Current (describes `data/scenario.py` as of commit `83718a0`)
- Related: ADR-0003, ADR-0004, ADR-0005, ADR-0009, ADR-0010

A scenario is one UTF-8 JSON file in `data/scenarios/`. Its file name without
`.json` is the scenario's key (`chandrayaan2`, `artemis2`).

## 1. Conventions

- All quantities are SI: metres, metres per second, kilograms, seconds,
  newtons, m³/s².
- Frame: ecliptic J2000, origin at the solar-system barycentre.
- Vectors are JSON arrays of 3 numbers. Arrays of 2 numbers are accepted and
  padded with z = 0.
- Times are seconds since the scenario's `epoch` (simulation time 0).
- Any violation of a MUST below raises `ScenarioError` naming the offending
  element.
- Keys not listed here are ignored by the loader. They are used for
  documentation (`note`, `source`, `detected_at`, `measured_delta_v`,
  `planned_at`, `coherence`, `target_source`, `provenance`).

## 2. Top level

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Display name |
| `bodies` | array | yes, non-empty | See §3 |
| `maneuvers` | array | no | See §4 |
| `milestones` | array | no | See §5 |
| `time_step` | number | no, default 60 | Integration step in seconds |
| `epoch` | string | no | Calendar time of t = 0, e.g. `2019-07-22T10:00:00 TDB`. Informational; not parsed |
| `description`, `source` | string | no | Free text |
| `limitations` | array of string | no | Known model gaps; printed in the verification report |

## 3. Bodies

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | Unique within the scenario |
| `location` | vector | yes | Position |
| `velocity` | vector | yes | Velocity |
| `mass` | number | yes | Used only to convert `force` into acceleration |
| `radius` | number | yes | Used for collision detection and drawing |
| `mu` | number | no | GM. If absent, computed as G × `mass` |
| `relative_to` | string | no | Name of another body; `location` and `velocity` are offsets from that body's state |
| `oblateness` | object | no | `j2`, `equatorial_radius`, `pole` (vector, need not be normalised, MUST NOT be zero) — all three required |
| `color` | `[r, g, b]` | no, default white | Drawing colour |
| `is_heavy` | bool | no, default true | Rendering hint |

Rules:

- Body names MUST be unique.
- `relative_to` MUST name a body in the same scenario and MUST NOT form a
  cycle. Chains are resolved in dependency order.
- The order of bodies in the loaded scenario is the order in the file.
- A massive body SHOULD give `mu` (ADR-0003).

## 4. Manoeuvres

| Key | Type | Required | Meaning |
|---|---|---|---|
| `body` | string | yes | The body that burns |
| `duration` | number > 0 | yes | Burn duration in seconds |
| `time_start` | number | one of | Fixed ignition time |
| `trigger` | object | one of | Event that starts the burn, §4.2 |
| `force` | number | one of | Thrust in newtons; acceleration = force / mass |
| `delta_v` | number | one of | Velocity change in m/s, spread evenly over `duration` |
| `target_apoapsis` | number > 0 | one of | Radius (not altitude) of the opposite apsis after the burn |
| `target_reference` | string | no | Body the target radius refers to. Defaults to `relative_to` |
| `direction` | vector | no | Fixed thrust direction, need not be normalised. Default: prograde |
| `relative_to` | string | no | Body in whose frame "prograde" is taken. Without it, the barycentric velocity is used — almost never what is wanted |

Rules:

- Exactly one of `time_start` / `trigger` MUST be given.
- Exactly one of `force` / `delta_v` / `target_apoapsis` MUST be given.
- `body`, `relative_to`, `target_reference` and a trigger's `reference` MUST
  name existing bodies.
- A `target_apoapsis` manoeuvre MUST resolve to a reference body
  (`target_reference` or `relative_to`).

### 4.1 Semantics

- A burn is active for `ignition ≤ t < ignition + duration`, evaluated at the
  start of each step and held for the whole step.
- A negative `delta_v`, or a target that requires slowing down, reverses the
  thrust direction.
- A `target_apoapsis` Δv is solved once at ignition from vis-viva. If the
  manoeuvre has a periapsis trigger on the same body as the target reference,
  it is solved for the periapsis of the current orbit rather than for the
  ignition point.
- If the direction is undefined (zero relative velocity), the burn contributes
  nothing.

### 4.2 Triggers

| `type` | Keys | Fires when |
|---|---|---|
| `time` | `time_start` (required) | t ≥ `time_start` |
| `periapsis` | `reference` (required), `after` (default 0), `skip` (default 0) | t ≥ `after`, `skip` periapsis passes around `reference` have been counted since then, and time to the next periapsis ≤ `duration` / 2 |

Any other `type` is an error.

## 5. Milestones

| Key | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | |
| `time` | number | yes | When to check |
| `body`, `relative_to` | string | yes | The two bodies whose separation is checked; MUST exist |
| `expected_distance` | number | yes | Centre-to-centre distance in metres |
| `tolerance` | number | yes | Allowed absolute deviation in metres |
| `status` | `verified` \| `aspirational` | no, default `verified` | See [verification.md](verification.md) |
| `date`, `note`, `source` | string | no | Documentation |

## 6. Example

```json
{
  "name": "Minimal",
  "time_step": 60,
  "bodies": [
    {"name": "Earth", "mu": 3.98600435507e14, "mass": 5.9722e24,
     "radius": 6.371e6, "location": [0, 0, 0], "velocity": [0, 0, 0]},
    {"name": "Probe", "mass": 1000, "radius": 5, "relative_to": "Earth",
     "location": [6.771e6, 0, 0], "velocity": [0, 7672.6, 0]}
  ],
  "maneuvers": [
    {"body": "Probe", "relative_to": "Earth", "duration": 300,
     "trigger": {"type": "periapsis", "reference": "Earth", "after": 3600},
     "target_apoapsis": 4.2164e7}
  ],
  "milestones": [
    {"name": "Apogee reached", "time": 30000, "body": "Probe",
     "relative_to": "Earth", "expected_distance": 4.2164e7,
     "tolerance": 5.0e5, "status": "verified"}
  ]
}
```

## 7. Known gaps

- No `format_version`; no JSON Schema; unknown keys are not reported (WI-014).
- `epoch` is free text, so nothing can convert between simulation time and
  calendar time, and nothing checks that the Horizons cache matches the epoch.
- A missing `mu` on a massive body falls back to G × mass without a warning.
- Propellant consumption is not modelled; `mass` is constant.
