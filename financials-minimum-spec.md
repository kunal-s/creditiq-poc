# Financials: what to extract, how to compute, how to cross-check

A reference for developers. It lists:
- the minimum financial data CreditIQ must extract;
- where each item is printed;
- how each figure and ratio is computed;
- how bank statements are processed;
- how the cross-checks compare sources.

Thresholds are **provisional** until RBL's policy replaces them (`config/policy.yaml`, `config/tolerances.yaml`). Every number in the examples is synthetic and has been checked.

**Priority:** **Must** = the bare minimum for the PoC. **Next** = after the Must set works.
**Today:** **Yes** = extracted or computed now; **Partly** = exists but incomplete; **New** = not built.

---

## 0. Conventions and terms

### 0.1 Conventions

| Topic | Rule |
|---|---|
| Money | Store every amount in **rupees** as a number. 1 lakh = 1,00,000; 1 crore = 100 lakh = 1,00,00,000. The examples below are in lakh |
| Unit on the statement | Read the heading ("All amounts in INR thousands", "Rs in lakhs", "₹ in crores") and multiply every line: rupees ×1; thousands ×1,000; lakhs ×1,00,000; millions ×10,00,000; crores ×1,00,00,000 |
| Negative numbers | (1,234), -1,234 and "1,234 Dr" are negative |
| Nil | "-", "—" or a blank cell on a printed row means **0**, not missing. A row that is not printed at all also counts as 0, but **only if the statement's totals tie** (§1.5). Otherwise it is missing and goes to review |
| Financial year (FY) | April to March. "FY 2024-25" runs 1 Apr 2024 to 31 Mar 2025. An income tax return's assessment year (AY) is the FY plus one: AY 2025-26 covers FY 2024-25 |
| Two columns | Each statement prints the current year and the previous year. Extract **both**, tagged with their year-end dates |
| Basis | Each statement is **audited**, **provisional** (current year, unaudited) or **projected** (future years). Read it from the title, the auditor's report, or a "provisional" or "projected" heading |
| Evidence | Every extracted value keeps its document and page; every computed value lists its inputs |
| Variance between two figures | \|A − B\| ÷ the larger of \|A\| and \|B\| × 100 (as the cross-checks already do) |

### 0.2 Terms

| Term | Plain meaning |
|---|---|
| Net worth (NW) | The owners' money in the business: share capital plus reserves (for a firm, the partners' capital) |
| Tangible net worth (TNW) | Net worth less intangible assets, which a lender cannot sell |
| TOL (total outside liabilities) | Everything the business owes to others: total liabilities less net worth |
| Borrowings, debt | Loans: term loans, and cash credit or overdraft from banks or NBFCs |
| CMLTD | Current maturities of long-term debt: the part of a term loan repayable in the next 12 months |
| CC / OD | Cash credit or overdraft: a running working-capital limit. The account is "drawn" up to a limit |
| EBITDA | Profit from operations before interest, tax, depreciation and amortisation |
| Cash accruals | Profit after tax plus depreciation: the cash the year's profit produces |
| DSCR | Debt-service coverage: how many times the year's cash covers the year's loan repayments and interest |
| Working capital | Money tied up in stock and receivables, less what suppliers fund |
| NWC (net working capital) | Current assets less current liabilities |
| MPBF | Maximum permissible bank finance: a working-capital limit method for larger limits |
| Turnover method (Nayak) | A working-capital limit method for limits up to ₹5 cr, worked from turnover |
| ABB | Average bank balance |
| NACH / ECS / ACH | Automated debits, used for loan instalments (EMIs) |
| Inward return / bounce | A cheque or auto-debit **issued by the borrower** that the bank refused, usually for insufficient funds. A bad sign |
| Outward return | A cheque **from the borrower's customer** that bounced |
| DPD / SMA | Days past due on a loan. SMA-0 is 1 to 30 days, SMA-1 is 31 to 60, SMA-2 is 61 to 90; beyond 90 days the loan is a non-performing asset (NPA) |
| CMR | CIBIL MSME Rank on a commercial bureau report, from 1 (lowest risk) to 10 |
| GSTR-3B / GSTR-1 | Monthly or quarterly GST returns. 3B is the summary with tax paid; 1 lists the sales |

---

## 1. Financial statements (audited, provisional, projected)

### 1.1 Document-level fields

| Key | What | Where it is printed | Example | Today | Priority |
|---|---|---|---|---|---|
| `company_name` | Entity name | Statement heading | Example Industries Pvt Ltd | Yes | Must |
| `financial_year` | Year-end date of each column | "Balance sheet as at 31 March 2025"; column headings | 2025-03-31 | Yes (current column only) | Must |
| `amount_unit` | Unit of every amount | Heading line: "All amounts in INR thousands" | lakhs → ×1,00,000 | **New** | **Must** |
| `statement_basis` | Audited, provisional or projected | Title; auditor's report present; "Provisional" stamp | audited | Partly (audited only) | Must |
| `auditor_name`, `audit_date` | Auditor and report date | Auditor's signature block | — | Yes | Must |
| `audit_opinion` | Unqualified, qualified, adverse, or emphasis of matter | Auditor's report, "Opinion" paragraph | unqualified | New | Next |

