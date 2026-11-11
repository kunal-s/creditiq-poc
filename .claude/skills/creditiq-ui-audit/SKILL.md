---
name: creditiq-ui-audit
description: Audit and critique CreditIQ RBL screens or a frontend diff against the house style — colour tokens and the pale-tint rule, contrast and accessibility, phone layouts, terminology and excluded words, the engine-records-every-change rule, page jumps and layout shift, test coverage — then report findings ranked by severity with file:line and the fix. Use it whenever someone asks to review, audit, critique, polish, QA or "check the UI/UX" of a screen, a PR or the current changes, asks "does this look right / is this good / why does this look odd", sends a screenshot of the app with a complaint about how it looks, or before handing back any UI work for sign-off — even if they don't say "audit".
---

# CreditIQ UI audit and critique

Two passes, then one report. The **audit** checks what can be checked (rules, numbers, code); the
**critique** judges what needs an eye (hierarchy, clarity, consistency with the rest of the app and
with what the bank's reviewers asked for). The standard both measure against is the `creditiq-ui`
skill and its references (`.claude/skills/creditiq-ui/references/*.md`) — read the relevant ones
rather than auditing from memory.

## Scope

Work out what is being audited before starting: the current changes (`git status`, `git diff`),
named files, a route, or a screenshot the user sent. For a screenshot, find the component that draws
it (`rg` the visible words in `terminology/rbl.yaml`, then the key in `src/`).

## Pass 1: audit (verifiable)

1. **Mechanical checks** — run the bundled script on the files in scope:
   `python3 .claude/skills/creditiq-ui-audit/scripts/ui_check.py [files…]`
   (no arguments = files git sees as changed under `src/`; `--all` for everything; `--json` for
   machine-readable). It flags raw colours and Tailwind's default palette, solid red areas, bold or
   dark-red words, words written in components instead of `t()`, `scrollIntoView`, inline colour
   styles, raw HTML, browser storage of records, the excluded words, buttons without `type`, images
   without `alt`. Its warnings are questions: open each one and decide.
2. **Gates** — `npx tsc --noEmit`, `npx eslint <files>`, `npx prettier --check <files>`,
   `npm run check:terms`. Any failure is a finding.
3. **Colour and contrast** — against `tokens.md`: every status in its three strengths (glyph solid,
   words in the text tone, areas tinted); no coloured washes on cards; small text ≥ 4.5:1 (note
   `text-critical-text` on full `bg-critical-soft` is only 4.2:1); colour never the only signal.
4. **Numbers and words** — totals equal the sum of their parts; the same count reads the same on
   every screen that shows it (compare them); the readiness vocabulary and retired words
   (`copy.md`); nothing that reads as a project note, a person or a meeting.
5. **Behaviour** — a person's change goes to the engine (no record-like state kept only in the
   browser); the page never jumps on load or selection; skeletons match the loaded shape; keyboard
   paths work and focus is visible; disabled controls say why.
6. **Phone** — 320, 400 and 768 px: no sideways page scroll; wide tables stack or scroll in their
   own box; tap targets usable. Run `MOBILE_WIDTH=<w> E2E_PORT=5175 npx playwright test
   --project=chromium e2e/mobile-layout.spec.ts` and look at screenshots.
7. **Tests** — the changed behaviour has a spec asserting it (by `data-testid`), the mock engine
   answers any new call, and the specs touched pass.

## Pass 2: critique (judgement)

Look at screenshots (1440 and ~1920 px, and 400 px — see `testing.md` for the throwaway spec), then
answer, in this order:

1. **The one question.** What does this screen answer, and is that the first thing the eye lands on?
   Is anything competing with it (a second big number, a saturated block, a banner)?
2. **Hierarchy and grouping.** Does size, weight and position follow importance? Are related things
   together and unrelated things apart? Is there a single path to the next action?
3. **Calm.** Count the saturated colours visible at once; more than a few small signals is noise.
   Is any red large? Is anything bold that does not need to be?
4. **Consistency.** Same status → same mark, chip and word as on the Overview, Files, Document
   readiness and Outputs. Same spacing and panel pattern as neighbouring steps. Matches the hosted
   original design (https://creditiq.joulestowatts.online/) where the screen exists there.
5. **Trust.** Can every figure be traced to its page (citation chips)? Does a changed figure show
   who changed it, when and why? Does the screen admit what it does not know (provisional, waiting
   for documents) rather than show a misleading zero?
6. **Words.** Plain, short, in the bank's terms; no system jargon; errors say what to do.

## The report

Lead with a one-paragraph verdict (ready / ready after fixes / not ready, and why), then the
findings, most severe first:

```
| # | Severity | Where | Finding | Fix |
|---|---|---|---|---|
| 1 | Blocker | src/…/X.tsx:42 | … what is wrong and who it affects | … the concrete change |
```

Severity: **Blocker** (wrong data or numbers, a hard-rule breach, inaccessible, broken on a phone),
**Major** (breaks the colour rule or consistency in a way a reviewer will notice, missing test),
**Minor** (polish), **Note** (a question or an optional improvement). Then list what was checked and
passed, briefly, and anything not checked (say why) — never imply a check that was not run.

If the user asked for fixes as well, make them after the report, re-run the checks that found each
problem, and report per finding: fixed / not fixed (why).
