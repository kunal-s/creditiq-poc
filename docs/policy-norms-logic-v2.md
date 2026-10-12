# Policy norms and approving authority (simple version)

This covers the test plan's two policy rows:

| ID | Test | What CreditIQ does | Pass rule | Criterion | Status today |
|---|---|---|---|---|---|
| **TC-24** | Policy norms and deviations | Assesses 13 norms on every application and lists each deviation with the norm, the actual value and the source | Agrees with RBL's deviation record | C4, C5 | Ready to run once RBL's case records are imported. The norms are provisional until RBL supplies its own |
| **TC-25** | Approving authority | Works out the authority the case needs from the approval matrix and the case, and compares it with the recorded approval | Agrees with the matrix; only where RBL provides the matrix | C4 | Shown on every case, but **not scored**: the matrix is provisional until RBL supplies its own |

For the full logic with code, see [policy-norms-logic.md](policy-norms-logic.md).

---

## TC-24 Policy norms and deviations

### How a norm is assessed

Each norm compares one figure, or a ratio of figures, with a threshold, and gives one result:

- **Pass:** the figure meets the norm.
- **Deviation:** it does not. It is listed with the norm, the actual value and the figures behind it, each with its document page. This is what TC-24 expects.
- **Cannot evaluate:** a figure is missing, still waiting for review, or would mean dividing by zero. The missing figure is named. A norm is never passed on a guess.
- **Not applicable:** the norm does not apply to this application (for example, a working-capital norm when only a term loan is requested).

**All thresholds are provisional**, proposed by the delivery team until RBL supplies its key Business Banking policy norms (`config/policy.yaml`). Financial figures come from the latest audited financial statements.

### Eligibility

| Norm | What it checks | Documents | Threshold | Applies to |
|---|---|---|---|---|
| **EL-01** Business vintage | Years since incorporation, counting completed months only | Certificate of incorporation | At least 3 years | Private limited companies |
| **EL-02** Bureau rank | The credit rank on the latest bureau report (1 is the lowest risk) | Commercial bureau report | At most rank 6 | All |
| **EL-03** Positive net worth | Share capital plus reserves is above zero | Audited financial statements | At least INR 1 | All |
| **EL-04** Profit | The latest year made a profit | Audited financial statements | At least INR 0 | All |
| **EL-05** Request against turnover | The amount requested as a share of annual turnover | Sourcing message (amount), audited financial statements (turnover) | At most 20% | Working capital up to INR 5 cr |

### Financial ratios

| Norm | What it checks | Documents | Threshold | Applies to |
|---|---|---|---|---|
| **FR-01** Current ratio | Current assets ÷ current liabilities | Audited financial statements | At least 1.20x | Working-capital requests |
| **FR-02** TOL / TNW | (Long-term borrowings + current liabilities) ÷ net worth. A zero or negative net worth is always a deviation | Audited financial statements | At most 3.00x | All |
| **FR-03** DSCR | (Profit after tax + depreciation) ÷ yearly instalments on existing loans and the proposed term loan. Each existing loan counted once | Audited financial statements; declaration of existing facilities, sanction letters, bank statements; the proposed instalment on the application | At least 1.50x | Term loans, or any borrower already paying instalments |
| **FR-04** Interest coverage | (Profit before tax + finance costs) ÷ finance costs | Audited financial statements | At least 2.50x | All |
| **FR-05** Debt / equity | Total borrowings ÷ net worth. A zero or negative net worth is always a deviation | Audited financial statements | At most 2.00x | All |
| **FR-06** Working-capital cycle | (Inventories + receivables − payables) ÷ turnover × 365 | Audited financial statements | At most 75 days | Working-capital requests |

### Documentation

| Norm | What it checks | Documents | Threshold | Applies to |
|---|---|---|---|---|
| **DOC-01** Blocking items open | Blocking checklist items still outstanding | The checklist (Completeness tab) | At most 0 | All |
| **DOC-02** Years of audited statements | Financial years of audited statements on file | Audited financial statements | At least 2 years | All |

