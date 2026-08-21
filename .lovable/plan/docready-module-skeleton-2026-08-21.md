# DocReady module skeleton

Adds DocReady as a distinct module inside CreditIQ: its own navigation group, its own case
workspace routes, and a working handoff into the existing appraisal pipeline. The nine existing
sections, the shell, and the design language are untouched.

## Navigation and entry point

New nav group **DocReady**, placed above Workbench so the two stages read in order:

- Readiness Console — `/docready`
- Case workspace — `/docready/$caseId` (Checklist, Collection, Validation, Readiness)
- Client portal preview — `/docready/$caseId/portal`

The persistent appraisal context strip stays appraisal-only; DocReady routes get their own case
strip (borrower, case id, readiness score, blocking gaps) built from the same visual pattern.

## Screens (skeleton now, filled from Section 2 seed)

1. **Readiness Console** — case list across MSME/SME applicants: borrower, product, requested
   limit, readiness percentage, documents outstanding, days in collection, owner. Filter and sort
   like the Memo Library. Southgate Textiles is the lead case.
2. **Case workspace** — four tabs sharing one case header:
   - *Checklist*: required document set derived from product and constitution, each item with
     status (not requested / requested / received / rejected / accepted), source, and reason.
   - *Collection*: chase timeline — requests sent, reminders, client uploads, and the open ask.
   - *Validation*: per-document machine checks (legibility, period coverage, signature, identifier
     match) and the resulting rejection reasons, reusing the exception-queue card pattern.
   - *Readiness*: score breakdown, blocking versus non-blocking gaps, and the handoff action.
3. **Client portal preview** — the borrower-facing upload view, same treatment as the existing
   Consent Journey screen.

## The handoff seam

On the Readiness tab, **Start credit appraisal** is enabled only when no blocking gap remains. It
creates a CAM record for the DocReady borrower (identifiers, constitution, product, facility ask,
branch, RM carried across) and navigates to `/appraisals/$id/identity`, so the new case appears in
My Appraisals and the context strip alongside Northwind. Collected documents are registered as
already-present sources so the pipeline does not re-ask for them.

## AI woven in

Copilot rail gains DocReady contexts: which documents are missing and why they matter, drafting
the next client chase message, explaining a rejection, and predicting readiness date. Inline AI
actions on the checklist (derive the required set) and validation (explain this rejection).

## Audit

Every DocReady request, upload, rejection, waiver, and the handoff itself is written to the same
audit event shape used by the Audit Ledger so the examiner walk-through covers stage one too.

## Technical notes

- New data module `src/data/docready.ts`: case, checklist item, document, validation check, chase
  event, readiness score types, plus a `useDocReadyState` hook mirroring `useAdminState` /
  `useAcqState` (in-memory, no backend).
- Route files, dot-named: `docready.index.tsx`, `docready.$caseId.tsx` (layout + case strip),
  `docready.$caseId.checklist|collection|validation|readiness.tsx`, `docready.$caseId.portal.tsx`.
- `src/data/seed.ts` gets the DocReady borrower records and a `createAppraisalFromCase` helper for
  the handoff; existing appraisals unchanged.
- Nav additions in `src/components/shell/nav.ts`; copilot branches in `CopilotRail.tsx`.
- Placeholder shapes are used only where Section 2 will supply exact figures; once you paste the
  seed dataset, values are replaced verbatim — no invented numbers survive.
- Each route defines its own `head()` metadata.
