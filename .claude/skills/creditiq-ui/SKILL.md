---
name: creditiq-ui
description: How to design and build any screen, panel, table, chart, form or visual change in the CreditIQ RBL frontend (React 19, Tailwind v4, TanStack Router and Query) so it looks and behaves like the rest of the app — its colour tokens and the "strong colour for small signals, pale tints for areas" rule, IBM Plex type scale, Panel/Chip/status components, terminology-driven copy, the engine-records-every-change pattern, phone layouts and Playwright tests. Use it whenever you touch anything under src/ that a person sees — a new step or tab, a redesign, "make it look better", colours, spacing, a status chip, a grid or spreadsheet view, copy changes, mobile fixes — even if the request only says "UI", "design", "frontend", "screen", "page" or names a screen (Overview, Files, Document readiness, Outputs, CAM).
---

# CreditIQ UI

CreditIQ is a working credit-appraisal system for RBL Bank's Business Banking Group. Credit analysts,
relationship managers and credit managers read it for hours, compare figures across documents and
act on what it tells them. So the design goal is not "striking" — it is **calm, exact and
trustworthy**: a screen should answer its one question at a glance, every number should be traceable
to its source, and nothing should shout unless something is genuinely wrong.

This skill is the house style. Its references hold the detail; read the one you need:

| Read | When |
|---|---|
| `references/tokens.md` | choosing any colour, tint, border, type size or spacing |
| `references/components.md` | before writing markup — reuse before you create |
| `references/copy.md` | any visible word, label, status or count |
| `references/react-quality.md` | state, data, effects, keyboard, accessibility, performance |
| `references/testing.md` | the browser tests and screenshots that prove it works |

The audit and critique of finished work is the sibling skill `creditiq-ui-audit`.

## 1. Decide before you build (write it down)

Long-lived apps drift when each component is designed on the spot. Before writing code for anything
bigger than a one-line fix, state a short **design note** in your reply — five or six lines, not an
essay — and keep to it:

1. **The question the screen answers** and the one thing a reader should see first (a verdict, a
   count, a table). Everything else is subordinate to it.
