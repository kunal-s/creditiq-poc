# Cross-verification rules (simple version)

CreditIQ runs **24 rules in 4 areas** on every application: identity consistency, turnover, bank accounts and existing obligations, the test plan's rows TC-20 to TC-23. Six more rules are defined but switched off (see [Switched off](#switched-off-not-run)). Each rule compares the same fact across the documents on file and gives one result:

- **Pass:** the documents agree, within the tolerance where the rule has one.
- **Fail:** they do not. The finding shows both values, each with its page.
- **Incomplete:** the check cannot finish yet. The missing document, missing months or value waiting for review is named.
- **Not applicable:** there is nothing to compare.

**Severity** is how serious a failure is: serious, moderate or mild. "Blocks" marks a failure that blocks submission: the draft memo cannot be started while it is not accepted or dismissed. Every failure, whatever its severity, is a discrepancy on the Cross-checks tab, where a person accepts it (a valid finding), dismisses it (not valid) or escalates it to the Credit Manager, always with a comment; the cross-verification stage is done once each one is accepted or dismissed.

**Tolerance** is how far two sources may differ and still agree. A percentage is measured against the larger of the two values. "Exact" means no difference is allowed. "Name match 0.90" means two names are treated as one when they are at least 90% similar, after case, punctuation and suffixes such as "Pvt Ltd" / "Private Limited" are made uniform. All tolerances are provisional until RBL supplies its own (`config/tolerances.yaml`).

For the full logic with code, see [cross-verification-logic.md](cross-verification-logic.md).

---

## 1. Identity consistency (test plan TC-20)

| Rule | What it checks | Documents | Tolerance | Severity |
|---|---|---|---|---|
| **ID-01** Entity PAN | The company's PAN is the same everywhere. The PAN inside the GSTIN (characters 3 to 12) counts too | Company PAN, Income tax return, GSTR-3B, Commercial bureau report, Declaration of existing facilities, Sourcing message | Exact | Serious (blocks) |
| **ID-02** GSTIN | The GSTIN is the same everywhere | GSTR-3B, Commercial bureau report, Declaration of existing facilities, Sourcing message | Exact | Serious (blocks) |
| **ID-03** Legal name | The company name reads the same everywhere. A bank's shortened account name (a leading part of the full name, 8+ characters and 2+ words) also counts as the same | Certificate of incorporation, Memorandum and articles, Board resolution, Company PAN, Income tax return, GSTR-3B, Audited financial statements, Bank statement, Commercial bureau report, Declaration of existing facilities, Sanction letter | Name match 0.90 | Moderate |
| **ID-04** Promoter set | Every promoter or director named anywhere is named in every source. A promoter without a KYC is flagged | Director KYC, Sourcing message, Commercial bureau report | Name match 0.90 | Serious (blocks) |
| **ID-05** CIN | The company's CIN is the same everywhere | Certificate of incorporation, Memorandum and articles, Commercial bureau report, Declaration of existing facilities, Sourcing message | Exact | Serious (blocks) |
| **ID-06** Director identifiers | Each director's DIN on the KYC matches the memorandum; the PAN on a KYC is a person's PAN, not the company's | Director KYC, Memorandum and articles | Exact (directors matched by name match 0.90) | Moderate |
| **ID-07** CIN particulars | The year and company type encoded in the CIN match the date of incorporation and the application's constitution | Certificate of incorporation (and the application) | Exact | Mild |
| **ID-08** Memorandum directors | Every director in the memorandum has a KYC or is named in the sourcing message | Memorandum and articles, Director KYC, Sourcing message | Name match 0.90 | Mild |
| **ID-09** Names in full | A person's first, middle and last name agree across documents. A part missing in one ("Tarun Velankar" against "Tarun S. Velankar"), given only as an initial, or spelt differently is flagged as a partial match, even where the names are alike enough for ID-04 | Director KYC, Memorandum and articles, Commercial bureau report | Exact, part by part | Mild |

## 2. Turnover (test plan TC-21)