### 1.2 Balance sheet

The layout is Schedule III (Division I) for most MSME companies. Ind AS companies (Division II) and firms use different labels, listed under "Also printed as".

**Liabilities side ("Equity and liabilities")**

| # | Key | Plain meaning | Printed as | Also printed as | Today | Priority |
|---|---|---|---|---|---|---|
| B1 | `share_capital` | Owners' invested capital | Share capital | Equity share capital; Partners' capital account; Proprietor's capital | Yes | Must |
| B2 | `reserves_and_surplus` | Profits kept in the business (can be negative) | Reserves and surplus | Other equity (Ind AS); Surplus in P&L; Retained earnings | Yes | Must |
| B3 | `share_application_money` | Money received for shares not yet issued | Money received against share warrants; Share application money pending allotment | — | New | Must (usually 0) |
| B4 | `long_term_borrowings` | Loans repayable after 12 months (term loans) | Long-term borrowings | Borrowings (non-current); Secured loans / Unsecured loans (firms; split by nature) | Yes | Must |
| B5 | `deferred_tax_liability` | Tax payable in future years | Deferred tax liabilities (net) | — | New | Must |
| B6 | `other_long_term_liabilities` | Other dues after 12 months | Other long-term liabilities | Other non-current liabilities; Other financial liabilities (non-current) | New | Must |
| B7 | `long_term_provisions` | Long-term provisions (for example gratuity) | Long-term provisions | Provisions (non-current) | New | Must |
| B8 | `short_term_borrowings` | Loans repayable within 12 months: bank CC/OD, **plus CMLTD** (since FY 2021-22) | Short-term borrowings | Borrowings (current); Bank overdraft; Cash credit | Yes | Must |
| B9 | `trade_payables` | Money owed to suppliers | Trade payables (MSME + others: add both) | Sundry creditors; Creditors for goods | Yes | Must |
| B10 | `other_current_liabilities` | Other dues within 12 months (statutory dues, advances from customers, expenses payable) | Other current liabilities | Other financial liabilities (current); Current liabilities | Yes | Must |
| B11 | `short_term_provisions` | Short-term provisions, tax payable | Short-term provisions | Provisions (current); Current tax liabilities (net) | Yes | Must |
| B12 | `total_equity_and_liabilities` | Total of the liabilities side | TOTAL | Total equity and liabilities | **New** | **Must** (tie-out) |

**Assets side**

| # | Key | Plain meaning | Printed as | Also printed as | Today | Priority |
|---|---|---|---|---|---|---|
| B13 | `net_fixed_assets` | Plant, machinery, buildings, after depreciation | Property, plant and equipment (net block) | Fixed assets: tangible assets; Net block | New | Must |
| B14 | `capital_work_in_progress` | Assets being built | Capital work-in-progress | — | New | Must |
| B15 | `intangible_assets` | Software, goodwill, brands | Intangible assets (+ under development) | Goodwill | New | Must |
| B16 | `non_current_investments` | Long-term investments, often in group companies | Non-current investments | Investments | New | Must |
| B17 | `deferred_tax_asset` | Tax saved in future years | Deferred tax assets (net) | — | New | Must |
| B18 | `long_term_loans_and_advances` | Long-term money lent or advanced | Long-term loans and advances | Loans (non-current) | New | Must |
| B19 | `other_non_current_assets` | Other long-term assets | Other non-current assets | Other financial assets (non-current) | New | Must |
| B20 | `current_investments` | Investments to be sold within 12 months | Current investments | — | New | Must |
| B21 | `inventories` | Stock: raw material, work in progress, finished goods | Inventories | Closing stock; Stock-in-trade | Yes | Must |
| B22 | `trade_receivables` | Money customers owe | Trade receivables | Sundry debtors; Debtors | Yes | Must |
| B23 | `cash_and_bank_balances` | Cash and bank balances | Cash and bank balances | Cash and cash equivalents **+** Other bank balances (Ind AS: add both) | Yes | Must |
| B24 | `short_term_loans_and_advances` | Short-term money lent or advanced | Short-term loans and advances | Loans (current); Advances recoverable | Yes | Must |
| B25 | `other_current_assets` | Other short-term assets (prepaid, GST input credit receivable) | Other current assets | Other financial assets (current) | **New** | **Must** |
| B26 | `total_assets` | Total of the assets side | TOTAL | Total assets | **New** | **Must** (tie-out) |

### 1.3 Profit and loss statement

