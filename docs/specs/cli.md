# Spec (draft): `orbital` command line

- Status: Draft — not implemented
- Related: ADR-0013, ADR-0012

## 1. Goal

Replace the root-level scripts with one command. Every subcommand takes a
scenario key and works from any directory.

## 2. Commands

| Command | Replaces | Does |
|---|---|---|
| `orbital list` | – | Lists available scenarios with name, epoch, number of bodies/burns/milestones |
| `orbital run <scenario> [--view matplotlib\|pygame\|none] [--until T]` | `main.py`, `main_matplotlib.py`, `main_rust_accelerated.py`, `main_matplotlib_rust.py` | Runs a scenario, optionally with a live view |
| `orbital verify [<scenario>...] [--json]` | `verification.py` | Milestone and tracking report |
| `orbital target <scenario> --maneuver N [--lower m --upper m] [--apply]` | `targeting.py` | Searches a manoeuvre target |
| `orbital detect-burns <scenario> [--step 30m] [--threshold 5]` | `detect_maneuvers.py` | Derives burns from the reference ephemeris |
| `orbital fetch <scenario> [--refresh]` | (missing today) | Downloads Horizons data into the cache |
| `orbital figures [--only name]` | `make_figures.py` | Regenerates README figures |
| `orbital animate [<scenario>] [--preview]` | `make_animations.py` | Regenerates animations |
| `orbital bench [<scenario>] [--steps N]` | `test_rust_integration.py`, benchmark mode of the viewers | Python vs Rust timing |

Global options: `--backend auto|python|rust` (default `auto`), `-v/--verbose`,
`-q/--quiet`, `--version`.

## 3. Behaviour

- Output is English.
- Results go to stdout, diagnostics to stderr via `logging`. Library code does
  not print.
- Exit codes: 0 success; 1 verification failed or search did not converge;
  2 usage error or unknown scenario; 3 required optional dependency or kernel
  missing.
- `--backend rust` fails with exit code 3 if the kernel is not built; `auto`
  falls back and says so once on stderr.
- `verify --json` emits one object per scenario with milestones, results,
  collision and tracking samples, for CI and for regenerating README numbers.
- Commands that need an optional dependency (`matplotlib`, `pygame`, `scipy`,
  `ffmpeg`) name the missing piece and the install command instead of a
  traceback.
- Commands that write files (`target --apply`, `fetch`, `figures`, `animate`)
  print each path written.
- Only `fetch` and `detect-burns` without a cache access the network.

## 4. Out of scope

Interactive cockpit controls (zoom, focus, time warp) belong to the viewer,
not the CLI; see WI-019.
