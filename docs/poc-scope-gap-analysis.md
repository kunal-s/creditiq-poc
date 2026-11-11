# POC Scope vs CreditIQ Today: Gap Analysis

| | |
|---|---|
| Compared | *Retail Assets AI POC Scope – Track 1 and 2* (RBL, draft of 4 November 2026) against this repository as of 5 November 2026 (branch `dev`, commit `e7d7bf2`) |
| Purpose | To show, in plain language, what the bank's POC scope asks for that we do not yet have, and what we have built that the scope does not ask for |
| How to read the status marks | ✅ **Have it**: built and working · 🟡 **Partly**: some of it is built, or it works only in a narrow case · ❌ **Missing**: not built |

---

## 1. The short version

**The big picture.** The POC scope covers two products, **LAP** (Loan Against Property) and **BBG** (Business Banking). CreditIQ today is built **only for BBG**, and within BBG mainly for **private limited companies** with working-capital and term-loan requests.

**What's strong.** For that BBG case, the full journey is built and works end to end:

- create a case from the RM's message;
- upload files, including ZIPs;
- grade, classify and extract each document, with page evidence and confidence;
- check completeness and produce a query list;
- cross-check the sources (triangulation);
- check policy norms and work out the approving authority;
- draft the CAM and the PD note.

The parts the scope cares about most (source evidence, confidence, human review, audit trail, and humans making the decision) are well covered.

**The biggest gaps:**

1. **LAP is not there at all.** It has no documents, no checklist, no income assessment (salary, Form 16, rent and so on), no property handling and no LTV.
2. **The documents we can read are a small slice of what the scope lists.** We recognise 13 document types. The scope lists roughly 80 to 100 kinds of document across LAP and BBG.
3. **The checklist only changes by constitution.** The scope wants it to change by product, customer type, case type, facility, credit program and processing stage.
4. **The financial spread can't be downloaded as an editable Excel file.** The scope asks for an editable spread in RBL's format with formulas. Ours is on screen only, in an interim layout.
5. **Bureau and GST analysis are thin.** There is no consumer bureau (CIBIL) for individuals, no DPD history or enquiries, and no GSTR-1 vs GSTR-3B check.
6. **Measuring success is only partly built.** The comparison with RBL's own outputs covers 2 of 7 areas. The scorecard is not built. Reviewer time isn't measured.
7. **Where the model runs doesn't match what we've told the bank.** The security document says the AI runs on Amazon Bedrock in Mumbai. The code calls OpenAI's public API. The scope requires us to disclose this exactly, so it has to be put right before we share anything.

**What we have that the scope doesn't ask for:** document tamper and forgery checks, case creation from a pasted RM message, deep bank-statement analytics, an approving-authority calculation, a chat assistant, mobile RM screens, an Administration screen for editing rules, and repeatable re-runs (we record each AI answer and replay it). Most of these help us in an evaluation. A few should be presented carefully (see §5).

---

## 2. What CreditIQ does today, in plain words

### 2.1 How a case flows through the system

1. **Create the case.** The RM pastes a sourcing email, WhatsApp message or call notes. CreditIQ reads it and suggests the borrower, PAN, GSTIN, facilities and amount, showing where in the message each value came from. The RM confirms or corrects them. It also warns if the same borrower already has a case.
2. **Upload documents.** One file, many files or a ZIP (including ZIPs inside ZIPs). Accepted formats are PDF, images, Excel, CSV and Word. Exact duplicate files are caught.
3. **Check quality.** Each page gets a grade (A, B, C or U) based on blur, skew, shadow, resolution and how readable it is. A bad page gets a plain-language re-scan request.
4. **Check tampering.** About 25 checks look for signs of editing: edit history, covered-up text, mismatched fonts, metadata, digital signatures, and whether a bank statement's balances add up. These raise flags for a person to look at. They never reject a document by themselves.
5. **Classify.** Each document is identified by what it contains, never by its file name. Rules are tried first and the AI model is only a fallback. A file labelled as one thing but containing another is flagged, and so is a document that belongs to the wrong person.
6. **Extract.** Key fields and tables are pulled from each document. Every value carries the page it came from, the area on the page, and a confidence score. Low-confidence items go to a review queue.
7. **Completeness.** The file is checked against the checklist. Each item is marked satisfied, insufficient (for example, too old or too few months), missing, waived or in review. A consolidated pre-login query list can be copied out as an email or text.
8. **Cross-check (triangulation).** About 30 rules check identity, turnover, tax, bank accounts and existing loans across sources. Each finding can be accepted, dismissed or escalated, with a comment.
9. **Financials and policy.** This step covers:
   - a year-by-year spread;
   - working-capital assessment (turnover method or MPBF);
   - ratios such as current ratio, TOL/TNW, DSCR and interest cover;
   - 13 policy norms, each showing the norm, the actual value and the result, including "could not evaluate";
   - the deviations;
   - the approving authority.