| # | Key | Plain meaning | Printed as | Also printed as | Today | Priority |
|---|---|---|---|---|---|---|
| P1 | `revenue_from_operations` | Sales, net of GST | Revenue from operations | Sales; Turnover; Income from operations; Gross receipts | Yes | Must |
| P2 | `other_income` | Interest, rent, gains: not from the business | Other income | Non-operating income | Yes | Must |
| P3 | `total_income` | P1 + P2 | Total revenue; Total income | — | New | Must (tie-out) |
| P4 | `cost_of_materials_consumed` | Raw material used | Cost of materials consumed | Raw material consumed | New | Must |
| P5 | `purchases_of_stock_in_trade` | Goods bought for resale | Purchases of stock-in-trade | Purchases | New | Must |
| P6 | `changes_in_inventories` | Change in stock. **Negative** when stock went up | Changes in inventories of finished goods, work-in-progress and stock-in-trade | (Increase)/decrease in stock | New | Must |
| P7 | `employee_benefits_expense` | Salaries and wages | Employee benefits expense | Salaries and wages; Staff cost | New | Next |
| P8 | `finance_costs` | Interest on loans. **No row means 0** | Finance costs | Interest; Interest and finance charges | Yes (absent row breaks EBITDA) | Must |
| P9 | `depreciation` | Wear and tear of fixed assets (non-cash) | Depreciation and amortisation expense | Depreciation | Yes | Must |
| P10 | `other_expenses` | Everything else | Other expenses | Administrative expenses; Manufacturing expenses (add all) | New | Next |
| P11 | `total_expenses` | Sum of expenses | Total expenses | — | New | Must (tie-out) |
| P12 | `exceptional_items` | One-off gains or losses | Exceptional items; Extraordinary items | — | New | Next |
| P13 | `profit_before_tax` | Profit before tax | Profit before tax | Net profit before tax | Yes | Must |
| P14 | `tax_expense` | Current tax + deferred tax | Tax expense (total) | Provision for tax | New | Must |
| P15 | `profit_after_tax` | Profit after tax | Profit/(Loss) for the year (or period) | Profit after tax; Net profit; Net profit transferred to capital account (firms) | Yes (label fragile) | Must |

### 1.4 From the notes to accounts (Next)

