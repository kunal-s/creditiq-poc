# Components: reuse before you create

Grep for an existing component before drawing a new one (`rg "export function" src/components`).
A second, slightly different status chip or card is how the app starts to look stitched together.

## Page and step frame

| Component | Where | Use |
|---|---|---|
| `PageHeader`, `PrimaryAction`, `SecondaryAction` | `components/common/PageHeader.tsx` | screens outside a case (Home, lists, admin) |
| `StepHeader` / `TabSection` | `components/case/TabSection.tsx` | a case step: kicker ("APPRAISAL BBG-… · STEP"), title, one-line purpose |
| `Panel` | `components/common/Panel.tsx` | the titled card: uppercase muted title, optional subtitle and `action` slot (buttons in the header) |
| `RailPanel`, `RailStats`, `RailRows` | `components/common/RailPanel.tsx` | the narrow right-hand column of counts and rows |
| `Details` | `components/common/Details.tsx` | a "why / more" disclosure under a row |

Page body: `px-4 py-5 sm:px-6`, sections `space-y-4`. Two columns from the content width:
`grid gap-4 @min-[49rem]/main:grid-cols-[minmax(0,1fr)_320px]` (main + rail) or
`@min-[65rem]/main:grid-cols-[minmax(0,1fr)_380px]`.

## Status and numbers

| Component | Where | Use |
|---|---|---|
| `Chip` + `Tone` (`positive`, `flag`, `critical`, `info`, `muted`, `primary`) | `common/Panel.tsx` | every status word; its tints come from `TONE_CLASS` |
| `StatusMark` | `case/checklist/Readiness.tsx` | the ✓ ✗ ! ◷ – circle beside a requirement (tinted circle, coloured glyph, `aria-hidden` — pair it with the word) |
| `DocumentReadiness` | same | "x / y requirements satisfied", the Satisfied / Not satisfied halves, the Missing / Insufficient / In review breakdown; each count filters |
| `DocumentStatusList` | same | every document under its section with mark and chip |
| `Kpi` | `common/Panel.tsx` | one figure with its label and note on a dashboard row |
| `ScoreBar` + `scoreTone` | `common/Panel.tsx`, `common/scoreTone.ts` | a score against a gate; the tone is decided for you |
| `ConfidenceChip`, `AverageConfidence` | `common/ConfidenceChip.tsx` | how sure a reading is |
| `SourceChip`, `Citations` | `common/SourceChip.tsx`, `case/Outputs.tsx` | "1 p.3": the page a figure rests on; opens the document viewer |
| `FieldValueButton` | `common/FieldValueButton.tsx` | an extracted value that opens its evidence |

The status vocabulary and its tones (keep them identical everywhere):

| Status | Mark | Chip tone |
|---|---|---|
| Satisfied | ✓ `Check` | `positive` |
| Missing | ✗ `X` | `critical` |
| Insufficient | ! `AlertTriangle` | `flag` |
| In review | ◷ `Clock` | `info` |
| Waived | – `Minus` | `muted` |

## Data views

| Component | Use |
|---|---|
| `QueryView` (`common/States.tsx`) | wrap every query: loading (`LoadingBlock` or your skeleton), `ErrorState` with retry, an `empty` title and description |
| `StackTable` (`common/StackTable.tsx`) | a table that becomes one card per row on a phone, each value beside its column label |
| `CamSheet` (`case/cam/CamSheet.tsx`) | the spreadsheet pattern: lettered columns, numbered rows, a cell address and contents bar, sticky headers, worksheet tabs, keyboard moves, edits sent to the engine |
| shadcn `Table`, `Tabs`, `Dialog`, `Popover`, `Select`, `Sheet`, `Tooltip`, … (`components/ui/*`) | primitives; restyle with tokens, never with raw colours |

Tables: header row `bg-surface-muted font-semibold`, hairline `border-border/70`, cells
`px-2–3 py-1.5`, figures `tabular text-right`, zebra `bg-surface-muted/50` on odd rows only when a
table is long. A table wider than its box scrolls inside an `overflow-x-auto` wrapper (the base layer
keeps its positioned children inside) or stacks with `StackTable` on phones.

## Icons

`lucide-react`, 14–16px (`size-3.5`/`size-4`), `aria-hidden` when a word sits beside them; a
standalone icon button needs an `aria-label` from `t()`.

## When to make a new component

Only when the same shape is needed twice and nothing above fits. Then: put it beside its siblings
(`components/common` if app-wide, `components/case/<area>` if not), give it a one-sentence doc
comment saying what it is and why, take colours from tokens, words from `t()`, and give its
interactive parts `data-testid`s. If it replaces an older pattern, replace the old uses too rather
than leaving two.
