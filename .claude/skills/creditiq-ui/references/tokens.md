# Tokens: colour, type, space

Source of truth: `src/styles.css` (`:root` values in oklch, mapped to Tailwind classes in
`@theme inline`). Never write a hex, rgb or oklch value in a component, and never use Tailwind's
default palette (`red-500`, `gray-600`, …): use these tokens so dark mode and any later re-theme
follow. To add a colour: a variable in `:root` (and `.dark` if it differs), then
`--color-<name>: var(--<name>)` in `@theme inline`.

## Neutrals and brand

| Token (class stem) | Approx. hex | Role |
|---|---|---|
| `background` | #f5f7f9 | the page behind the content |
| `surface` | #ffffff | cards, panels, table bodies |
| `surface-muted` | #f1f4f6 | header rows, zebra stripes, quiet fills |
| `muted` | — | skeleton bars, tracks of meters |
| `border` | #dce0e5 | every hairline; `border-border/70` inside grids |
| `foreground` | #151b22 | body text (17.3:1 on white) |
| `muted-foreground` | #646d76 | secondary text (5.3:1 on white, 4.8:1 on surface-muted) |
| `primary` | #16516a | selected tab, main action, links, focus rings (8.7:1) |
| `primary-foreground` | near white | text on primary (8.3:1) |
| `accent` | #e2edf3 | the current row/column highlight, selected items |
| `sidebar*` | dark slate | the app shell's side menu only |
| `ring` | teal | focus outline (`focus-visible:outline-ring`) |

## Status colours: three strengths each

| Meaning | Solid hue (small marks, solid "done" fills) | Readable text | Pale tint (areas) |
|---|---|---|---|
| Satisfied, met, ready | `positive` #2a7449 | `text-positive` (5.7:1; 5.1:1 on its tint) | `positive-soft` #e0f7e9 |
| Insufficient, warning, below gate | `flag` #b0660c | `text-flag-foreground` #5d3000 (9.7:1 on tint) | `flag-soft` #fdeed7 |
| Missing, blocking, refused | `destructive` / `critical` #c22826 | `text-critical-text` #be4b47 (4.9:1 on white) | `critical-soft` #ffe9e7 |
| In review, information | `info` #246582 | `text-info` (5.7:1 on its tint) | `info-soft` #e2f3fc |
| Waived, not applicable | — | `text-muted-foreground` | `muted` / `surface-muted` |

Contrast notes that matter:

- `text-critical-text` on the *full* `bg-critical-soft` is 4.2:1, under the 4.5:1 small-text
  floor. Behind red words use the tint at 60% (`bg-critical-soft/60`, as the critical `Chip` does)
  or keep the text at least 14px semibold.
- `text-destructive` (5.8:1) is reserved for glyphs (✗, octagon icons) and focus/error outlines; for
  words use `text-critical-text` at normal weight.
- Never put `text-muted-foreground` on a tint darker than `surface-muted`.

## Strength by area: the tint ladder

The wider the element, the paler its colour. Opacity suffixes keep the hue and the token:

| Element | Strength |
|---|---|
| Glyph, 1–2px rule, focus ring, dot | solid hue |
| Status word | its text tone, normal weight; in a `Chip` |
| Chip / tag background | `*-soft` (red at `/60`) with `border-<hue>/25–35` |
| Bar segment, meter fill, band edge | `bg-<hue>/30–45` (`bg-positive` stays solid: progress achieved is the one emphasis) |
| Row highlight, override cell | `bg-<hue>-soft/50–60` |
| Card or panel | neutral `surface`; never washed with a status colour |

`scoreTone()` (`src/components/common/scoreTone.ts`) already gives the tinted fills for score bars
(`bg-positive`, `bg-flag/60`, `bg-destructive/40`): use it rather than choosing again.

## Dark mode

`.dark` overrides the neutral and brand tokens only; status tokens inherit their light values and
read acceptably on dark surfaces at the strengths above. Because everything goes through tokens, a
dark pass needs no component changes — another reason not to hard-code colours.

## Type

| Use | Class |
|---|---|
| Page title | `text-[17px]`–`text-[22px] font-semibold tracking-tight` |
| Big count ("2 / 9") | `text-[34px] font-semibold leading-none tracking-tight tabular` |
| Section heading in a card | `text-[13px]`–`[17px] font-semibold` |
| Panel title | `text-[12px] font-semibold uppercase tracking-wide text-muted-foreground` |
| Field label / kicker | `field-label` utility |
| Body, table cells | `text-[12.5px]`–`text-[13px]` |
| Secondary, notes | `text-[11px]`–`text-[12px] text-muted-foreground` |
| Chips | `text-[10.5px] font-medium` (the `Chip` component) |
| Figures | add `tabular`, right-align in tables |

Fonts: IBM Plex Sans (`font-sans`) and IBM Plex Mono (`font-mono`, for ids, codes and hashes).
Headings h1–h3 get `letter-spacing: -0.011em` from the base layer.

## Space and shape

- 4px grid. Common: `gap-1.5/2/3/4`, `px-4 py-2.5` (panel header), `px-4 py-3` (panel body),
  `px-3 py-1.5` (table cell), `px-4 py-5 sm:px-6` (page body).
- Radius `rounded` (6px) for cards, `rounded-sm` for small controls, `rounded-full` for marks and dots.
- Touch targets: the base layer widens the tap area of small buttons and links on coarse pointers;
  keep visual size dense.
- Elevation: borders, not shadows. A popover or menu may use `shadow-lg`.
