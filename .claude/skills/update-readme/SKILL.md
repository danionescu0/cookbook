---
name: update-readme
description: Use this proactively — without being asked — at the end of any turn where you added a feature, changed an API/data-model/workflow, or made a notable architectural decision in this repo (cookbook). Checks whether readme.MD reflects what was just built and updates it if not. Skip only for changes with no effect on documented behavior (pure refactors, formatting, dependency bumps, test-only changes).
---

# Keep readme.MD current

`readme.MD` at the repo root is this project's single source of truth for what the app does, how
it's built, and why. It is long and deliberately detailed — treat it as living documentation, not
a changelog: update the sections that describe current behavior, don't just append a note saying
something changed.

## When to run this

At the end of any task that changed what the app *does* or *how it's built* — a new feature, a
changed API/data model, a new background job, a new admin setting, a UI behavior change, a
meaningful bugfix that changes documented behavior, or a non-trivial design tradeoff. Do this
without waiting for the user to ask "update the readme" — treat it as part of finishing the task,
the same way you'd run the test suite.

Skip it for changes that don't affect anything readme.MD describes: pure refactors, formatting,
dependency version bumps, or test-only changes with no behavior change.

## What to check, in order

Read the relevant part of each section before deciding whether it needs a change — most tasks only
touch 2-4 of these, not all of them:

1. **Status** (checklist near the top) — add a new `- [x]` bullet for a finished feature, in the
   same terse-but-complete style as the surrounding ones. If a change makes an existing `[ ]`
   bullet true, flip it and update the wording (this has been missed before — e.g. the reverse
   proxy stayed unchecked long after it was actually built).
2. **Features** — a short, punchy bullet list. Add one if the change is user-facing enough to
   belong here.
3. **Architecture / Tech Stack** — only touch these if a new technology, service, or queue was
   introduced, or an existing row's description is now wrong (e.g. a model swap, a new library).
4. **Project Structure** (the annotated file tree) — this is the part most likely to silently go
   stale. Every new file, and every file whose responsibility meaningfully changed, needs its
   comment updated. Match the existing terse `# what it does / key detail` comment style.
5. **Core Workflows** — if the change adds or alters a step in how a feature actually works end to
   end, update the relevant numbered workflow, or add a new one following the existing numbering
   and cross-reference style (`see workflow #N`, `see [Design Decisions](#design-decisions)`).
6. **Data Model (sketch)** — any new table, column, or changed constraint goes here, with the same
   inline rationale style the existing entries use (not just the column list).
7. **Deployment** — only for changes to how the app is built/deployed/configured at the infra
   level.
8. **Testing** — update the per-layer test counts (they're exact numbers, not "many") and append a
   short clause describing what the new tests cover, matching the existing dense comma-separated
   style. If you did a live/manual verification (ran it against the real dev stack, checked real
   data, watched it in the browser), add a bullet to the "Notes on the current setup" list
   describing what was actually verified and how — this repo's convention is to record real
   verification, not just "tests pass."
9. **Design Decisions** — if the change involved a real tradeoff (not just "did the obvious
   thing"), add a bullet explaining *why*, in the same voice as the existing ones: what problem
   forced the decision, what alternatives were considered/rejected, and any surprising consequence.
   This is usually the most valuable section to get right — it's what stops the same debate from
   happening twice.

Leave **Getting Started**, **Contents**, and **Original Spec** alone unless the change directly
affects them (e.g. a new required `.env` var, which _would_ need a Getting Started update).

## Style notes specific to this file

- Match the existing voice: dense, narrative, specific numbers over vague words ("191 tests" not
  "many tests"), cross-references via `[Section Name](#anchor)` rather than duplicating content.
- Don't add a separate "changelog" or "recent changes" section — integrate the update into the
  section that describes the relevant behavior, so the doc always reads as current state.
- Don't rewrite or reflow paragraphs you didn't need to touch, even if you could tighten them —
  keep diffs scoped to what actually changed.
- If you're not sure a section needs a change, grep it for the old behavior first (e.g. an old
  model name, an old test count, an old file name) rather than assuming.

## After updating

Run through the section list above as a mental checklist and report — briefly — which sections you
touched and which you deliberately left alone, so the user can sanity-check the scope. Don't commit
the change unless the user has asked for that (same standing rule as everywhere else in this repo).
