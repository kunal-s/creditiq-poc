import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight, ClipboardPaste, Sparkles, Wand2 } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { t } from "@/config/terminology";

export const Route = createFileRoute("/applications/new")({
  head: () => ({
    meta: [
      { title: `${t("page.newApplication.title")} — ${t("tenant.product.name")}` },
      {
        name: "description",
        content: `Begin an application with a borrower name, PAN and GSTIN. ${t("tenant.product.name")} resolves the legal entity, its group and its directors from there.`,
      },
    ],
  }),
  component: NewApplication,
});

const FACILITY_TYPES = [
  "Cash Credit enhancement with LC/BG sub-limit",
  "Cash Credit renewal",
  "Fresh working capital sanction",
  "Term Loan",
  "Term Loan with working capital",
];

const PAN_PATTERN = /[A-Z]{5}[0-9]{4}[A-Z]/;
const GSTIN_PATTERN = /[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]/;

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

function NewApplication() {
  const [borrower, setBorrower] = useState("");
  const [pan, setPan] = useState("");
  const [gstin, setGstin] = useState("");
  const [facility, setFacility] = useState(FACILITY_TYPES[0]);
  const [amount, setAmount] = useState("");
  const [purpose, setPurpose] = useState("");
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");

  const ready = borrower.trim().length > 2 && pan.trim().length >= 10;

  function extractFromPaste() {
    const panMatch = pasteText.toUpperCase().match(PAN_PATTERN);
    const gstinMatch = pasteText.toUpperCase().match(GSTIN_PATTERN);
    if (!panMatch && !gstinMatch) {
      toast("No identifiers found", {
        description:
          "Couldn't find a PAN or GSTIN pattern in the pasted text — enter them manually.",
      });
      return;
    }
    if (panMatch) setPan(panMatch[0]);
    if (gstinMatch) setGstin(gstinMatch[0]);
    setPasteOpen(false);
    toast.success("Identifiers extracted", {
      description: [panMatch && `PAN ${panMatch[0]}`, gstinMatch && `GSTIN ${gstinMatch[0]}`]
        .filter(Boolean)
        .join(" and "),
    });
  }

  function submit() {
    toast.success("Application recorded", {
      description:
        "Entity resolution and case creation begin once the intake pipeline is live for this instance.",
    });
  }

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow={t("page.newApplication.eyebrow")}
        title={t("page.newApplication.title")}
        purpose={`Start with a name and its identifiers; ${t("tenant.product.name")} does the rest.`}
        actions={
          <>
            <button
              type="button"
              onClick={() =>
                toast("Saved as draft", {
                  description: "Draft intake retained for this session only.",
                })
              }
              className="h-8 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              Save as draft
            </button>
            <button
              type="button"
              disabled={!ready}
              onClick={submit}
              className="flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-40"
            >
              Submit application <ArrowRight className="h-3.5 w-3.5" />
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
                  <Sparkles className="h-3.5 w-3.5 text-primary" /> Paste the RM's request and I
                  will pull out the identifiers
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
                    placeholder="Borrower's registered name"
                  />
                </Field>
              </div>
              <Field label="PAN" hint="Ten characters, as issued by the Income Tax Department.">
                <input
                  className={inputClass + " tabular uppercase"}
                  value={pan}
                  onChange={(e) => setPan(e.target.value.toUpperCase())}
                  placeholder="AAAAA9999A"
                  maxLength={10}
                />
              </Field>
              <Field label="GSTIN" hint="Optional. Improves the state and address match.">
                <input
                  className={inputClass + " tabular uppercase"}
                  value={gstin}
                  onChange={(e) => setGstin(e.target.value.toUpperCase())}
                  placeholder="27AAAAA9999A1ZP"
                  maxLength={15}
                />
              </Field>
            </div>
          </Panel>

          <Panel
            title="Proposed facility"
            subtitle="Indicative at intake; the spread and policy checks will firm it up."
          >
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
                  placeholder="0.00"
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
                    placeholder="Working capital purpose, in the RM's own words."
                  />
                </Field>
              </div>
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <div className="rounded border border-border bg-surface p-4 text-[12.5px] leading-relaxed text-muted-foreground">
            <p className="field-label">Intake record</p>
            <p className="mt-1.5">
              Account aggregator consent is requested at the data step, purpose-bound to this
              application.
            </p>
            <p className="mt-2">
              Looking for work already in progress? Open{" "}
              <Link to="/appraisals" className="font-medium text-primary hover:underline">
                {t("nav.myAppraisals")}
              </Link>
              .
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