| Key | Plain meaning | Where | Used for |
|---|---|---|---|
| `current_maturities_of_long_term_debt` | Term-loan principal due in the next 12 months | Note on short-term borrowings: "Current maturities of long-term debt" | DSCR principal; MPBF (not bank working-capital finance) |
| `bank_working_capital_borrowings` | CC/OD from banks | Note on short-term borrowings: "Loans repayable on demand from banks" | MPBF |
| `loans_from_directors` | Unsecured loans from promoters | Note on borrowings: "From directors / related parties" | Quasi-equity (if RBL's policy allows) |
| `finance_costs_term_loans` | Interest on term loans | Note on finance costs | DSCR |
| `receivables_over_6_months` | Old receivables | Ageing schedule in the note on trade receivables | Quality of receivables; drawing power |
| `contingent_liabilities` | Guarantees given, disputed dues | Note: "Contingent liabilities and commitments" | Risk |

### 1.5 Integrity checks: run before computing anything

| Check | Formula | Tolerance | If it fails |
|---|---|---|---|
| Balance sheet balances | `total_assets` = `total_equity_and_liabilities` | Rounding: 1 unit of the printed unit | Statement goes to review |
| Liabilities add up | B1 + … + B11 = B12 | Rounding × number of lines | Review; an extracted line is wrong or missing |
| Assets add up | B13 + … + B25 = B26 | Same | Same |
| Income add up | P1 + P2 = P3 | Same | Same |
| Expenses add up | P4 + P5 + P6 + P7 + P8 + P9 + P10 = P11 | Same | Same |
| Profit arithmetic | P3 − P11 (± P12) = P13; P13 − P14 = P15 | Same | Same |
| Previous year agrees | The previous-year column of year t = the current-year column of year t−1's own statement | 1% | Finding: restated accounts (FS-01) |

---

## 2. Computed figures and ratios

### 2.1 The example company (amounts in ₹ lakh, FY 2024-25)

| Balance sheet | ₹ lakh | | Profit and loss | ₹ lakh |
|---|---|---|---|---|
| Share capital | 100 | | Revenue from operations | 3,000 (previous year 2,600) |
| Reserves and surplus | 420 | | Other income | 20 |
| Long-term borrowings | 300 | | Materials consumed | 2,000 |
| Deferred tax liability | 10 | | Purchases of stock-in-trade | 100 |
| Other long-term liabilities | - (0) | | Change in inventories | −50 |
| Long-term provisions | 15 | | Employee cost | 250 |
| Short-term borrowings (CC 400 + CMLTD 80) | 480 | | Finance costs (term loan 35, CC 75) | 110 |
| Trade payables | 350 | | Depreciation | 60 |
| Other current liabilities | 90 | | Other expenses | 280 |
| Short-term provisions | 35 | | Total expenses | 2,750 |
| **Total** | **1,800** | | Profit before tax | 270 |
| Net fixed assets | 520 | | Tax | 70 |
| Capital work-in-progress | 30 | | Profit after tax | 200 |
| Intangible assets | 20 | | | |
| Non-current investments | 40 | | | |
| Long-term loans and advances | 25 | | | |
| Other non-current assets | 5 | | | |
| Inventories | 600 | | | |
| Trade receivables | 450 | | | |
| Cash and bank | 40 | | | |
| Short-term loans and advances | 50 | | | |
| Other current assets | 20 | | | |
| **Total** | **1,800** | | | |

### 2.2 Computed lines

| Key | Formula | Meaning | Example | Today |
|---|---|---|---|---|
| `cost_of_sales` | P4 + P5 + P6 | What the goods sold cost | 2,000 + 100 − 50 = **2,050** | New |
| `gross_profit` | P1 − cost_of_sales | Sales less cost of sales | 3,000 − 2,050 = **950** | New |
| `ebitda` | P13 + P8 + P9 − P2 | Operating profit before interest and depreciation (other income left out) | 270 + 110 + 60 − 20 = **420** | Partly: today P13 + P8 + P9, which keeps other income in (see §6) |
| `cash_accruals` | P15 + P9 | Cash the year's profit produces | 200 + 60 = **260** | New |
| `net_worth` | B1 + B2 + B3 | Owners' money | 100 + 420 + 0 = **520** | Yes (without B3) |
| `tangible_net_worth` | net_worth − B15 | Owners' money excluding intangibles | 520 − 20 = **500** | New |
| `total_debt` | B4 + B8 | All loans | 300 + 480 = **780** | Yes |
| `total_outside_liabilities` | B12 − net_worth (check: B4 + … + B11) | Everything owed to others | 1,800 − 520 = **1,280** | Partly: today B4 + current liabilities only |
| `current_assets` | B20 + B21 + B22 + B23 + B24 + B25 | Assets turning into cash within 12 months | 0 + 600 + 450 + 40 + 50 + 20 = **1,160** | Partly: misses B20 and B25 |
| `current_liabilities` | B8 + B9 + B10 + B11 | Dues within 12 months | 480 + 350 + 90 + 35 = **955** | Yes |
| `net_working_capital` | current_assets − current_liabilities | Long-term money funding working capital | 1,160 − 955 = **205** | Yes |

### 2.3 Ratios

| Key | Formula | What it tells credit | Better when | Provisional norm | Example | Edge cases | Today |
|---|---|---|---|---|---|---|---|
| `revenue_growth` | P1(t) ÷ P1(t−1) − 1 | Is the business growing | Higher | Trend | 3,000 ÷ 2,600 − 1 = **15.4%** | Needs the previous year (column 2) | Yes (CAM) |
| `gross_margin` | gross_profit ÷ P1 | Pricing power | Higher | Industry | 950 ÷ 3,000 = **31.7%** | Services: no cost of sales, so N/A | New |
| `ebitda_margin` | ebitda ÷ P1 | Operating profitability | Higher | Industry | 420 ÷ 3,000 = **14.0%** | — | Yes |
| `pat_margin` | P15 ÷ P1 | Net profitability | Higher | > 0 | 200 ÷ 3,000 = **6.7%** | — | Yes |
| `current_ratio` | current_assets ÷ current_liabilities | Can it pay its short-term dues | Higher | ≥ 1.20 (published bank range 1.17 to 1.33) | 1,160 ÷ 955 = **1.21** | Denominator 0: N/A | Yes (inputs incomplete) |
| `tol_tnw` | total_outside_liabilities ÷ tangible_net_worth | How much of the business is funded by others | Lower | ≤ 3.0 (published 4 to 5) | 1,280 ÷ 500 = **2.56** | TNW ≤ 0: automatic deviation | Partly |
| `debt_equity` | total_debt ÷ tangible_net_worth | Leverage | Lower | ≤ 2.0 (published 3) | 780 ÷ 500 = **1.56** | TNW ≤ 0: deviation | Partly |
| `debt_ebitda` | total_debt ÷ ebitda | Years of profit needed to repay the debt | Lower | ≤ 3.6 to 4.5 | 780 ÷ 420 = **1.86** | EBITDA ≤ 0: deviation | New |
| `interest_coverage` | ebitda ÷ P8 | How many times profit covers interest | Higher | ≥ 2.5 (published 2.0 to 2.6) | 420 ÷ 110 = **3.82** | No interest: **N/A (pass)**, not "cannot evaluate" | Partly (EBIT basis; see §6) |
| `dscr` | (P15 + P9 + term-loan interest) ÷ (term-loan interest + principal due in the year) | Can it repay its loans from its cash | Higher | ≥ 1.5 (published 1.2 to 1.5) | (200 + 60 + 35) ÷ (35 + 80) = **2.57** | Add the proposed loan's yearly interest and principal to the denominator. Without the interest split: (P15 + P9) ÷ yearly EMIs = 260 ÷ 115 = 2.26 (today's conservative form) | Partly |
| `inventory_days` | B21 ÷ cost_of_sales × 365 | Days of stock held | Lower | Industry | 600 ÷ 2,050 × 365 = **106.8** | No inventory: 0 | New (today on sales) |
| `receivable_days` | B22 ÷ P1 × 365 | Days customers take to pay | Lower | ≤ 90 is common | 450 ÷ 3,000 × 365 = **54.8** | — | New |
| `payable_days` | B9 ÷ cost_of_sales × 365 | Days the business takes to pay suppliers | — | Industry | 350 ÷ 2,050 × 365 = **62.3** | — | New |
| `working_capital_cycle` | inventory_days + receivable_days − payable_days | Days money is tied up | Lower | ≤ 75 | 106.8 + 54.8 − 62.3 = **99.3** | — | Partly (on sales) |

### 2.4 Working-capital limit: two methods, chosen by the size of the working-capital request