10. **Outputs.** A draft CAM in 7 sections and a PD question note, both with citations. The CAM can be edited section by section. Both download as Word or PDF.
11. **Comparison.** CreditIQ's results are shown beside RBL's own record for the case, so a reviewer can decide who was right.

### 2.2 Controls that run across every step

- Four roles: RM, Credit Analyst, Credit Manager and Administrator. The server enforces what each role can see and do.
- Maker-checker for values typed in by hand.
- An append-only audit trail.
- Every rule is versioned configuration. It is never changed silently, and the system doesn't learn from use.

### 2.3 Under the hood

- The **web app** (React) and the **engine** (Python) hold cases, rules and outputs.
- A separate **document-processing service** does reading, OCR (PaddleOCR), classification and extraction.
- A separate **chat assistant service** sits alongside.
- The AI model is **OpenAI `gpt-5.4-nano`**. Every answer is recorded, so a re-run replays it instead of asking again.

---

## 3. In the POC scope, but not (fully) in our codebase

### 3.1 Products

| POC asks for | Status | What we have / what's missing |
|---|---|---|
| **BBG** (business credit) | 🟡 Partly | Built for BBG, but solid only for **private limited companies**. Partnerships and proprietorships get only the common items on the checklist, because we can't read a partnership deed or a proprietor's declaration. LLPs, trusts and others aren't covered. |
| **LAP** (secured retail: customer identity, income, banking, existing loans, property) | ❌ Missing | Nothing LAP-specific exists: no LAP case type, documents, checklist, income assessment, property handling or LAP policy norms. |
| A view of which LAP and BBG documents and checks can be **reused for other retail products** | ❌ Missing | No such mapping or report. |

### 3.2 Case inputs (scope §2.1)

| POC input | Status | Notes |
|---|---|---|
| Application ID, customer ID | 🟡 Partly | We create our own case ID (`BBG-…`). There is no field for the bank's application ID or customer ID from LOS. |
| Product | 🟡 Partly | No separate product field; the requested facilities (CC, TL and so on) stand in for it. |
| **Case type** (new, renewal, enhancement, takeover) | ❌ Missing | No such field. "Enhancement" is only a word the message reader recognises. |
| Requested amount | ✅ Have it | One total amount. Amounts per facility are not captured. |
| **Branch** | ❌ Missing | Branch exists on users, not on the case. |
| RM | ✅ Have it | |
| Processing stage | 🟡 Partly | Our own internal stages (Intake → Documents → … → Outputs). The bank's stages (for example login, PD, post-sanction) are not modelled and don't drive anything. |
| Name, constitution, PAN, GSTIN, Udyam, addresses | ✅ Have it | Udyam is captured from the message but isn't a document type we read. |
| Applicants, **co-applicants, guarantors**, promoters, directors, partners | 🟡 Partly | Directors and promoters are handled well. Co-applicants and guarantors have no specific roles, documents or checks. Party editing after creation is still in the backlog. |
| Existing and proposed facilities, purpose, repayment | 🟡 Partly | Facilities and purpose are captured. There is no repayment schedule or tenor, and no takeover or enhancement details. |
| **Collateral and property details** | ❌ Missing | Only a "collateral present: yes/no" flag. |
| Bureau, existing obligations, repayment conduct, sanction letters, total exposure | 🟡 Partly | See §3.6. |
| RBL checklist, policy checks, exception rules, CAM template, approval hierarchy | 🟡 Partly | All are configurable and versioned, but **today they hold provisional values we wrote ourselves**, not RBL's. Exception (waiver or deferral) rules are basic. |
| **Reference inputs**: RM summary, historical CAM, financial spread, prior credit queries, customer clarifications, reviewer comments | 🟡 Partly | The RM's message is used. RBL's reference workbook can be imported for comparison. Historical CAMs and prior queries are **not used as inputs** to drafting. Customer clarifications have no place to go. |

### 3.3 Documents we can read

The scope lists documents by category. We recognise **13 document types**:

- certificate of incorporation;
- MOA/AOA;
- board resolution;
- company PAN;
- director KYC;
- audited financials;
- ITR;
- GSTR-3B;
- GSTR-1;
- bank statement;
- declaration of existing facilities;
- sanction letter;
- commercial bureau report.

