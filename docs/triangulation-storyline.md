# Triangulation: a storyline

| | |
|---|---|
| Scope | How one fact is triangulated across sources: FRD F-18 (fact alignment) and F-19 (cross-checks) |
| Code | [engine/facts.py](../engine/facts.py) (alignment), [engine/crosschecks.py](../engine/crosschecks.py) (the rules) |
| Configuration | [config/crosschecks.yaml](../config/crosschecks.yaml), [config/alignment.yaml](../config/alignment.yaml), [config/tolerances.yaml](../config/tolerances.yaml) |
| Full logic | [cross-verification-logic.md](cross-verification-logic.md); the short rule list is [cross-verification-logic-v2.md](cross-verification-logic-v2.md) |

This page follows one fact, a borrower's turnover for FY 2025-26, from four sources to a verdict. The borrower is fictional. The figures are the worked example in [cross-verification-logic.md §10.4](cross-verification-logic.md#104-worked-example). Tolerances are the provisional values in `config/tolerances.yaml`.

---

## Act 1: Four sources, four versions of the same fact

Turnover for FY 2025-26 shows up in four places, and each source has its own reason to be wrong:

| Source | What it says | Its weakness |
|---|---|---|
| **Audited financials** | ₹4.80 cr, revenue from operations | Prepared by the borrower and only once a year |
| **GST returns (GSTR-3B)** | ₹40 L a month, but only Aug to Mar are on file | Coverage gaps |
| **Bank statements** | ₹4.10 cr of credits across all accounts | Contains money that isn't sales |
| **RM's sourcing message** | "About ₹5 cr" | A claim, not evidence |

Each value was extracted **on its own**. No document was corrected to match another (CLAUDE.md rule 7), so any disagreement is still there to be found.

## Act 2: Making the sources comparable (fact alignment)

The four raw numbers can't be compared yet. `facts._turnover` turns each one into a figure for **the same financial year, on the same basis**:

- **Audited:** taken from the printed revenue row for FY 2025-26.
- **GST:** outward supplies (taxable, zero-rated and nil-rated rows) summed over the return periods on file. It records **8 of 12 months covered** and names Apr to Jul as missing.
- **Bank:** this figure needs cleaning first. Credits go through the exclusion rules in order, and the first rule that matches removes the credit:
  - "TL DISB ₹50,00,000" matches `loan_disbursal` and is removed as borrowed money, not sales.
  - Transfers between the borrower's own accounts, reversals and bounced cheques would also be removed.
  - Only months that **every** account's statements cover are counted.

  The result is **₹3.60 cr** of business credits, and the ₹50 L exclusion is kept with its transaction.
- **Declared:** the RM's ₹5 cr is applied to the latest financial year ended before the appraisal date.

Every figure keeps links to its pages and field values, and records whether any value is still waiting for review. All of it can be inspected at `GET /api/cases/{id}/facts`.

## Act 3: Comparing the sources in pairs

The rules compare the four figures pair by pair:

```
            Audited ₹4.80 cr
           /       |        \
      TO-01      TO-03      TO-04
         /         |          \
   GST (8/12) —TO-02— Bank ₹3.60 cr     Declared ₹5.00 cr
         \___TO-05 (shared months)___/
```

Every pair goes through the same steps:

1. **Are both figures present?** If one is missing, the outcome is **incomplete** and the missing source is named. If nothing is expected (for example, the RM declared nothing), it's **not applicable**.
2. **Does each figure cover the full year?** If not, the outcome is **incomplete** and the missing months are named. A partial year is never compared, because it would always look low.
3. **Is any value still waiting for review?** If so, the outcome is **incomplete** until a person confirms or corrects it (the review gate, F-17.2).
4. **How far apart are they?** The gap is `|a − b| ÷ max(a, b)`, measured against the larger figure so the order doesn't matter. It **passes** within the tolerance and **fails** beyond it.

## Act 4: The verdicts

| Rule | Comparison | Outcome | Why |
|---|---|---|---|
| TO-01 | Audited vs GST | **Incomplete** | GST covers 8 of 12 months; Apr to Jul are named as missing |
| TO-02 | GST vs bank | **Incomplete** | Same GST gap |
| TO-03 | Audited ₹4.80 cr vs bank ₹3.60 cr | **Fail** (moderate) | 25.0% apart; tolerance 1% |
| TO-04 | Declared ₹5.00 cr vs audited ₹4.80 cr | **Fail** (mild) | 4.0% apart; tolerance 2% |
| TO-05 | GST ₹3.20 cr vs bank ₹2.40 cr, Aug to Mar | **Fail** (moderate) | 25.0% apart; every month is flagged in the month-by-month table |

TO-05 fills the gap left by TO-01 and TO-02. When no source covers a whole year, it still compares GST with the bank over **exactly the months both cover**, as long as they share at least 3.

Taken together, the results say more than any single comparison: GST and the audited accounts are close to each other, but the bank sees about 25% less. So the borrower may be banking part of its sales elsewhere, through an account that hasn't been disclosed. That points straight at the bank-accounts checks (BA-01, BA-02) and becomes a query for the borrower.

Each failure carries **both sides**: the values, their pages, the side that differs, the variance and the tolerance. A gap is never reported without its evidence.

## Act 5: The same pattern for every other fact

Turnover is the richest example, but every area follows the same three steps: collect each source's version, align the versions, then compare them pair by pair.

| Fact | Sources | How it's aligned | How it's compared |
|---|---|---|---|
| **Identity** (ID-01 to ID-09) | PAN, GSTIN, CIN, company name, directors and promoters, as read from each document and the case record | Names matched at 0.90 similarity after suffixes like "Pvt Ltd" are made uniform | Values are grouped (identical for identifiers, a name match for names). One group means the sources agree. If one group has a clear majority, the others are marked as the sides that differ |
| **Bank accounts** (BA-01, BA-02) | Bank statements, the declaration of existing facilities, the RM's "existing banking" field, transfer narrations | One account set, keyed by bank and last four digits; the same account seen in two places is merged | Every declared account has a statement, and every account on file was declared |
| **Obligations** (OB-01 to OB-03) | Sanction letters, bureau, RM declaration, bank debits | Recurring NACH, ECS or EMI debits inferred as instalments (at least 3 months, within 5% of the median amount); lender names matched | Facilities reconcile across sources; instalments go to declared lenders; declared borrowings show up as payments in the bank |

## Act 6: The picture updates as evidence arrives

Triangulation isn't run once. It runs again after every document read, every review decision and every configuration publish (`pipeline.refresh_case`):

- When the April to July GST returns arrive, TO-01 and TO-02 change from **incomplete** to a real pass or fail.
- When a reviewer confirms a value that was waiting for review, any check held back by the review gate completes.
- A finding's ID is built from the case, rule and scope, so it stays the same across runs, and any decision made on it stays attached.
- An open finding that no longer fails is withdrawn. Decided findings are kept as the record.

---

**The pattern in one line:** each source gives its own version of a fact; alignment puts the versions in the same period, units and naming; pairwise comparison against configured tolerances shows where they agree and where they don't; and a check without enough evidence stays incomplete, naming what's missing, rather than passing or failing.