**Turnover method** (working-capital request up to ₹5 cr). T = accepted projected turnover for next year (from projections; otherwise provisional; otherwise the latest audited year). Example: T = 3,450, request CC ₹450 lakh.

| Step | Formula | Example |
|---|---|---|
| Working-capital requirement | 25% × T | 862.5 |
| Minimum margin from the borrower | 5% × T | 172.5 |
| Actual NWC | net_working_capital | 205 |
| Margin used | Larger of the minimum margin and the actual NWC | 205 |
| **Eligible bank finance** | Requirement − margin used | **657.5** |
| For reference: 20% of T | 20% × T | 690 |
| Result | Request ≤ eligible? | 450 ≤ 657.5: within |

**MPBF, second method** (working-capital request above ₹5 cr). Example: request CC ₹600 lakh, existing bank CC 400.

| Step | Formula | Example |
|---|---|---|
| Current assets (CA) | current_assets | 1,160 |
| Other current liabilities (OCL) | current_liabilities − bank working-capital borrowings (CMLTD stays in OCL) | 955 − 400 = 555 |
| Working-capital gap (WCG) | CA − OCL | 605 |
| Minimum margin | 25% × CA | 290 |
| Leg 1 | WCG − minimum margin | 315 |
| Leg 2 | WCG − actual NWC | 605 − 205 = 400 |
| **MPBF** | **Lower** of leg 1 and leg 2 | **315** |
| Result | Request ≤ MPBF? | 600 > 315: shortfall of 285, a deviation |

---

## 3. Other sources: fields to extract

| Document | Key | What | Where printed | Today | Priority |
|---|---|---|---|---|---|
| **GSTR-3B** (one per month, or per quarter for quarterly filers) | `gstin` | GST registration number | Top | Yes | Must |
| | `tax_period` | Month or quarter ("Jun", "Apr-Jun") | "Period" | Yes (quarters: **New**) | Must |
| | `filing_date` | Date filed | "Date of ARN" | Yes | Must |
| | 3.1(a), (b), (c) taxable value | Sales: taxable, zero-rated (exports), nil or exempt | Table 3.1, "Total taxable value" | Yes | Must |
| | 3.1(a), (b) IGST + CGST + SGST | GST collected on those sales | Table 3.1, tax columns | Extracted, **unused** | Must |
| **GSTR-1** | Total outward value per period | Sales invoiced | Section totals (4A, 5, 6A, 7; less credit notes 9B) | Yes | Must |
| **Income tax return** (ITR-6 for companies, ITR-5 for firms, ITR-3 for proprietors) | `pan`, `assessment_year`, `filing_date` | Identity and year | Acknowledgement and form | Yes | Must |
| | `turnover` | Sales per the return | Part A-P&L or computation: "Revenue from operations / Gross receipts" | Yes | Must |
| | `profit_before_tax` | Profit per the return | Computation: "Profit as per P&L" | Yes | Must |
| | `tax_paid` | Tax paid | "Taxes paid" | Yes | Next |
| **Commercial bureau report** | `report_date`, `credit_rank` | Date; CMR 1 to 10 | Summary page | Yes | Must |
| | Per facility: lender, type, sanctioned, outstanding, **overdue**, **DPD / asset class**, **status** | Each loan the business has | Credit facilities table | Partly (DPD/class, suit-filed and wilful-default flags: **New**) | Must |
| | Enquiries in the last 6 months | Recent loan applications | Enquiry section | New | Next |
| **Declaration of existing facilities** | Per facility: lender, type, limit, outstanding, EMI, as-of date | What the borrower says it owes | Facilities table | Yes (as-of date: New) | Must |
| | Per account: bank, account number, type | Accounts declared | Bank accounts table | Yes | Must |
| **Sanction letters** (other lenders) | Lender, facility, amount, EMI, rate, tenor | Terms of existing loans | Facilities table | Partly (rate, tenor: New) | Next |
| **Application / sourcing message** | Amount **per facility** (CC, TL, PC, BG), tenor, proposed EMI, declared turnover | The request | Message or form | Partly (total only) | **Must** |
| **Stock statement** | Date; raw material, WIP, finished goods; receivables by age; creditors | For drawing power | Statement | New type | Next |

---

## 4. Bank statements

### 4.1 Fields to extract

| Part | Key | What | Today | Priority |
|---|---|---|---|---|
| Header | `account_holder_name`, `bank_name`, `account_number`, `ifsc` | Whose account, which bank | Yes | Must |
| Header | `account_type` | Current, cash credit (CC), overdraft (OD), savings | **New** | **Must** |
| Header | `sanctioned_limit`, `drawing_power` | Limit printed on CC/OD statements | **New** | **Must** (CC/OD) |
| Header | `statement_period_start`, `statement_period_end` | Period covered | Yes | Must |
| Header | `opening_balance`, `closing_balance` | Balances. **Dr means negative** (CC/OD drawn) | Yes | Must |
| Transactions | `date`, `description` (narration), `reference_number`, `debit`, `credit`, `balance` | One row per transaction | Yes (running-balance repair) | Must |

### 4.2 Processing pipeline

