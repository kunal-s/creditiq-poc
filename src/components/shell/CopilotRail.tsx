import { useRouterState } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Sparkles, X, ArrowUp, FileSearch } from "lucide-react";
import { CURRENT_USER } from "@/data/seed";

type Answer = { text: string; citations: string[] };
type Ctx = { scope: string; note: string; actions: string[]; answers?: Record<string, Answer> };

function contextFor(pathname: string): Ctx {
  if (pathname.startsWith("/docready/") && pathname.includes("/readiness"))
    return {
      scope: "DocReady readiness — Southgate Textiles Pvt Ltd",
      note: "Readiness is weighted, not counted. I will say what still blocks the file and when it is likely to clear.",
      actions: [
        "What is still blocking the handoff",
        "When will this file be ready",
        "What carries across into the appraisal",
      ],
      answers: {
        "What is still blocking the handoff": {
          text: "One item, materially. The FY2026 financial statement failed attestation — no auditor signature, no UDIN, and the balance sheet is headed provisional. CCB ratio policy requires three audited years for a term loan of this size, so the spread cannot be built on it. The KYC set is the second gap: Vikram Sethi is missing entirely and his address proof, when supplied, was seven months old against the two-month rule. The missing co-operative bank sanction letter and the three late GST filings are recorded but non-blocking; they belong in the conduct narrative, not in the gate.",
          citations: [
            "Southgate_FS_FY2026_provisional.pdf — attestation check",
            "MCA director list, CIN U17120PN2011PTC141288",
            "CCB ratio and policy configuration — audited-years requirement",
          ],
        },
        "When will this file be ready": {
          text: "20 August 2026 on current commitments, nine days inside the 29 August target sanction date. The auditor has committed to the signed FY2026 set by 19 August, and the client's median response on portal asks across this case is two days, which covers the two KYC items. The one risk I would name is the bank statements: if Account Aggregator consent is not granted and statements come as PDFs for both accounts, comparable MSME cases took a further four to six days.",
          citations: ["Chase ledger DR-2026-0142", "Portal response times, this case"],
        },
        "What carries across into the appraisal": {
          text: "The handoff creates a CAM opened at the identity step with PAN, GSTIN, the Udyam registration, constitution and the Ichalkaranji SME Branch relationship already populated, plus the facility ask of INR 4.55 cr as CC and TL. Every accepted document is registered as present, so the pipeline does not re-ask the borrower for the two audited years, the GST filings or the accepted KYC. The handoff itself is written to the audit ledger with the document set attached.",
          citations: ["DocReady handoff record", "Appraisal intake — prefilled identifiers"],
        },
      },
    };
  if (pathname.startsWith("/docready"))
    return {
      scope: "DocReady — MSME document readiness",
      note: "Stage one of the engine: get a complete, usable file out of the client. I chase precisely, never in bulk.",
      actions: [
        "Why was the FY2026 statement rejected",
        "Draft the next chase for Southgate",
        "Which cases in the region are at risk",
      ],
      answers: {
        "Why was the FY2026 statement rejected": {
          text: "Attestation, not content. The figures extracted cleanly and are legible at 300 dpi, but there is no auditor signature, no UDIN on any page, and the balance sheet header reads 'provisional'. FY2024 and FY2025 are audited, signed and carry UDINs, so two of the three required years are already usable. The re-ask quotes exactly that defect rather than asking for 'financials' again — Southgate's auditor replied the same day with a 19 August commitment.",
          citations: [
            "Southgate_FS_FY2026_provisional.pdf — pages 1 to 9",
            "Attestation rule: auditor signature and UDIN required",
          ],
        },
        "Draft the next chase for Southgate": {
          text: "One message, four items, no repetition of anything already received: the signed and UDIN-bearing FY2026 statement, KYC for Vikram Sethi, a current address proof for him dated within two months, and the second term-loan sanction letter that the CIBIL commercial report shows against the borrower. Suggested opening: 'Thank you for the documents received on 6 August — the FY2024 and FY2025 statements and the GST filings are complete and need no further action. Four items remain.' Press 'Draft the next chase' on the collection screen to load it.",
          citations: ["Chase ledger DR-2026-0142", "Open checklist items, four"],
        },
        "Which cases in the region are at risk": {
          text: "Three of the six open cases. Konkan Steel Traders has sat 19 days with two blocking gaps and no client reply in eleven — that is the one I would escalate to the relationship manager. Solapur Weaving Mills is at 41% readiness with the Udyam certificate never supplied. Vashi Cold Storage is a softer risk: readiness is high but the collateral valuation is with an external valuer, outside the client's control. The other three are tracking normally.",
          citations: ["Readiness console, six open cases", "Collection aging by case"],
        },
      },
    };
  if (pathname.includes("/cross-verification"))
    return {
      scope: "Cross-verification — Northwind Manufacturing Ltd",
      note: "Three contradictions on this borrower. One is serious and blocks submission until you adjudicate it.",
      actions: [
        "Why is flag one flagged",
        "Draft the risk note for flag one",
        "Show me the months where deposits fell short",
        "What happens if I accept all three",
      ],
      answers: {
        "Why is flag one flagged": {
          text: "Because two independent sources disagree with the borrower's own numbers, and they agree with each other. FY2025 revenue in the audited statement and the ITR is INR 142.31 cr. GSTR-3B outward supplies for the same twelve months are INR 119.83 cr, and customer credits into Meridian 4471 and Horizon 2205 under consent are INR 121.44 cr — a gap of INR 22.48 cr and INR 20.87 cr. Rule XV-04 tolerates 5%; these are 15.8% and 14.7%. The two independent figures sit within INR 1.61 cr of each other, which makes an extraction error unlikely; either turnover is overstated or collections are moving outside the banking and GST system. I have not decided which — that is your call.",
          citations: [
            "Northwind_Manufacturing_Audited_FS_FY2025.pdf — page 14, line I",
            "GSTN return ledger, 27AABCN4521Q1ZP, FY2024-25 aggregate",
            "Account Aggregator bundle under consent CONS-2026-0418-A",
            "CCB CAM template v4.2, cross-verification rule 4.1",
          ],
        },
        "Draft the risk note for flag one": {
          text: "Suggested wording: \u201cDeclared FY2025 turnover of INR 142.31 cr is not supported by independent evidence. GST outward supplies total INR 119.83 cr and customer credits into the two consented accounts total INR 121.44 cr, shortfalls of INR 22.48 cr and INR 20.87 cr respectively; the two independent sources agree with one another to within INR 1.61 cr. Pending the borrower's reconciliation, the assessment is run on the lower independently evidenced turnover of INR 121.44 cr and drawing power is sized accordingly.\u201d Press 'Draft the risk note' on the flag to load this into the adjudication box, then edit it — the wording is yours to sign off.",
          citations: [
            "Flag XV-0418-01, evidence set",
            "CCB CAM template v4.2, risk narrative — revenue quality",
          ],
        },
        "Show me the months where deposits fell short": {
          text: "All twelve. The audited turnover implies INR 11.86 cr of sales a month; credits never exceed INR 12.18 cr and average INR 10.12 cr, with the widest shortfall in August 2024 at INR 2.74 cr and the narrowest in March 2025 at INR 0.32 cr. GST and bank credits track each other within INR 0.40 cr in every single month, so this is not a timing difference in one or two periods — it is a level difference across the year. The month table is on flag one under 'Show the twelve months'.",
          citations: [
            "Account Aggregator monthly credit summary, both accounts",
            "GSTR-3B monthly outward supplies, FY2024-25",
          ],
        },
        "What happens if I accept all three": {
          text: "Flag one stops blocking and all three carry into the draft: revenue quality, leverage and debt service, and business concentration. Accepting flag two restates total debt with the implied Crestline residual of about INR 1.85 cr and moves DSCR from 1.61 to 1.44, still above the 1.25 floor. Accepting flag three records a soft-cap breach at 38.4% against 35% with the OEM contract as mitigant. Accepted findings reach the rating rationale, so the CCB-4 first cut should be re-run before submission.",
          citations: [
            "Flags XV-0418-01 / 02 / 03",
            "CCB rating model, qualitative overlay — evidence quality",
          ],
        },
      },
    };
  if (pathname.startsWith("/audit"))
    return {
      scope: "Audit ledger — examiner walk-through",
      note: "Read-only. I answer strictly from the recorded ledger; where the record is silent, I say so rather than infer.",
      actions: [
        "Walk me through how the turnover figure was arrived at",
        "List every human override in this memo",
        "Who adjudicated the serious flag and why",
        "What is different about the Aurora record",
      ],
      answers: {
        "Walk me through how the turnover figure was arrived at": {
          text: "Three sources returned a figure for FY2025. The audited statement uploaded by Marcus Chen on 31 July at 07:14 shows INR 142.31 cr on page 14, line I. GSTN returned INR 119.83 cr across twelve GSTR-3B returns at 07:04, with no human handling. The Account Aggregator bundle under consent CONS-2026-0418-A returned customer credits of INR 121.44 cr at 07:09. The extraction engine mapped the declared figure into the spread at 07:21; rule XV-04 compared the three at 07:36 and raised a serious contradiction at 15.8% and 14.7% against a 5% tolerance. At 07:41 Elena Rossi accepted the finding rather than resolving it, recording that the two independent sources agree within INR 1.61 cr, and the memo was then run on evidenced turnover of INR 121.44 cr with the limit cut to INR 15.80 cr. Every step is in the trace panel under 'FY2025 turnover carried into the memo'.",
          citations: [
            "Ledger CAM-2026-0418, events NW-02, NW-03, NW-04, NW-05, NW-06, NW-07",
            "Trace nw-turnover, seven steps",
          ],
        },
        "List every human override in this memo": {
          text: "Two overrides are recorded on CAM-2026-0418, both by Elena Rossi, Credit Analyst, both with the original value retained. At 08:01 the recommended Cash Credit was overridden from INR 18.50 cr to INR 15.80 cr, reason: drawing power at 20% of evidenced turnover of INR 121.44 cr supports INR 15.80 cr. At 08:03 the internal rating was held at CCB-4 (watch) against a CCB-3 model score, reason: policy 6.3 requires a one-notch downgrade wherever a serious finding is accepted rather than resolved, and the restated DSCR is 1.44x. Separately, one human edit is recorded at 07:58 on Risk Assessment. Nothing else in this memo was changed by hand. Aurora's CAM-2026-0402 has no overrides at all — one edit on Banking Conduct and nothing more.",
          citations: ["Ledger CAM-2026-0418, events NW-11, NW-12, NW-13", "Ledger CAM-2026-0402, event AU-05"],
        },
        "Who adjudicated the serious flag and why": {
          text: "Elena Rossi, Credit Analyst, at 07:41 on 31 July 2026. She accepted XV-0418-01 as a genuine risk rather than resolving it, and her recorded reasoning is verbatim in the ledger: both independent sources agree within INR 1.61 cr and the shortfall is present in all twelve months, so it is a level difference and not a timing effect; the assessment is run on evidenced turnover of INR 121.44 cr with drawing power sized at INR 15.80 cr pending the borrower's reconciliation. That adjudication is what unblocked submission, and the finding carried forward into the memo rather than disappearing.",
          citations: ["Ledger CAM-2026-0418, event NW-07", "Flag XV-0418-01, adjudication record"],
        },
        "What is different about the Aurora record": {
          text: "Aurora Foods is the clean run. All five sources returned complete on 9 June 2026 with no fallback upload, declared turnover of INR 88.15 cr agreed with GST to within 1.2% and with bank credits to within 1.9%, and all 22 cross-verification rules passed with a single informational note on seasonality. The rating model returned CCB-2 with no qualitative overlay, and the analyst accepted it unchanged. The only human change in the whole memo is a two-sentence addition to Banking Conduct explaining the festive-season utilisation peak. The committee sanctioned it on 12 June 2026 and the memo was sealed read-only at 15:41.",
          citations: ["Ledger CAM-2026-0402, events AU-01 through AU-08"],
        },
      },
    };
  if (pathname.startsWith("/admin/policy"))
    return {
      scope: "Ratio policy — Continental Commercial Bank",
      note: "Draft policy v6.3 against published v6.2. I back-test any threshold you move against the 142 live exposures in the West Region book before you publish.",
      actions: [
        "Show me which current borrowers this threshold change would reclassify",
        "What happens to Northwind if I raise the current ratio floor to 1.30x",
        "Which ratios cannot be relaxed",
      ],
      answers: {
        "Show me which current borrowers this threshold change would reclassify": {
          text: "On the seeded book of eight, raising the current-ratio acceptable floor from 1.20x to 1.30x moves four borrowers. Northwind Manufacturing Ltd at 1.28x goes acceptable to marginal, Trident Industrial Packaging Pvt Ltd at 1.24x goes acceptable to marginal, Sahyadri Pharma Distributors Pvt Ltd at 1.21x goes acceptable to marginal, and Konkan Steel Traders Pvt Ltd at 1.09x is already adverse and stays there. Aurora Foods Ltd at 1.52x is untouched. Extrapolated across the 142 live West Region exposures on the same distribution, expect roughly 31 reclassifications, of which none become adverse — the marginal band absorbs them.",
          citations: [
            "Draft ratio policy v6.3 against published v6.2",
            "Seeded portfolio, current-ratio column, spreads as at 31 July 2026",
          ],
        },
        "What happens to Northwind if I raise the current ratio floor to 1.30x": {
          text: "Northwind's FY2025 current ratio is 1.28x, computed from current assets of INR 68.42 cr over current liabilities of INR 53.45 cr in the audited balance sheet. At a 1.30x floor it reclassifies from acceptable to marginal. That does not change the CCB-4 grade on its own — the financial-risk sub-score falls by two points to 61, still inside the CCB-4 band of 55 to 69 — but it adds a covenant line to the recommendation, and the July refresh already showed the ratio drifting to 1.19x, which would then be adverse rather than marginal.",
          citations: [
            "Northwind FY2025 audited balance sheet, spread line Current assets and Current liabilities",
            "CCB risk grid, CCB-4 band 55 to 69",
          ],
        },
        "Which ratios cannot be relaxed": {
          text: "Two carry hard floors that this screen will not let you go below. The current ratio has a board floor of 1.10x for manufacturing exposures, and DSCR has a policy floor of 1.20x for term exposures above INR 10 cr. Anything below either is an adverse classification requiring Chief Credit Officer sign-off, so relaxing the configured threshold under the floor would put the tenant out of policy rather than change the outcome.",
          citations: ["CCB Credit Risk Policy v6.2, clause 4.2 board floors"],
        },
      },
    };
  if (pathname.startsWith("/admin/templates"))
    return {
      scope: "CAM template designer — CCB house style",
      note: "Eight sections, formal and evidence-led tone, citations in line. I can propose structure but I never publish a template.",
      actions: [
        "Draft a section outline for a new Trade Finance annexure",
        "Which sections are mandatory under CCB policy",
        "What changes in Northwind's memo if I move Risk Assessment up",
      ],
      answers: {
        "Draft a section outline for a new Trade Finance annexure": {
          text: "I would place it after Facility Structure and before Risk Assessment, at about 320 words with every figure cited. Four headings: Trade cycle and instrument mix — LC and BG usage against sanctioned sublimits, evidenced from core banking; Counterparty and country exposure — buyer concentration and geography, evidenced from GST outward supplies; Devolvement and invocation history — 36 months from core banking conduct; and Documentary discipline — bill discounting overdues and negotiation delays. Three of the four draw on sources already connected, so nothing new is needed from the borrower.",
          citations: ["CCB CAM template v4.2 running order", "Connected sources: GST returns, CCB core and origination"],
        },
        "Which sections are mandatory under CCB policy": {
          text: "Clause 3.1 makes four sections mandatory in every CAM and this screen will not let you switch them off: Borrower and Group Profile, Financial Analysis, Risk Assessment, and Recommendation. The remaining four — Facility Structure, GST and Bureau Findings, Security and Covenants, and Conduct of Account — are at the tenant's discretion, though dropping GST and Bureau Findings would leave rule XV-04's output with nowhere to land in the memo.",
          citations: ["CCB Credit Risk Policy v6.2, clause 3.1"],
        },
        "What changes in Northwind's memo if I move Risk Assessment up": {
          text: "Only the running order and the citation numbering. The body text is generated per section from the same evidence set, so moving Risk Assessment above Financial Analysis puts the turnover contradiction and its adjudication on page one, before the reader has seen the spread it arises from. In-line citations renumber automatically; endnotes would regroup per section. My advice is to leave it after Financial Analysis so the contradiction reads as a conclusion rather than an assertion.",
          citations: ["Northwind memo CAM-2026-0418, sections 3 and 5"],
        },
      },
    };
  if (pathname.startsWith("/admin/connectors"))
    return {
      scope: "Connectors and consent — CCB tenant",
      note: "Eight sources, one degraded. I can tell you exactly what stops being provable if a source is switched off.",
      actions: [
        "What breaks if I switch off the bureau connector",
        "Why is adverse media degraded",
        "Is a 30-day consent window enough",
      ],
      answers: {
        "What breaks if I switch off the bureau connector": {
          text: "Three things, in order of seriousness. Cross-verification rule XV-11 loses one of its two corroborating sources for undisclosed lenders, which is how the Crestline Capital facility of INR 4.20 cr was found on Northwind. Existing obligations then come only from the borrower's own declaration, so the Conduct of Account section rests on internal conduct alone. And the rating model's conduct input degrades, which under CCB's evidence-quality overlay caps the achievable grade at CCB-3 regardless of financials. The bureau is marked as required in this tenant for that reason.",
          citations: ["Cross-verification rule XV-11", "CCB rating model, evidence-quality overlay"],
        },
        "Why is adverse media degraded": {
          text: "Refinitiv World-Check has been timing out on batch screening since 24 July under provider incident REF-88214. Success rate over 30 days is 71.5% against a 99% target and median latency is 28.4 seconds. On Northwind's run the entity screen returned hits but the batch timed out on two of the three directors. The appraisal continued with a partial marker rather than blocking, and the gap is recorded in Risk Assessment and in the audit ledger.",
          citations: ["Connector health, adverse media and sanctions", "Northwind acquisition run, 31 July 2026, 07:33 partial"],
        },
        "Is a 30-day consent window enough": {
          text: "For a first appraisal, yes — Northwind's median time from consent to submitted memo was nine days. It is thin for periodic review: the July refresh on Northwind found the bank-statement consent taken on 14 July had lapsed before the refresh ran, which is why the refreshed dossier shows bank figures as unavailable and falls back to two-source triangulation. A 60-day window with the reminder at 10 days would have avoided that without widening the purpose.",
          citations: ["Northwind consent record, taken 14 July 2026", "Northwind refresh, bank figures unavailable"],
        },
      },
    };
  if (pathname.startsWith("/admin/users"))
    return {
      scope: "Users and roles — CCB tenant",
      note: "Nine people, six roles. I check every role change against segregation of duties before it takes effect.",
      actions: [
        "Who can approve a memo above INR 25 crore",
        "Does anyone author and approve",
        "What would break if Elena became a Credit Manager",
      ],
      answers: {
        "Who can approve a memo above INR 25 crore": {
          text: "Two people. Anand Iyer as committee chair holds authority to INR 40 cr and has approved 27 memos. Ingrid Larsson as Chief Credit Officer is unlimited within board policy, with 12 approvals on record. Sofia Almeida stops at INR 25 cr and only for CCB-1 to CCB-3, so Northwind's INR 25.25 cr aggregate at CCB-4 is above her delegation and routes to Anand Iyer.",
          citations: ["Delegated authority matrix, CCB West Region", "Northwind CAM-2026-0418 routing"],
        },
        "Does anyone author and approve": {
          text: "Not today. No user holds a role that is both authoring and approving, and no approver on this tenant has authored memos. If you moved a Credit Analyst or Relationship Manager into Credit Manager or Chief Credit Officer, policy 2.4 would raise a watch conflict immediately — the person could not approve any memo they had authored, and the screen would flag them.",
          citations: ["CCB Credit Risk Policy 2.4, segregation of duties"],
        },
        "What would break if Elena became a Credit Manager": {
          text: "She has 34 authored memos on record, so the change raises a watch conflict rather than a clean move: she must not approve any memo she authored, which includes CAM-2026-0418 on Northwind, currently awaiting review. In practice CAM-2026-0418 would have to reroute to Anand Iyer, and her four open exceptions would need reassignment before her authoring rights lapse.",
          citations: ["User record, Elena Rossi — 34 authored", "Exception queue, owner filter — Elena Rossi"],
        },
      },
    };
  if (pathname.startsWith("/admin"))
    return {
      scope: "Admin — Continental Commercial Bank",
      note: "The control plane: ratio policy, CAM template, connectors and roles. I explain the consequence of a change; I never publish one.",
      actions: ["What changed in this tenant recently", "Which settings block submissions", "Who owns credit policy here"],
    };
  if (pathname.startsWith("/exceptions"))
    return {
      scope: "Exception queue — West Region",
      note: "Open cross-verification findings across every appraisal on the book, oldest and most severe first.",
      actions: [
        "Which open exceptions are blocking a submission",
        "What is the oldest thing sitting here",
        "Which of these are mine",
      ],
      answers: {
        "Which open exceptions are blocking a submission": {
          text: "Two. XV-0418-01 on Northwind Manufacturing Ltd, appraisal CAM-2026-0418 — declared turnover INR 142.31 cr against GST of INR 119.83 cr and bank credits of INR 121.44 cr, raised today and owned by Elena Rossi. And XV-0426-01 on Sahyadri Pharma Distributors Pvt Ltd, appraisal CAM-2026-0426 — GSTR-3B for January and February 2026 are not on the GSTN ledger, so two months of the turnover test cannot be evidenced; that one is 11 days old and sits with Devika Sundaram. The other two exceptions, both on Trident Industrial Packaging, are reportable but not blocking.",
          citations: [
            "Exception queue, 31 July 2026",
            "CCB CAM template v4.2, rule 4.1 — serious contradictions block submission",
          ],
        },
        "What is the oldest thing sitting here": {
          text: "XV-0426-01 on Sahyadri Pharma, raised 20 July 2026 and 11 days open. It is blocking and it is not moving: the missing GSTR-3B filings have to come from the borrower before the spread can be evidenced, so a chaser to Devika Sundaram is the practical next step.",
          citations: ["Exception queue, appraisal CAM-2026-0426"],
        },
        "Which of these are mine": {
          text: "Elena Rossi owns the three Northwind findings on CAM-2026-0418 and the bureau-overdue exception XV-0421-01 on Trident Industrial Packaging. Only the Northwind turnover flag blocks anything today.",
          citations: ["Exception queue, owner filter — Elena Rossi"],
        },
      },
    };
  if (pathname.includes("/identity"))
    return {
      scope: "Entity resolution — Northwind Manufacturing Ltd",
      note: "One high-confidence registry match, three directors, and one suggested group link awaiting your decision.",
      actions: [
        "Why did you link Northwind Logistics",
        "Check for other entities sharing these directors",
        "How sure are you this is the right Northwind",
        "What is missing before I confirm",
      ],
      answers: {
        "Why did you link Northwind Logistics": {
          text: "Northwind Logistics Ltd (CIN U63030MH2016PLC276104, PAN AABCL8890R) shares Rajesh Malhotra, DIN 01847362, who is Managing Director of the borrower and a Director of the logistics company since 3 February 2016. Both registered offices sit in the Pune district, and the logistics entity invoices the borrower under GSTIN 27AABCL8890R1Z4. I suggested the link; I did not add it — group perimeter stays yours to confirm. Its LEI is not obtained, which I have carried forward as an open item.",
          citations: [
            "MCA DIN master, DIN 01847362 — refreshed 29 July 2026",
            "MCA company master, CIN U63030MH2016PLC276104",
            "GSTN taxpayer search, 27AABCL8890R1Z4",
          ],
        },
        "Check for other entities sharing these directors": {
          text: "Sweeping all three DINs returns two companies outside the current perimeter: Malhotra Family Holdings Pvt Ltd (Rajesh and Anita Malhotra, investment holding, no bank facilities and no GST turnover) and Deccan Toolings Ltd (Sameer Deshpande, independent directorship only, no shareholding). Neither meets the group-perimeter test in the CAM v4.2 template, so I have left both out.",
          citations: [
            "MCA DIN master, DINs 01847362 / 01847388 / 02911574",
            "CCB CAM template v4.2, group perimeter rule 3.2",
          ],
        },
        "How sure are you this is the right Northwind": {
          text: "High confidence. The PAN supplied at intake, AABCN4521Q, maps to exactly one company, CIN U27310MH2009PLC198435, and the GSTIN state code and principal place of business agree with the registered office in Chakan, Pune. A near-duplicate exists — Northwind Manufacturing Private Ltd, CIN U28999MH2014PTC258771 — but it holds a different PAN, no common directors, and a GST turnover band of INR 5–10 cr against the declared FY25 turnover of INR 84.60 cr. I will not pick between them for you; the disambiguation panel is one click away.",
          citations: [
            "Income Tax PAN verification, AABCN4521Q",
            "MCA company master, CIN U27310MH2009PLC198435",
            "GSTN taxpayer search, 27AABCN4521Q1ZP",
          ],
        },
        "What is missing before I confirm": {
          text: "Two things. The suggested link to Northwind Logistics Ltd is still pending your decision, and that entity has no LEI on the LEIL registry. Separately, the borrower's own LEI 894500XYZ7NORTHWIND12 expires 31 March 2027, inside the proposed facility tenor, so renewal should become a sanction condition.",
          citations: [
            "LEIL registry lookup — 30 July 2026",
            "Intake note, Marcus Chen, Pune Corporate Branch",
          ],
        },
      },
    };
  if (pathname.includes("/consent"))
    return {
      scope: "Consent journey — Northwind Manufacturing Ltd",
      note: "Plain language for the borrower: what is being shared, with whom, for how long, and how to stop it.",
      actions: [
        "What am I actually agreeing to",
        "Can the bank take money from my account",
        "What happens if I decline",
        "How do I withdraw this later",
      ],
      answers: {
        "What am I actually agreeing to": {
          text: "You are letting Continental Commercial Bank read the transactions and balances on two accounts — Meridian Bank current account ending 4471 and Horizon Bank cash credit account ending 2205 — for 01 April 2025 to 31 March 2026. It is read-only, it is fetched once, and it is used only to assess this limit enhancement.",
          citations: ["Consent artefact CONS-2026-0418-A, purpose code 103", "Appraisal CAM-2026-0418"],
        },
        "Can the bank take money from my account": {
          text: "No. This permission carries no payment instruction and no login credentials. It lets your bank see statements; it cannot move money, change a mandate or open anything new.",
          citations: ["Account Aggregator consent template, data-access scope"],
        },
        "What happens if I decline": {
          text: "Nothing is fetched from either bank. Your appraisal continues, but you will be asked to send bank statements for the same window yourself, and your analyst records them as supplied by you rather than fetched under consent. It usually adds a few days.",
          citations: ["CCB data policy, CAM v4.2 section 2.4 — fallback provenance"],
        },
        "How do I withdraw this later": {
          text: "From your Account Aggregator app, or by telling Marcus Chen at the Pune Corporate Branch. Withdrawing stops any further access immediately. Statements already shared for this appraisal stay on the file, because the credit decision has to remain reconstructable.",
          citations: ["Consent artefact CONS-2026-0418-A, revocation clause", "CCB retention schedule"],
        },
      },
    };
  if (pathname.includes("/upload"))
    return {
      scope: "Manual upload fallback",
      note: "Documents supplied here are marked provenance 'fallback', not 'consent', everywhere they are used.",
      actions: [
        "Check this upload matches the borrower on file",
        "What do I still need to upload",
        "Does fallback data weaken the memo",
      ],
      answers: {
        "Check this upload matches the borrower on file": {
          text: "On the statement supplied for account 4471 the account holder reads 'Northwind Manufacturing Ltd', the PAN on the header is AABCN4521Q and the IFSC is MERI0000318 — all three agree with the confirmed entity. The period runs 01 April 2025 to 31 March 2026 with no missing months and no page gaps in the pagination.",
          citations: [
            "Meridian_Bank_4471_Apr2025-Mar2026.pdf, pages 1 and 148",
            "Confirmed entity, CIN U27310MH2009PLC198435",
          ],
        },
        "What do I still need to upload": {
          text: "Only the Horizon Bank cash credit statement for account 2205 over the same window. GST, bureau, registry, charges, LEI and three years of audited financials with ITR acknowledgements are already in.",
          citations: ["Acquisition console, appraisal CAM-2026-0418"],
        },
        "Does fallback data weaken the memo": {
          text: "It does not stop the spread, but assurance is lower: a supplied PDF is not verified at source. The figure trail records provenance 'fallback' and the cross-verification section notes it, which is what the examiner walk-through looks for.",
          citations: ["CCB CAM template v4.2, evidence assurance grades"],
        },
      },
    };
  if (pathname.includes("/data"))
    return {
      scope: "Data acquisition — Northwind Manufacturing Ltd",
      note: "Seven permitted sources. Bank data waits on borrower consent; adverse media returned partial after one feed timed out.",
      actions: [
        "What is still missing before I can spread this",
        "Explain the CERSAI charge",
        "Why is adverse media only partial",
        "How fresh is this evidence set",
      ],
      answers: {
        "What is still missing before I can spread this": {
          text: "One blocking gap: bank-account data for Meridian 4471 and Horizon 2205 over 01 April 2025 to 31 March 2026, which is still awaiting the borrower's Account Aggregator consent. Without it the bank-credits versus declared-turnover line cannot be run. Adverse media is partial because one feed timed out — non-blocking, but retry it before submission. Everything else is received: GST returns, CIBIL Commercial, MCA and CERSAI, LEI, and three years of audited financials with ITR.",
          citations: [
            "Acquisition console, appraisal CAM-2026-0418 — 31 July 2026",
            "CCB CAM template v4.2, completeness rule 2.1",
          ],
        },
        "Explain the CERSAI charge": {
          text: "One subsisting charge, ID 100482913, in favour of Continental Commercial Bank for INR 12.20 cr, created 30 August 2025 over stock and book debts — that is our own existing Cash Credit. One older charge, ID 100311874, held by Horizon Bank for INR 4.50 cr from November 2021, was satisfied on 18 January 2024. No other lender holds a subsisting charge, so the proposed enhancement to INR 18.50 cr needs a modification of our existing charge rather than a fresh first charge.",
          citations: [
            "CERSAI charge register, CIN U27310MH2009PLC198435",
            "MCA index of charges — updated 24 July 2026",
          ],
        },
        "Why is adverse media only partial": {
          text: "Two of three feeds returned clean — 412 documents on national press, zero hits on sanctions and watchlists for the entity, the group and the three DINs. The regional-language aggregator timed out after 30 seconds and scanned nothing, so the screen is incomplete rather than negative. Retry is on the row; the run so far shows only routine trade-press coverage of a new OEM order win.",
          citations: ["Screening run SCR-2026-118842 — 30 July 2026, 07:16"],
        },
        "How fresh is this evidence set": {
          text: "Registry, charges and LEI were pulled 30 July 2026 at 07:10, GST at 07:12 and the bureau report at 07:14, all inside the 30-day freshness rule. The audited financials and ITR were ingested from Marcus Chen's upload on 28 July 2026. Bank data has no timestamp yet because nothing has been fetched.",
          citations: ["Acquisition console provenance log", "CCB data policy, CAM v4.2 section 2.2"],
        },
      },
    };
  if (pathname === "/")
    return {
      scope: "Credit Workbench",
      note: "I can see your four in-flight appraisals and the two open Northwind discrepancies.",
      actions: [
        "Start an appraisal",
        "Summarise what needs my attention",
        "What changed since Friday",
        "Draft the Northwind discrepancy note",
      ],
    };
  if (pathname.startsWith("/borrowers/"))
    return {
      scope: "Borrower dossier — Northwind Manufacturing Ltd",
      note: "Four memos since 2023, rated CCB-4, next review 31 August 2026. A refresh against v4 is available; the bank-data consent behind it has expired.",
      actions: [
        "What deteriorated since the last review",
        "Draft an early-warning note for the current-ratio breach",
        "Why are the bank figures a month old",
      ],
      answers: {
        "What deteriorated since the last review": {
          text: "Three things moved against you and one held. The current ratio slipped from 1.28x to 1.19x on the June 2026 provisionals, which is below CCB's 1.20x minimum and the first breach since the 2023 sanction — creditors stretched to INR 31.60 cr while receivables stayed flat. Quarterly turnover fell to INR 31.14 cr against an FY2025 run rate of INR 35.58 cr, a 12.5% softening, with June at INR 9.02 cr the weakest month in eighteen. The Crestline Financial Services obligation raised as flag XV-0418-02 grew from INR 4,37,500 to INR 6,12,000 a month from the April instalment, INR 73.44 lakh a year, still unregistered. DSCR eased from 1.61x to 1.54x, inside policy. Only conduct held: CMR-4 unchanged, no overdues in 27 months, all returns filed on time.",
          citations: [
            "Provisional balance sheet, quarter ended 30 June 2026",
            "GSTR-3B April, May and June 2026",
            "Meridian Bank 4471, April to June 2026",
            "TransUnion CIBIL Commercial, pulled 31 July 2026",
          ],
        },
        "Draft an early-warning note for the current-ratio breach": {
          text: "Suggested note: \u201cEarly warning — liquidity. Northwind Manufacturing Ltd's current ratio has fallen to 1.19x on the provisional balance sheet for the quarter ended 30 June 2026, against 1.28x at the last appraisal and CCB's 1.20x minimum. Current assets of INR 62.84 cr cover current liabilities of INR 52.81 cr; the movement is on the liability side, with creditors at INR 31.60 cr against INR 26.90 cr, while receivables were flat at INR 29.42 cr. Coming alongside a 12.5% fall in quarterly turnover and a non-bank obligation that has grown to INR 73.44 lakh a year, this is treated as a liquidity warning rather than a timing effect. Recommended: creditor ageing and a stock statement for the September quarter, and monthly monitoring of the ratio until it is back above 1.20x.\u201d Every figure there is already evidenced in the refresh.",
          citations: [
            "Provisional balance sheet, 30 June 2026 (branch-supplied, unaudited)",
            "CCB ratio policy — current ratio minimum 1.20x",
            "Refresh changes CHG-01, CHG-02, CHG-03",
          ],
        },
        "Why are the bank figures a month old": {
          text: "Because consent CONS-2026-0418-A expired on 24 July 2026. It ran for thirty days from 24 June under the borrower's Account Aggregator authorisation, signed by Rajesh Malhotra, and covered the Meridian Bank current account 4471 and OD account 8802. Everything else in the refresh is current: GST direct from GSTN, the bureau pull from 31 July, the registry and charge index, and the branch-supplied provisionals. The Crestline change is the one item resting on the expired window, so it reads to 30 June only. Request fresh consent from the banner and the bank figures advance to 30 July.",
          citations: [
            "Consent record CONS-2026-0418-A",
            "Account Aggregator authorisation, 30-day window",
          ],
        },
      },
    };
  if (pathname === "/memos")
    return {
      scope: "Memo library — West Region",
      note: "Four borrowers on the book, thirteen memos on record. One is with the committee, one is due for review inside sixty days.",
      actions: [
        "Which borrowers are due for review",
        "Where is each borrower right now",
        "Which borrower has deteriorated",
      ],
      answers: {
        "Which borrowers are due for review": {
          text: "One inside sixty days: Northwind Manufacturing Ltd on 31 August 2026, rated CCB-4, and its dossier already shows a current-ratio breach on the June quarter. Trident Industrial Packaging Ltd follows on 30 September 2026 but its memo is still in draft, so the review will be met by the sanction itself. Aurora Foods Ltd is not due until 30 June 2027. Sahyadri Pharma Distributors is a first sanction with no review date set.",
          citations: ["Memo library review schedule", "Northwind dossier refresh, 31 July 2026"],
        },
        "Where is each borrower right now": {
          text: "Northwind Manufacturing Ltd, CAM-2026-0418, is in committee review at CCB-4 with three open cross-verification findings. Aurora Foods Ltd, CAM-2026-0402, was completed on 12 June 2026 at CCB-2 with no findings. Trident Industrial Packaging Ltd, CAM-2026-0421, is drafting — five of eight sections written on a INR 14.30 cr term loan. Sahyadri Pharma Distributors, CAM-2026-0426, is still gathering data and is waiting on the borrower's bank consent.",
          citations: ["Appraisal register", "Memo library, 31 July 2026"],
        },
        "Which borrower has deteriorated": {
          text: "Northwind, and only Northwind. Its refresh shows the current ratio through the 1.20x floor at 1.19x, quarterly turnover down 12.5%, and the undisclosed Crestline obligation up to INR 73.44 lakh a year. Aurora Foods improved at its last renewal — turnover INR 88.15 cr, current ratio 1.61x, DSCR 2.24x. The other two have no prior memo to deteriorate against.",
          citations: ["Northwind dossier refresh CHG-01 to CHG-03", "Aurora Foods CAM-2026-0402"],
        },
      },
    };
  if (pathname.includes("/draft"))
    return {
      scope: "CAM draft — Northwind Manufacturing Ltd",
      note: "Eight sections in CCB template v4.2, drafted from the resolved evidence. Every quantitative claim is cited; anything you change is marked as yours.",
      actions: [
        "Tighten this section",
        "Justify the CCB-4 rating",
        "Rewrite the risk narrative to reflect flag one",
        "Which claims in this memo are uncited",
      ],
      answers: {
        "Tighten this section": {
          text: "The risk section runs to 214 words against the template's 150-word guide, mostly because the mitigants are listed twice. A tighter version keeps all seven citations and reads: financial score CCB-3, one-notch overlay for the open serious finding, revenue quality as the binding risk with the supportable limit at INR 15.80 cr on evidenced turnover, understated leverage from the Crestline obligation taking DSCR to 1.44x, then mitigants in one sentence. Press 'Regenerate with copilot' on the section to load it — it lands marked as copilot text accepted by you, and you can edit it before it counts as yours.",
          citations: [
            "CCB CAM template v4.2, section 7 length guide",
            "Flags XV-0418-01 and XV-0418-02",
            "Spread ratio grid — DSCR restated 1.44x",
          ],
        },
        "Justify the CCB-4 rating": {
          text: "The financial score alone supports CCB-3: turnover CAGR of 21.5% to INR 142.31 cr, TOL/TNW 2.34x against a 3.00x ceiling, DSCR 1.61x against a 1.25x floor, current ratio 1.28x against a 1.20x floor, and a clean bureau record at CMR-4 with no overdues in 24 months. The evidence-quality overlay in rating model v3.1 applies a one-notch downgrade wherever a serious cross-verification finding is open or accepted, and XV-0418-01 is exactly that — a turnover gap of INR 22.48 cr to GST and INR 20.87 cr to bank credits, present in all twelve months. That is what takes it to CCB-4 (watch). Restating for the undisclosed Crestline obligation would not on its own move it further; it costs 0.17x of DSCR and 0.06x of TOL/TNW.",
          citations: [
            "CCB rating model v3.1, qualitative overlay — evidence quality",
            "Spread ratio grid FY2025",
            "Flag XV-0418-01 evidence set",
            "TransUnion CIBIL Commercial, CMR-4, pulled 29 July 2026",
          ],
        },
        "Rewrite the risk narrative to reflect flag one": {
          text: "Suggested wording: \u201cThe dominant risk on this proposal is revenue quality. Declared FY2025 turnover of INR 142.31 cr is contradicted by GST outward supplies of INR 119.83 cr and customer credits of INR 121.44 cr into the two consented accounts, sources that agree with one another to within INR 1.61 cr and diverge from the declaration in every one of the twelve months. Drawing power on the requested INR 18.50 cr Cash Credit is sized off that contested turnover; on evidenced turnover the supportable limit is INR 15.80 cr. Sanction is therefore recommended at the lower limit pending a written reconciliation.\u201d Every figure in that paragraph is already cited in section 6, so the citations carry over unchanged.",
          citations: [
            "Flag XV-0418-01",
            "GSTR-3B aggregate FY2024-25 — INR 119.83 cr",
            "Account Aggregator credit summary — INR 121.44 cr",
            "Nayak method assessment, 25% of projected turnover",
          ],
        },
        "Which claims in this memo are uncited": {
          text: "None of the quantitative ones. Every number in the eight sections resolves to a citation: the registry facts to MCA and GSTN, the conduct figures to the bureau and the consented statements, the financials and ratios to the spread and its underlying documents, and the three findings to the discrepancy board. Three qualitative statements carry no citation by design — the assessment of mitigants in section 7, the recommendation itself in section 8, and the sentence attributing the call to the analyst. Those are judgement, not evidence, and the template intends them to be unsourced.",
          citations: ["CCB CAM template v4.2, citation policy 2.4"],
        },
      },
    };
  if (pathname.includes("/rating"))
    return {
      scope: "Rating and recommendation — Northwind Manufacturing Ltd",
      note: "CCB-4 is the model's first cut. The rating that leaves this screen is yours, and any move from the first cut is recorded with a reason.",
      actions: [
        "What would move this to CCB-3 or CCB-5",
        "How was the first cut produced",
        "Is the reduced limit defensible",
      ],
      answers: {
        "What would move this to CCB-3 or CCB-5": {
          text: "To CCB-3, two things have to happen: the borrower reconciles FY2025 turnover to GST and bank credits with documentation the committee accepts, and the Crestline Financial Services obligation is disclosed and registered. That lifts the evidence-quality overlay, and the financial score of CCB-3 stands on its own. To CCB-5, either the reconciliation fails or INR 121.44 cr is taken as the true revenue base — on that base EBITDA margin falls to about 12.8% of a much smaller number, DSCR restates to 1.44x with the Crestline obligation, and the non-disclosure becomes a management-quality mark rather than an oversight. A second consecutive year of a turnover gap would make CCB-5 the floor rather than the risk case.",
          citations: [
            "CCB rating model v3.1, financial score and qualitative overlay",
            "Flags XV-0418-01 and XV-0418-02",
            "Spread ratio grid — DSCR 1.61x, restated 1.44x",
          ],
        },
        "How was the first cut produced": {
          text: "Financial score from the three-year spread: growth, margin, leverage, coverage and liquidity, which maps to CCB-3. Behavioural score from conduct — 91.4% average CC utilisation, no cheque returns, CMR-4 with no overdues in 24 months — which is neutral. Then the evidence-quality overlay, one notch down for an open serious finding. CCB-4, watch. I produced the first cut; I have not confirmed it, and the model cannot. Confirmation is attributed to you.",
          citations: [
            "CCB rating model v3.1",
            "Spread FY2023 to FY2025",
            "Meridian Bank 4471 conduct summary under consent",
          ],
        },
        "Is the reduced limit defensible": {
          text: "Yes, and the arithmetic is short. Nayak assessment at 25% of turnover gives INR 18.50 cr on declared turnover of INR 142.31 cr and INR 15.80 cr on the independently evidenced INR 121.44 cr. Recommending the lower figure keeps the bank inside the evidence rather than inside the declaration, and the balance of INR 2.70 cr is left available on a satisfactory reconciliation. It costs the borrower nothing if the declaration is correct.",
          citations: [
            "Nayak method, CCB working capital assessment policy",
            "Account Aggregator credit summary — INR 121.44 cr",
          ],
        },
      },
    };
  if (pathname.includes("/submission"))
    return {
      scope: "Submission and routing — Northwind Manufacturing Ltd",
      note: "The checklist reads the live state of this appraisal. The serious turnover finding must be adjudicated and the rating confirmed by a human before the memo can leave.",
      actions: [
        "Summarise this memo for the committee cover note",
        "What is still blocking submission",
        "Who sees this after I submit",
      ],
      answers: {
        "Summarise this memo for the committee cover note": {
          text: "Suggested cover note: \u201cNorthwind Manufacturing Ltd (CAM-2026-0418, Pune Corporate Branch) seeks enhancement of its Cash Credit limit from INR 12.20 cr to INR 18.50 cr with an LC/BG line of INR 6.75 cr. Turnover has compounded at 21.5% to INR 142.31 cr with PAT of INR 6.94 cr, and leverage and coverage remain inside policy at TOL/TNW 2.34x and DSCR 1.61x. Cross-verification found that declared FY2025 turnover is contradicted by GST filings of INR 119.83 cr and bank credits of INR 121.44 cr, and identified an undisclosed obligation of INR 52.50 lakh a year to Crestline Financial Services. The proposal is rated CCB-4 (watch) and is recommended at a reduced Cash Credit limit of INR 15.80 cr, sized on independently evidenced turnover, with the balance released on a satisfactory reconciliation and five sanction conditions.\u201d That is 128 words, which fits the committee papers' cover box.",
          citations: [
            "Memo sections 2, 4, 6, 7 and 8",
            "Flags XV-0418-01 and XV-0418-02",
            "CCB committee papers format, cover box 130-word limit",
          ],
        },
        "What is still blocking submission": {
          text: "Two hard checks, in this order. First, flag XV-0418-01 — the turnover contradiction — must carry a recorded adjudication; the rule is that a serious cross-verification finding cannot be passed to the committee undecided. Second, the rating must be confirmed by you on the rating panel: CCB-4 is currently the model's first cut, and an unconfirmed rating is not a rating. The advisory items — the two non-serious findings and how many sections you have rewritten — do not block; they simply travel with the memo as they stand.",
          citations: [
            "CCB CAM template v4.2, rule 4.1",
            "CCB credit policy, human confirmation of internal ratings",
          ],
        },
        "Who sees this after I submit": {
          text: "Sofia Almeida, Credit Manager for the West Region, first — review targeted 08 July 2026 under a two-working-day service level. From there it lists for the West Region Credit Committee, chaired by Anand Iyer, at the sitting on 14 July 2026; total exposure of INR 25.25 cr is inside that committee's INR 50 cr delegation, so it does not escalate. The memo also appears in the memo library at the moment of submission, with the full evidence pack, every citation and the override trail attached.",
          citations: [
            "CCB delegation of authority matrix, West Region",
            "Routing configuration, CAM-2026-0418",
          ],
        },
      },
    };
  if (pathname.includes("/cross-verification"))
    return {
      scope: "Cross-Verification",
      note: "Triangulating declared financials, GST filings, bank credits and bureau conduct.",
      actions: [
        "Explain the turnover gap",
        "Trace the undisclosed lender payment",
        "Rank discrepancies by credit impact",
      ],
    };
  if (pathname.includes("/spread"))
    return {
      scope: "Financial spread — Northwind Manufacturing Ltd",
      note: "Three audited years are spread and the CCB ratios are computed. One balance-sheet figure is waiting on your confirmation, and the GST turnover gap is parked for cross-verification.",
      actions: [
        "Trace this figure to source",
        "Explain why DSCR is 1.61",
        "Which ratios are close to breaching",
        "What is the low-confidence figure",
      ],
      answers: {
        "Trace this figure to source": {
          text: "FY2025 turnover of 142.31 cr comes from line I, 'Revenue from operations', on page 14 of Northwind_Manufacturing_Audited_FS_FY2025.pdf, where it reads 1,42,31,08,442 — uploaded by Marcus Chen on 28 July 2026 and carried as fallback provenance because it was supplied rather than pulled. FY2024 118.74 cr and FY2023 96.42 cr come from the FY2024 statement and its comparatives. PAT 6.94 cr is tied additionally to the ITR-6 acknowledgement for AY2025-26. Click any cell and the source panel lands on the page and line.",
          citations: [
            "Northwind_Manufacturing_Audited_FS_FY2025.pdf — page 14, line I",
            "Northwind_Manufacturing_Audited_FS_FY2024.pdf — pages 11 to 13",
            "ITR-6 acknowledgement 418277340290925, AY2025-26",
          ],
        },
        "Explain why DSCR is 1.61": {
          text: "Cash available for debt service is PAT 6.94 cr plus depreciation 4.28 cr plus finance costs 4.55 cr, so 15.77 cr. Debt service is finance costs 4.55 cr plus scheduled principal repayments of 5.24 cr on the Horizon Bank term loan, so 9.79 cr. That gives 1.61x against the CCB policy floor of 1.50. It was 1.72x in FY2024; the erosion is finance costs rising 21% on higher cash-credit utilisation while PAT grew 14%. The proposed enhancement is not yet loaded into the denominator.",
          citations: [
            "Audited FS FY2025 — page 14, finance costs and depreciation",
            "ITR-6 AY2025-26 — profit after tax 6,94,02,415",
            "CIBIL Commercial report 2026073000418 — section 4, scheduled repayments",
            "CCB credit policy manual, DSCR floor 1.50, effective 01 April 2026",
          ],
        },
        "Which ratios are close to breaching": {
          text: "Three to watch. Working-capital cycle at 87 days is already 12 days beyond the 75-day auto-components benchmark and has lengthened 16 days in three years. DSCR at 1.61x is 7% above its 1.50 floor and fell 0.11x in one year. Current ratio at 1.28x is 7% above its 1.20 floor and has fallen in each of the three years. TOL/TNW at 2.34x and interest coverage at 3.42x both have real headroom.",
          citations: [
            "CCB credit policy manual, sections 4.1 to 4.4",
            "CreditIQ spread, FY2023 to FY2025, appraisal CAM-2026-0418",
          ],
        },
        "What is the low-confidence figure": {
          text: "Current liabilities for FY2025, spread at 32.70 cr. Page 12 of the audited statement splits other current liabilities across two schedules, and the extracted total of 6.32 cr does not tie to schedule 11's 6.33 cr — a one-lakh difference that I will not silently absorb. It feeds the current ratio, so I have routed it for a human check rather than confirming it myself. Correcting it records the original extraction and your reason to the audit trail.",
          citations: [
            "Northwind_Manufacturing_Audited_FS_FY2025.pdf — page 12 and schedule 11",
            "CCB extraction policy: any figure below 0.90 extraction confidence is routed for maker check",
          ],
        },
        "Why do GST turnover and the financials differ": {
          text: "GSTR-3B outward supplies for FY2025 total 147.77 cr against 142.31 cr of declared revenue, a gap of 5.46 cr. Credits into the two consented accounts total 136.85 cr. The gap is consistent with scrap sales and inter-unit stock transfers being taxable but not revenue, though I have not tested that. The spread carries the audited figure unchanged; the reconciliation belongs to cross-verification.",
          citations: [
            "GSTR-3B FY2025 aggregate, GSTIN 27AABCN4521Q1ZP",
            "Account Aggregator bundle under consent CONS-2026-0418-A",
          ],
        },
      },
    };
  if (pathname.startsWith("/appraisals/new"))
    return {
      scope: "New appraisal intake",
      note: "Give me a name and one identifier and I will resolve the entity, its group and its people.",
      actions: [
        "Paste a sanction request and I will pull out the identifiers",
        "What is the minimum I need to start",
        "Has this borrower been appraised before",
      ],
      answers: {
        "Paste a sanction request and I will pull out the identifiers": {
          text: "Open the paste panel on the intake form. From Marcus Chen's request I lift the legal name Northwind Manufacturing Ltd, PAN AABCN4521Q, GSTIN 27AABCN4521Q1ZP, the enhancement from INR 12.20 cr to INR 18.50 cr, the LC/BG sub-limit of INR 6.75 cr and the stated purpose, then leave every field editable before you start.",
          citations: ["Email from Marcus Chen, Pune Corporate Branch — 30 July 2026"],
        },
        "What is the minimum I need to start": {
          text: "A legal name plus a PAN. GSTIN is optional but sharpens the state and address match, and the facility fields can be filled in later at the spread step.",
          citations: ["CCB intake policy, CAM v4.2 section 1.1"],
        },
        "Has this borrower been appraised before": {
          text: "Northwind Manufacturing Ltd holds an existing Cash Credit limit of INR 12.20 cr sanctioned 30 August 2025 and was last appraised in August 2025; appraisal CAM-2026-0418 is the enhancement now in progress.",
          citations: ["CCB borrower master, customer 27-PUN-004182"],
        },
      },
    };
  if (pathname.startsWith("/entities/") || pathname.startsWith("/people/"))
    return {
      scope: "Entity graph",
      note: "Registry identity, directorships and group relationships as they stand today.",
      actions: [
        "Summarise this record",
        "How does this connect to Northwind Manufacturing",
        "What is unresolved on this entity",
      ],
      answers: {
        "How does this connect to Northwind Manufacturing": {
          text: "Through Rajesh Malhotra, DIN 01847362: Managing Director of Northwind Manufacturing Ltd and a Director of Northwind Logistics Ltd since 3 February 2016. That single shared directorship is the basis of the suggested group link on appraisal CAM-2026-0418.",
          citations: ["MCA DIN master, DIN 01847362"],
        },
      },
    };
  if (pathname.startsWith("/appraisals"))
    return {
      scope: "Appraisal workspace",
      note: "I have this borrower's evidence set, spread and citation trail loaded.",
      actions: ["Summarise this step", "List unresolved items", "Show the evidence behind a figure"],
    };
  if (pathname.startsWith("/memos"))
    return {
      scope: "Memo Library",
      note: "23 memos issued this month across the West Region book.",
      actions: ["Find memos rated CCB-5 or worse", "Compare two memos", "Export a committee pack"],
    };
  if (pathname.startsWith("/audit"))
    return {
      scope: "Audit trail",
      note: "Every figure, override and reason is reconstructable for examiner walk-through.",
      actions: ["Reconstruct a decision", "Show all analyst overrides", "Prepare an examiner pack"],
    };
  return {
    scope: "Administration",
    note: "Control-plane settings shape how every memo in this bank is produced.",
    actions: ["Explain a policy threshold", "What changed in configuration", "Review role permissions"],
  };
}

