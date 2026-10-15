# Cross-verification demo guide

Three test applications are loaded in the local app to demonstrate the cross-checks: the test plan's four rows, **TC-20 Identity**, **TC-21 Turnover**, **TC-22 Bank accounts** and **TC-23 Existing obligations**. They are also the four areas of the Cross-checks tab.

The applications are synthetic test data, created in the local store by `workflow/seed_cv_test_cases.py`. That script lives in the git-ignored `workflow/` folder, so it is not in the repository; see [Resetting after a rehearsal](#resetting-after-a-rehearsal). The rules themselves are described in [cross-verification-logic-v2.md](cross-verification-logic-v2.md) (simple) and [cross-verification-logic.md](cross-verification-logic.md) (full).

## Which application to use

Use all three, in this order. If you only have time for one, use **Kestrel**.

| Order | Application | What it shows | Time |
|---|---|---|---|
| 1 | **BBG-2026-000004 Kestrel Fabricators Pvt Ltd (TEST)** | A file full of problems: discrepancies in all four areas, and a blocked submission | 10 min |
| 2 | **BBG-2026-000005 Heronbay Polymers Pvt Ltd (TEST)** | A clean file: every source agrees, so all four areas are green | 2 min |
| 3 | **BBG-2026-000006 Marigold Agro Foods Pvt Ltd (TEST)** | An unfinished file: the checks say what is missing instead of guessing | 3 min |

## Before you start

1. The app runs at **http://localhost:4173**.
2. Sign in as **ananya.krishnan@rblbank.com** (Credit Analyst). The password is `auth.demoPassword` in `config/roles.yaml`. For escalations, the Credit Manager is **meenal.kulkarni@rblbank.com**. To change a tolerance or a norm, the Administrator is **nikhil.sawant@rblbank.com**.
3. On **Appraisals**, the three applications are marked **(TEST)**.
4. In each one, open the **Cross-checks** tab.

## How the Cross-checks tab is laid out

| Part | What it shows |
|---|---|
| Header | A one-line summary, then how many discrepancies are adjudicated, the run (for example XR-000004-003), how many rules ran across how many sources, and when. Buttons: **Spread**, **Exception queue** and **Continue to draft**, which stays locked while a blocking discrepancy is open |
| Banner | Only when submission is blocked: "Submission blocked — n serious discrepancies unadjudicated", with the most important one. **Adjudicate now** opens it |
| Overview | Four area cards: **Identity consistency**, **Turnover**, **Bank accounts**, **Existing obligations**. Red: open discrepancies. Amber: some checks could not run. Green: everything checked agrees. Each card shows its open discrepancies by severity, a **Blocking** badge, how many are decided, how many checks could not run or passed, its top finding, and up to three key figures underneath: the values that differ (the two PANs, the turnover in crores, the accounts and lenders concerned), what was confirmed when nothing differs, or what is missing. Click a card to jump to its section, or a key figure to open its check |
| Sections | One per area: its discrepancies, ranked by credit impact (the first card on the page is open); **Could not be checked**, each saying what would complete it; **Passed** (collapsed); **Facts behind these checks** (collapsed) |

Each discrepancy is a card with a reference (XV-…), its severity, and **Blocks submission** when it blocks. Opened, a card shows:

- **The sources side by side:** one column per document, tagged **Declared**, **Borrower-supplied** or **Independent**, with the value, what it covers, **Open the evidence** (the rows read from the document, each opening its page) and **Trace to the source** (the page itself).
- **The gap:** on each leg, against the tolerance ("RBL tolerance: 1% — breached on …"). For a check without amounts, the difference in words, with the differing characters marked.
- **The decision:** **Accept** (valid; it stays on the query list), **Dismiss** (not valid) or **Escalate** (to the Credit Manager). A comment is always required.

---

## 1. Kestrel Fabricators (TEST): a file with problems

**What you see first:**
- **Banner:** "Submission blocked — 3 serious discrepancies unadjudicated", pointing at ID-01.
- **Overview:**
  - Identity consistency: 6 open (3 serious · 2 moderate · 1 mild), **Blocking**.
  - Turnover: 6 open (5 moderate · 1 mild).
  - Bank accounts: 2 open (2 moderate).
  - Existing obligations: 2 open (2 serious).
- **Header:** 16 discrepancies; "24 rules across 13 sources".
- **Key figures on the cards:** the PAN AAACK1234F against the bureau's AAACK9999Z; GST INR 12.00 cr against bank credits INR 9.00 cr, 25.0% apart, and the tax return's INR 11.90 cr against the same INR 9.00 cr; account ·5678 declared with no statement; Ashwood Finserv declared at INR 80.00 lakh against INR 95.00 lakh sanctioned.

If decisions were recorded in a rehearsal, the counts show them. [Reset](#resetting-after-a-rehearsal) for the state above.

**The message:** CreditIQ lines up the same fact from every document, shows exactly where they disagree with the page behind each value, and ranks what matters most.

### TC-20 Identity consistency

| Check | What to point out |
|---|---|
| **ID-01 Entity PAN** (the first card, already open) | Two columns: 16 documents and the sourcing message give AAACK1234F; the commercial bureau report gives AAACK9999Z, with "9999Z" marked. The line underneath says so in words. Click **Trace to the source** on the bureau column to open its page |
| **ID-02 GSTIN** | The bureau shows a GSTIN from another state (29…) against the GST returns (27…) |
| **ID-03 Legal name** | The FY 2024-25 audited statements carry another company's name, Kestrel Engineering Works |
| **ID-04 Promoter set** | The RM named three directors; there is no KYC for **Sunil Karve** |
| **ID-06 Director identifiers** | Ishita Barve's DIN on the KYC differs from the memorandum by one digit |
| **ID-09 Names in full** (mild) | The bureau report names **Tarun S. Velankar**; the director KYC and the memorandum say Tarun Velankar. The names are alike enough for ID-04, but the middle name is missing in two documents: a partial match. Open the card: each document's column splits the names into first, middle and last name. Open **Line by line**: "Missing" is marked in red in the middle-name column |

### TC-21 Turnover

Each turnover card shows its two figures large even when closed, the lower one in red, with how far apart they are.

| Check | What to point out |
|---|---|
| **TO-02 GST vs bank** | GST INR 12.00 cr against INR 9.00 cr of business credits, a gap of INR 3.00 cr, 25.0%, beyond the 1% tolerance. **Open the evidence** on the GST column: each month's return, its filing date and its outward supplies. On the bank column: credits and excluded credits by month and account, and each excluded credit on its own line (the INR 50 lakh loan disbursal and a reversal), so the banked figure is cleansed before it is compared |
| **TX-05 Tax return vs bank** | The FY 2025-26 income tax return shows turnover of INR 11.90 cr; the bank shows INR 9.00 cr, 24.4% apart. The same return agrees with the audited INR 11.80 cr (TX-03) and GST's INR 12.00 cr (TX-04), both under **Passed**: the tax return and the books agree, the bank does not |
| **TO-03 Audited vs bank** | Audited INR 11.80 cr against INR 9.00 cr banked, 23.7% apart |
| **TX-02 Profit vs the tax return** | FY 2024-25: profit before tax INR 60.00 lakh in the books against INR 45.00 lakh in the return, 25.0% apart. The FY 2025-26 return agrees with its books (under **Passed**) |
| **TO-04 Declared vs evidenced** | The RM declared INR 18 cr; the audited figure is INR 11.80 cr, 34.4% apart (tolerance 2%) |
| **TO-01 Audited vs GST** | Audited INR 11.80 cr against GST INR 12.00 cr, 1.7% apart: close, but beyond the 1% tolerance |
| **TX-01, TX-03, TX-04** (under **Passed**) | A return for each year due; the tax return against audited and GST, each 0.8% apart |

Point out that the bank figure is **cleansed** first, and that three independent sources (audited, GST, the tax return) agree around INR 11.8 to 12 cr while the bank shows INR 9 cr: sales may be banked elsewhere.

### TC-22 Bank accounts

| Check | What to point out |
|---|---|
| **BA-01 Declared accounts have statements** | The RM declared account ·5678, but no statement was given for it |
| **BA-02 Accounts on file are declared** | An Ironleaf Bank account ·7777 has a statement nobody declared, and account ·1122 appears only in a transfer |

Open **Facts behind these checks** to show every account and where it appears.

### TC-23 Existing obligations

| Check | What to point out |
|---|---|
| **OB-01 Facilities reconcile** | Three columns: the declaration, the sanction letters and the bureau. Ashwood Finserv is declared at INR 80 lakh but sanctioned at INR 95 lakh (sanction letter and bureau agree): a gap of INR 15 lakh, 15.8%, beyond the 5% tolerance. The bureau also shows a Tidewater Finance loan that was never declared |
| **OB-02 EMIs go to declared lenders** | The bank statement pays Tidewater INR 2.50 lakh every month, INR 30 lakh a year, to a lender nobody declared |
| **OB-03** (under **Passed**) | The loans in the books are paid in the bank |

### Show what happens next

1. **Decide.** On ID-04 choose **Accept**, type a comment and **Record decision**. The card shows who decided, when and why. The identity card's counts, the banner ("2 serious…") and the header update at once.
2. **Escalate.** On ID-02 choose **Escalate** with a comment. It stays open and blocking. Signed in as the Credit Manager, accept or dismiss it on the board, or from the **Review queue**, where it is marked **Escalated**; a comment is required there too.
3. **Unlock.** Once ID-01, ID-02 and ID-04 are accepted or dismissed, the banner disappears and **Continue to draft** unlocks.
4. **Elsewhere.** On the **Completeness** tab the pre-login query list carries a plain question for each accepted finding (a dismissed one drops out). **Outputs → Draft CAM and PD note** carry the findings into the memo and the personal discussion.

---

## 2. Heronbay Polymers (TEST): a clean file

**What you see:**
- **Overview:** all four area cards green ("No discrepancy").
- **Checks:** 24 passed and 1 not applicable, including the tax return's turnover against audited, GST and bank (TX-03 to TX-05), and the directors' names in full (ID-09).
- **Header:** no discrepancy.

**The message:** CreditIQ doesn't raise false alarms. When the documents agree, every check passes.

What to point out:

- Open **Passed** in any section: each check is listed with its variance where it has one (for example TO-02, 0.5%; every turnover figure is within 1% of the others), so a pass is evidenced, not assumed.
- **TO-05** is not applicable because the GST returns and bank statements cover exactly one financial year, which TO-02 already compares.

---

## 3. Marigold Agro Foods (TEST): a file that isn't complete yet

**What you see:**
- **Overview:**
  - Identity consistency: amber (6 could not be checked · 3 passed).
  - Turnover: 1 open (1 moderate), with 4 could not be checked · 2 passed · 4 not applicable (its tax return shows no turnover).
  - Bank accounts: green.
  - Existing obligations: amber (2 could not be checked · 1 passed).
- **One discrepancy:** TO-05 (below).

**The message:** when something is missing, CreditIQ says exactly what, rather than passing or failing a check it can't complete.

What to point out:

| Check | What to point out |
|---|---|
| **ID-04, ID-05, ID-06, ID-08** | Each says what would complete it: "To complete it, provide the director KYC", "… the memorandum and articles of association". Click **Add to query list** on one: it shows **On the query list**, and the Completeness tab's query list asks the customer for it |
| **TO-01 to TO-03** | GST returns and statements run September to August, so each financial year is only partly covered: "GST outward supplies covers 7 of 12 months". Each asks for the missing months, for example "GSTR-3B returns for Apr 2025 to Aug 2025" |
| **TO-05 GST vs bank, months both cover** | Still compares GST against the bank over the 12 months both cover (Sep 2025 to Aug 2026): GST INR 5.04 cr against INR 4.80 cr of business credits, 4.8% apart, beyond the 1% tolerance |
| **OB-01, OB-02** | A sanction letter and monthly EMIs are on file, but no declaration of existing facilities, so both ask for it |
| **ID-01** | **Waiting for review**: the tax return's PAN was read with low confidence. Click it, confirm the PAN, then come back: ID-01 now passes. Checks never rely on a value a person hasn't confirmed |

---

## Test plan rows at a glance

| Test plan row | Expected | Show it on |
|---|---|---|
| TC-20 Identity | Mismatches in PAN, GSTIN, names or the promoter set flagged with their sources | Kestrel, Identity consistency: ID-01, ID-02, ID-03, ID-04 |
| TC-21 Turnover | Turnover compared across sources; variances beyond tolerance flagged with values; incomplete coverage stated | Kestrel, Turnover: TO-01 to TO-04, and the tax return: TX-05 (against the bank), TX-02 (profit). Heronbay: every turnover check passing, within 1%. Marigold, Turnover: TO-01 to TO-03 (coverage), TO-05 (4.8% over the months both cover) |
| TC-22 Bank accounts | Accounts without statements and undeclared accounts identified | Kestrel, Bank accounts: BA-01, BA-02 |
| TC-23 Existing obligations | Obligations reconciled; EMIs to lenders not declared identified | Kestrel, Existing obligations: OB-01, OB-02 |

The board-resolution and financial-statement checks (BR-01 to BR-04, FS-01, FS-02) are switched off, so they no longer appear: Kestrel's board-resolution, restatement and year-end balance findings are not shown. The income-tax checks (TX-01 to TX-05) run under Turnover.

## Resetting after a rehearsal

Decisions, escalations and query-list additions made during a rehearsal stay on the applications. To start again from the original state, run from the repository root:

```powershell
.venv\Scripts\python.exe workflow\seed_cv_test_cases.py delete
.venv\Scripts\python.exe workflow\seed_cv_test_cases.py create
```

Recreated applications get new numbers (case numbers are never reused), and their discrepancy references start again at XV-…-01. Before merging, run only `delete`.

The sample RBL records for the policy demonstration (below) are removed with `.venv\Scripts\python.exe workflow\seed_policy_reference.py delete` and stored again with `create` (after the applications exist).

---

## Policy checks (TC-24, TC-25)

The **Policy** tab of the same applications shows the policy norms and the approving authority. The norms and the approval matrix are provisional proposals until RBL supplies its own.

| Part | What to point out |
|---|---|
| Overview | Five cards: **Eligibility**, **Financial ratios**, **Documentation**, **Security cover** and **Approving authority**. Each norm card shows its deviations large and its key norms with actual against required. Click a card to jump to its section |
| Sections | Each norm with its required and actual values, the figures it used with their pages, and **How was this decided** (the formula, the ratio's definition and its note) |
| Approving authority | The amount picks an authority per product; each group of deviations moves it one level up; the highest wins. "At least" when a norm could not be evaluated, with whether it could rise |

**Kestrel:**
- Deviations: FR-06 working-capital cycle at 90 days against at most 75; DOC-01 with 3 blocking checklist items open.
- Cannot evaluate: FR-03 DSCR, because the term loan's proposed instalment was not entered.
- Authority: **Head Office Credit Committee**, at least (the amount needs the Zonal Credit Committee; each deviation moves it one level up).

**Marigold:**
- Deviations: EL-05 request against turnover at 60.5% against at most 20%; FR-06; DOC-01 (7 items); DOC-02 with 1 year of audited statements.
- Cannot evaluate: EL-02 bureau rank (no report on file).
- Authority: **Zonal Credit Committee**, at least.

**Scoring against RBL's record.** Sign in as the Credit Manager (meenal.kulkarni@rblbank.com) and open the **Comparison** tab. A sample RBL record is stored for each application:

| Application | What it shows |
|---|---|
| Kestrel | FR-06 **Agree** (90 days on both); DOC-01 **Differ** (3 against 6 items); FR-03 **Missed** (RBL recorded a DSCR of 1.32x that CreditIQ could not assess); approving authority **Agree** (Head Office Credit Committee) |
| Marigold | EL-05, FR-06 and DOC-02 **Agree**; DOC-01 **New** (found only by CreditIQ); approving authority **Differ** (RBL's record says Regional Credit Head, lower than the matrix requires) |

Decide a Differ or New item as **Valid** or **Not valid** with a reason; the area scores show the share of RBL's deviations found (C4) and of CreditIQ's upheld (C5). The approving authority is shown but not scored while the matrix is provisional (TC-25 counts only once RBL's matrix is published). The analyst never sees RBL's record.

---

## Changing a tolerance or a norm (Administration → Settings)

Sign in as the Administrator (**nikhil.sawant@rblbank.com**). Settings opens straight away. It shows the tolerances, the policy norms, the cross-check rules and the approval matrix in force (details in [admin-settings.md](admin-settings.md)).

1. Change **Turnover variance between sources** from 1 to 2 (%). The field is marked "was 1%" and the bar counts one change.
2. **Review and publish** lists the change (1% → 2%). Type a note and **Publish**. The new version is in force and every application's checks run again under it.
3. Sign in as the analyst and open Kestrel's Cross-checks: TO-01 (audited against GST, 1.7% apart) now passes, because it is within 2%. **Administration → Configuration** lists the new version as **Edited on screen**.

**Put it back afterwards:** change the value back to 1 and publish again. A later publish from the configuration files refuses to undo a screen edit unless asked (`--discard-app-edits`).