Anything else is marked "unclassified" and sent to a person.

#### BBG documents (scope §2.3)

| Category | Status | What's missing |
|---|---|---|
| Application and case summary | 🟡 Partly | The RM message is used. The **application form**, customer declarations and facility request letter are not read. |
| KYC and identity | 🟡 Partly | Director KYC and company PAN only. Missing: KYC for **guarantors, co-applicants, property owners and group entities**, and address proof as its own type. |
| Business and constitution | 🟡 Partly | COI and MOA/AOA are read. **Missing:** partnership or LLP deed, GST registration certificate, **Udyam**, proof of business vintage, ownership or management details, proof of applying for partnership registration. |
| Financial | 🟡 Partly | Audited financials, ITR and GST returns are read. **Missing:** provisional financials as their own type, notes to accounts and schedules in detail, **projections, project cost, means of finance, capacity details, assumptions**. |
| Banking | ✅ Have it | Bank statements are read in depth (see §4). |
| Bureau and exposure | 🟡 Partly | Commercial bureau report and sanction letters are read. **Missing:** a lender-wise exposure statement, **statements of account**, and repayment history. |
| Working-capital and term-loan | 🟡 Partly | The working-capital assessment is *calculated*. **Missing:** term-loan details, project documents, repayment schedules, **takeover statements**, payment evidence. |
| **Trade finance** | ❌ Missing | Export or packing-credit records, EEFC, export turnover, LC and BG declarations, orders in hand, tender lists, contracts: none are read. |
| **Security and collateral** | ❌ Missing | No property-owner KYC and no collateral documents. Security-cover norms are marked "cannot be evaluated". |
| **Post-PD and post-sanction** | ❌ Missing | Additional schedules, clarifications, other lenders' sanction letters, Annexure I, compliance declarations, **LEI, ZED**, and social or environmental declarations. |
| Supporting and exception | 🟡 Partly | A person can **waive** a checklist item with a reason. Explanation, approval, deferral and waiver *documents* are not read. |

#### LAP documents (scope §2.2)

| Category | Status | What's missing |
|---|---|---|
| Application documents (form, declarations, **consent**, photographs) | ❌ Missing | |
| KYC (PAN, **Form 60, Aadhaar**, other valid IDs, photographs, **signature-proof cheque**, OSV, authorised-person documents) | 🟡 Partly | Only director KYC (PAN and ID details) exists, and it's built for company directors. |
| **Address and residence** (address proof, ownership proof, rent agreement, electricity or gas bill) | ❌ Missing | |
| Business and constitution (GST registration, Udyam, Shop Act, COI, MOA/AOA, deeds) | 🟡 Partly | Same as BBG above. |
| **Income: salaried** (Form 16, salary slips, salary certificate) | ❌ Missing | |
| Income: self-employed (ITR, P&L, balance sheet, audit report, GST, **sales and purchase registers, TDS certificates**) | 🟡 Partly | ITR, financials and GST are read. Registers and TDS certificates are not. |
| Banking (salary, business, rent credits, EMI accounts) | 🟡 Partly | Bank statements are read, but the analysis is built for business current accounts. There is no salary-credit or rent-credit view. |
| Bureau and loan (bureau report, sanction, **loan agreement, SOA, repayment schedule, EMI evidence, closure letters**) | 🟡 Partly | Only a commercial (company) bureau report and sanction letters. **No consumer bureau (CIBIL) report** for individuals. |
| **Property and security** (ownership papers, completion evidence, owner KYC) | ❌ Missing | |
| **Professional qualification** (registration, medical degree) | ❌ Missing | |
| **Other income** (rent, agricultural land and income, commission) | ❌ Missing | |
| Supporting and exception (affidavits, discrepancy declarations, explanations, waivers) | ❌ Missing | Waivers can be recorded by a person, but these documents aren't read. |

### 3.4 Checklist rules

| POC asks for | Status | Notes |
|---|---|---|
| Checklist chosen by **product** | ❌ Missing | Only one product exists. |
| … by **customer type** / constitution | 🟡 Partly | Private limited, partnership and proprietorship, but only private limited is complete. |
| … by **case type** (new, renewal, enhancement, takeover) | ❌ Missing | No case-type field. |
| … by **credit program** | ❌ Missing | |
| … by **facility** | 🟡 Partly | The plumbing exists (`requires_attributes`), but **no checklist item uses it yet**. |
| … by **processing stage** (pre-login, post-PD, post-sanction) | ❌ Missing | One checklist for every stage. |
| "Not applicable" status | 🟡 Partly | Items that don't apply are simply left off the list. They aren't shown as "not applicable". |
| Checklist size | 🟡 Partly | **10 items** today. The bank's real checklist will be several times larger. |

