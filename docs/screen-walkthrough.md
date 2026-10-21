# CreditIQ (RBL BBG) — end-to-end screen walkthrough

**What this is.** Every screen in the application, in the order a case moves through it, with
each component on the screen named, what it is, what it does when you use it, and a scenario
that shows it working. Written from the code (`src/routes`, `src/components`), the label
catalogue (`terminology/rbl.yaml`) and `docs/functional-requirements.md` §5–§7.

**How to read a screen entry.**

| Part | Meaning |
|---|---|
| **Route** | The address. `$caseId` is an appraisal number, e.g. `BBG-2026-000004` |
| **Who sees it** | Roles whose permissions open it (`config/roles.yaml`) |
| **Purpose** | The one line the screen itself prints under its title |
| **Components** | Every card, chip, table, field and CTA, with what pressing it does |
| **Scenario** | A concrete run-through, using the three synthetic test files |

**Vocabulary.** On screen a case is called an **appraisal** and an **application**; the engine's
record is a *case*. A **finding** / **discrepancy** is one cross-check outcome. A **review item**
is anything waiting for a person. **Readiness** is the weighted completeness score against a gate.

**Sign-in used in the scenarios** (fictional directory in `config/roles.yaml`; the shared
password is the `auth.demoPassword` value in that file):

| Person | Role | Used for |
|---|---|---|
| arjun.deshpande@rblbank.com | Relationship Manager (RM) | Creates the appraisal, uploads files, sends the query list |
| ananya.krishnan@rblbank.com | Credit Analyst | Resolves review items, reads data, cross-checks, policy, outputs |
| meenal.kulkarni@rblbank.com | Credit Manager | Checker, escalated discrepancies, Comparison, Scorecard |

**The three test files used throughout** (synthetic, seeded locally; see
[cross-verification-demo-guide.md](cross-verification-demo-guide.md)):

| Appraisal | Character |
|---|---|
| Kestrel Fabricators Pvt Ltd | A file full of problems — discrepancies in all four cross-check areas, submission blocked |
| Heronbay Polymers Pvt Ltd | A clean file — every source agrees, every check passes |
| Marigold Agro Foods Pvt Ltd | An unfinished file — the checks say what is missing instead of guessing |

---

## Contents