| Step | What happens | Output |
|---|---|---|
| 1. Extract | Header fields and transaction rows | Rows with page evidence |
| 2. Validate | The checks in §4.3 | Validated rows; issues sent to review |
| 3. Classify | Each transaction gets **one category** from §4.4. The first matching rule wins, in table order | Category per row, with the rule that matched |
| 4. Find recurring debits | Same counterparty, at least 3 months, amounts within 5% → an EMI | List of EMIs by lender |
| 5. Aggregate | Per account, per month: the columns in §4.5 | Monthly table |
| 6. Compute | 12-month metrics and flags (§4.6) | Metrics with the months they cover |
| 7. Feed | Business credits → turnover checks; EMIs → obligations and DSCR; accounts → account checks; flags → CAM and PD note | — |

### 4.3 Validation checks

| Check | Rule | If it fails |
|---|---|---|
| Running balance | Previous balance + credit − debit = balance, row by row (±₹1) | Repair a single bad cell arithmetically and record it; otherwise send to review |
| Statement total | Opening + total credits − total debits = closing | Review |
| Coverage | 12 months for each account, no gaps between consecutive statements | "Incomplete", with the missing months named |
| Overlap | Two statements covering the same days: count each transaction once (date + amount + reference) | Remove duplicates |
| Account identity | Holder name matches the borrower; one account number throughout | Finding |

### 4.4 Transaction categories

**Credits** (money in). Rules apply in this order.

| # | Category | What it is | Narration clues (examples, case-insensitive) | Counts as business credit? |
|---|---|---|---|---|
| C1 | `own_transfer` | Money moved from another of the borrower's own accounts | The narration names another account in the case's account set; SELF, OWN A/C, SWEEP | **No** |
| C2 | `loan_disbursal` | A loan being paid out to the borrower | DISB, DISBURSAL, LOAN A/C, TL DISB | **No** |
| C3 | `reversal` | A debit reversed, a refund, or a returned auto-debit coming back | REV, REVERSAL, REFUND, RTN of an earlier debit | **No** |
| C4 | `bounced_deposit` | A customer's cheque credited, then returned | A credit later matched by an O/W RTN or CHQ RET debit of the same amount within 7 days | **No** (exclude the original credit) |
| C5 | `investment_redemption` | FD, mutual fund or sweep money coming back | FD, TD, MF, REDEMPTION, SWEEP IN | **No** |
| C6 | `interest_received` | Interest paid by the bank | INT PD, INTEREST CREDIT | **No** |
| C7 | `tax_refund` | Tax refunds | CBDT REFUND, IT REFUND, GST REFUND | **No** |
| C8 | `promoter_credit` | Money from promoters, directors or group companies | Counterparty matches a promoter, director or group-company name | **No** (promoter funding, not sales) |
| C9 | `cash_deposit` | Cash paid in | BY CASH, CASH DEP, CSH DEP | **Yes** (also counted separately) |
| C10 | `business_credit` | Everything else: customer receipts | NEFT, RTGS, IMPS, UPI, CLG from other parties | **Yes** |

**Debits** (money out)

| # | Category | What it is | Narration clues | Used for |
|---|---|---|---|---|
| D1 | `return_issued` | The borrower's own cheque or auto-debit **refused** (a bounce) | I/W RTN, INWARD RETURN, ECS RTN, NACH RTN, ACH DEBIT RETURN, INSUFF, FUNDS INSUFFICIENT; the RTN CHGS line marks the event | Bounce count; early warning. Count **events**, not charge lines |
| D2 | `emi` | A loan instalment | NACH, ECS, ACH DR, EMI, SI, LOAN REPAY; recurring (step 4) | Obligations; DSCR |
| D3 | `interest_debit` | Interest charged on a CC/OD or loan | INT, INTEREST, INT.COLL, INT DEBIT | Finds working-capital lenders; finance-cost check |
| D4 | `penal_charge` | Penalty interest or charges | PENAL, OVERDUE INT, ADDL INT, EXCESS INT | Stress signal |
| D5 | `bank_charge` | Fees | CHGS, CHARGES, SMS CHG, GST ON CHG | — |
| D6 | `tax_payment` | Tax paid | GST, CBIC, GSTN, CBDT, TDS, ADV TAX, CHALLAN | Compliance evidence |
| D7 | `salary_statutory` | Salaries, PF, ESIC | SALARY, SAL, EPFO, ESIC | Business is running |
| D8 | `cash_withdrawal` | Cash taken out | CASH WDL, ATM, SELF (cash cheque) | Early warning (heavy cash withdrawal) |
| D9 | `own_transfer` | Money moved to another of the borrower's own accounts | As C1 | Excluded from business debits |
| D10 | `promoter_debit` | Money paid to promoters, directors or group companies | As C8 | Diversion signal |
| D11 | `business_debit` | Everything else: supplier and expense payments | — | — |

### 4.5 Monthly figures per account

