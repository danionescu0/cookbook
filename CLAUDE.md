# Cookbook — instructions for Claude

`readme.MD` is this repo's source of truth for what the app does, how it's built, and why — read
the relevant section before assuming behavior. In particular, **before implementing any frontend
UI change, read [UI Conventions](readme.MD#ui-conventions)** and follow it: reuse the existing
`src/ui/` primitives (buttons, `useConfirm`, `Pagination`, the debounced-search hook, the
diacritic-insensitive matcher) instead of re-implementing them, match the existing loading/error/
empty/no-results state patterns and their exact CSS classes, and follow the accessibility and i18n
rules there. The goal: every new screen should look and behave like it was always part of the app,
not like a one-off.

Concretely, for any UI-facing change:

1. Check `src/ui/` for a primitive that already does this before writing a new one.
2. Match the existing color tokens (`cream`, `ink`, `terracotta`, `olive` — see `src/index.css`),
   not ad-hoc hex values or Tailwind defaults.
3. Add any new user-facing string to **both** `src/i18n/translations/en.ts` and `ro.ts` — `ro.ts`
   is declared as `const ro: Translation = {...}` against the type inferred from `en.ts`, so a key
   missing from either file fails the build (`tsc -b`), not something to check by hand.
4. Add a Vitest + Testing Library test under `src/tests/` for new interactive behavior.
5. Run the `update-readme` skill at the end of the task — it's listed as available and should be
   invoked proactively, not only when asked, whenever a change alters documented behavior.

Standing repo conventions (from prior sessions, still apply):

- Never `git add -A`/`git add .` — stage specific files by name.
- Only commit/push when the user explicitly asks.
- Postgres is the real database; the test suite substitutes SQLite via `api/app/tests/conftest.py`
  — any Postgres-only SQL function used in a query needs an equivalent registered there.
