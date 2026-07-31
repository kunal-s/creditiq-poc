import { useRouterState } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Sparkles, X, ArrowUp, FileSearch } from "lucide-react";
import { CURRENT_USER } from "@/data/seed";

type Answer = { text: string; citations: string[] };
type Ctx = { scope: string; note: string; actions: string[]; answers?: Record<string, Answer> };

function contextFor(pathname: string): Ctx {
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