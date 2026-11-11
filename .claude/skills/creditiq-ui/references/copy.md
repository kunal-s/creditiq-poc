# Copy: every word on screen

## Where words live

Every visible string — labels, buttons, statuses, empty states, errors, tooltips, `aria-label`s,
placeholders, page titles — is a key in `terminology/rbl.yaml`, read with `t("area.key", { vars })`
from `@/config/terminology`. Add new keys beside their neighbours with a one-line YAML comment
saying where they show. Interpolate with `{name}`; for counts the house style is "{n} file(s)" or a
separate key for one (`toGo` / `toGoOne`).

Why: the bank's terms change (the reviewers renamed "Completeness" to "Document readiness" across
every screen in one pass); a word kept in code would be missed.

## Voice

- British English, plain and formal; sentence case for everything except panel titles and field
  labels (which the CSS uppercases — write them in sentence case).
- Say what a thing *is* or what happens, not how the system works inside: "Reading the documents
  (3 of 4)", not "Job queued".
- Short. A heading is a noun phrase ("Document readiness"); a status line is one sentence; an empty
  state is a title plus one sentence on what to do.
- Numbers as the bank writes them: `INR 3.00 cr`, `INR 50.00 lakh`, `1.59x`, `12 Jun 2015`,
  `29 Sep 2026`; percentages without decimals unless the gate needs one (`74.3 points to go`).
- Buttons are verbs: "Create case", "Download Excel", "Save my words", "Add to query list".

## The readiness vocabulary (agreed with the bank's reviewers)

- The measure is **Document readiness**, shown as satisfied of total: **"3 / 7 requirements
  satisfied"**. The weighted percentage is secondary and always says so: "38% weighted · 85% review
  gate".
- Every requirement is **Satisfied** or **Not satisfied**; Not satisfied breaks down into **Missing**,
  **Insufficient** and **In review**. **Waived** counts with Satisfied and is named when present.
  Total = Satisfied + Not satisfied, always.
- **Blocking** is a property of a not-satisfied requirement: "Blocks credit review", "Blocking credit
  review: 2" — never a separate count beside the others.
- Retired words — do not bring back: *Outstanding*, *Blocking gaps*, *Readiness score*,
  *Completeness* (as the name of the step), *Validation and completeness*.
- Name documents, not fractions: list each document under its category with its mark and status
  rather than "1 of 3 satisfied".

## Never on screen

- *fraud, forged, fake, tampered* (and their variants): describe what was found ("the figures on
  page 2 do not match the totals").
- A full model id, an internal job id, a stack trace, a file path on the server.
- People at the bank, meetings, reviewers, requirement rationale or project notes ("until the
  template is received", "as agreed on Tuesday") — the screen must read as a working system at the
  bank (CLAUDE.md rule 9). Stakeholder names: `npm run check:terms` finds them.

## Errors and empty states

- An error says what failed and what to do: "The file could not be downloaded. Try again." A
  refusal from the engine already carries its reason in words — show it (`refusal(error)`).
- An empty state says why it is empty and the next step: "Nothing on this sheet yet." / "Upload the
  documents to start."
- A disabled control explains itself in its `title`: "Every condition must be met first: …".