### 3.5 Track A: Document intelligence (scope §3A)

| Capability | Status | Notes |
|---|---|---|
| Bulk and ZIP uploads | ✅ Have it | |
| Classify by content | ✅ Have it | Within the 13 types only. |
| **Split merged files into logical documents** | 🟡 Partly | Several copies of the *same* type are split (for example two directors' KYC in one PDF). A PDF that mixes *different* types (for example PAN + ITR + bank statement) is **flagged but not split**. Grouping several photos into one document is blocked (backlog item C1). |
| Scan quality check | ✅ Have it | Blur, skew, shadow, resolution and blank pages, with re-scan reasons. Tested on constructed samples only, not yet on RBL's real scans. |
| Duplicate check | 🟡 Partly | Exact copies only. A re-scan of the same document, or the same statement exported twice, is not caught. |
| Completeness and checklist applicability | 🟡 Partly | See §3.4. |
| Extract key fields with page evidence and confidence | ✅ Have it | |
| Compare information across documents and raise consolidated queries | ✅ Have it | |
| Document status: available, missing, incomplete, poor quality, duplicate, unrecognised, not applicable | 🟡 Partly | All present in some form, except "not applicable" (left off the list) and "duplicate" at document level (only at file level). |
| Structured extraction of **customer, financial, GST, banking, bureau, facility, obligation, security** fields | 🟡 Partly | Strong for customer (company), financial, GST and banking. Thin for bureau and obligations. **No security fields.** |
| "Ready for RBL Credit review" marker | ✅ Have it | A "Ready for credit" badge, based on a readiness score and no blocking gaps. |
| **Email files (.eml/.msg)** | ❌ Missing | Not accepted. |
| **Word files** | 🟡 Partly | Accepted at upload but **can't actually be processed**: the document service has no Word reader. This is a silent gap to fix or block. |
| Regional language or handwritten documents | ❌ Missing | OCR is English only and has no handwriting support. (The scope doesn't name these, but real LAP files will contain them.) |

### 3.6 Track B: Credit analysis, spread, policy, CAM, PD (scope §3B)

| Capability | Status | Notes |
|---|---|---|
| **Editable financial spread in RBL's format, with formulas and ratios** | 🟡 Partly | The spread is shown on screen with source links, and each derived figure shows its formula. A person can edit figures with a reason. **However:** (1) it isn't in RBL's format yet (their template hasn't arrived); (2) **there's no Excel download**; (3) it's short: 7 P&L lines and 11 balance-sheet lines. |
| Triangulate **financials, GST, banking** | ✅ Have it | Turnover across audited financials, GST, bank and ITR, plus what the RM said. |
| Triangulate **bureau** | 🟡 Partly | Bureau facilities are reconciled with declared and sanctioned loans. There is no DPD history, enquiries or overdue trend. |
| **GST depth** | 🟡 Partly | GSTR-3B is used. **GSTR-1 is read but never compared** with 3B. |
| **Consumer bureau (CIBIL) for individuals** | ❌ Missing | Needed for LAP borrowers, and for BBG promoters and guarantors. |
| Policy rules showing norm, actual, result and "could not evaluate" | ✅ Have it | 13 norms. **All thresholds are our provisional guesses** until RBL sends its policy. |
| Policy exceptions for human review | ✅ Have it | Deviations are listed by category, with the approving authority. |
| **Security-cover and LTV norms** | ❌ Missing | Shown as "cannot be evaluated". |
| **LAP-style assessment**: FOIR, income eligibility, LTV, salaried or rental income | ❌ Missing | |
| Term-loan assessment | 🟡 Partly | DSCR uses existing EMIs plus a proposed EMI. There are no projections and no repayment schedule. |
| Project finance and trade-finance assessment | ❌ Missing | |
| **One consolidated, fully editable CAM in RBL's format** | 🟡 Partly | 7 sections, with citations and editing, and Word or PDF download. **It's in our assumed layout, not RBL's**, because their CAM format hasn't arrived. A Word download can be edited, but it isn't a live editable template. The recommendation is left for credit, as the scope requires. |
| **PD questions linked to the finding and evidence** | ✅ Have it | Each question says why it's asked and links to the evidence. |
| Clear list of missing documents, open queries, policy exceptions, human-review items | ✅ Have it | |
| Use historical reference outputs as an input | ❌ Missing | Historical CAMs and spreads are used only for comparison, not as a guide when drafting. |

### 3.7 Expected outcomes and success measurement (scope §4, §5)

| POC asks for | Status | Notes |
|---|---|---|
| Changes and approvals recorded | ✅ Have it | Append-only audit trail. |
| Compare results with RBL-validated samples | 🟡 Partly | RBL's reference workbook can be imported. **Only 2 of 7 areas are compared** (policy deviations and approving authority). Classification, key fields, discrepancies, queries and the decision itself are **not yet compared**. |
| **Accuracy measures**: classification, field extraction, **table extraction**, checklist status, mismatch alerts, % of fields with valid sources, documents or fields wrongly accepted | 🟡 Partly | The criteria are defined (C1 to C9 in the FRD), but the **scorecard screen is a placeholder**. Table-extraction accuracy and "wrongly accepted" counts aren't measured at all. |
| Accuracy of spread line items, formulas, ratios; CAM section completion; unsupported statements; reviewer corrections; PD question relevance | 🟡 Partly | The underlying data exists (overrides, citations, corrections), but nothing adds it up into a score. |
| **System processing time** | 🟡 Partly | Machine time per stage is recorded. It can be seen from the command line, not on screen. |
| **RBL reviewer time vs the manual process** | ❌ Missing | Nothing records how long a reviewer spends. |
| At least one **unseen case** in the live demo | 🟡 Partly | The pipeline can take a new case, but nothing shows the end-to-end live run has been rehearsed (FRD F-27). AI answers are replayed from recordings by default, so **an unseen case needs live model calls**. We need to be sure that mode works (the backlog says the OpenAI adapter hasn't been run against the live API yet). |
| **Controlled variants** (missing, incomplete, poor quality, mislabelled, merged) reported separately | 🟡 Partly | Each condition is detected. There's no report that shows variant results separately. |
| Freeze checklist, fields, rules, tolerances, formats before scoring | ✅ Have it | Every configuration version is immutable and recorded against each output. |

### 3.8 Data and operating controls (scope §6)

| POC asks for | Status | Notes |
|---|---|---|
| Masked or anonymised data; restricted access | 🟡 Partly | Case data is kept outside git with restricted folder permissions, and access is by role. Masking is a data-preparation step, not something the product does. **Sign-in uses one shared password**, not named individual credentials. |
| Deletion within the agreed period, with written confirmation | 🟡 Partly | A case can be deleted. A full **purge with a deletion record** is in the backlog (F-01.5). |
| No training on RBL data | 🟡 Partly | Nothing learns at runtime, by design. But data is sent to **OpenAI's public API**, so we must confirm and document the no-training and no-retention terms. |
| Audit trail: original file, classification, value, confidence, page, rule, observation, correction, version, user, timestamp | ✅ Have it | Every item on that list is recorded. |
| Human oversight; RBL keeps the decision | ✅ Have it | Nothing is sanctioned, rejected or sent by the system. |
| Production integration only after separate approval | ✅ Have it | No live integration with LOS, DMS or any partner (file-based only). |
| **Disclose hosting, cloud region, model location, external APIs, sub-processors, logs, backups, retention** | ❌ Mismatch | `docs/security/` says AWS Mumbai and Amazon Bedrock, with no data leaving India. **The code uses OpenAI's public API** (`config/ingestion/llm.yaml`, and the assistant service). One of the two must change before this goes to the bank. |
| Systems of record stay LOS and DMS | ✅ Have it | We don't replace them. (The scope also expects AI to work *over* them. We have no connector yet, which is fine for a POC.) |

---

## 4. In our codebase, but not asked for in the POC scope

These are capabilities we have built that the scope doesn't mention. Most are an advantage. Each row says how we should treat it.

| What we have | Plain description | How to treat it |
|---|---|---|
| **Document tamper and forgery checks** | About 25 checks for signs a PDF was edited, plus a per-file integrity report and a reviewer verdict | Strong differentiator. The scope only says "quality". Show it as an extra layer of document intelligence. |
| **Case creation from a pasted RM message** | Reads an email, WhatsApp text or call notes and suggests case details, each linked to where it came from | Useful, but the scope expects case details to come **from LOS**. We need a plain form or LOS-style input as well. |
| **Deep bank-statement analytics** | 29 transaction categories; bounces; cash share; round-tripping; related-party flows; statutory payments; month-end window dressing; customer concentration; EMI detection | Goes well beyond "triangulate banking". Good to show. |
| **Approving-authority calculation** | Works out which level must approve, from amount and deviations | The scope lists the approval hierarchy as an input but doesn't ask us to compute it. Fine to show, as long as we're clear it **advises and doesn't route**. |
| **Chat assistant** | Explains why documents were rejected and drafts a follow-up email to the customer (records it; doesn't send it) | Not asked for. The FRD itself calls a copilot out of scope. Show as optional, or keep switched off. |
| **Mobile RM screens** | Phone layout for creating a case and uploading files | Not asked for. A nice extra. |
| **Administration screen** | The Administrator edits tolerances, norm thresholds, cross-check rules and the approval matrix, and publishes a new version | Supports "RBL owns the rules". Good to show. |
| **Repeatable re-runs** | Every AI answer is recorded and replayed, so the same file always gives the same result | Supports "freeze before scoring". Note that it works against the unseen-case demo unless the live mode is ready. |
| **Readiness score and gates** | A weighted percentage, with a gate for credit review and one for disbursement | The scope only says "complete or not". Our score is extra, and its weights are our own. |
| **Maker-checker on manual entry** and **escalation to the Credit Manager** | A second person must check typed values; escalated findings can only be closed by a manager | Stronger than asked. Good. |
| **CAM templates** | Analysts can rearrange CAM sections into a saved template | Helpful once RBL's format arrives. |
| **CAM section rewrite with AI** | Optional per-section redraft. It is rejected if it invents figures | Not asked for. A good safety story. |
| **Rating and Submission screens** | Rating says "not rated"; Submission shows a pre-submission checklist | **Careful:** the scope says AI won't classify customers or make decisions. These screens do neither, but their names may suggest it. Consider hiding them for the POC. |
| **Memo library** | One list of every case's CAM status | Small extra. |
| **Partner outputs as sources** | Can take GST or bank-statement analysis reports from partners as files | Not in the scope. Waiting for samples. |

---

## 5. Things to fix or check soon (not features, but risks)

1. **Model location.** The code (OpenAI public API) and the security document (Amazon Bedrock, Mumbai) disagree. The scope requires full disclosure. Decide which is true and make both match.
2. **Word files.** They pass upload but can't be processed. Either add a reader or reject them at upload with a clear message.
3. **Live mode for the unseen case.** The OpenAI adapter hasn't been run against the live API (backlog). The unseen-case demo depends on it.
4. **Real RBL inputs.** Policy norms, tolerances, the approval matrix, the CAM format, the spread template and the checklist are all provisional. Every accuracy score depends on these arriving and being frozen.
5. **Out-of-date docs.** `docs/screen-walkthrough.md` and the FRD screen map still list the assistant, memo library, rating, submission and admin editing as "not built". The README's "Current state" section describes a much earlier base.
6. **A known matching bug.** Rule OB-02 treats a payment to "Indian Overseas Bank" as a payment to "Indian Bank" (backlog).

---

## 6. Suggested order to close the gaps

| Priority | Gap | Why first |
|---|---|---|
| 1 | Fix the model-location mismatch; get live model calls working | Blocks the data-flow sign-off and the unseen-case demo |
| 2 | Add **case type, branch, product, application or customer ID, co-applicants and guarantors** to the case | Cheap, and every checklist rule depends on them |
| 3 | Make the checklist depend on **product, case type, facility and stage**; show "not applicable" | Core to Track A's scoring |
| 4 | **Excel export of the spread** in RBL's format, with formulas | Explicit Track B output |
| 5 | Split **mixed-type** merged PDFs; detect **near-duplicates** | Named in the scope's controlled variants |
| 6 | Broaden BBG documents: partnership or LLP deed, GST registration, Udyam, provisional financials, projections, SOA, repayment schedules, sanction letters from other lenders | Brings BBG coverage close to the scope list |
| 7 | **Consumer bureau** report; GSTR-1 vs 3B; bureau DPD and enquiries | Completes triangulation |
| 8 | **LAP product**: identity and address documents, salaried and other income documents, property documents, FOIR, LTV and income-eligibility norms, LAP CAM sections | Largest single gap. Needs RBL's LAP checklist and policy first |
| 9 | Finish the comparison (the other 5 areas), the **scorecard**, and a **reviewer-time** log | How the POC will be judged |
| 10 | Trade-finance and post-sanction documents; security-cover norms | Lower priority. The scope says "may be added based on POC stage" |