Compared one financial year at a time (April to March). A year where a source covers fewer than 12 months is **incomplete**, with the missing months named. Bank credits are **cleansed** first: transfers between the borrower's own accounts, loan disbursals, reversals and returned cheques are removed.

| Rule | What it checks | Documents | Tolerance | Severity |
|---|---|---|---|---|
| **TO-01** Audited vs GST | Audited turnover against GST outward supplies | Audited financial statements, GSTR-3B | 1% | Moderate |
| **TO-02** GST vs bank | GST outward supplies against cleansed bank credits | GSTR-3B, Bank statement | 1% | Moderate |
| **TO-03** Audited vs bank | Audited turnover against cleansed bank credits | Audited financial statements, Bank statement | 1% | Moderate |
| **TO-04** Declared vs evidenced | The turnover the RM declared against audited turnover. Not applicable when nothing was declared | Sourcing message, Audited financial statements | 2% | Mild |
| **TO-05** GST vs bank, shared months | GST against bank credits over the months both cover, when they don't line up with one financial year. Each month is shown | GSTR-3B, Bank statement | 1%; needs at least 3 shared months | Moderate |
| **TX-01** Returns on file | Every audited year has its income tax return, once it is due | Audited financial statements, Income tax return | Due 214 days after the year end | Mild |
| **TX-02** Profit agrees | Profit before tax in the audited statements against the profit in the tax return | Audited financial statements, Income tax return | 10% | Moderate |
| **TX-03** Tax return vs audited | The turnover the income tax return shows against audited revenue, for the year the return covers | Income tax return, Audited financial statements | 1% | Moderate |
| **TX-04** Tax return vs GST | The tax return's turnover against GST outward supplies for that year (all 12 returns needed) | Income tax return, GSTR-3B | 1% | Moderate |
| **TX-05** Tax return vs bank | The tax return's turnover against cleansed bank credits for that year (all 12 months needed) | Income tax return, Bank statement | 1% | Moderate |

The tax-return checks follow the returns: a return is filed after its year ends, so they compare the years the returns cover. A return that shows no turnover leaves TX-03 to TX-05 not applicable; so does a source that does not reach the return's year.

## 3. Bank accounts (test plan TC-22)

The account set is built from every document: statements, the declaration, the RM's message, and accounts named in transfers. An account is identified by its last four digits and its bank.

| Rule | What it checks | Documents | Tolerance | Severity |
|---|---|---|---|---|
| **BA-01** Declared accounts have statements | Every account the borrower or RM declared has a statement on file. Not applicable when no accounts were declared | Declaration of existing facilities, Sourcing message, Bank statement | Exact on the last four digits; bank names by name match 0.90 | Moderate |
| **BA-02** Accounts on file are declared | Every account with a statement was declared, and no account appears only in transfers without a statement | Bank statement, Declaration of existing facilities, Sourcing message | Exact on the last four digits; bank names by name match 0.90 | Moderate |

## 4. Existing obligations (test plan TC-23)

Loan instalments are found in bank statements as debits with an EMI cue (NACH, ECS, EMI…) to the same lender. Lender names are matched without words such as "Bank", "Finance" or "Limited", so "Tidewater Finance Limited" and "TIDEWATER FIN" are one lender.

| Rule | What it checks | Documents | Tolerance | Severity |
|---|---|---|---|---|
| **OB-01** Facilities reconcile | Each existing facility appears in the declaration and in a sanction letter or the bureau report, with matching sanctioned amounts. Flags a facility not declared, a declared facility nothing else shows, or amounts that differ | Declaration of existing facilities, Sanction letter, Commercial bureau report, Sourcing message | Sanctioned amounts within 5%; lenders by name match 0.90 or the same first significant word | Serious |
| **OB-02** EMIs go to declared lenders | Every lender paid by instalment in the bank statements is declared | Bank statement, Declaration of existing facilities, Sourcing message | An instalment is a debit in at least 3 months with amounts within 5%; lenders by name match 0.90 or the same first significant word | Serious |
| **OB-03** Borrowings are serviced | Long-term borrowings in the books have instalments in the bank, and instalments in the bank have borrowings in the books | Audited financial statements, Bank statement | None: presence on both sides | Moderate |

