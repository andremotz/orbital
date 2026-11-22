# ADR-0013: Installable package with a single CLI

- Status: Proposed
- Date: 2026-11-22

## Context

The repository root holds 13 Python scripts next to four top-level packages
with generic names (`data`, `models`, `physics`, `rendering`). Consequences
today:

- Everything only works when run from the repository root; tests patch
  `sys.path` by hand.
- There are four entry points for viewing a simulation (`main.py`,
  `main_rust_accelerated.py`, `main_matplotlib.py`, `main_matplotlib_rust.py`).
  The two matplotlib ones are near-duplicates.
- Two files named `test_*.py` in the root are demo/benchmark scripts, not part
  of the test suite.
- `pyproject.toml` declares the dependencies, extras and Python floor
  (WI-002), but has package discovery switched off: installing it installs
  only the dependencies, and the code runs from the checkout.
- The Rust kernel is built by a shell script that copies a `.so` into the
  root.

## Decision

1. Move the code into one package, `orbital/` (src layout), with subpackages
   `physics`, `models`, `scenario`, `horizons`, `verification`, `targeting`,
   `viz`. Scenario files and the Horizons cache become package data.
2. Switch packaging on in the existing `pyproject.toml`; the extras (`viz`,
   `pygame`, `targeting`, `dev`) stay as declared.
3. One console script, `orbital`, with subcommands:
   `run`, `verify`, `target`, `detect-burns`, `figures`, `animate`, `bench`.
   The integrator backend is an option (`--backend auto|python|rust`), not a
   separate program.
4. Build the Rust kernel with `maturin` as an optional extension module of the
   same package (`orbital._kernel`).
5. Root scripts are removed once their subcommand exists.

## Consequences

- `pip install -e .[dev]` gives a working environment; imports work from
  anywhere; the `sys.path` patches go away.
- One place to document usage; the README shrinks.
- Wheels with a compiled kernel become possible.
- A large move-only change. It should land as its own commit(s) with no
  behaviour change, after CI exists (WI-001) so the move is verifiable.
- README commands and regenerate instructions change.

## Alternatives considered

- **Keep flat scripts with the dependency-only `pyproject.toml`.** The
  current state: dependencies are declared, but the duplicated entry points
  and the cwd dependence remain.
- **Keep the shell build.** Works on macOS/Linux, but no wheels, no Windows,
  and a build artefact in the source root.
