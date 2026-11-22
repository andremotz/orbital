# ADR-0005: Mission data lives in JSON scenarios, with provenance

- Status: Accepted
- Date: 2026-08-01 (commit `2491d65`), recorded 2026-11-22

## Context

Bodies, initial states and burns were hard-coded in Python. Adding a mission
meant editing source, and nothing recorded where a number came from.

## Decision

A mission is one JSON file under `data/scenarios/`. It holds bodies,
manoeuvres and milestones in SI units, and — alongside the values — their
`source`, `provenance` and known `limitations`. The loader
(`data/scenario.py`) validates strictly and raises `ScenarioError` with the
offending path instead of guessing: unknown references, reference cycles,
ambiguous manoeuvre definitions and malformed vectors are all errors.

Bodies may be positioned `relative_to` another body; the loader resolves the
chain.

The format is specified in [specs/scenario-format.md](../specs/scenario-format.md).

## Consequences

- A new mission is a data change, not a code change (Artemis II was added this
  way).
- The limitations of a scenario travel with it and are printed in the
  verification report.
- The format has no version field and no machine-readable schema; unknown keys
  are silently ignored, so a typo in an optional key goes unnoticed (WI-014).
- Tools write back into scenario files (`targeting.py --apply`), so the files
  are partly generated. That is recorded per value (`target_source`), not per
  file.