export function CopilotRail({ onClose }: { onClose: () => void }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const ctx = useMemo(() => contextFor(pathname), [pathname]);
  const [draft, setDraft] = useState("");
  const [asked, setAsked] = useState<string | null>(null);
  const answer = asked ? ctx.answers?.[asked] : undefined;

  return (
    <aside className="hidden w-80 shrink-0 flex-col border-l border-border bg-surface xl:flex">
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Sparkles className="h-4 w-4 text-primary" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-semibold leading-tight">CreditIQ Copilot</p>
          <p className="truncate text-[11px] text-muted-foreground">Context: {ctx.scope}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close copilot"
          className="grid h-6 w-6 place-items-center rounded text-muted-foreground hover:bg-muted"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
        <div className="rounded border border-border bg-surface-muted p-3">
          <p className="text-[12.5px] leading-relaxed text-foreground">
            Good morning, {CURRENT_USER.name.split(" ")[0]}. {ctx.note}
          </p>
        </div>

        <p className="field-label">Starting actions</p>
        <div className="space-y-1.5">
          {ctx.actions.map((a) => (
            <button
              key={a}
              type="button"
              onClick={() => (ctx.answers?.[a] ? setAsked(a) : setDraft(a))}
              className="flex w-full items-center gap-2 rounded border border-border bg-surface px-2.5 py-2 text-left text-[12.5px] text-foreground transition-colors hover:border-primary/40 hover:bg-accent"
            >
              <FileSearch className="h-3.5 w-3.5 shrink-0 text-primary" />
              {a}
            </button>
          ))}
        </div>

        {asked && (
          <div className="rounded border border-border bg-surface p-3">
            <p className="text-[12px] font-medium text-foreground">{asked}</p>
            {answer ? (
              <>
                <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/90">{answer.text}</p>
                <p className="field-label mt-2.5">Cited from</p>
                <ul className="mt-1 space-y-1">
                  {answer.citations.map((c) => (
                    <li key={c} className="text-[11.5px] leading-snug text-muted-foreground">
                      · {c}
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="mt-2 text-[12.5px] text-muted-foreground">
                I need this step's evidence set before I can answer that.
              </p>
            )}
            <button
              type="button"
              onClick={() => setAsked(null)}
              className="mt-2.5 text-[11.5px] font-medium text-primary hover:underline"
            >
              Clear
            </button>
          </div>
        )}

        <div className="rounded border border-info/25 bg-info-soft p-3">
          <p className="field-label">Grounding</p>
          <p className="mt-1 text-[11.5px] leading-relaxed text-foreground/80">
            Answers cite the filing, statement or page they came from. The copilot never changes a
            figure or a rating; you do.
          </p>
        </div>
      </div>

      <div className="border-t border-border p-3">
        <div className="flex items-end gap-2 rounded border border-border bg-surface p-2 focus-within:ring-1 focus-within:ring-ring">
          <textarea
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Ask about this screen…"
            className="max-h-28 min-h-[2.5rem] w-full resize-none bg-transparent text-[12.5px] outline-none placeholder:text-muted-foreground"
          />
          <button
            type="button"
            aria-label="Send"
            className="grid h-7 w-7 shrink-0 place-items-center rounded bg-primary text-primary-foreground disabled:opacity-40"
            disabled={!draft.trim()}
          >
            <ArrowUp className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}