2. **Where it lives**: route and step (`src/routes/appraisals.$caseId.*.tsx`), and what already sits
   there. Check the hosted original design (https://creditiq.joulestowatts.online/) for the screen's
   layout when one exists; match it unless the user has asked for something else.
3. **Its words**: the terminology keys it needs (`terminology/rbl.yaml`), new or existing.
4. **Colour roles**: which elements are *signals* (saturated) and which are *areas* (pale tints or
   neutral) — see §3.
5. **States**: loading, empty, error, provisional, read-only role, and the narrowest phone width.
6. **Proof**: the test ids and the specs that will show it works.

If the request conflicts with an established pattern or a hard rule (§6), say so in the note and
propose the nearest compliant design rather than silently picking one.

## 2. The system in one page

- **Type**: IBM Plex Sans (`font-sans`), IBM Plex Mono for codes. Small, dense scale: body
  `text-[12.5px]`–`[13px]`, secondary `text-[11px]`–`[12px]`, labels via the `field-label` utility
  (11px, uppercase, tracked, muted), panel titles `text-[12px] font-semibold uppercase tracking-wide
  text-muted-foreground`, page titles `text-[17px]`–`[22px] font-semibold tracking-tight`. Figures in
  tables and counts use `tabular` (tabular numerals) and right-align.
- **Surfaces**: page `bg-background`, cards and panels `bg-surface` with `border border-border` and
  `rounded` (6px). Subtle fills `bg-surface-muted`. Shadows almost never; one hairline border is the
  separator.
- **Primary** is a deep teal-blue (`primary`, #16516a). It marks the selected tab, the main action,
  links and focus — not decoration.
- **Status colours** each have three strengths: the solid hue (`positive`, `flag`, `critical`/
  `destructive`, `info`), a readable text tone (`text-positive`, `text-flag-foreground`,
  `text-critical-text`, `text-info`) and a pale tint (`*-soft`).
- **Spacing**: 4px grid; panels `px-4 py-2.5` headers, `px-4 py-3` bodies; gaps `gap-2`–`gap-4`.
- **Layout** responds to the content area, not the window: `<main>` is `@container/main`, so use
  `@min-[49rem]/main:` style variants for two-column layouts; components with their own container use
  a named one (`@container/glance`).

## 3. The colour rule (the one people notice)

> **Saturated colour is for small signals. Anything wide is a pale tint or neutral.**

The user rejected, in turn: a strong red top rule, a pink-washed card, solid red discs, bold dark-red
words and a solid red progress bar. What they accepted:

| Element | Use | Not |
|---|---|---|
| A status word | a `Chip` with its tone (pale tint, tinted border, readable text) | bare bold red/green text |
| A status mark (✓ ✗ ! ◷) | `StatusMark`: tinted circle, coloured glyph | solid filled red/green disc |
| A progress or score bar | done = solid `bg-positive`; the rest pale (`bg-destructive/30`, `bg-flag/40`, `bg-info/35`) | a long solid red bar |
| Red text that must stay readable | `text-critical-text` (4.9:1 on white), normal weight | `text-destructive font-semibold` |
| A card for a bad verdict | white card; the colour lives in the verdict's icon tile | a coloured wash or a thick coloured rule |
| A warning strip | `bg-flag-soft` + `text-flag-foreground` | saturated amber |

Colour is never the only signal: every coloured mark carries its word (or `aria-label`). Before you
add any colour, ask "is this a small signal?" — if not, tint it or make it neutral. Details, values
and contrast figures: `references/tokens.md`.

## 4. Building

- **Reuse first.** `Panel`, `Chip` (`TONE_CLASS`), `Kpi`, `ScoreBar`, `StatusMark`,
  `DocumentReadiness`, `DocumentStatusList`, `QueryView`/`LoadingBlock`/`ErrorState`, `StackTable`,
  `Details`, the shadcn primitives in `src/components/ui`. Catalogue and when to make something new:
  `references/components.md`.
- **Every visible word comes from `t("…")`** (`@/config/terminology`), the key added to
  `terminology/rbl.yaml` with the surrounding keys. No string literals in JSX, `aria-label`,
  `title` or `placeholder`. Wording rules and the domain vocabulary: `references/copy.md`.
- **A person's change is the engine's record.** Edits, overrides, decisions and choices go through
  the API (which keeps who and when, and the decision log); the screen never keeps such state only in
  the browser (`localStorage` is for view preferences only). See `references/react-quality.md`.
- **Numbers must add up.** If a screen shows a total and its parts, the parts sum to the total and
  nothing is counted twice (a property such as "blocking" is a note on a part, not another part).
- **Never move the page under the reader.** No `scrollIntoView` on load or on selection inside a
  scrolling grid; scroll the container. No layout shift between loading and loaded (skeletons take
  the loaded shape).
- **Phone widths are first-class**: check 320, 400 and 768 px; wide tables become `StackTable` cards
  or scroll inside their own box — the page itself never scrolls sideways.
- **Comments** follow the codebase voice: a plain-English sentence on *what the thing is and why*,
  above the component; a header comment listing the component's test ids where it has many.

## 5. Proving it

1. `npx prettier --check <files>` · `npx tsc --noEmit` · `npx eslint src e2e` (0 errors) ·
   `npm run check:terms` · `npm run build`.
2. `python3 .claude/skills/creditiq-ui-audit/scripts/ui_check.py <changed files>` — the mechanical
   style checks (raw colours, solid red areas, literal copy, page-jump scrolls, excluded words).
3. Browser tests against the mock engine: `E2E_PORT=5175 npx playwright test --project=chromium
   <specs>`; then the phone layout at three widths (`MOBILE_WIDTH=320|400|768 … e2e/mobile-layout.spec.ts`).
   Add or update specs for what you changed: `references/testing.md`.
4. **Look at it.** Screenshot the changed screen at 1440 (and ~1920, the user's monitor) and at
   400 px, and read the screenshots before saying it is done.
5. Report per screen as **done / partly done / not done**, with what is missing. Never round up.

## 6. Hard rules (from CLAUDE.md — breaking these is a defect, not a style choice)

- Nothing on screen may read as anything other than a working system at the bank: no people at the
  bank, meetings or requirement rationale; no internal notes ("until X arrives") in UI copy.
- Never on screen: the words *fraud, forged, fake, tampered*; a full model id; stakeholder names
  (`npm run check:terms` sweeps for them).
- No AGPL/GPL/LGPL runtime dependencies; add a library only with its licence checked and a reason.
- Configuration governs behaviour; the UI never computes a rule outcome the engine owns.
- Work stays in this repo on the WSL filesystem; nothing under `workflow/` is ever committed.