| Column | Formula |
|---|---|
| `credits_count`, `credits_total` | Count and sum of all credits |
| `excluded_by_category` | Sum per excluded category (C1 to C8) |
| `business_credits` | Sum of C9 + C10 |
| `cash_deposits` | Sum of C9 |
| `debits_count`, `debits_total` | Count and sum of all debits |
| `cash_withdrawals` | Sum of D8 |
| `emi_paid` (per lender) | Sum of D2 |
| `interest_debited`, `penal_charges` | Sum of D3; sum of D4 |
| `returns_issued_count`, `returns_issued_value` | Count and value of D1 events |
| `bounced_deposits_count` | Count of C4 |
| `opening`, `closing`, `min_balance`, `max_balance` | From the running balance |
| `abb` | Average of the **end-of-day balance for every calendar day** (carry the balance forward on days without transactions) |
| `days_negative` (current account) or `days_overdrawn` (CC/OD) | Days the balance was below 0, or drawn beyond the limit or drawing power |
| `utilisation_pct` (CC/OD) | Average daily drawn amount ÷ limit (or drawing power, if lower) × 100 |

### 4.6 12-month metrics and flags

| Metric | Formula | Provisional flag |
|---|---|---|
| Business credits, 12 months | Sum of monthly business_credits, all accounts | Feeds the turnover checks (§5) |
| ABB, 12 months | Average of the monthly ABB | — |
| ABB cover | ABB ÷ (existing monthly EMIs + proposed EMI) | < 1.5 times |
| Cash-deposit share | cash_deposits ÷ business_credits | > 25% (unless a cash business) |
| Returns issued | Count in the last 6 and 12 months; bounce ratio = returns_issued_count ÷ (cheque + auto-debit debits) | > 2 in 6 months, or ratio > 3% |
| CC/OD utilisation | Average and peak utilisation_pct | Average > 95%, or any month > 100% |
| Continuous overdrawing (CC/OD) | Longest run of consecutive days overdrawn | ≥ 30 days ≈ SMA-1; ≥ 60 ≈ SMA-2; ≥ 90 = out of order |
| Counterparty concentration | Top customer's share; top 5 customers' share of business credits | Top customer > 35% |
| Cash withdrawals | cash_withdrawals ÷ debits_total | > 25% |
| Promoter and related-party flows | Sum of C8 and D10 | Any large or round-tripped amount: flag for review |
| EMIs to lenders not declared | Lenders in D2 not in the declaration | Any (OB-02) |

### 4.7 Worked example: one month, current account, June 2025 (rupees)

Opening balance 25,000.

| Date | Narration | Debit | Credit | Balance | Category |
|---|---|---|---|---|---|
| 01-Jun | ACH RTN CHGS TATA CAPITAL INSUFF FUNDS | 590 | | 24,410 | D1 return_issued (1 event) |
| 02-Jun | NEFT-ABC TRADERS-INV 112 | | 3,54,000 | 3,78,410 | C10 business_credit |
| 05-Jun | NACH DR HDFC BANK EMI | 45,000 | | 3,33,410 | D2 emi |
| 08-Jun | BY CASH DEPOSIT | | 60,000 | 3,93,410 | C9 cash_deposit |
| 10-Jun | TRF FROM A/C XX4521 (own CC) | | 1,00,000 | 4,93,410 | C1 own_transfer (excluded) |
| 15-Jun | GST PMT CBIC | 38,000 | | 4,55,410 | D6 tax_payment |
| 20-Jun | RTGS-XYZ STEELS-PO 778 | 2,40,000 | | 2,15,410 | D11 business_debit |
| 25-Jun | SALARY JUN BULK | 1,10,000 | | 1,05,410 | D7 salary_statutory |
| 28-Jun | CASH WDL SELF | 50,000 | | 55,410 | D8 cash_withdrawal |
| 30-Jun | TL DISB LOAN A/C 9876 | | 5,00,000 | 5,55,410 | C2 loan_disbursal (excluded) |

| Monthly figure | Value |
|---|---|
| Credits total (4) | 10,14,000 |
| Excluded (own transfer 1,00,000 + loan disbursal 5,00,000) | 6,00,000 |
| **Business credits** | **4,14,000** |
| Cash-deposit share | 60,000 ÷ 4,14,000 = 14.5% |
| Debits total (6) | 4,83,590 |
| Closing (check: 25,000 + 10,14,000 − 4,83,590) | 5,55,410 |
| Minimum balance | 24,410 |
| ABB (daily) | 3,25,010 |
| EMI paid | 45,000 (HDFC Bank) |
| Returns issued | 1 (Tata Capital EMI). Is Tata Capital in the declaration? If not, OB-02 flags it |
| ABB cover | 3,25,010 ÷ 45,000 = 7.2 times |

---

## 5. Cross-verification

### 5.1 How every check works

| Step | What happens |
|---|---|
| 1. Pick the period | Align both sources to the same window: a financial year (April to March), or the months both cover |
| 2. Check coverage | Each side must cover the whole window (12 monthly returns, 4 quarterly returns, or 12 months of statements for every account). If not, the result is **incomplete**, naming the missing months |
| 3. Compute each side | Sum the figures over the window, keeping the evidence for each |
| 4. Compare | Variance % = \|A − B\| ÷ the larger × 100, or a coverage ratio A ÷ B × 100 where the check says so |
| 5. Decide | Within tolerance: **pass**. Outside: **fail**, a finding with both values, the gap and the evidence on each side. Nothing to compare: **not applicable** |
| 6. Human decision | A person accepts, dismisses or escalates each finding, with a comment |

