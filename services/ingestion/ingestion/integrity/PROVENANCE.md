# Provenance

The modules in this package are ported from the bank's integrity application:

| | |
|---|---|
| Source | `RBL/fault_detection`, `backend/src/tamper` |
| Policy | `integrity_policy_v3` |
| Source commit | `9fdc58f` |
| Ported | 29 October 2026 |
| Scope | Use case 1 only: a digitally generated PDF edited after it was issued |

## What changed in the port

- **Shape.** Findings return `IntegrityFinding` (`ingestion/contracts.py`), not the
  source's `Check`/`CheckResult`. Same fields, CreditIQ naming.
- **Configuration.** Thresholds, the editing-tool list and the per-type rules come
  from `config/ingestion/integrity.yaml`, published with the rest of the
  configuration version. The source read `backend/config/policy.yaml` and
  `backend/config/doctypes/*.json`.
- **Document type.** CreditIQ's `classify` stage supplies the type. The source
  detected it itself from keywords.
- **Quality.** Not ported: `config/ingestion/quality.yaml` already grades pages
  with the same reason codes (FRD F-07).
- **No model.** The source's AI second opinion (`review.py`) is not ported.
  Every check here is deterministic code plus a threshold.

## Not ported (use case 2 and later phases)

`regions.py`, `textlayer.py`, `typestyle.py`, `origin.py`, `raster.py`,
`blocks.py` (use case 2); the statement-arithmetic checks and `BS_BALANCES`
(they need the ledger, so they belong in `validate`); signatures (`pyhanko`).
