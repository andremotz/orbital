# ADR-0001: Record architecture decisions

- Status: Accepted
- Date: 2026-11-22

## Context

The reasoning behind this project's design is unusually valuable — most
decisions were forced by a concrete, measured failure (an apogee stalled at
94,000 km, a burn that fired 13.6 hours late). Today that reasoning lives in
German docstrings, commit messages and README prose. It is hard to find, and
it is easy to undo a decision without knowing what it was protecting against.

## Decision

Significant decisions are recorded as ADRs under `docs/adr/`, one file per
decision, numbered sequentially, in the Context / Decision / Consequences
format. Accepted ADRs are not edited; a reversed decision gets a new ADR that
supersedes the old one.

A decision is "significant" if reversing it would change a public data format,
a numerical result, or the structure of the code.

## Consequences

- New contributors (and future us) can see *why*, not only *what*.
- Docstrings can shrink to what the code does and link to the ADR for the
  history.
- One more thing to keep up: a change that reverses an ADR without a new ADR
  is a review finding.
