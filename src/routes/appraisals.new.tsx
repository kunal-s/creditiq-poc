import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, ClipboardPaste, Sparkles, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { DEMO_INTAKE, RECENT_BORROWERS, SANCTION_REQUEST_TEXT } from "@/data/identity";
import { CURRENT_USER } from "@/data/seed";

export const Route = createFileRoute("/appraisals/new")({
  head: () => ({
    meta: [
      { title: "Start a new appraisal — CreditIQ" },
      {
        name: "description",
        content:
          "Begin a credit appraisal with a borrower name, PAN and GSTIN. CreditIQ resolves the legal entity, its group and its directors from there.",
      },
      { property: "og:title", content: "Start a new appraisal — CreditIQ" },
      {
        property: "og:description",
        content: "Minimal input in, a resolved borrower out: name, PAN and GSTIN start the appraisal.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
    ],
  }),
  component: NewAppraisal,
});

const FACILITY_TYPES = [
  "Cash Credit enhancement with LC/BG sub-limit",
  "Cash Credit renewal",
  "Fresh working capital sanction",
  "Term Loan",
  "Term Loan with working capital",
];

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-muted-foreground">{hint}</span>}
    </label>
  );
}

const inputClass =
  "mt-1 h-9 w-full rounded border border-border bg-surface px-2.5 text-[13px] text-foreground outline-none placeholder:text-muted-foreground/70 focus:border-primary/60 focus:ring-1 focus:ring-ring";