- [0. The shell: what is on every screen](#0-the-shell-what-is-on-every-screen)
- [1. Sign in](#1-sign-in--sign-in)
- [2. Appraisals (the workbench)](#2-appraisals-the-workbench)
- [3. New appraisal](#3-new-appraisal--appraisalsnew)
- [4. The case workspace frame](#4-the-case-workspace-frame-header-stages-tabs)
- [5. Overview](#5-overview--appraisalscaseid)
- [6. Files — stage 1, quality and classification](#6-files--appraisalscaseiddocuments)
- [7. Extracted data — stage 2](#7-extracted-data--appraisalscaseidextraction)
- [8. Completeness — stage 3](#8-completeness--appraisalscaseidcompleteness)
- [9. Cross-checks — stage 4](#9-cross-checks--appraisalscaseidcross-verification)
- [10. Policy — stage 5](#10-policy--appraisalscaseidpolicy)
- [11. Outputs — stage 6](#11-outputs--appraisalscaseidoutputs)
- [12. Comparison](#12-comparison--appraisalscaseidcomparison)
- [13. Review queue](#13-review-queue--review)
- [14. Scorecard](#14-scorecard--scorecard)
- [15. Audit trail](#15-audit-trail--audit)
- [16. Administration](#16-administration--admin)
- [17. Guide to the steps (Help)](#17-guide-to-the-steps--help)
- [18. The evidence viewer](#18-the-evidence-viewer-opens-over-any-tab)
- [19. Dialogs](#19-dialogs)
- [20. Chip and status glossary](#20-chip-and-status-glossary)
- [21. Empty, loading, error and redirect states](#21-empty-loading-error-and-redirect-states)
- [22. Three end-to-end scenarios](#22-three-end-to-end-scenarios)
- [23. What is deliberately not built](#23-what-is-deliberately-not-built)

---

## 0. The shell: what is on every screen

`src/components/shell/AppShell.tsx`

| Component | What it is | What it does |
|---|---|---|
| **Brand mark + product name** (top left, `CI CreditIQ`) | Link | Returns to the workbench (`/`) |
| **Bank line** — "RBL Bank / Business Banking Group" | Static text | Tenant identity, from `terminology/rbl.yaml` |
| **User block** (top right) — name, role label, initials avatar | Static | Shows who is signed in and with which role |
| **Sign out** (door icon) | CTA | Ends the session and returns to `/sign-in` |
| **Menu** (hamburger, phones only) | CTA | Opens the side navigation as a sheet from the left |
| **Side navigation** | Grouped links, gated per role | See the table below |
| **Toasts** (bottom right) | Transient confirmations | "Decision recorded", "Files received: 6", "Copied as an email…", failures |
| **Evidence viewer** | Right-hand side panel | Opens over any tab when you click a value, a citation or a page; see §18 |

**Side navigation, by group** (a group a role may not see is not rendered at all):

| Group | Items | RM | Analyst | Manager |
|---|---|---|---|---|
| **Appraisal {id}** (only while a case is open) | Overview; *Documents and data* → Files, Extracted data, Completeness; *Verification and policy* → Cross-checks, Policy; Outputs; Comparison | Overview, Files, Completeness | all but Comparison | all |
| **Workbench** | Appraisals, New appraisal | ✔ | ✔ | Appraisals only (no create) |
| **Governance** | Review queue, Scorecard, Audit trail | — | Review queue, Audit trail | ✔ all |
| **Administration** | Configuration, Policy norms, Checklist, Document types, Users and roles | — | ✔ | ✔ |
| **Help** | Guide to the steps | ✔ | ✔ | ✔ |

Each case step in the side menu carries a **status dot**: grey = not started, blue = in progress,
amber = needs attention, green = done. Role gating is enforced on the server as well as hidden
in the menu.

**Scenario.** Arjun (RM) signs in and sees only *Appraisal …*, *Workbench* and *Help*. He asks
why he cannot see the Scorecard: his role has no `scorecard.read` permission, so the Governance
group is not rendered for him. Ananya (analyst) signs in on the same case and the same menu now
also carries Review queue, Audit trail and the five Administration screens.

---

## 1. Sign in — `/sign-in`

**Who sees it.** Everyone, including anyone not yet signed in: any address visited without a
session bounces here.

| Component | What it is | What it does |
|---|---|---|
| **Brand block** — `CI`, "CreditIQ", "RBL Bank · Business Banking Group" | Static header | Identifies the tenant |
| **Email** | Text field (`you@rblbank.com` placeholder) | The bank email address |
| **Password** | Password field | The issued password |
| **Sign in** | Primary CTA (full width) | Opens the session and goes to the workbench. Disabled until the page is interactive, and while submitting it reads "Signing in…" |
| **Help line** | Static | "Use your bank email address and the password issued to you." |
| **Failure toast** | Toast | "Sign-in failed — Check the email and password and try again." No session is opened |

**Scenario.** Ananya opens `http://localhost:4173/appraisals/BBG-2026-000004/policy` from a saved
link. She has no session, so the app lands her on Sign in. She signs in with her analyst address;
she arrives at the workbench (not back at the policy tab — the sign-in always lands on `/`), and
reopens the case from the Appraisals table.

---

## 2. Appraisals (the workbench)

**Route.** `/` — the screen the app opens on.

**Purpose.** "Every application in progress, with its stage and the items waiting for review."

### 2.1 Greeting strip and counters

| Component | What it is | What it does |
|---|---|---|
| **Eyebrow** "Business Banking Group" + **"Welcome, {first name}"** | Heading | Greets the signed-in user; under it, "{role} · {branch}" |
| **Counter card: Applications in progress** | Big number + "Borrowers: n" | Count of cases not yet *Completed*; links back to `/` (it is the list below) |
| **Counter card: Open review items** | Big number, amber when > 0, sub-label "waiting for a decision" | For a role with `review.read`, the size of the review queue and a link to `/review`; for an RM, the sum of its own cases' open items |
| **Counter card: Ready for credit** | Big number + "gate met, nothing blocking" | How many in-flight cases pass the review gate with no blocking item left |
| **New appraisal** | Primary CTA with `+` | Opens `/appraisals/new`. Hidden for the Credit Manager (no `case.create`) |

Each counter card reveals a small ↗ arrow on hover to show it is a link.

### 2.2 "Appraisals" panel (left, wide)

| Component | What it is | What it does |
|---|---|---|
| **Sub-line** | "Every appraisal you can see, with its stage and review items" | — |
| **Stage filter** | Select, default "All open appraisals" | Shows only the chosen stage; the default hides *Completed* |
| **Mine** | Toggle (only for roles that can see every case) | Keeps only cases where you are the RM |
| **With review items** | Toggle | Keeps only cases with at least one open review item |
| **Table (desktop)** | Columns: Borrower, Facilities and amount, Stage, RM, Created, Review items | A row with 2 or more open review items is tinted amber |
| ↳ **Borrower** | Link | Opens that case's Overview |
| ↳ **Stage chip** | Link, coloured by stage | Jumps straight to the tab of that stage (or to Overview if your role may not open it) |
| ↳ **Review items** | "n open" amber pill, or "Clear" | The pill links to the Review queue for roles that may see it |
| **Cards (phones)** | The same six fields stacked per card | Same links |
| **Empty state** | "No applications yet / Applications appear here once they are created" | Offers the *New appraisal* link when your role may create |

### 2.3 "Needs attention" panel (right)

| Component | What it is | What it does |
|---|---|---|
| **Count pill** "n open" | Amber badge | Open review items (analyst/manager) or flagged cases (RM) |
| **Review queue** link | CTA | Opens `/review` (hidden for the RM) |
| **Item rows** | Up to 8 rows: kind, summary, borrower · case id | Each row opens where that item is decided — a finding goes to Cross-checks, a field to Extracted data, a type/quality/party item to Files. Red triangle icon for *finding* and *quality*, blue document icon for the rest |
| **Empty** | "Nothing is waiting for a decision." | — |

**Scenario.** Ananya signs in on Monday. The counters read 3 applications in progress /
15 open review items / 0 ready for credit. She presses the **With review items** toggle; all three
stay. In **Needs attention** the first row is "Finding — Entity PAN differs between the bureau
report and 16 documents · Kestrel Fabricators". She clicks it and lands on the Cross-checks tab
of that case with the discrepancy card already open.

---

## 3. New appraisal — `/appraisals/new`

**Who sees it.** RM, Credit Analyst (`case.create`).
**Purpose.** "Paste the sourcing email or notes. CreditIQ proposes the application; nothing is
created until you confirm it."

### 3.1 Before reading the message

| Component | What it is | What it does |
|---|---|---|
| **Channel** | Select (Email, WhatsApp, Call notes… from the engine's `meta`) | Records how the lead arrived; locked once a proposal exists |
| **Message** | Large textarea, placeholder "Paste the email, message or notes here…" | The sourcing email or notes, as received |
| **Read the message** | Primary CTA | Sends the text for parsing; reads "Reading…" while it works. Disabled with no text or no channel |
| **"Nothing is stored until you create the application."** | Note beside the CTA | Reassurance: the paste is not persisted yet |
| **Proposed application** (right) | Empty panel | "The proposed application appears here once the message has been read." |

### 3.2 After reading — the two-panel confirm screen

**Left: the message, marked up.**

| Mark | Meaning |
|---|---|
| Plain highlight | A span the reader used for a proposed field |
| Amber ring | A *candidate* for the field you have selected |
| Blue ring | The span of the field you have selected |
| Greyed text | Set aside before reading (headers, quoted text, signatures) — hover says so; nothing is proposed from it |

**Edit message** (pencil) returns the panel to the editable textarea, keeping the text.

**Right: "Proposed application".** One row per field: Borrower, Constitution, Facilities,
Amount requested (INR), PAN, GSTIN, CIN, Udyam, Promoters, Declared turnover (INR), Existing
banking, Contact, Proposed monthly instalment on the term loan (INR).

| Component | What it is | What it does |
|---|---|---|
| **Status chip per field** | Found / Unclear / Not found / Invalid | How the reader rates its own result |
| **Field editor** | Text input; a select for Constitution; a row of toggles for Facilities; numeric-only for amounts; forced upper case for PAN/GSTIN/CIN/Udyam | Edit the proposal in place. Clicking the row also highlights its span in the message |
| **Amount helper** | Grey line under the amount | Shows the typed figure formatted, e.g. "INR 5.00 cr" |
| **"Could be:" candidate buttons** | Amber pills (Unclear/Invalid fields only) | One click adopts that candidate as the value and moves the highlight to its span |
| **Confirm this value** | Row CTA, appears on any field needing confirmation (amber left border) | Marks the value as settled by you; the row then shows a green "Confirmed by you" chip |
| **"To confirm before creating: n"** | Amber footer of the panel | How many fields still need your confirmation |

### 3.3 Duplicate warning, attachments, create bar

| Component | What it is | What it does |
|---|---|---|
| **Duplicate banner** | Amber block: "An application for this borrower already exists: {id} · {borrower}" | Appears when the reader (or the engine, on create) finds a match |
| ↳ **Open it** | CTA | Opens the existing appraisal |
| ↳ **Create anyway** | CTA | Reveals "Reason for creating another application (required)"; creation stays blocked until it is filled |
| **Attachments** | Upload zone + file list (name, size, remove ✕) | Optional. Files queued here are uploaded to the new appraisal's Files tab once it is created |
| **"Still needed: …"** | Note in the create bar | The minimum fields the engine requires that are still empty |
| **Discard** | Secondary CTA | Clears the message, the proposal and the attachments |
| **Create application** | Primary CTA | Creates the case. Disabled while anything is missing, unconfirmed, or a duplicate is unresolved. On success a toast says "Application {id} created" and you land on the new case — the **Overview** if attachments were uploaded (processing has already begun), otherwise the **Files** tab |
| **Attachment fallback toast** | Toast | If the upload fails, "The application was created; add the attachments from its Documents screen." |

**Scenario.** Arjun pastes a sourcing email for a fabrication company asking for INR 5 cr of cash
credit and a term loan. He presses **Read the message**. The panel proposes Borrower (Found),
Constitution = Private limited company (Found), Facilities = Cash credit + Term loan (Found),
Amount 5,00,00,000 (Found), PAN (Found), GSTIN (**Unclear** — two candidates in the signature
block), Declared turnover INR 18 cr (Found), Proposed instalment (Not found). He clicks the GSTIN
row: the message scrolls to it and two amber candidates appear; he picks the 27-series one, the
row turns "Confirmed by you". The footer still says "To confirm before creating: 1" for the
constitution the reader marked unclear; he presses **Confirm this value**. He drops the customer's
ZIP into **Attachments**, presses **Create application**, and lands on the Overview of
`BBG-2026-000004` with reading already under way.

---

## 4. The case workspace frame (header, stages, tabs)

`src/routes/appraisals.$caseId.tsx` — this frame sits above **every** tab of a case.

### 4.1 Case header

| Component | What it is | What it does |
|---|---|---|
| **Eyebrow** | Constitution label, e.g. "Private limited company" | — |
| **Borrower name** | H1 | — |
| **Identifier line** | Appraisal number, then PAN, GSTIN, Udyam and the RM's name, separated by thin rules | Monospaced; only identifiers on record are shown |
| **Readiness** | Percentage + coloured bar + "{n} outstanding · {gate}% review gate" | Weighted completeness. The bar turns red when anything blocking is open, amber below the gate, green when the gate is met. Reads "provisional" while constitution/facilities are unconfirmed |
| **Ask** | "{facilities} · INR {amount}" | What the borrower asked for |
| **Stage** | Text | The case's current stage (Intake → … → Completed) |
| **"{n} blocking"** | Red CTA | Jumps to Completeness, anchored at the Readiness summary |
| **"Ready for credit"** | Green badge (shield) | Shown instead, once the gate is met with nothing blocking |
| **"{n} open"** | Amber CTA (triangle) | Open review items on this case → Review queue (roles with `review.read`) |
| **Delete application** | Bordered CTA (bin) | Opens the delete dialog (§19.2); only for roles with `case.delete` |

### 4.2 Stage progress bar

Six stages in processing order: **Quality and classification · Extraction · Validation and
completeness · Cross-verification · Policy checks · Outputs**.

| Component | What it is | What it does |
|---|---|---|
| **Stage tile** | Numbered circle + stage name + detail line ("8 of 9 documents classified") | Click opens that stage's tab. A stage your role may not open shows its status but is not a link |
| **Status mark** | Number (not started) / spinner (in progress) / triangle (needs attention) / tick (done) | Live: it updates without a page reload while processing runs |
| **Phone collapse** | "Stage 3 of 6 — Validation and completeness" with a chevron | Tap to expand the full list |
| **Flow summary line** | Grey strip under the header on the sub-tabs | Repeats the active stage and its detail, e.g. "Extraction · 7 of 9 documents extracted" |

**Scenario.** Ananya opens Kestrel. The header reads 62% readiness, "6 outstanding · 70% review
gate", a red **3 blocking** button and an amber **15 open**. The stage bar shows stages 1–3 ticked,
stage 4 with an amber triangle ("15 need attention"). She clicks the fourth tile and goes straight
to Cross-checks.

---

## 5. Overview — `/appraisals/$caseId`

**Who sees it.** All roles. **Purpose.** Where the case is, what needs a person next, and the
counts behind each stage.

| Component | What it is | What it does |
|---|---|---|
| **Next** bar | Bordered strip: "Next" + one sentence + **Open →** | The single next action. With no documents yet: "Upload the borrower's documents to start processing." Otherwise the first unfinished stage and its detail; when nothing is pending: "Nothing is waiting. Processing is up to date." The link is omitted if your role cannot open that stage |
| **KPI: Quality and classification** | "8/9" + detail, amber when it needs attention | Documents classified |
| **KPI: Open review items** | Count, amber when > 0 | Items waiting on a person for this case |
| **KPI: Validation and completeness** | "18/24" + detail, green or red | Checklist items satisfied |
| **KPI: Stage** | Stage name + the status of the next stage | — |
| **Processing stages** panel | Numbered list of the six stages: name, detail, status chip, **Open** link | The same navigation as the header bar, with room for the detail line. "Open" appears only for a stage that has started and that your role may see |
| **Still needed** panel | Up to 6 checklist items that are missing or insufficient, each with its status chip and deficiency; "n more" at the foot | **Open** jumps to Completeness → the checklist |
| **Waiting for a decision** panel | Up to 6 open review items with kind + summary | Each row opens where it is decided; "n more" opens the Review queue. Hidden for roles without `review.read` |

**Scenario.** Arjun (RM) opens Marigold the morning after uploading. The **Next** bar says
"Validation and completeness: 7 of 24 items satisfied — Open →". **Still needed** lists "Director
KYC — Missing", "Memorandum and articles of association — Missing", "GSTR-3B returns —
Insufficient: 7 of 12 months". He has no *Waiting for a decision* panel (no `review.read`). He
clicks **Open** and goes to Completeness to copy the query list.

---

## 6. Files — `/appraisals/$caseId/documents`

**Stage 1 of 6: quality and classification.** All roles; uploading needs `document.upload`.
**Purpose.** "Every file received, how it was split, and where each document is. Anything that
needs a person is flagged on its row, with what to do."

### 6.1 Right rail

| Component | What it is | What it does |
|---|---|---|
| **Add documents** panel | Upload zone | Accepts single files, several files or ZIP archives: PDF, JPG, PNG, TIFF, XLSX, CSV, DOCX, ZIP |
| ↳ **Drop files or a ZIP here** | Drag target | The border lights up while dragging; dropping starts the upload ("Uploading…") |
| ↳ **Choose files** | Primary CTA | Opens the file picker (multiple allowed) |
| ↳ **Take a photo** | CTA, phones only | Opens the rear camera for a photographed document |
| ↳ **Toast** | "Files received: 6" | On success; a failure shows the designed error instead |
| **Summary** panel | Four tiles: Documents identified, Need attention, Not identified, Label mismatches (the last three amber when non-zero) | At-a-glance state of the register |
| ↳ **File status counts** | Registered / Duplicate / Ignored / Rejected / Exception, each with a count | How the raw files were received |

### 6.2 "Files received" — the register

| Component | What it is | What it does |
|---|---|---|
| **Sub-line** | "Every file with its status; archives shown as folders" — or, while work runs, a spinner and "Reading documents…" | The panel polls and updates without a reload |
| **Filter chips** | **All (n)** · **Needs attention (n)** · **Processing (n)** | *Needs attention* keeps documents with an open review item, a checklist defect, a label mismatch, or status unclassified / exception / in review. *Processing* keeps those still moving through the pipeline |
| **Folder row** (ZIP) | Chevron + folder + archive path + "(n)" | Collapses or expands the archive's contents, nested to any depth |
| **File row** | Document icon, original file name, size, status chip | One per file as received |
| ↳ **"Duplicate of {name}"** | Grey note | Same SHA-256 as a file already registered |
| ↳ **Reason text** | Grey note | Why a file was rejected or set aside |
| ↳ **Reading…** track | Five-segment bar | A registered file whose documents have not appeared yet |
| **Document row** (indented under its file) | Chevron · page range (e.g. `3–7`) · type name · instance · flags · track · grade chip | One per *logical* document found inside the file |
| ↳ **Type name** | Button | Opens the evidence viewer at the document's first page. Unclassified documents read "Not identified" in amber with a `?` icon |
| ↳ **Instance** | Grey suffix | What makes this instance unique — the period, account or person, e.g. "FY 2024-25", "·5678" |
| ↳ **Label mismatch chip** | Amber: "label says: {file name hint}" | The file name suggests a different document from its content; hovering explains "The content decides" |
| ↳ **"n defect(s)"** | Red chip | Checklist deficiencies that name this document |
| ↳ **Stage track** | Five segments + the step it is on: Received → Quality → Split → Classified → Extracted | Blue pulsing = running, amber = needs a person, green = done ("Extracted") |
| ↳ **Grade chip** | Clear / Readable / Hard to read / Unreadable | The page-quality grade for the document |

### 6.3 Row actions (what a person can do on the row)

| Component | What it is | What it does |
|---|---|---|
| **"Assign as:" + candidate buttons** | Up to 3 buttons, each "Type name 86%" | One click assigns that type to an unclassified document and records the decision; a toast confirms "Assigned as {type}" |
| **Other type…** | CTA | Opens the decision dialog with the full published type list |
| **"Resolve: {kind}"** | Amber CTA per open item (Quality exception, Party or label flag, Uncertain split, Manual entry) | Opens the decision dialog for that item |
| **Check the extracted values →** | Link | On a document in review, jumps to Extracted data anchored at the fields |
| **"Waiting for credit review"** | Grey note | Shown instead of the buttons to a role without `review.decide` |

### 6.4 Expanded document detail (the chevron)

| Component | What it is | What it does |
|---|---|---|
| **Summary grid** | Document type (+ confidence + what decided it: Signals / Layout / Page reading / Assigned by a person), Readability ("2 of 9 pages are hard to read"), Values read ("14 values, 91% average confidence") | How this document was identified and how legible it is |
| **Label-mismatch note** | Amber block | "The file is labelled X; its content reads as Y. The content decides; the mismatch is reported." |
| **Unclassified note** | Amber block with a **Review queue** link | "No type from the published list fits this document with enough confidence. It is not counted against any checklist item until a person assigns a type." |
| **Key values** | Up to 6 field/value pairs + "n more values →" | The headline values read from this document; the link opens Extracted data |
| **Deficiencies** | Red rows: checklist item name — deficiency | What the checklist found wrong with this document |
| **Pages table** | Page (clickable) / Grade / Reasons (Low resolution, Blur, Skew, Shadow, OCR below floor, Corrupt, Password protected, Blank, Missing page) + "OCR 72%" | Shown only when some page is hard to read or unreadable. The page number opens the viewer at that page |
| **Open document** | CTA | Opens the evidence viewer at the first page |

**Scenario.** Arjun uploads the customer's ZIP. The register shows a folder with 11 files; one row
is **Duplicate** of another ("Duplicate of statements/HDFC_Apr.pdf"). A merged 23-page PDF has
split into four document rows: *Audited financial statements · FY 2024-25* (pages 1–9),
*ITR acknowledgement · AY 2025-26* (10–11), *GSTR-3B · Jul 2025* (12–13) and one amber
**Not identified** (14–23). A photographed KYC page carries a **Hard to read** grade; expanding it
shows pages 2 and 3 with reasons "Blur, OCR below floor" and the note "Send a clearer copy of the
affected pages". Ananya then presses the **Needs attention (3)** filter, sees the unidentified
document with candidate buttons "Stock and book-debt statement 61%" and "Debtors and creditors
ageing 24%", and clicks the first; the row turns green and the checklist picks it up.

---

## 7. Extracted data — `/appraisals/$caseId/extraction`

**Stage 2 of 6.** Credit Analyst and Credit Manager (`data.read`). Two sections in one tab.

### 7.1 Section "Extracted data"

**Purpose.** "Key fields by source, each with its confidence and a link to the page it came from."

| Component | What it is | What it does |
|---|---|---|
| **Status filter chips** | All fields · Please check · Not found · Corrected | Narrows every table below to that status |
| **Section headings** | Entity and identity · Financials · GST and tax · Banking · Bureau, collateral and other | Fields are grouped by the group of the document they came from |
| **Document panel** | One per document: type name as the title; sub-line = file name · pages · instance | Groups the fields read from that document |
| ↳ **Grade chip** | Shown only for Hard to read / Unreadable | Warns that the source pages are poor |
| ↳ **Open document** | CTA in the panel header | Opens the viewer at that document |
| **Field table** | Columns Field / Value / Confidence / Status | One row per field |
| ↳ **Value** | Button | Opens the evidence viewer at the exact page (and region, where known) with the value, its confidence and its method in the viewer's header. Missing values read as the reason: "not found on the document", "not found on the page it points to", "could not be read" |
| ↳ **Confidence chip** | Percentage with a dot; amber when the field is in review | Hovering shows the composition: Classification, Page grade, Text or OCR trust, Validation, Agreement of two reads |
| ↳ **Status chip** | Confirmed / Please check / Corrected / Not found / Rejected | The engine routes anything below threshold to *Please check* — it is never silently accepted |
| ↳ **Confirm** | Green row CTA (only on *Please check*, needs `review.decide`) | Accepts the read value in one click; the row turns *Confirmed* |
| ↳ **Correct…** | Row CTA | Opens the evidence viewer **with the correction form showing**, so a correction is always made with the page in view |
| **Table blocks** | A table read from a document (e.g. ageing, account lines): Row + one column per column | Every cell keeps its own value button, confidence chip, status chip and decision; cells in review are tinted amber |
| **"How was this decided"** | Collapsed details at the foot of each document panel | Field / Read by (Read from fixed layout, Read from the page text, Typed in, Entered by a person) / As printed (the raw text where it differs from the parsed value) |
| **Extraction summary** (right rail) | Fields count and *Please check* count side by side, then counts for Confirmed / Corrected / Not found / Rejected | — |
| ↳ **Show the n in review** | CTA | Switches the filter to *Please check* |

### 7.2 Section "Entity and parties"

**Purpose.** "The borrower's identifiers and the promoters, directors or partners, each with the
document it came from."

| Component | What it is | What it does |
|---|---|---|
| **Borrower identifiers** | Rows: Borrower, Constitution, PAN, GSTIN, CIN, Udyam | Each with a **source chip** — "From the message", "Entered by a person", "Document · page n" (clickable) or "Bureau report". A value a person changed also prints "(proposed: …)" so both are kept. Missing values read "Not on record" |
| **Parties** | One row per person: name, role (Borrower / Director / Partner / Proprietor / Guarantor / Promoter), PAN, DIN, source chip | Under each non-borrower, "KYC:" with a button per KYC document (type · pages) that opens the viewer, or amber "none received" |
| ↳ **Party count** | "Parties: 4" in the header | — |
| ↳ **Empty** | "No parties yet / Parties appear as constitution, KYC and bureau documents are read." | — |
| **Identity fields from documents** | Field / value / confidence / status / decision rows, limited to constitution, registration and KYC documents | "click a value to see its page" |
| **KYC coverage** (right rail) | Parties / With KYC / Without KYC counts | — |

**Scenario.** Ananya filters to **Please check**. Three rows remain: *Turnover* on the FY 2025-26
income tax return at 54%, and two PAN reads at 61% and 58%. She clicks the turnover value: the
viewer opens at page 2 of the return with the figure's region outlined, the header showing
"Confidence 54% · Read from the page text". The printed figure matches, so she presses **Confirm**
in the viewer; the row turns *Confirmed* and the turnover cross-checks that were waiting on it now
run. On the second PAN the printed text reads `AAACK1234F` but the parsed value shows `AAACK1234E`;
she presses **Correct…**, types the right value with a reason, and the row becomes *Corrected* —
the system value is kept beside it, and configuration is untouched.

---

## 8. Completeness — `/appraisals/$caseId/completeness`

**Stage 3 of 6.** All roles (`checklist.read`). Three anchored sections: `#readiness`,
`#checklist`, `#queries` — the header's "n blocking" button and the workbench's attention rows
land on them directly.

### 8.1 Readiness summary (`#readiness`)

| Component | What it is | What it does |
|---|---|---|
| **Verdict line** | Green shield "Ready for credit", or red triangle "Not ready for credit review: 62% against a 70% gate" | The headline judgement |
| **Blocking line** | "3 blocking item(s) still open. Each one stops the case reaching credit review." or "No blocking gap remains on this case." | — |
| **"n blocking cross-check finding(s) to decide →"** | Red link | Appears when failed blocking discrepancies exist; opens the Cross-checks tab |
| **Readiness score** | Big percentage + coloured bar | Weighted by section and document importance, not a plain count of files |
| **Status counts** | Satisfied / Insufficient / Missing / In review / Waived, each coloured | — |
| **Gate badges** | "Review gate 70% · Met/Not met" and "Disbursement gate 90% · Met/Not met" | Hovering shows "threshold 70% · now 62%" |
| **Provisional note** | Amber line | "The constitution or facilities are not confirmed yet, so this checklist is provisional. It is derived again once they are." |

### 8.2 "Required document set" (`#checklist`)

| Component | What it is | What it does |
|---|---|---|
| **Sub-line** | "24 requirements derived from the private limited company constitution and the cash credit and term loan ask. Blocking items stop credit review; the rest do not." | Says where the checklist came from |
| **Filter chips** | All (n) · Open (n) · Blocking (n) · Satisfied (n) | Narrows the list; "No item matches this filter." when empty |
| **Section bands** | Constitution and KYC · Financials · Banking and operations · Collateral and security, each with "weight 30%" | The weighting behind the score |
| **Item row** | Chevron, item name, **Blocking** chip, deficiency in amber, basis line + "linked documents: 2", status chip (Satisfied / Insufficient / Missing / In review / Waived) | Click anywhere to expand |
| ↳ **Why it is required** | Expanded text | The policy or process reason |
| ↳ **What to ask the customer for** | Expanded text (open items only) | The exact request, which is what the query list uses |
| ↳ **What complete means** | Collapsed details | The coverage rule from configuration: "Financial years: 2", "Months for every account: 12", "Every party that needs KYC" |
| ↳ **Deficiency callout** | Red block: "Insufficient — only 7 of 12 months received" | — |
| ↳ **Linked document buttons** | One per document satisfying the item (type · pages) | Opens the viewer at that document |
| ↳ **See machine checks** | Link | Opens the Files tab for the quality and classification detail |

### 8.3 "Pre-login query list" (`#queries`, sticky on wide screens)

| Component | What it is | What it does |
|---|---|---|
| **Sub-line** | "4 open · 2 resolved" | — |
| **Copy as email** | Primary CTA | Copies a ready-to-send mail: subject "Documents and clarifications for {borrower} ({id})", "Dear Sir or Madam," the numbered asks and a closing. Toast: "Copied as an email. Paste it into your mail." |
| **Copy** | Secondary CTA | Copies the plain numbered list |
| **Group bands** | Documents needed · Documents to redo · Clarifications · Resolved, each with a count | Items are grouped by what the customer must do |
| **Numbered item** | "3. Please send the GSTR-3B returns for Apr 2025 to Aug 2025." | Plain-language ask, numbered continuously across the open groups |
| ↳ **Evidence** | Link on items that have a source page | Opens the viewer at the page behind the ask |
| ↳ **Resolved items** | Struck through with a green tick and a "Resolved" chip | Kept for the record |
| **Footer note** | "Nothing is sent from CreditIQ; copy the list and send it yourself." | The product never mails the customer |
| **Copy failure** | Toast | "Copying is blocked in this browser. Select the text and copy it." |
| **Empty** | "No queries / Nothing is needed from the customer right now." | — |

**Scenario.** Marigold: the verdict reads "Not ready for credit review: 41% against a 70% gate"
with "7 blocking item(s) still open". Arjun filters the checklist to **Blocking (7)**, expands
*Director KYC* — "Why it is required: KYC is required for every director of a private limited
company", "What to ask the customer for: PAN and Aadhaar for each director named in the
memorandum", coverage "Every party that needs KYC". He presses **Copy as email** on the query
list, which carries all seven asks plus the GST months the cross-checks added, pastes it into
Outlook and sends it. Two days later the director KYC arrives; he uploads it on the Files tab, the
item turns **Satisfied**, the readiness bar moves to 58%, and the matching query line moves into
**Resolved** struck through.

---

## 9. Cross-checks — `/appraisals/$caseId/cross-verification`

**Stage 4 of 6.** Credit Analyst and Credit Manager (`finding.read`).
**Title.** "Cross-verification and discrepancy". The engine lines up every source against every
other; the board shows its view as given and never recomputes it.

### 9.1 Tab header

| Component | What it is | What it does |
|---|---|---|
| **Kicker** | "Appraisal {id} · Cross-verification" | — |
| **Summary line** | "Every source lined up against every other. 15 discrepancies found for this borrower, ranked by credit impact, each with its evidence attached and a decision required from you." | Variants for none / one / all decided / not run |
| **Meta line** | "1 of 15 adjudicated · XR-000004-003 · 24 rules across 13 sources · 09 Oct 2026, 14:00" | What ran, when, and how much is decided |
| **Spread** | CTA (← arrow) | Opens the Financials section of Financials and Policy (`/policy#financials`) |
| **Exception queue** | CTA | Opens the Review queue |
| **Continue to draft** | Primary CTA (→) | Opens Outputs → Draft CAM. **Locked** (grey, padlock) while any blocking discrepancy is unadjudicated; hovering says "Submission is blocked until every blocking discrepancy is accepted or dismissed." |

### 9.2 Blocking banner

| Component | What it is | What it does |
|---|---|---|
| **Banner** | Red block: "Submission blocked — 3 serious discrepancies unadjudicated", then the most important one: its reference, explanation and policy reference | Appears only while submission is blocked |
| **Adjudicate now** | Red CTA | Scrolls to that discrepancy's card, expands it and focuses it |

### 9.3 Area overview — four cards

Cards, in the engine's order: **Identity consistency** (PAN, GSTIN, CIN, name and directors agree
across every document) · **Turnover** (audited, GST, banked and declared agree within tolerance) ·
**Bank accounts** (every declared account has a statement; every account on file was declared) ·
**Existing obligations** (declared facilities agree with sanction letters, the bureau and the bank).

| Component | What it is | What it does |
|---|---|---|
| **Card top border + icon** | Red = open discrepancies, amber = some checks could not run, green = everything checked agrees, grey = clear/decided | The area's status at a glance |
| **Area title** | Button covering the whole card surface | Scrolls to that area's section and focuses its heading |
| **Blocking** badge | Red pill | At least one open discrepancy in this area blocks submission |
| **Big number + "open discrepancies"** | Count | Undecided discrepancies |
| **Severity breakdown** | "3 serious · 2 moderate · 1 mild" | — |
| **Decided line** | "1 of 6 decided" | — |
| **Others line** | "5 could not be checked · 12 passed · 2 not applicable" | — |
| **Top line** | The open discrepancy of greatest credit impact — or "Every discrepancy decided" / "No discrepancy" | — |
| **Key figures** (up to 3) | Label in small caps, then the figures side by side (the differing one in red), then a note | Each is a button that opens **its own** finding: a discrepancy's card (expanded, as *Adjudicate now* does) or, for a passed or incomplete check, its row in the list below, opening the collapsed list and marking the row |

### 9.4 Area section

| Component | What it is | What it does |
|---|---|---|
| **Heading** | Area icon + title + purpose | The scroll target of the card |
| **Counts line** | "8 rules · 2 discrepancies · 1 could not be checked · 4 passed" | The engine's counts |
| **Discrepancies** | One card each, ranked by credit impact within the area; the board's top finding opens automatically | See §9.5 |
| **"No discrepancy in this area."** | Grey strip | When the area has none |
| **Could not be checked (n)** | List with "Each check says what would complete it" | See §9.6 |
| **Passed (n)** | Collapsed list | Each passed check with its rule, what it compared, its scope and the variance it measured, so a pass is evidenced, not assumed; "Not applicable (n)" rows follow with why |
| **Facts behind these checks** | Collapsed panel | The aligned facts the checks used (§9.7) |

### 9.5 A discrepancy card

**Collapsed:** rank number · severity chip (Serious / Moderate / Mild) · **Blocks submission**
padlock badge · decision chip once decided (Accepted / Dismissed / Escalated) · reference `XV-…`,
rule id and scope in monospace · the finding's title · for amount checks the two figures large with
the differing one red and how far apart they are · the one-line explanation.

**Expanded:**

| Component | What it is | What it does |
|---|---|---|
| **Rule line** | "Rule TO-02 — GST outward supplies against business credits in the bank, tolerance 10% · owner Ananya Krishnan" | What the rule compares and who owns it |
| **Compare the pages side by side** | CTA (columns icon) | Opens the viewer in compare mode with one pane per source, each at its page and region, labelled with what that source says |
| **Source columns** (2–4) | One per source: label, provenance chips (**Declared** / **Borrower-supplied** / **Independent**), the value large, coverage line | The value turns red when it differs; for identifiers the differing characters are marked one by one against the value most sources give |
| ↳ **Differs** chip | Red | This column is the odd one out |
| ↳ **Relies on a person's entry** chip | Amber | The value rests on a manual entry |
| ↳ **Waiting for review** chip | Amber, clickable | The value is below threshold; opens it at its page to confirm or correct — checks never rely on a value a person has not confirmed |
| ↳ **Open the evidence** | Link | Expands the rows read from that document inside the card (§ evidence panel): one row per line, with totals and excluded lines marked, each with a page button |
| ↳ **Trace to the source** | Link | Opens the viewer at that column's page |
| **Gap strip** | One leg per comparison: "INR 3.00 cr · 25.0% of GST", red where breached, plus "RBL tolerance: 10% — breached on GST against bank" | How far apart the sources are, as the engine measured it. For a check without amounts, the difference in words instead |
| **Line by line (n)** | Collapsed table | The per-row comparison behind the figure (months, names split into first/middle/last, accounts) with the differing cells marked |
| **Adjudicate** | "A decision is required on every discrepancy" + three radio cards | **Accept** — "A valid finding; it stays on the query list" · **Dismiss** — "Not a valid finding" · **Escalate** — "Hand to the Credit Manager; stays open and blocking" (not offered once escalated) |
| ↳ **Comment** | Textarea, "What you concluded, and on what evidence" | Required, minimum 3 characters: "Every decision on a discrepancy is recorded with a comment…" |
| ↳ **Record decision** | Primary CTA | Saves. The card then shows the decision chip, who decided, when, why, and what the decision means. Counts, the banner and the header update at once |
| ↳ **Refusal line** | Red text | The engine's own words when it refuses — comment too short, or decided/escalated meanwhile; the board re-reads the engine so the other person's decision appears in place |
| ↳ **Escalation note** | Blue block | "Escalated to the Credit Manager by {name} · {when}" with the comment |
| ↳ **Waiting for the Credit Manager** | Amber line with a padlock | Shown to an analyst on an escalated discrepancy |
| ↳ **"Waiting for a reviewer's decision."** | Grey line | Shown to a role without `review.decide` |

### 9.6 "Could not be checked" row

| Component | What it is | What it does |
|---|---|---|
| **Row** | Amber left border; rule id, what it compares, scope, explanation | A check that could not run — never a silent pass or fail |
| **"To complete it, provide …"** | Sentence | Exactly what is missing, e.g. "the director KYC", "GSTR-3B returns for Apr 2025 to Aug 2025" |
| **Add to query list** | CTA (needs `review.decide`) | Puts that request on the pre-login query list; the row then shows a green **On the query list** chip |
| **Waiting for review** | Chip | When the check is held up by an unconfirmed value instead of a missing document |
| **Add documents →** | Link | Opens the Files tab |

### 9.7 "Facts behind these checks"

Collapsed panels, per area, each value carrying its pages: **Identifiers by document** (each
identifier with every document that states it, a second value highlighted) · **Directors and
promoters** (each person, the sources naming them, DIN and PAN as printed) · **Turnover by
financial year** (audited, GST, banked, declared) · **Bank credits** ("Credits 11.20 cr · excluded
2.20 cr · business inflow 9.00 cr" — transfers between own accounts, loan disbursals, reversals and
returned cheques are taken out before comparison) · **Bank accounts** (declared / not declared,
statements received / none) · **Obligations** (instalments seen in the statements and the facilities
each source records).

**Scenario (Kestrel).** Ananya opens the tab. The banner reads "Submission blocked — 3 serious
discrepancies unadjudicated", pointing at **ID-01**. The four cards read: Identity 6 open
(3 serious · 2 moderate · 1 mild) **Blocking**; Turnover 5 open; Bank accounts 2 open; Existing
obligations 2 open. A key figure on the identity card shows `AAACK1234F` against `AAACK9999Z` —
she clicks it and ID-01's card opens: column one "16 documents and the sourcing message", column
two "Commercial bureau report" (**Independent**) with `9999Z` marked character by character. She
presses **Trace to the source** on the bureau column, reads the page, chooses **Accept** with the
comment "Bureau PAN is a data error at the bureau; 16 primary documents agree. Raising a bureau
correction request." and presses **Record decision**. The banner drops to "2 serious…". On
**ID-02** (a GSTIN from another state on the bureau) she chooses **Escalate** with a comment; it
stays open and blocking. On **TO-02** she opens **Open the evidence** on the bank column and shows
the INR 50 lakh loan disbursal and a reversal being excluded before the comparison, then accepts
the finding so it stays on the query list. Once ID-01, ID-02 (by Meenal) and ID-04 are decided,
the banner disappears and **Continue to draft** unlocks.

---

## 10. Financials and Policy — `/appraisals/$caseId/policy`

**Stage 5 of 6.** Credit Analyst and Credit Manager (`finding.read`).
**Title.** "Financials and Policy." The tab holds the spread (moved from Outputs, FRD decision
C.4-10) and the policy norms: the overview cards, then the **Financials** section (`#financials`),
then each family of norms and the approving authority.

### 10.0 Financials

The spread year by year, every figure selectable, with a rail showing how many lines are traced to
a page and where the selected figure was read from.

| Component | What it is | What it does |
|---|---|---|
| **Interim notice** | Blue line | "This spread uses an interim layout. It will follow RBL's spread template, with an Excel export, when the template is available." |
| **Period** | Year picker | Shades the selected year down every table; says the year end and basis |
| **Turnover banner** | Amber banner | The open turnover discrepancy of greatest impact, its figures, and "Take this to Cross-checks" |
| **Turnover by year** | Table | Every source (audited, GST, bank credits, ITR, declared) by financial year; green where a cross-check found it within tolerance, red where it differs, amber where part of the year is missing |
| **Profit and loss, Balance sheet** | Tables, INR crore | Each line by year; a figure relying on a person's entry is marked amber and named under the table |
| **Working-capital assessment** | Table | The method and why, each step with its basis and an eye to its page, and the eligible finance against the request |
| **Trend notes** | Two cards | Turnover growth and the change in the working-capital cycle from the year before |
| **Spread status, Source panel** | Rail | Lines traced, figures relying on a person's entry, periods, layout; the selected figure's document and page, with "Open the page" |

The ratios are not repeated here: each financial-ratio norm below carries its band, **Within
policy** (green), **Marginal** (amber, still a deviation) or **Outside policy** (red), against the
configured acceptable and marginal values, with "marginal {value}" under the required value.

### 10.1 Header

| Component | What it is | What it does |
|---|---|---|
| **Kicker** | "Appraisal {id} · Policy checks" | — |
| **Summary line** | "2 deviations · 1 cannot be evaluated · 9 passed · 1 not applicable · FY 2025-26 · provisional norms" | The engine's counts and the year the figures come from |
| **Interim notice** | Blue line with an info icon | "These norms are interim proposals until RBL's own policy norms are supplied." |

### 10.2 Overview — five cards

Four families — **Eligibility** (whether the borrower qualifies at all) · **Financial ratios**
(liquidity, leverage, debt service, working-capital cycle) · **Documentation** (the documents the
policy requires on file) · **Security cover** (collateral cover against the amount requested) —
and one **Approving authority** card.

| Component | What it is | What it does |
|---|---|---|
| **Family card** | Coloured top border by status: a norm deviates / a norm cannot be evaluated / every norm met / no norm yet | — |
| ↳ **Title button** | Covers the card | Scrolls to that family's section and focuses its heading |
| ↳ **Deviation count** | Big number + "deviation(s)" | — |
| ↳ **Others line** | "1 cannot be evaluated · 3 passed · 1 not applicable" | — |
| ↳ **Key norms** (up to 3) | Label, actual against required, and a note when something is missing | Each opens its own norm row below |
| ↳ **Pending line** | "No eligibility norm can be evaluated yet." / "No financial-ratio norm is configured." | For a family with nothing to show |
| **Approving authority card** | "Who must approve the case under the approval matrix" | — |
| ↳ **Named authority** | "Zonal Credit Committee (level 3)", prefixed "At least" when a norm could not be evaluated | — |
| ↳ **Rise line** | "Would rise to Head Office Credit Committee (level 4) if FR-03 deviated" / "Would not rise even if …" | What the unassessed norms could do |
| ↳ **Amount / Deviations lines** | "Amount: Regional Credit Head" · "Deviations: process +1 level, financial at least Zonal Credit Committee" | The two forces that set the authority |
| ↳ **Provisional** chip | Grey | The matrix is provisional until RBL supplies its own |
| ↳ **Unavailable** | "No approval matrix published yet" / "Cannot be determined" / "Could not be loaded" | — |

### 10.3 Family section — one row per norm

| Component | What it is | What it does |
|---|---|---|
| **Outcome icon** | Passed / Deviation / Cannot evaluate / Not applicable | Leftmost on the row |
| **Norm id + label** | e.g. `FR-06` "Working-capital cycle" | — |
| **Category chip** | Red, on a deviation, e.g. "Financial" / "Process" | The deviation category, which drives the approving authority |
| **Provisional chip** | Grey | This norm is an interim proposal |
| **Required / Actual** | Two columns, the actual coloured by outcome | e.g. Required "at most 75 days", Actual "90 days" |
| **Reason line** | Red or amber | "Cannot evaluate: proposed monthly instalment is zero." · "Cannot evaluate until turnover is reviewed." |
| **Missing line** | Amber | "Cannot evaluate: valuation report not on file." |
| **Inputs** | Chips: label + value | Every figure the norm used. A figure read from a document is a **dotted-underlined button** that opens its page; one with no page says where it came from — **Open blocking checklist items** (links to Completeness), "(No instalment debits in the bank statements on file)", "(No term loan requested)", "(From the case header)". Chips **Relies on a person's entry** and **Awaiting review** flag soft inputs |
| **How was this decided** | Collapsed details | The formula, the ratio's definition, and any note |

### 10.4 Approving authority section

| Component | What it is | What it does |
|---|---|---|
| **Required: {authority}** + **Level n** chip | Headline | Who must approve under the matrix |
| **Basis line** | "INR 5.00 cr requested · Cash credit, Term loan" | — |
| **Lower-bound note** | Amber block | "1 norm(s) could not be evaluated (FR-03). If they are deviations, the matrix would require Head Office Credit Committee." (or the "would not change" variant) |
| **How this was decided** | Open details, numbered steps | One step per rule: "Cash credit: INR 5.00 cr is above INR 3.00 cr and up to INR 7.50 cr, so Regional Credit Head"; "Financial deviation (FR-06): 1 level(s) above the amount authority, so Zonal Credit Committee". Norm ids inside a step are buttons that scroll to that norm's row. The step that settles it carries a **Decides** chip |
| **Provisional footer** | "Waiting for RBL's approval and delegation matrix." | — |
| **Compared with RBL's record on the Comparison tab** | Link (Credit Manager only) | RBL's recorded approval is never shown here — the analyst stays blind to it |
| **Not published** | "The approval matrix is not part of the published configuration." | Shown instead of the section body |

**Scenario (Kestrel).** The cards read: Eligibility green, Financial ratios red (1 deviation),
Documentation red (1 deviation), Security cover amber, Approving authority "At least Head Office
Credit Committee (level 4)". Ananya clicks the Financial ratios card and lands on **FR-06**:
Required "at most 75 days", Actual "90 days" in red, inputs *Inventory days 46* and *Debtor days
61* each opening the audited balance sheet page, and "How was this decided" giving the formula.
**FR-03 (DSCR)** says "Cannot evaluate: proposed monthly instalment is zero" — the RM never
entered the term loan's instalment. **DOC-01** deviates with "3 blocking checklist items open",
its input linking to Completeness. In the authority section, step 1 puts the amount at Zonal
Credit Committee, step 2 raises it one level for the financial deviation, step 3 is marked
**Decides** — Head Office Credit Committee — and the amber note says FR-03, if it turns out to be
a deviation, would not raise it further.

---

## 11. Outputs — `/appraisals/$caseId/outputs`

**Stage 6 of 6.** Credit Analyst and Credit Manager (`output.read`). Two views switched by pills
at the top: **Draft CAM** · **PD note** (the address carries `?view=cam|pd`). The spread moved to
Financials and Policy (§10.0); an earlier `?view=spread` link opens it there.

### 11.1 Draft CAM

**Purpose.** "The draft Credit Approval Memo, and the questions for the personal discussion, every
statement traceable to its page."

| Component | What it is | What it does |
|---|---|---|
| **Eyebrow / title** | "Draft for credit" / "Credit Approval Memo" | — |
| **Interim note** | "Sections follow an interim list until RBL's CAM template is available. Every figure links to the page it comes from." | — |
| **Numbered sections** | The template's sections, each with paragraphs and optional tables | — |
| ↳ **Citations** | Small `p12` buttons after a statement or in a cell | Open the viewer at that page; up to four per statement |
| ↳ **Section empty line** | Grey text | What the section is waiting for |
| **Summary section** | Grouped lists: **Findings (n)** · **Deviations from policy (n)** · **Norms not assessed (n)** · **Open queries (n)** | Everything credit must weigh, each item with its reference, severity chip and citations. The findings here are the discrepancies **accepted** on the Cross-checks tab; dismissed ones drop out |
| **Recommendation section** | Dashed empty box: "For credit to complete." | Deliberately left blank — the product prepares, credit decides |

### 11.2 PD note

| Component | What it is | What it does |
|---|---|---|
| **Title / sub-line** | "Questions for the personal discussion" / "7 question(s), most serious first, each tied to its finding and pages." | — |
| **Numbered question** | The question in plain language | — |
| ↳ **Severity chip** | Serious / Moderate / Mild | — |
| ↳ **Source** | "Cross-check finding" / "Policy deviation" / "Open gap" | Where the question came from |
| ↳ **Rule link** | "TO-02 · GST turnover against bank credits" | Opens the tab that owns it — Cross-checks or Policy |
| ↳ **Citations** | `p` buttons | Open the pages behind the question |
| **Empty** | "No questions yet / Questions come from cross-check findings, policy deviations and open gaps." | — |

**Scenario.** After unlocking the board, Ananya presses **Continue to draft** and lands on
**Draft CAM**. Section 4 reads "Audited turnover for FY 2025-26 was INR 11.80 cr (p3), against GST
outward supplies of INR 12.00 cr (p1)." She clicks `p3`: the viewer opens the audited P&L at the
figure. The summary section lists "Findings (4)" — including the accepted PAN and turnover
discrepancies — "Deviations from policy (2)", "Norms not assessed (1)" and "Open queries (5)". The
recommendation box is empty, for credit. She switches to **PD note**: question 1, Serious, source
"Cross-check finding", "Business inflow in the bank is INR 3.00 cr below GST turnover for
FY 2025-26 — where is the balance of sales banked?", linking to TO-02. She prints the note for the
personal discussion.

---

## 12. Comparison — `/appraisals/$caseId/comparison`

**Who sees it.** Credit Manager only (`comparison.adjudicate`).
**Purpose.** "This case's output beside the assessment RBL credit made at the time, for
adjudication." Decisions are recorded beside the output and never change it.

| Component | What it is | What it does |
|---|---|---|
| **Waiting state** | "RBL's record for this appraisal has not been imported yet." | Shown until a record exists |
| **Record bar** | "Record imported from {workbook} on {date}" | Where RBL's record came from |
| ↳ **Confirm the record** | CTA | The reviewer confirms the imported record before it is scored; afterwards the bar reads "Confirmed by {name} on {date}" |
| ↳ **Self-confirm note** | "The record must be confirmed by someone other than who imported it." | The button is disabled for the importer |
| ↳ **"RBL's record shows no deviations"** | Grey note | When the record has none |
| **Counts line** | "Deviations: Agree 3 · Differ 1 · New 1 · Missed 1" | — |
| **Overlay note** | "Decisions are recorded beside the output and never change it." | — |
| **Provisional note** | Amber | "Norms are interim proposals: agreement is indicative until RBL's norms are published." |
| **Not scored note** | Amber | "Not scored while the approval matrix is provisional." |
| **Filter chips** | All (n) · To decide (n) · Agree (n) · Differ (n) · New (n) · Missed (n) | Narrows the rows |
| **Area panels** | **Deviations** and **Approving authority**, each with a score line — "2 of 3 deviations in RBL's record found · 3 of 4 CreditIQ deviations upheld (1 awaiting a decision)" / "Recorded approval agrees with the matrix: 1 of 1" | — |
| **Row: Item** | Norm label + its id + category chip | — |
| **Row: CreditIQ** | The value, as a dotted-underlined button where it has evidence, with the requirement underneath | Opens the page behind the figure |
| **Row: RBL record** | What the record says, who approved it, and "Where in the record: {sheet/cell}" | — |
| **Row: Status chip** | **Agree** / **Differ** / **New** (found only by CreditIQ) / **Missed** (in the record, not found) | — |
| **Notes** | One line each: "Value differs: 90 days against 88 days" · "Category differs: …" · "CreditIQ assessed it as passed: 1.42x against at least 1.25x" · "CreditIQ could not evaluate it: proposed instalment" · "No norm in the policy covers this deviation." · "The recorded approval is below the required authority." | Why the status is what it is |
| **Authority detail** | "Rule applied: …", "On RBL's recorded deviations, the matrix requires Zonal Credit Committee", and the full step list | Only on the approving-authority row |
| **Adjudicate** | **Valid** / **Not valid** toggle, then a **Reason** field and **Save decision** | Records the reviewer's verdict on each comparison item. A reason of at least 3 characters is required |
| ↳ **Decided line** | "Valid · Meenal Kulkarni · 13 Oct 2026 · same ratio, different rounding" | — |
| ↳ **Change decision** | Link | Re-opens the toggle |
| ↳ **Stale warning** | Amber | "CreditIQ's result or the record has changed since this decision; decide again." |
| **Other areas note** | "Classification, key fields, discrepancies, queries and decision are compared once their sheets are imported." | What this tab will cover later |

**Scenario.** Meenal signs in as Credit Manager and opens Kestrel's Comparison. The record bar says
it was imported from a workbook that morning by someone else, so she presses **Confirm the
record**. The counts read "Agree 1 · Differ 1 · New 0 · Missed 1". FR-06 is **Agree** (90 days on
both sides) — she marks it **Valid** with the reason "same cycle, same conclusion". DOC-01 is
**Differ** (CreditIQ 3 open items against the record's 6) with the note explaining the values; she
marks it **Valid** anyway ("CreditIQ counted only blocking items"). FR-03 is **Missed** — RBL
recorded a DSCR of 1.32x that CreditIQ could not assess because the instalment was never entered;
she marks it **Not valid** with that reason, which is exactly the gap the readout needs to show.
The approving-authority row is **Agree**: Head Office Credit Committee on both sides.

---

## 13. Review queue — `/review`

**Who sees it.** Credit Analyst and Credit Manager (`review.read`). Deciding needs
`review.decide`; an escalated discrepancy needs `finding.escalation` (Credit Manager).
**Purpose.** "Everything waiting for a person across cases, with the decision each one needs."

| Component | What it is | What it does |
|---|---|---|
| **KPI: Open items** | Count + "Applications: 3" | — |
| **KPI: Type assignment** | Count + "documents waiting for a type" | — |
| **KPI: Field review** | Count + "values below threshold" | — |
| **KPI: Oldest open** | Date + "raised on" | How long the queue's tail has waited |
| **Kind filter** | Pills: All kinds · Type assignment · Field review · Quality exception · Party or label flag · Uncertain split · Manual entry · Finding | — |
| **Case filter** | Select: "All cases" or "{borrower} · {id}" | — |
| **Show decided** | Checkbox | Adds decided items to the table |
| **Table** | Columns Kind / Item / Raised / Decision / Action, oldest first | — |
| ↳ **Kind chip** | Red for Quality exception and Finding, blue otherwise; plus an amber **Escalated** chip | — |
| ↳ **Item** | Link: the item's summary, with "{borrower} · {id}" underneath | Opens where the item is decided in context (Files / Extracted data / Cross-checks) |
| ↳ **Raised** | Date, and the maker's name for a maker-checker item | — |
| ↳ **Decision** | "Open", or the decision chip with its reason, who decided, and after a correction both values ("System AAACK1234E · corrected AAACK1234F") | — |
| ↳ **Decide ↗** | CTA | Opens the decision dialog (§19.1) |
| ↳ **Decide (padlocked)** | Disabled CTA + "Waiting for the Credit Manager" | An escalated discrepancy an analyst may not close |
| ↳ **View ↗** | CTA | For items with no decision of their own: opens them in context |
| **Empty** | "Nothing is waiting here. Every item has a decision." | — |

**Scenario.** Ananya filters to **Type assignment**: four documents across two appraisals are
waiting for a type. She presses **Decide** on the first, picks *Stock and book-debt statement*
from the published list, adds the reason "index page says stock statement; content matches", and
records it. The row moves to *decided*, the Files tab row turns green, and the checklist item it
satisfies flips to **Satisfied**. Later Meenal filters to **Finding**, sees ID-02 marked
**Escalated**, presses **Decide** (only she can), and dismisses it with a comment.

---

## 14. Scorecard — `/scorecard`

**Who sees it.** Credit Manager (`scorecard.read`).
**Purpose.** "The success criteria, per case and across the case set."

| Component | What it is | What it does |
|---|---|---|
| **Page header** | Eyebrow "Governance", title, purpose | — |
| **Pending state** | "Nothing to show yet / This view fills in once the case has been processed this far." | The criteria scoring (C1–C9) is the one screen still to be built; the route, the menu entry and the role gate already exist |

**Scenario.** Meenal opens the Scorecard expecting the C1–C9 table and sees the designed pending
state — nothing is broken, and the scoring arrives with its feature. The per-case comparison
scores she needs today are on each case's Comparison tab.

---

## 15. Audit trail — `/audit`

**Who sees it.** Credit Analyst and Credit Manager (`audit.read`).
**Purpose.** "Who did what, and when. Entries are added as work happens and are never changed."

| Component | What it is | What it does |
|---|---|---|
| **Activity filter** | Select: "All activity" or one action — Signed in, Created an appraisal, Deleted an appraisal, Stage changed, Uploaded files, Ran document processing, Read a document again, Decided a review item, Imported RBL's record, Confirmed RBL's record, Decided a comparison item, Escalated a discrepancy to the Credit Manager, Put a request on the query list | — |
| **Person filter** | Select: "Everyone" or a named user | — |
| **Appraisal number** | Text field | Filters to one case |
| **Entry** | Action label · actor name · timestamp · case id (a link) | The case id opens that appraisal |
| ↳ **How was this decided** | Collapsed details | The entry's detail payload, key by key |
| **Empty** | "No activity matches these filters." | — |

**Scenario.** Before the readout Ananya filters the trail to **Decided a review item** for Kestrel.
She sees each decision with its actor and time, expands one and finds the field id, the system
value, the corrected value and the reason — the record that nothing was changed silently.

---

## 16. Administration — `/admin`

**Who sees it.** Credit Analyst and Credit Manager (`config.read`). **Read-only**: an administrator
publishes a change from the command line as a new immutable version.
**Purpose.** "What the published configuration says and who may do what."

Five pill tabs across the top: **Configuration · Policy norms · Checklist · Document types ·
Users and roles.**

### 16.1 Configuration — `/admin`

| Component | What it is | What it does |
|---|---|---|
| **In force now** panel | Published / Published by / Version | The version every result on every screen was produced under |
| ↳ **Read-only note** | "Configuration is read-only here. An administrator publishes a change as a new version, and earlier versions are kept." | — |
| **Version history** panel | "Every version ever published, newest first" | One row per version: "Version 7", an **In force** chip on the current one, when and by whom, the note, and "3 section(s) changed: policy norms, tolerances, cross-checks" (or "First version.") |

### 16.2 Policy norms — `/admin/policy`

One panel per family (Eligibility, Financial ratios, Security cover, Documentation) with
"n norm(s)" and a table: **Norm** (with a *Provisional* chip where it is an interim proposal) /
**Requirement** ("at least 1.25 times", "at most 75 days") / **Deviation counted as** (the
category that drives the approving authority).

### 16.3 Checklist — `/admin/checklist`

| Component | What it is | What it does |
|---|---|---|
| **Gates line** | "An appraisal is ready for credit review at 70% and for disbursement at 90%, and only when nothing blocking remains." | The thresholds the readiness summary measures against |
| **Section panels** | One per checklist section, with "weight 30%" | — |
| ↳ **Item** | Name, a **BLOCKING** chip, why it is required, and "Applies to: private limited company, partnership firm…" | The source of every row on a case's Required document set |

### 16.4 Document types — `/admin/document-types`

One panel per group — Application, Constitution, Registration, Identity and KYC, Financial
statements, Working capital, Tax, Banking, Collateral, Credit bureau, Other — with "n document
type(s)" and each type's name and description. This is the closed list the classifier may choose
from and the list offered when a person assigns a type by hand.

### 16.5 Users and roles — `/admin/users`

| Component | What it is | What it does |
|---|---|---|
| **People** table | Name / Role / Email / Branch | The sign-in directory |
| **What each role may do** | One block per role, listing its permissions in plain words — "Create appraisals", "Open every appraisal", "Decide review items", "Decide escalated cross-check discrepancies", "Enter values by hand", "Check values entered by hand", "Decide comparisons", "See the scorecard"… | With the note "Permissions are enforced by the server; the menu only hides what a role cannot use." |

**Scenario.** At the readout someone asks why the case needs 70% and not 80%. Ananya opens
**Administration → Checklist**, reads the gates line, and shows that the number is configuration,
not code. Asked who could have changed it, she opens **Configuration** and shows the version
history: the last publish was five days ago, by the administrator, changing "policy norms,
tolerances" — and every result on screen carries that version.

---

## 17. Guide to the steps — `/help`

**Who sees it.** Everyone.
**Purpose.** "What each step of an appraisal does, what the statuses mean and what is asked of you."

| Component | What it is | What it does |
|---|---|---|
| **The steps** | A numbered list of the six steps, each with a plain-language paragraph — e.g. *Files*: "Every file you upload is checked for readability and identified as a kind of document. A file that cannot be read is sent back with a request for a clearer copy." | The in-product explanation of the pipeline |
| **What the statuses mean** | Not started / In progress / Needs attention / Done, each with a sentence | Explains the dots and chips used everywhere else |

**Scenario.** A new RM joins mid-PoC. Instead of a briefing, he reads *Guide to the steps* and
learns that **Needs attention** means "Something needs a person: a document, a value or a
decision" — the same words that appear on his case's stage bar.

---

## 18. The evidence viewer (opens over any tab)

`src/components/docviewer/DocViewer.tsx`. Every value, figure, finding, citation, page number and
query line opens it. It is a right-hand panel over the current tab — you never leave the tab.

| Component | What it is | What it does |
|---|---|---|
| **Header** | "Evidence", the document type, the file name and its page range | — |
| **Close** | ✕, the dark backdrop, or `Esc` | Closes the panel |
| **Field strip** | Field name · value · "Confidence 54%" · "Method Read from the page text" | Shown when a field opened the viewer |
| **Confirm / Correct** | Decision row beside the page | Confirms the value, or reveals the correction form (value + reason + save) — a correction is always made with the page in view |
| **Page pager** | ‹ page indicator › | "Page 4 · pages 3–7" within the document's own range |
| **Grade chip** | Clear / Readable / Hard to read / Unreadable | The grade of the page on screen |
| **Region highlighted** | Chip | The value's region is outlined on the page image, when the engine recorded one |
| **Page image** | Rendered by the engine (no PDF library in the browser) | "Rendering page" while it loads |
| **Compare mode** | "Sources side by side" | Two or more panes, each labelled with what that source says (e.g. "Commercial bureau report: AAACK9999Z") at its own page and region. Opened by **Compare the pages side by side** on a discrepancy card |
| **Back to page n** | Link | Returns from a compare pane to the originating page |

**Scenario.** On the spread, the FY 2025-26 turnover reads INR 11.80 cr. Ananya clicks it: the
viewer opens the audited P&L at page 3 with the line outlined, and the header shows 96% confidence
read from a fixed layout. She pages forward to the balance sheet, then closes with `Esc` — still on
the Spread, scrolled where she was.

---

## 19. Dialogs

### 19.1 Decision dialog (review items)

Opened from the Review queue's **Decide**, from **Other type…** or **Resolve: {kind}** on a
document row.

| Component | What it is | What it does |
|---|---|---|
| **Title / sub-line** | The kind of item / "{borrower} · {id}" | — |
| **Summary block** | The item's own words | What is being decided |
| **System value** | "System value: 1,18,00,000" | For a field item, what the engine read |
| **Decision** | Radio pills, by kind: **Confirm** / **Correct** / **Waive** / **Assign type**; on a quality item "Correct" reads **Enter manually** | — |
| **Document type** | Select "Choose from the published list…" | For *Assign type* and for manual entry of an unclassified document |
| **Corrected value** | Text field | For a field correction; a number stays a number |
| **The person this document belongs to** | Select of parties, plus "None of these parties" | For a party or label flag |
| **Manual entry** | Field name / Value row pairs, **Add a field**, remove ✕ | For a quality exception: a maker types the document's values as printed; "A checker who is not you confirms them before they are used" |
| **Reason / Comment** | Textarea, labelled "Reason (required)", "Reason (optional)" or "Comment (required)" | On a discrepancy a comment of at least 3 characters is always required, whether it is confirmed or waived |
| **Overlay note** | "The decision is recorded with your name and reason. The system value is kept beside it." | Nothing learns at runtime |
| **Refusal line** | Red | The engine's words when it refuses — a comment too short, or an item escalated or decided meanwhile |
| **Cancel / Record decision** | Footer CTAs | *Record decision* is disabled until the form is valid; on success a toast says "Decision recorded" |

### 19.2 Delete application

Opened from **Delete application** in the case header (`case.delete`).

| Component | What it is | What it does |
|---|---|---|
| **Title / description** | "Delete BBG-2026-000004?" / "This removes {borrower} and every file, document, extracted value, checklist state, query and review item it holds. It cannot be undone. A record that it was deleted is kept." | — |
| **Reason** | Text field, placeholder "For example, restarting the test run" | Required, at least 3 characters |
| **Type {id} to confirm** | Text field | Must match the appraisal number exactly |
| **Keep it** | Cancel CTA | — |
| **Delete permanently** | Destructive CTA | Deletes and returns to the workbench with a toast "{id} deleted". A case being processed is refused: "This application is being processed. Try again when processing finishes." |

---

## 20. Chip and status glossary

**Case stages** (header, workbench): Intake · Documents · Extraction · Completeness ·
Cross-verification · Policy · Outputs · Completed.

**Stage status** (stage bar, side menu dots): Not started · In progress · Needs attention · Done.

**File status**: **Registered** (green) · **Duplicate** (grey, same hash) · **Ignored** (grey) ·
**Rejected** (red) · **Exception** (amber).

**Document status**: Received · Graded · Split · Classified · **Unclassified** (amber) · Extracted ·
**Accepted** (green) · **In review** (amber) · **Exception** (red) · Superseded · Duplicate.

**Page quality grade**: **Clear** (A) · **Readable** (B) · **Hard to read** (C, amber) ·
**Unreadable** (U, red). Reasons: Low resolution · Blur · Skew · Shadow · OCR below floor ·
Corrupt · Password protected · Blank · Missing page.

**Field status**: **Confirmed** · **Please check** (amber, below threshold) · **Corrected** ·
**Not found** · **Rejected**. Method: Read from fixed layout · Read from the page text · Typed in ·
Entered by a person.

**Checklist status**: **Satisfied** · **Insufficient** (amber) · **Missing** (red) · **In review** ·
**Waived**. Defects: Incomplete · Outdated · Unsigned · Unstamped.

**Finding outcome**: Pass · **Finding** · **Incomplete** · Not applicable. Severity: **Serious** ·
**Moderate** · **Mild**. Decision: **Accepted** · **Dismissed** · **Escalated**.
Provenance of a source column: **Declared** · **Borrower-supplied** · **Independent**.

**Policy outcome**: **Passed** · **Deviation** · **Cannot evaluate** · **Not applicable**.

**Comparison status**: **Agree** · **Differ** · **New** (CreditIQ only) · **Missed** (record only);
verdicts **Valid** / **Not valid**.

**Review kinds**: Type assignment · Field review · Quality exception · Party or label flag ·
Uncertain split · Manual entry · Finding.

---

## 21. Empty, loading, error and redirect states

Every screen uses the same designed states rather than a blank page.

| State | Words |
|---|---|
| Loading | Skeleton rows in place of the panel |
| Nothing yet | "Nothing to show yet / This view fills in once the case has been processed this far." |
| Not your role | "Not part of your role / Your role does not include this view. Ask a credit analyst or credit manager if you need it." |
| Case not found | "No application {id} / It does not exist, or it is not assigned to you." |
| Configuration not published | "Configuration not published / The checklist and document configuration has not been published yet. An administrator publishes it from the command line." |
| Service unreachable | "The service is not reachable / CreditIQ cannot reach the case service right now. Check the connection, then try again." — with **Try again** |
| Rejected request | "Not accepted / The service did not accept this request." · "Not done / This conflicts with the current state of the case." |
| 404 | A large "404", "Page not found", and **Go to the workbench** |
| Page crash | "This page did not load", with **Try again** and **Go to the workbench** |

**Saved links still work.** Earlier addresses redirect to their new home: `/appraisals` and
`/docready` → the workbench; `/exceptions` → `/review`; `/appraisals/{id}/upload` → Files;
`/appraisals/{id}/identity` → Extracted data `#identity`; `/appraisals/{id}/data` → Extracted data
`#fields`; `/appraisals/{id}/spread` and Outputs `?view=spread` → Financials and Policy `#financials`; `/appraisals/{id}/draft` → Outputs
`?view=cam`; `/docready/{id}/checklist|readiness|collection` → Completeness `#checklist` /
`#readiness` / `#queries`; `/docready/{id}/validation` → Files.

---

## 22. Three end-to-end scenarios

### 22.1 Kestrel Fabricators — a file full of problems (the main demonstration)

1. **Sign in** as the RM. The workbench shows 2 applications in progress.
2. **New appraisal.** Paste the sourcing email → **Read the message** → the proposal comes back
   with the GSTIN *Unclear*; pick the candidate, **Confirm this value** on the constitution, attach
   the customer's ZIP, **Create application**.
3. **Overview.** "Next: Quality and classification — reading 11 documents." The stage bar's first
   tile spins.
4. **Files.** The archive opens as a folder; a merged PDF splits into four documents; one file is a
   **Duplicate**; one document is **Not identified** and one carries **Hard to read** pages with
   reasons. Sign in as the analyst and assign the unidentified type from its candidates.
5. **Extracted data.** Filter to **Please check**: confirm a turnover read at 54%, correct a PAN
   misread by one character in the viewer with a reason.
6. **Completeness.** "Not ready for credit review: 62% against a 70% gate", 3 blocking items.
   **Copy as email** and send the pre-login query list.
7. **Cross-checks.** "Submission blocked — 3 serious discrepancies". Identity 6 open, Turnover 5,
   Bank accounts 2, Existing obligations 2. Accept **ID-01** (bureau PAN wrong) with a comment;
   escalate **ID-02** to the Credit Manager; on **TO-02** show the bank figure being cleansed
   before comparison and accept it; show **BA-01** (a declared account with no statement) and
   **OB-02** (monthly instalments paid to a lender nobody declared). When the last blocking
   discrepancy is decided, **Continue to draft** unlocks.
8. **Policy.** FR-06 deviates (90 days against at most 75), DOC-01 deviates on 3 blocking items,
   FR-03 cannot be evaluated because the instalment was never entered. The approving authority is
   "at least Head Office Credit Committee", with the step that decides marked.
9. **Outputs.** The draft CAM with citations, the accepted findings and deviations in its summary, and an empty
   recommendation; the PD note's questions, most serious first.
10. **Comparison** (Credit Manager). Confirm RBL's record, then adjudicate: FR-06 **Agree**,
    DOC-01 **Differ**, FR-03 **Missed**, authority **Agree**.
11. **Audit trail.** Every one of those decisions, with who, when and why.

### 22.2 Heronbay Polymers — a clean file (2 minutes)

Open **Cross-checks**: all four area cards green, "No discrepancy". Open **Passed** in any section
and every check lists the variance it measured (TO-02 at 2.0% inside a 10% tolerance), so a pass is
evidenced rather than assumed; TO-05 is **Not applicable** with its reason. The header reads no
discrepancy, **Continue to draft** is unlocked from the start, and Completeness shows the gate met
with "Ready for credit" in the case header. The point: no false alarms.

### 22.3 Marigold Agro Foods — an unfinished file (3 minutes)

**Cross-checks** shows no discrepancies and three amber areas. Each incomplete check says what
would complete it — "To complete it, provide the director KYC", "GSTR-3B returns for Apr 2025 to
Aug 2025" — and **Add to query list** puts that request straight onto the Completeness tab's query
list, where the row then reads **On the query list**. **ID-01** is **Waiting for review**: the tax
return's PAN was read with low confidence; clicking it opens the value at its page, and once it is
confirmed ID-01 passes. **Policy** shows EL-05 (request against turnover at 60.5% against at most
20%) and DOC-02 (one year of audited statements) deviating, EL-02 unevaluable with no bureau report,
and the authority at "at least Zonal Credit Committee". The point: when something is missing the
product says exactly what, instead of passing or failing a check it cannot complete.

### 22.4 The same case through three pairs of eyes

| | RM (Arjun) | Analyst (Ananya) | Manager (Meenal) |
|---|---|---|---|
| Menu | Workbench, Help | + Review queue, Audit trail, Administration | + Scorecard |
| Case tabs | Overview, Files, Completeness | all but Comparison | all |
| Can | Create, upload, read the checklist, copy the query list, delete own cases | Decide review items, confirm/correct values, assign types, adjudicate discrepancies, enter values by hand | Check manual entries, decide escalated discrepancies, adjudicate the Comparison |
| Cannot | See extracted data, cross-checks, policy, outputs or the review queue | Adjudicate the Comparison or close an escalated discrepancy | Create an appraisal |

---

## 23. What is deliberately not built

Named in the FRD's screen map as out of scope for the PoC, so nothing on screen points at them:
the copilot rail, a memo library, an audit walk-through, borrower/entity/person dossiers, the
consent journey, rating, submission and a customer portal. Configuration editing screens are also
out: Administration is read-only and an administrator publishes a new version from the command
line. The **Scorecard** is the one in-scope screen still showing its pending state (§14).

Out of scope behind the screens: live integration with any RBL or partner system (GST,
bank-statement analysis, bureau, screening, CRM, loan workflow, email) — partner outputs arrive as
files; consent and OTP-based retrieval; and the credit recommendation, rating, pricing and sanction
themselves. Credit decides; CreditIQ prepares, checks and drafts.
