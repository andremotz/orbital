# Project documentation

| Folder / file | What it holds |
|---|---|
| [`adr/`](adr/README.md) | Architecture Decision Records — why the project is built the way it is |
| [`specs/`](specs/README.md) | Specifications — contracts that code and data must satisfy |
| [`work-items.md`](work-items.md) | Backlog — concrete, prioritised pieces of work |
| `figures/`, `animations/` | Generated assets embedded in the top-level README |

## How the three relate

- An **ADR** records a decision and the reasoning behind it. It is immutable
  once accepted; a changed decision gets a new ADR that supersedes the old one.
- A **spec** describes behaviour precisely enough to test against. Specs are
  living documents and are updated together with the code.
- A **work item** is a unit of work. It links to the ADR that motivates it and
  the spec it has to satisfy, and is deleted (or moved to a changelog) once
  done.
