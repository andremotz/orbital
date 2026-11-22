# ADR-0007: JPL Horizons as ground truth, cached for offline use

- Status: Accepted
- Date: 2026-08-02 (commit `dad086c`), recorded 2026-11-22

## Context

Initial states were estimated, and there was nothing to compare a run against
except published summary figures. JPL Horizons provides state vectors for
planets and for spacecraft — for Chandrayaan-2 an orbit solution fitted to DSN
tracking data, i.e. the trajectory actually flown.

## Decision

- Initial states and reference trajectories come from JPL Horizons
  (`data/horizons.py`), converted to SI, in the ecliptic J2000 frame.
- Celestial bodies are fetched relative to the solar-system barycentre, the
  spacecraft geocentrically, and combined locally. The two routes differ by a
  constant 116 km for Chandrayaan-2 because Horizons uses different Earth
  ephemerides for them.
- Every response is cached as JSON under `data/horizons_cache/` and committed.
  Tests and normal runs read only the cache; only an explicit refresh goes
  online.

## Consequences

- Tests are deterministic and need no network.
- Results are reproducible even if Horizons revises an orbit solution — and,
  for the same reason, the cache can go stale without anyone noticing. Each
  cache file should record when and with which query it was fetched (WI-015).
- The parser is a regular expression over Horizons' text format. A format
  change upstream breaks refreshes, not the cached runs.
- The repository carries ~0.5 MB of ephemeris data.
