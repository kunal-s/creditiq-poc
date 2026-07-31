import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import {
  ArrowRight,
  ChevronDown,
  CircleAlert,
  FileUp,
  RefreshCw,
  Send,
  ShieldCheck,
  Sparkles,
  Terminal,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { ConfidenceChip, Panel, SourceChip } from "@/components/identity/chips";
import { getAppraisal } from "@/data/seed";
import {
  CONSENT_ACCOUNTS,
  CONSENT_WINDOW,
  SOURCES,
  STATUS_LABEL,
  STATUS_TONE,
  bankRowFor,
  setAcqState,
  useAcqState,
  type AcqSource,
} from "@/data/acquisition";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/$id/data")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Data acquisition — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "Gather every permitted source for the confirmed borrower — GST, bureau, registry, LEI, screening, bank data under consent and uploaded financials — with provenance, freshness and confidence on each row.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "website" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: DataAcquisitionConsole,
});

function StatusChip({ status, label }: { status: AcqSource["status"]; label?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
        STATUS_TONE[status],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {label ?? STATUS_LABEL[status]}
    </span>
  );
}

function DataAcquisitionConsole() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();

  const acq = useAcqState();
  const [open, setOpen] = useState<string | null>("gst");
  const [raw, setRaw] = useState<string | null>(null);

  const rows: AcqSource[] = SOURCES.map((s) => {
    if (s.key === "bank") return { ...s, ...bankRowFor(acq) };
    if (s.key === "media" && acq.mediaRetried)
      return {
        ...s,
        status: "received" as const,
        confidence: "high" as const,
        note: undefined,
        freshness: "Re-run 31 July 2026, 07:33 — all three feeds returned",
        findings: [
          "All three feeds returned on retry. No material hits on the borrower, the group or the three directors.",
          "Two routine trade-press mentions of a new OEM order win; nothing credit-relevant.",
        ],
      };
    return s;
  });

  const ready = rows.filter((r) => r.status === "received").length;
  const pending = rows.length - ready;
  const partial = rows.filter((r) => r.status === "partial").length;

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Data`}
        title="Data acquisition console"
        purpose="Every permitted source for the confirmed borrower, pulled under consent where the law requires it, with provenance and freshness held against each row."
        actions={
          <>
            <Link
              to="/appraisals/$id/upload"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <FileUp className="h-3.5 w-3.5" /> Upload a document
            </Link>
            {acq.bank === "consented" || acq.bank === "fallback" ? (
              <Link
                to="/appraisals/$id/spread"
                params={{ id: a.id }}
                className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
              >
                Continue to spread <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : (
              <Link
                to="/appraisals/$id/consent"
                params={{ id: a.id }}
                onClick={() => {
                  if (acq.bank === "awaiting") setAcqState({ bank: "requested" });
                  toast("Consent request sent", {
                    description:
                      "Account Aggregator request CONS-2026-0418-A delivered to the authorised signatory for accounts 4471 and 2205.",
                  });
                }}
                className="flex h-9 items-center gap-1.5 rounded bg-primary px-3.5 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
              >
                <Send className="h-3.5 w-3.5" /> Send consent request for bank data
              </Link>
            )}
          </>
        }
      />

      <div className="grid gap-4 px-6 py-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          <Panel
            title="Source board"
            subtitle={`${rows.length} permitted sources for ${a.borrower} · PAN ${a.pan} · GSTIN ${a.gstin}`}
          >
            <ul className="divide-y divide-border">
              {rows.map((s) => {
                const expanded = open === s.key;
                return (
                  <li key={s.key}>
                    <div className="grid grid-cols-[minmax(0,1.5fr)_minmax(0,1.1fr)_auto] items-start gap-x-4 gap-y-1.5 px-4 py-3">
                      <div className="min-w-0">
                        <button
                          type="button"
                          onClick={() => setOpen(expanded ? null : s.key)}
                          className="flex items-center gap-1.5 text-left text-[13px] font-medium text-foreground hover:text-primary"
                        >
                          <ChevronDown
                            className={cn(
                              "h-3.5 w-3.5 text-muted-foreground transition-transform",
                              expanded && "rotate-180",
                            )}
                          />
                          {s.name}
                        </button>
                        <p className="mt-0.5 pl-5 text-[11.5px] text-muted-foreground">
                          {s.category} · {s.connector}
                        </p>
                        <p className="mt-0.5 pl-5 text-[11.5px] text-muted-foreground">{s.coverage}</p>
                      </div>

                      <div className="min-w-0 text-[11.5px] text-muted-foreground">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <SourceChip source={s.provenance} />
                          <ConfidenceChip level={s.confidence} />
                        </div>
                        <p className="mt-1">{s.freshness}</p>
                      </div>

                      <div className="flex flex-col items-end gap-1.5">
                        <StatusChip status={s.status} label={s.note ? s.note.split(" — ")[0] : undefined} />
                        {s.key === "bank" ? (
                          <Link
                            to="/appraisals/$id/consent"
                            params={{ id: a.id }}
                            className="text-[11.5px] font-medium text-primary hover:underline"
                          >
                            Consent journey
                          </Link>
                        ) : (
                          <Link
                            to="/appraisals/$id/spread"
                            params={{ id: a.id }}
                            hash={s.downstream.anchor}
                            className="text-right text-[11.5px] font-medium text-primary hover:underline"
                          >
                            {s.downstream.label}
                          </Link>
                        )}
                      </div>
                    </div>

                    {s.note && (
                      <div className="mx-4 mb-3 flex flex-wrap items-center gap-2 rounded border border-flag/35 bg-flag-soft px-3 py-2 text-[12px] text-flag-foreground">
                        <CircleAlert className="h-3.5 w-3.5 shrink-0" />
                        <span className="min-w-0 flex-1">{s.note}</span>
                        {s.key === "media" && (
                          <button
                            type="button"
                            onClick={() => {
                              setAcqState({ mediaRetried: true });
                              toast("Adverse media re-run complete", {
                                description:
                                  "Regional-language aggregator returned on retry — 187 documents scanned, no material hits.",
                              });
                            }}
                            className="flex h-7 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[11.5px] font-medium text-foreground hover:bg-muted"
                          >
                            <RefreshCw className="h-3 w-3" /> Retry source
                          </button>
                        )}
                        {s.key === "bank" && acq.bank === "declined" && (
                          <Link
                            to="/appraisals/$id/upload"
                            params={{ id: a.id }}
                            className="flex h-7 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[11.5px] font-medium text-foreground hover:bg-muted"
                          >
                            <FileUp className="h-3 w-3" /> Use manual fallback
                          </Link>
                        )}
                      </div>
                    )}

                    {expanded && (
                      <div className="border-t border-border bg-surface-muted px-4 py-3 pl-9">
                        <ul className="space-y-1 text-[12.5px] text-foreground">
                          {s.findings.map((f) => (
                            <li key={f} className="flex gap-2">
                              <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-muted-foreground" />
                              <span>{f}</span>
                            </li>
                          ))}
                        </ul>
                        <button
                          type="button"
                          onClick={() => setRaw(raw === s.key ? null : s.key)}
                          className="mt-2.5 flex h-7 items-center gap-1.5 rounded border border-border bg-surface px-2.5 text-[11.5px] font-medium text-foreground hover:bg-muted"
                        >
                          <Terminal className="h-3 w-3" />
                          {raw === s.key ? "Hide raw returned content" : "View raw returned content"}
                        </button>
                        {raw === s.key && (
                          <div className="mt-2 rounded border border-border bg-surface p-3">
                            <p className="field-label">{s.raw.title}</p>
                            <pre className="mt-1.5 overflow-x-auto text-[11.5px] leading-relaxed text-muted-foreground">
                              {s.raw.lines.join("\n")}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </Panel>
        </div>

        <div className="space-y-3">
          <Panel title="Acquisition summary" subtitle={`Appraisal ${a.id} · ${a.stage}`}>
            <div className="grid grid-cols-2 divide-x divide-border border-b border-border">
              <div className="px-4 py-3">
                <p className="text-[22px] font-semibold tabular-nums text-positive">{ready}</p>
                <p className="text-[11.5px] text-muted-foreground">Sources ready</p>
              </div>
              <div className="px-4 py-3">
                <p className="text-[22px] font-semibold tabular-nums text-flag-foreground">{pending}</p>
                <p className="text-[11.5px] text-muted-foreground">Sources pending</p>
              </div>
            </div>
            <dl className="divide-y divide-border text-[12.5px]">
              <div className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">Partial or degraded</dt>
                <dd className="tabular-nums">{partial}</dd>
              </div>
              <div className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">Consent artefact</dt>
                <dd className="text-right">
                  {acq.bank === "awaiting" ? "Not yet sent" : acq.consentRef}
                </dd>
              </div>
              <div className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">Data window</dt>
                <dd className="text-right">{CONSENT_WINDOW}</dd>
              </div>
            </dl>
          </Panel>

          <Panel title="Bank data under consent" subtitle="Two linked accounts in scope">
            <ul className="divide-y divide-border">
              {CONSENT_ACCOUNTS.map((acc) => (
                <li key={acc.id} className="px-4 py-2.5 text-[12.5px]">
                  <p className="font-medium text-foreground">
                    {acc.bank} · {acc.masked}
                  </p>
                  <p className="text-[11.5px] text-muted-foreground">
                    {acc.type} · {acc.branch} · IFSC {acc.ifsc}
                  </p>
                </li>
              ))}
            </ul>
            <div className="border-t border-border px-4 py-3">
              <Link
                to="/appraisals/$id/consent"
                params={{ id: a.id }}
                className="flex h-8 items-center justify-center gap-1.5 rounded border border-border bg-surface text-[12.5px] font-medium text-foreground hover:bg-muted"
              >
                <ShieldCheck className="h-3.5 w-3.5" /> Open consent journey
              </Link>
            </div>
          </Panel>

          <div className="rounded border border-border bg-surface p-4">
            <p className="flex items-center gap-1.5 text-[13px] font-semibold">
              <Sparkles className="h-3.5 w-3.5 text-primary" /> Inline AI action
            </p>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
              Check the evidence set against the CAM v4.2 completeness rule and list what still blocks
              the spread, in the order it blocks it.
            </p>
            <button
              type="button"
              onClick={() =>
                toast("Completeness check complete", {
                  description:
                    acq.bank === "consented" || acq.bank === "fallback"
                      ? "All seven sources are in. Spread can be built; bank credits are INR 5.46 cr below GST turnover and will surface in cross-verification."
                      : "Bank-account data is the only blocking gap. Adverse media is partial but non-blocking; everything else is in.",
                })
              }
              className="mt-3 flex h-8 w-full items-center justify-center gap-1.5 rounded bg-primary text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              Check what blocks the spread
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