---

## Summary

| Area | Rules | Test plan | Serious | Moderate | Mild |
|---|---|---|---|---|---|
| Identity consistency | ID-01 to ID-09 | TC-20 | 4 | 2 | 3 |
| Turnover | TO-01 to TO-05, TX-01 to TX-05 | TC-21 | | 8 | 2 |
| Bank accounts | BA-01, BA-02 | TC-22 | | 2 | |
| Existing obligations | OB-01 to OB-03 | TC-23 | 2 | 1 | |
| **Total that run** | **24** | | **6** | **13** | **5** |
| Switched off | BR-01 to BR-04, FS-01, FS-02 | | 1 | 3 | 2 |

Four rules block submission when they fail: ID-01, ID-02, ID-04 and ID-05.

### Tolerances in one place

Tightened on 12 October 2026: turnover from 10% to 1%, declared turnover from 20% to 2%, name match from 0.85 to 0.90.

| Tolerance | Value | Used by |
|---|---|---|
| Turnover variance | 1% | TO-01, TO-02, TO-03, TO-05, TX-03, TX-04, TX-05 |
| Declared turnover variance | 2% | TO-04 |
| Name match | 0.90 similarity | ID-03, ID-04, ID-06, ID-08, ID-09 (to find the person), BA-01, BA-02, OB-01, OB-02 |
| Shared months for GST against bank | at least 3 | TO-05 |
| Income tax return due | 214 days after the year end | TX-01 |
| Profit variance | 10% | TX-02 |
| Previous-year figures | 1% | FS-01 (switched off) |
| Year-end bank balance | 1% | FS-02 (switched off) |
| Facility sanctioned amount | 5% | OB-01 |
| EMI amount match | 5% | OB-02 (finding instalments) |
| EMI months | at least 3 | OB-02 (finding instalments) |

---

## Switched off (not run)

On 11 October 2026 the board-resolution, income-tax and financial-statement rules were switched off, so the cross-verification board covers the test plan's four areas. On 12 October the income-tax rules (TX-01, TX-02) came back, under Turnover, with the new tax-return turnover checks (TX-03 to TX-05). These six stay off. They stay in `config/crosschecks.yaml` with `enabled: false`, are still validated, and can be switched back on by removing that line and publishing. While switched off they give no finding, so no discrepancy, query, CAM or PD-note entry, and BR-01 no longer blocks submission.

### Borrowing authority (the board resolution)

| Rule | What it checks | Documents | Tolerance | Severity |
|---|---|---|---|---|
| **BR-01** Resolution covers the amount | The board resolution's borrowing limit is at least the amount requested | Board resolution (and the application's amount) | None: limit must be at least the amount | Serious (blocks) |
| **BR-02** Signatories are directors | Everyone authorised to sign is a director on file | Board resolution, Director KYC, Memorandum and articles, Sourcing message | Name match 0.90 | Moderate |
| **BR-03** Resolution names this bank | The resolution authorises borrowing from RBL Bank (RBL Bank Limited, RBL Bank or Ratnakar Bank Limited) | Board resolution | Name match 0.90, ignoring words such as "Bank" and "Limited" | Moderate |
| **BR-04** Resolution correctly dated | The resolution is dated after incorporation and not after the appraisal date | Board resolution, Certificate of incorporation | None: dates must be in order | Mild |

### Financial statements

| Rule | What it checks | Documents | Tolerance | Severity |
|---|---|---|---|---|
| **FS-01** Previous-year figures | The previous-year column of the later statements matches that year's own statements (revenue, profit after tax, net worth, borrowings). A difference means the accounts were restated | Audited financial statements (two years) | 1% per line | Moderate |
| **FS-02** Year-end bank balance | The bank balances on the year end are not more than the audited cash and bank balance | Audited financial statements, Bank statement | 1% above the audited figure | Mild |
