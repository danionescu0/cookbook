# Use MADR to record architecture decisions

## Context and Problem Statement

Cookbook's design decisions — data-model shape, API contracts, worker pipeline structure — have
so far lived only in commit messages, code comments, and contributors' memory. As the app grows
(imports, sharing, AI extraction, nutrition, notifications), non-obvious tradeoffs are getting
harder to reconstruct later, and easy to accidentally re-litigate or regress. We need a
lightweight, consistent place to write these decisions down.

## Decision Drivers

* Low overhead — a record should be quick to write and quick to read, not a bureaucratic gate.
* Plain Markdown, versioned alongside the code, reviewable in the same pull request as the
  change it documents.
* A structure that consistently captures *why*, not just *what*, including options that were
  considered and rejected.

## Considered Options

* No formal ADRs — keep relying on commit messages and code comments.
* A wiki or external document store.
* [MADR](https://adr.github.io/madr/) (Markdown Architecture Decision Records) committed to the
  repository under `docs/adr/`.

## Decision Outcome

Chosen option: "MADR committed to the repository under `docs/adr/`", because it keeps decisions
next to the code they affect, versioned and reviewable exactly like everything else, with a
template that already asks the right questions.

### Consequences

* Good, because decision history survives independently of any one person's memory and any one
  commit message.
* Good, because reviewers can request an ADR update in the same PR that changes behavior.
* Neutral, because it adds one more file per significant decision — kept intentionally sparse to
  avoid ADR fatigue.