### 5.2 Checks

| ID | What is compared | Side A | Side B | Window | Tolerance (provisional) | Severity | Today |
|---|---|---|---|---|---|---|---|
| TO-01 | Audited sales vs GST sales | P1, audited statements | Sum of 3.1(a)+(b)+(c) taxable value, GSTR-3B | One FY | 1% (5% suggested; see §6) | Moderate | Yes |
| X-01 (re-bases TO-02, TO-03, TX-05) | Bank receipts vs GST sales **including tax** | Business credits, all accounts (§4) | Sum of 3.1(a)+(b)+(c) taxable value + IGST + CGST + SGST | One FY, or months both cover (at least 3) | Coverage A ÷ B: 85 to 115% passes; 70 to 85% or above 115% is moderate; below 70% is serious | Moderate or serious | Partly: today compared with taxable value at 1% |
| TX-03 | Tax-return sales vs audited sales | ITR `turnover` | P1 | The FY the return covers (AY − 1) | 1% | Moderate | Yes |
| TX-02 | Tax-return profit vs audited profit | ITR `profit_before_tax` | P13 | Same | 10% | Moderate | Yes |
| X-02 | GSTR-1 vs GSTR-3B | GSTR-1 outward value | 3B 3.1(a)+(b)+(c) | Each period | 1% | Moderate | New |
| X-04 | Loans in the books vs loans reported elsewhere | total_debt at year end | Sum of bureau outstanding; sum of declared outstanding | Nearest dates; state the gap in days | 10% | Serious | New |
| OB-01 | Each existing facility appears everywhere | Declaration | Sanction letters; bureau | Current | Sanctioned amounts within 5% | Serious | Yes |
| OB-02 | Every lender paid by EMI is declared | EMI lenders (D2) | Declaration | Statement months | Name match | Serious | Yes |
| X-06 | EMI amounts agree | Declared or sanctioned EMI | EMI seen in the bank | Statement months | 5% | Moderate | New |
| X-07 | Overdue with other lenders | Bureau overdue, DPD, asset class | Bank D1 returns on EMIs | Last 12 months | Any overdue beyond 30 days, or SMA-1 or worse | Serious | New |
| X-08 | Interest is plausible for the debt | P8 ÷ average total_debt (this year and last) | — | One FY | 6% to 18% a year | Mild | New |
| FS-02 | Year-end cash in the books vs the bank | B23 | Sum of all accounts' balances on 31 March | Year end | Bank no more than books + 1% | Mild | Built, switched off |
| FS-01 | Previous-year figures restated | Previous-year column of year t | Current column of year t−1 | Year t−1 | 1% | Moderate | Built, switched off |
| BA-01, BA-02 | Accounts declared vs accounts with statements | Declaration and message | Statements; transfers | Current | Last 4 digits | Moderate | Yes |
| X-09 | Projected sales are believable | Projected T | GST outward, last 12 months × 1.15 | Latest 12 months | Projection ≤ run-rate + 15% | Moderate | New |

### 5.3 Worked example (FY 2024-25, ₹ lakh)

| Check | Side A | Side B | Result |
|---|---|---|---|
| TO-01 audited vs GST | 3,000 | 2,960 | 1.33% apart: **fails at 1%**, passes at 5% |
| TO-02 today: bank vs GST taxable | 3,210 | 2,960 | 7.79% apart: **fails at 1%**, though nothing is wrong. Bank receipts include the GST collected |
| X-01 proposed: bank vs GST including tax | 3,210 | 2,960 + 532.8 tax = 3,492.8 | Coverage 91.9%: **passes** (85 to 115%) |
| TX-02 tax-return profit vs audited profit | 268 | 270 | 0.7%: passes |
| X-04 books vs bureau loans | 780 (31 Mar 2025) | 745 (30 Sep 2025, 183 days later) | 4.5%: passes (10%) |
| FS-02 year-end cash | 40 (books) | 38.5 (statements on 31 Mar) | Bank below books: passes |

---

## 6. Definitions to confirm with RBL

The formulas above use these choices until RBL confirms its own.

| Item | Used here | Alternative | Effect |
|---|---|---|---|
| EBITDA | Excludes other income (operating) | Includes it (today's code) | Margin, interest cover and debt/EBITDA |
| Tangible net worth | Net worth − intangibles | Also deduct deferred tax asset and revaluation reserve; add promoter loans as quasi-equity | TOL/TNW, debt/equity |
| Interest coverage | EBITDA ÷ finance costs | EBIT ÷ finance costs (today's code) | Interest coverage |
| DSCR | Adds back term-loan interest | Without the add-back (today's code, conservative) | DSCR |
| Turnover method margin | The larger of 5% of T and the actual NWC | Fixed at 20% of T | Eligible amount |
| ABB | Daily average | Average on fixed dates (for example the 5th, 10th, 15th, 20th, 25th and month end; 3,59,743 in the §4.7 example) | ABB and ABB cover |
| Turnover tolerances | Audited vs GST 1%; bank as a coverage band | RBL's working tolerances | Number of findings (criterion C5) |
| Ratio thresholds | `config/policy.yaml` (provisional) | RBL's policy | Deviations |
