# Paste-text recipe import

## Context and Problem Statement

Today a recipe gets into Cookbook three ways: import from a URL, import from a bookmarks file, or
type every field by hand on `/submit-recipe`. There is no way to take a block of text a user
already has — a WhatsApp message, an email, a photo-OCR dump, a page copied from a notebook — and
turn it into a structured recipe without retyping it field by field. How should Cookbook let users
import a recipe from pasted free-form text, reusing as much of the existing import pipeline as
possible?

## Decision Drivers

* Reuse the existing `ImportJob` → RabbitMQ → worker → `claude_client` pipeline rather than
  building a parallel one.
* `worker/app/claude_client.py` already has `parse_recipe_from_text()`, built for Instagram
  captions — exactly the same "messy free-form text → structured, translated recipe" problem.
* Extraction calls use a forced `tool_choice`, which guarantees structured output but cannot also
  take an agentic web-search turn first.
* No new secrets, services, or dependencies — everything must ride on the already-configured
  Anthropic key and SDK.
* The `max_imports_per_user` quota must apply uniformly across every import origin.

## Considered Options

* Extend `/submit-recipe`'s manual entry form with a "paste to prefill" helper.
* A dedicated, separate ingestion service/route outside the `ImportJob` pipeline.
* A fourth `ImportJob` type (`PASTE`) that reuses the existing pipeline, skipping the fetch step.

## Decision Outcome

Chosen option: "A fourth `ImportJob` type (`PASTE`)", because it reuses the queueing, quota,
review-panel, and worker-extraction machinery that URL and bookmark imports already have, with
the only new work being the extraction prompt/tool and the fetch step being skipped (there is
nothing to fetch).

### Consequences

* Good, because `PendingImportsPanel`, quota enforcement, and the review/acknowledge flow all
  apply to paste imports for free.
* Good, because `ImportJobType` is `Enum(..., native_enum=False)` (a `VARCHAR`), so adding
  `PASTE` needs no enum migration.
* Bad, because `DELETE /recipes/{id}` cleans up its originating `ImportJob` by matching
  `ImportJob.source == recipe.source_url`; a paste job has no URL, so its `done` job row survives
  recipe deletion. Accepted as harmless — `done` jobs are already filtered out of every
  in-progress list — rather than fixed here.

## Sub-decisions

### Two AI calls, not one

Every existing extraction call uses forced `tool_choice={"type": "tool", ...}`, which guarantees
structured output but makes the model emit that tool *immediately* — it can never take a
server-side web-search turn first. Rather than rewrite extraction into an agentic tool-use loop (a
large, risky change to the most load-bearing function in the app), web research is a **separate,
preceding, freeform call** (`research_recipe_context`) whose text output is fed into the
unchanged, still-forced extraction call (`parse_recipe_from_pasted_text`) as reference material
only. The extraction guarantee is preserved untouched. `research_recipe_context` is skipped
silently when the configured provider is DeepSeek (its Anthropic-compatible endpoint has no
server-side web search), and is best-effort: any failure degrades to plain extraction rather than
failing the import.

### `recipes.is_from_import` instead of a `source_url` proxy

A paste-import recipe has no `source_url`, but two places used "`source_url` is not null" as a
proxy for "this came from an import": `PendingImportsPanel`'s review-card predicate and
`POST /recipes/{id}/acknowledge-import`'s guard. Both switch to a new `is_from_import` boolean
column (backfilled `= source_url IS NOT NULL` for existing rows), so a paste import gets the same
dismissible "Recently imported" review card as a URL import.

**Deliberately left alone:** the community-share gate (`routers/recipes.py`'s toggle-share and
`RecipeList.tsx`) keeps testing `source_url`. A pasted recipe is the user's own text, not a scrape
of someone else's page, so it stays shareable exactly like a manually-added recipe.

### Single web-enrichment checkbox, not two

The original plan sketched two independent checkboxes ("fill gaps from the web" and "find
pictures"). The API and data model expose only one opt-in boolean, `enrich_from_web`, because both
behaviors come from the same research call and the same extraction tool schema — there is no way
to ask for images without also running the research step that finds them, and no meaningful way to
run research without allowing the model to surface images it saw along the way. `PasteImportPanel`
therefore renders one checkbox, labeled to describe both effects, rather than two checkboxes that
would silently control the same underlying flag.

### Hallucinated image URLs are tolerated, not prevented

The paste extraction tool schema gained an `images` array; the model may propose image URLs it saw
during search. `process_images()` already silently skips any URL that doesn't resolve to real
image bytes, so a bad suggestion yields a recipe with fewer images rather than a failed import. The
user can always add or fix images from the existing Edit page.

### Quota and cost

Paste imports count against `max_imports_per_user` exactly like URL and bookmark imports, so the
cap can't be sidestepped by pasting instead of linking. Both aspects of `enrich_from_web` default
**off**, so a default paste import spends tokens the same way an Instagram import does — the
opt-in web-research call is the only place in the app that spends tokens on freeform,
non-forced-tool reasoning, and it's only paid for when a user asks for it.
