# ADR-0012: English as the single project language

- Status: Proposed
- Date: 2026-11-22

## Context

The repository mixes languages. The README, commit messages, figure and
animation labels are English. Docstrings, comments, error messages, CLI
output, scenario notes/limitations and `RUST_INTEGRATION.md` are German.
Identifiers are English. The verification report a user sees on the command
line is German, the README that explains it is English.

For a public repository this narrows the audience for exactly the part that
is most valuable here — the reasoning in the docstrings.

## Decision

English is the language for everything in the repository: identifiers,
docstrings, comments, error messages, CLI output, scenario metadata and
documentation.

Migration is incremental, file by file, each as a pure-translation commit with
no behaviour change. New and touched code is written in English from now on.
Tests that assert on message text are updated in the same commit.

## Consequences

- One audience, one vocabulary; the README can quote program output verbatim.
- A sizeable, purely mechanical diff across almost every file, which makes
  `git blame` noisier. Keeping translation commits separate from functional
  ones (and listing them in `.git-blame-ignore-revs`) limits that.
- Risk of losing nuance in the carefully written German explanations. Long
  historical explanations should move into ADRs rather than be translated in
  place.

## Alternatives considered

- **Keep German docstrings.** No work, but keeps the split.
- **Translate only user-facing output.** Fixes the README/CLI mismatch, leaves
  the reasoning inaccessible.
