# React, data, accessibility, performance

## Data

- **Types** come from the engine's contract: `@/api/types` (generated into `src/api/schema.gen.ts`
  by `npm run gen:api`). Never hand-write a type the API already describes. After an engine contract
  change, run `npm run gen:api`.
- **Calls** go through `api` in `@/api/client` (it adds the session token and turns refusals into
  errors with the engine's words). Downloads use its `download()` (a plain link cannot carry the
  token).
- **Queries and mutations** live in `src/domain/*.ts` as hooks (`useCam`, `useChecklist`,
  `useCaseProgress`, `useCamChange` …). Query keys are arrays starting with the resource:
  `["cases", caseId, "cam"]`. A mutation that returns the updated resource writes it to the cache
  (`setQueryData`) and invalidates what it changes elsewhere — so every view of it updates at once.
- **The engine keeps the record.** Anything a person decides or changes (an override, words, a
  template choice, a document's label, a decision on a finding) is sent to its endpoint, which keeps
  who and when and writes the decision log; then the screen shows what came back. State held only in
  the browser is lost on reload, invisible to colleagues and missing from the audit — so
  `useState` holds only the view (what is open, selected, typed but not yet saved), and
  `localStorage`/`sessionStorage` only view preferences (`creditiq.cam.mode`), wrapped in try/catch.
- **Permissions**: `useCan("review.decide")` and friends (`@/domain/session`). Hide or disable what
  a role cannot do, and say why in a `title`; the engine refuses anyway, so the screen is a courtesy,
  not the control.
- **Routes**: TanStack file routes under `src/routes` (`createFileRoute`). The route tree is
  generated (`npm run build` regenerates it); a syntax error in any route file stops the dev server's
  route generation, so typecheck before handing back.
- Never compute what the engine decides (a gate, a rule outcome, a score); display the engine's
  value. Derived display values (a breakdown of counts) go in `src/domain` as pure functions with
  their invariant checked (`readinessBreakdown` throws if the parts do not add up).

## Components

- One component per idea; props typed inline; no `any`. Pure helpers outside components.
- `useMemo` for derived lists that feed big trees (a grid's layout); not by reflex elsewhere.
- Effects synchronise with the outside world only; they never derive state.
- Keys are stable ids, not indexes, where rows can reorder.
- No `dangerouslySetInnerHTML`; text is text.
- Heavy or rare code (a document viewer, a large library) is loaded lazily.

## Interaction

- **Never move the page under the reader.** Keep a selected cell or row in view by scrolling its own
  container (compare `getBoundingClientRect` of the box and the cell); `scrollIntoView` also scrolls
  every ancestor — the whole page jumps. Do not scroll on first render.
- No layout shift: a skeleton has the loaded content's shape and height (tests compare them).
- Every `<button>` has `type="button"` unless it submits a form.
- Spreadsheet-like editing follows the spreadsheet: arrows move, Enter/F2/double-click edit, typing
  starts an edit, Enter keeps, Escape leaves it as it was, Tab keeps and moves on; a blur after
  Enter/Escape must not commit twice (guard with a ref).
- A change that must be justified (an override) asks for its reason right where it was made, and
  sends nothing until it is given.

## Accessibility (WCAG 2.2 AA)

- Text contrast at least 4.5:1 (3:1 for 18px+ or 14px+ bold) — the token table in `tokens.md` gives
  the figures; tints behind red text at `/60`.
- Colour is never the only signal: a mark carries its word, a chip its label, a bar its numbers.
- Every control reachable and operable by keyboard, with a visible focus ring
  (`focus-visible:outline-2 focus-visible:outline-ring` or `ring-2 ring-ring`).
- Landmarks and roles: one `h1` per page (the step title), headings in order; grids use
  `role="grid"`/`row`/`gridcell`/`columnheader`/`rowheader` with `aria-selected` and
  `aria-activedescendant`; tab strips `role="tablist"`/`tab` with `aria-selected`; toggles
  `aria-pressed`; disclosures `aria-expanded`; live updates in a `role="status"` region.
- Images have `alt` from `t()`; decorative icons `aria-hidden`.
- Touch: dense visuals are fine — the base layer enlarges tap areas on coarse pointers.

## Performance

- Keep the main bundle lean: no library for what a few lines do; dynamic `import()` for rare
  features.
- Long lists render only what is open (bands collapse; done items fold away).
- Avoid re-rendering whole grids on each keystroke: keep the editor's text in its own component
  state and commit once.

## Dependencies

A new package needs: a reason, its licence checked (no AGPL/GPL/LGPL at runtime — CLAUDE.md rule
10), and an exact version in `package.json` with the lockfile updated by `npm install`. Python
packages go in `requirements.in` and are locked with `pip-compile --generate-hashes --strip-extras`.