function NewAppraisal() {
  const navigate = useNavigate();
  const [borrower, setBorrower] = useState("");
  const [pan, setPan] = useState("");
  const [gstin, setGstin] = useState("");
  const [facility, setFacility] = useState(FACILITY_TYPES[0]);
  const [amount, setAmount] = useState("");
  const [purpose, setPurpose] = useState("");
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");

  const ready = borrower.trim().length > 2 && pan.trim().length >= 10;

  function applyDemo() {
    setBorrower(DEMO_INTAKE.borrower);
    setPan(DEMO_INTAKE.pan);
    setGstin(DEMO_INTAKE.gstin);
    setFacility(DEMO_INTAKE.facilityType);
    setAmount(DEMO_INTAKE.amount);
    setPurpose(DEMO_INTAKE.purpose);
  }

  function extractFromPaste() {
    applyDemo();
    setPasteOpen(false);
    toast.success("Identifiers extracted", {
      description: "PAN AABCN4521Q and GSTIN 27AABCN4521Q1ZP lifted from the sanction request, with the limit and purpose.",
    });
  }

  function start() {
    toast.success("Appraisal CAM-2026-0418 opened", {
      description: "Resolving Northwind Manufacturing Ltd against MCA, GSTN and LEIL registries.",
    });
    navigate({ to: "/appraisals/$id/identity", params: { id: "CAM-2026-0418" } });
  }

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow="Appraisal"
        title="Start a new appraisal"
        purpose="Start with a name and its identifiers; CreditIQ does the rest."
        actions={
          <>
            <button
              type="button"
              onClick={() => toast("Saved as draft", { description: "Draft intake retained for 30 days under your workbench." })}
              className="h-8 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              Save as draft
            </button>
            <button
              type="button"
              disabled={!ready}
              onClick={start}
              className="flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            >
              Start appraisal <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </>
        }
      />

      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <Panel
            title="Borrower identifiers"
            subtitle="Name plus one identifier is enough. Everything else is resolved from the registries."
            action={
              <button
                type="button"
                onClick={() => setPasteOpen((v) => !v)}
                className="flex h-7 items-center gap-1.5 rounded border border-primary/40 bg-accent px-2.5 text-[12px] font-medium text-primary hover:bg-accent/70"
              >
                <ClipboardPaste className="h-3.5 w-3.5" /> Paste a sanction request
              </button>
            }
          >
            {pasteOpen && (
              <div className="border-b border-border bg-surface-muted px-4 py-3">
                <p className="flex items-center gap-1.5 text-[12.5px] font-medium">
                  <Sparkles className="h-3.5 w-3.5 text-primary" /> Paste the RM's request and I will pull
                  out the identifiers
                </p>
                <textarea
                  rows={5}
                  value={pasteText}
                  onChange={(e) => setPasteText(e.target.value)}
                  placeholder="Paste the email, sanction request or credit note here…"
                  className="mt-2 w-full resize-none rounded border border-border bg-surface p-2.5 text-[12.5px] outline-none focus:ring-1 focus:ring-ring"
                />
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPasteText(SANCTION_REQUEST_TEXT)}
                    className="h-7 rounded border border-border bg-surface px-2.5 text-[12px] text-foreground hover:bg-muted"
                  >
                    Use Marcus Chen's request
                  </button>
                  <button
                    type="button"
                    disabled={!pasteText.trim()}
                    onClick={extractFromPaste}
                    className="flex h-7 items-center gap-1.5 rounded bg-primary px-2.5 text-[12px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
                  >
                    <Wand2 className="h-3.5 w-3.5" /> Extract identifiers
                  </button>
                </div>
              </div>
            )}

            <div className="grid gap-4 px-4 py-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <Field label="Borrower legal name">
                  <input
                    className={inputClass}
                    value={borrower}
                    onChange={(e) => setBorrower(e.target.value)}
                    placeholder="Northwind Manufacturing Ltd"
                  />
                </Field>
              </div>
              <Field label="PAN" hint="Ten characters, as issued by the Income Tax Department.">
                <input
                  className={inputClass + " tabular uppercase"}
                  value={pan}
                  onChange={(e) => setPan(e.target.value.toUpperCase())}
                  placeholder="AABCN4521Q"
                  maxLength={10}
                />
              </Field>
              <Field label="GSTIN" hint="Optional. Improves the state and address match.">
                <input
                  className={inputClass + " tabular uppercase"}
                  value={gstin}
                  onChange={(e) => setGstin(e.target.value.toUpperCase())}
                  placeholder="27AABCN4521Q1ZP"
                  maxLength={15}
                />
              </Field>
            </div>
          </Panel>

          <Panel title="Proposed facility" subtitle="Indicative at intake; the spread and policy checks will firm it up.">
            <div className="grid gap-4 px-4 py-4 sm:grid-cols-2">
              <Field label="Facility type">
                <select
                  className={inputClass}
                  value={facility}
                  onChange={(e) => setFacility(e.target.value)}
                >
                  {FACILITY_TYPES.map((f) => (
                    <option key={f}>{f}</option>
                  ))}
                </select>
              </Field>
              <Field label="Proposed amount (INR cr)">
                <input
                  className={inputClass + " tabular"}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="18.50"
                  inputMode="decimal"
                />
              </Field>
              <div className="sm:col-span-2">
                <Field label="Purpose" hint="One or two lines in the RM's own words is enough.">
                  <textarea
                    rows={3}
                    className="mt-1 w-full resize-none rounded border border-border bg-surface p-2.5 text-[13px] outline-none focus:border-primary/60 focus:ring-1 focus:ring-ring"
                    value={purpose}
                    onChange={(e) => setPurpose(e.target.value)}
                    placeholder="Working capital for a new OEM order book."
                  />
                </Field>
              </div>
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Recent borrowers" subtitle="Shortcut to an entity this desk has already resolved.">
            <ul className="divide-y divide-border">
              {RECENT_BORROWERS.map((b) => (
                <li key={b.name} className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() =>
                      b.prefill
                        ? applyDemo()
                        : toast("Identifiers loaded", { description: `${b.name} pre-filled from the borrower master.` })
                    }
                    className="block w-full text-left"
                  >
                    <span className="text-[13px] font-medium text-foreground hover:text-primary">{b.name}</span>
                    <span className="mt-0.5 block text-[11px] text-muted-foreground tabular">
                      PAN {b.pan} · GSTIN {b.gstin}
                    </span>
                    <span className="mt-0.5 block text-[11.5px] text-muted-foreground">{b.context}</span>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>

          <div className="rounded border border-border bg-surface p-4 text-[12.5px] leading-relaxed text-muted-foreground">
            <p className="field-label">Intake record</p>
            <p className="mt-1.5">
              Raised by Marcus Chen, Relationship Manager, Pune Corporate Branch. Assigned to{" "}
              {CURRENT_USER.name}, {CURRENT_USER.role}. Template: Continental Commercial Bank CAM v4.2
              (West Region). Account aggregator consent is requested at the data step, purpose-bound to
              this appraisal.
            </p>
            <p className="mt-2">
              Looking for work already in progress? Open{" "}
              <Link to="/appraisals" className="font-medium text-primary hover:underline">
                My Appraisals
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