**Security cover:** no norm yet. Collateral values need valuation reports, which are not among the document types yet.

### Example (Kestrel, BBG-2026-000004)

| Deviation | Norm | Actual | Source |
|---|---|---|---|
| FR-06 Working-capital cycle | At most 75 days | 90 days | FY 2025-26 audited statements: inventories, receivables, payables, turnover |
| DOC-01 Blocking items open | At most 0 | 3 | The checklist |

FR-03 (DSCR) cannot be evaluated: a term loan is requested, but no proposed instalment was entered. The other ten norms pass or do not apply.

### How TC-24 is scored

1. RBL's deviation record for the case is imported and confirmed by the Credit Manager.
2. The **Comparison** tab (Credit Manager only) puts RBL's recorded deviations beside CreditIQ's. Each is marked **Agree**, **Differ**, **New** (found only by CreditIQ) or **Missed** (recorded only by RBL).
3. The Credit Manager marks each of CreditIQ's deviations **Valid** or **Not valid**, with a reason.
4. **C4:** the share of RBL's recorded deviations that CreditIQ found. **C5:** the share of CreditIQ's deviations marked valid. Both need at least 85%.

While the norms are provisional, agreement is indicative only: CreditIQ applies the proposed thresholds, not RBL's.

---

## TC-25 Approving authority

### How the authority is worked out

1. **The amount** picks an authority for each product requested.
2. **Each group of norms with a deviation** moves it up one level. Eligibility deviations need at least the Regional Credit Head.
3. **The highest wins.** Deviations do not add up: each counts from the amount's authority.
4. **Unassessed norms make it a minimum.** If a norm could not be evaluated, the answer is "at least" this authority, with how high it could go.

### The matrix

| Authority (lowest first) | Working capital up to | Term loan up to | Non-fund up to |
|---|---|---|---|
| 1. Credit Officer | INR 2 cr | INR 1 cr | INR 3 cr |
| 2. Regional Credit Head | INR 5 cr | INR 3 cr | INR 7.5 cr |
| 3. Zonal Credit Committee | INR 15 cr | INR 10 cr | INR 20 cr |
| 4. Head Office Credit Committee | INR 50 cr | INR 35 cr | INR 60 cr |
| 5. Management Credit Committee | Above | Above | Above |

| Group with a deviation | Effect |
|---|---|
| Eligibility | One level up, at least Regional Credit Head |
| Financial ratios | One level up |
| Documentation | One level up |
| Security cover | One level up, at least Zonal Credit Committee (no security-cover norm yet) |

The matrix is a provisional proposal, until RBL supplies its approval and delegation matrix (`config/approval_matrix.yaml`). The screen marks it "Provisional matrix".

### Example (Kestrel, INR 6.50 cr, cash credit and term loan)

| Step | Authority |
|---|---|
| Amount: INR 6.50 cr, in the working-capital band up to INR 15 cr and the term-loan band up to INR 10 cr | Zonal Credit Committee |
| Financial ratios deviation (FR-06) | One level up: Head Office Credit Committee (deciding) |
| Documentation deviation (DOC-01) | One level up: Head Office Credit Committee |
| **Required** | **Head Office Credit Committee, at least** (DSCR could not be evaluated) |

### How TC-25 is scored

On the **Comparison** tab, the authority CreditIQ works out is put beside the approval recorded in RBL's case record and marked Agree or Differ. The analyst never sees the recorded approval while appraising. **TC-25 counts towards C4 only once RBL's matrix is published;** until then it is shown but reported as not scored.

---

## Where the results appear

- **Policy tab:** each norm with its result and figures, then the approving authority.
- **Draft CAM:** a policy section listing the deviations.
- **PD note:** a question for each deviation and each norm that could not be evaluated.
- **Stage progress:** the Policy stage needs attention while a norm cannot be evaluated.
- **Comparison tab:** CreditIQ against RBL's record, for both rows.

## What RBL still has to supply

| For | What |
|---|---|
| TC-24 | Its key Business Banking policy norms, and each case's deviation record |
| TC-25 | Its approval and delegation matrix, and each case's recorded approval |
