# Southgate Textiles — Synthetic Specimen Document Set

Synthetic specimen PDFs for the working-capital loan demo. **Every document is
fictional and marked as such** (diagonal SPECIMEN watermark + footer on every
page). Nothing here is a real instrument; all identifiers are invented.

Applicant: *Southgate Textiles Private Limited* (fictional) — CIN
`U17291TZ2016PTC027431`, applying for CC ₹2.85 cr + Term Loan ₹1.40 cr
(total ₹4.25 cr). Reference date for all staleness/age calculations: **21 August 2026**.

## Contents

`manifest.json` drives the viewer: for each file it records the title, the
checklist requirement, the verdict (`satisfied` / `insufficient` / `missing`),
the defect type (`stale` / `incomplete` / `inconsistent`), a plain-language
reason, the page count, and — for defective files — the page number and a
verbatim text snippet that evidences the defect so the viewer can jump to and
highlight it. The title deed additionally lists the two documents it contradicts.

### The contradiction (priority group one)
- **Southgate_Title_Deed_Coimbatore_Unit.pdf** — page 3 carries a subsisting
  equitable mortgage of the collateral in favour of **Meridian Bank**
  (14 March 2024, ₹1,75,00,000).
- **Southgate_Nil_Facilities_Declaration.pdf** — declares *no* facilities and
  *unencumbered* collateral. Contradicted by the title deed and the bank statement.
- **Southgate_CCB_CA_Statements_12m.pdf** — a single account only; a recurring
  monthly `MERIDIAN BANK EMI DR` of ₹2,18,750 evidences an undisclosed second
  banking relationship whose statement was never provided.

### Other defective documents (priority group two)
- **Stock_BookDebt_30Jun2026** — *stale* (position as at 30 June 2026, 52 days old).
- **GSTR3B_Dec2025_Jul2026** — *incomplete* (Aug–Nov 2025 returns absent; gap
  flagged on the cover).
- **Provisional_FY2026** — *incomplete* (balance sheet absent; page numbering
  jumps 1, 2, **6, 7**).
- **Board_Resolution_draft** — *incomplete* (plain paper, no letterhead; blank
  signature block).

### Clean / satisfied documents (priority group three)
Certificate of Incorporation, MOA & AOA, entity PAN, director KYC (masked
identifiers), audited financials FY2024 & FY2025, ITR acknowledgements.

## Regenerating

The set is produced deterministically (no randomness that changes run to run):

```
pip install reportlab pymupdf
python3 scripts/docgen/generate.py     # writes this folder + manifest.json
python3 scripts/docgen/validate.py     # 217 assertions over the rendered PDFs
```
