import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  ArrowUpRight,
  Download,
  FileCheck2,
  Fingerprint,
  Lock,
  ShieldCheck,
  Sparkles,
  UserRound,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import {
  AUDIT_MEMOS,
  HUMAN_KINDS,
  KIND_LABEL,
  KIND_TONE,
  getAuditMemo,
  recordExport,
  sessionEvents,
  tracesFor,
  useExports,
  type AuditEvent,
  type AuditMemo,
  type EventKind,
  type EventLink,
  type TraceStep,
} from "@/data/audit";
import { useXVState } from "@/data/crossverify";
import { useMemoState } from "@/data/memo";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/audit")({
  head: () => {
    const title = "Audit ledger and examiner walk-through — CreditIQ";
    const description =
      "Reconstruct any credit decision end to end: what each source returned, what the system drafted, every human edit and override with author and reason, how each discrepancy was adjudicated, and who approved.";
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
  component: AuditLedger,
});

const APPRAISAL_ROUTES = {
  identity: "/appraisals/$id/identity",
  data: "/appraisals/$id/data",
  consent: "/appraisals/$id/consent",
  upload: "/appraisals/$id/upload",
  spread: "/appraisals/$id/spread",
  "cross-verification": "/appraisals/$id/cross-verification",
  draft: "/appraisals/$id/draft",
  rating: "/appraisals/$id/rating",
  submission: "/appraisals/$id/submission",
} as const;

function RecordLink({ link, appraisalId }: { link: EventLink; appraisalId: string }) {
  const cls =
    "inline-flex items-center gap-1 rounded border border-border bg-surface px-1.5 py-0.5 text-[11.5px] text-muted-foreground hover:bg-muted hover:text-foreground";
  if (link.kind === "person")
    return (
      <Link to="/people/$slug" params={{ slug: link.slug ?? "" }} className={cls}>
        <UserRound className="h-3 w-3" />
        {link.label}
      </Link>
    );
  if (link.kind === "borrower")
    return (
      <Link to="/borrowers/$slug" params={{ slug: link.slug ?? "" }} className={cls}>
        {link.label}
        <ArrowUpRight className="h-3 w-3" />
      </Link>
    );
  const to = APPRAISAL_ROUTES[link.target as keyof typeof APPRAISAL_ROUTES] ?? APPRAISAL_ROUTES.spread;
  return (
    <Link
      to={to}
      params={{ id: appraisalId }}
      {...(link.anchor ? { hash: link.anchor.replace("#", "") } : {})}
      className={cls}
    >
      {link.label}
      <ArrowUpRight className="h-3 w-3" />
    </Link>
  );
}

const FILTERS: { id: EventKind | "all" | "human"; label: string }[] = [
  { id: "all", label: "All events" },
  { id: "human", label: "Human changes only" },
  { id: "source", label: "Sources" },
  { id: "extraction", label: "Extraction and checks" },
  { id: "draft", label: "Drafting" },
  { id: "adjudication", label: "Adjudications" },
  { id: "override", label: "Overrides" },
  { id: "edit", label: "Edits" },
];

function AuditLedger() {
  const xv = useXVState();
  const memoState = useMemoState();
  const exportsList = useExports();
  const [memoId, setMemoId] = useState("aurora");
  const [filter, setFilter] = useState<EventKind | "all" | "human">("all");
  const [traceId, setTraceId] = useState<string | null>(null);
  const [openEvent, setOpenEvent] = useState<string | null>(null);

  const memo = getAuditMemo(memoId);
  const events = useMemo(() => {
    const session = [...sessionEvents(memo, xv, memoState)].sort((a, b) => a.atSort - b.atSort);
    return [...memo.events, ...session];
  }, [memo, xv, memoState]);

  const shown = events.filter((e) =>
    filter === "all" ? true : filter === "human" ? e.human && HUMAN_KINDS.includes(e.kind) : e.kind === filter,
  );

  const traces = tracesFor(memo.id);
  const trace = traces.find((t) => t.id === traceId) ?? null;
  const changes = events.filter((e) => e.human && HUMAN_KINDS.includes(e.kind));
  const memoExports = exportsList.filter((x) => x.memoId === memo.id);

  function onExport() {
    const rec = recordExport(memo, events.length);
    const body = [
      `CONTINENTAL COMMERCIAL BANK — EXAMINER RECORD`,
      `Memo ${memo.reference} · ${memo.borrower}`,
      `Export ${rec.reference} · generated ${rec.at} for Omar Haddad, Compliance and Audit`,
      `Content digest ${rec.digest} · ${rec.pages} pages · read-only, tamper-evident`,
      ``,
      ...events.map(
        (e) =>
          `${e.at} — [${KIND_LABEL[e.kind]}] ${e.title}\n    Actor: ${e.actor} (${e.actorRole})\n    ${e.detail}` +
          (e.original ? `\n    Original: ${e.original}` : "") +
          (e.replacement ? `\n    Replacement: ${e.replacement}` : "") +
          (e.reason ? `\n    Reason: ${e.reason}` : ""),
      ),
    ].join("\n");
    const url = URL.createObjectURL(new Blob([body], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `${rec.reference}_${memo.reference}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Examiner record ${rec.reference} generated`, {
      description: `Digest ${rec.digest}. Any change to the underlying record breaks the digest.`,
    });
  }

  return (
    <div>
      <PageHeader
        eyebrow="Governance · Audit"
        title="Audit ledger and examiner walk-through"
        purpose="Read-only reconstruction of a credit decision: what every source returned, what the system extracted and drafted, every human edit and override with its reason, how each discrepancy was adjudicated, and who recommended and approved."
        actions={
          <>
            <span className="hidden items-center gap-1.5 rounded border border-border bg-surface-muted px-2 py-1.5 text-[11.5px] text-muted-foreground lg:inline-flex">
              <Lock className="h-3.5 w-3.5" /> Read-only for Omar Haddad, Compliance and Audit
            </span>
            <button
              onClick={onExport}
              className="flex h-9 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
            >
              <Download className="h-3.5 w-3.5" /> Export examiner record
            </button>
          </>
        }
      />

      <div className="space-y-4 px-6 py-5">
        {/* memo selector */}
        <div className="grid gap-3 md:grid-cols-2">
          {AUDIT_MEMOS.map((m) => (
            <button
              key={m.id}
              onClick={() => {
                setMemoId(m.id);
                setTraceId(null);
                setOpenEvent(null);
              }}
              className={cn(
                "rounded border bg-surface px-4 py-3 text-left transition-colors",
                m.id === memoId ? "border-primary ring-1 ring-primary/25" : "border-border hover:bg-muted",
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-[13.5px] font-semibold text-foreground">{m.borrower}</p>
                  <p className="mt-0.5 text-[12px] text-muted-foreground">
                    {m.reference} · {m.issued} · {m.branch}
                  </p>
                </div>
                <span
                  className={cn(
                    "shrink-0 rounded border px-1.5 py-0.5 text-[10.5px] font-medium",
                    m.seriousFlags ? "border-critical/30 bg-critical-soft text-critical" : "border-positive/30 bg-positive-soft text-positive",
                  )}
                >
                  {m.rating} · {m.ratingLabel}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-muted-foreground">
                <span>{m.events.length} recorded events</span>
                <span>
                  {m.events.filter((e) => e.human && HUMAN_KINDS.includes(e.kind)).length} human changes
                </span>
                <span>
                  {m.seriousFlags} serious {m.seriousFlags === 1 ? "finding" : "findings"}
                </span>
                <span>{m.status}</span>
              </div>
            </button>
          ))}
        </div>

        {/* memo header strip */}
        <div className="rounded border border-border bg-surface">
          <div className="grid gap-x-6 gap-y-3 px-4 py-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              { label: "Memo", value: `${memo.reference} · ${memo.borrower}` },
              { label: "Analyst of record", value: memo.analyst },
              { label: "Approval", value: memo.approver },
              { label: "Facilities", value: memo.facilities },
              { label: "Sector", value: memo.sector },
              { label: "Sealed", value: memo.sealedAt },
              { label: "Content digest", value: memo.digest },
              { label: "Retention", value: memo.retention },
            ].map((f) => (
              <div key={f.label} className="min-w-0">
                <p className="field-label">{f.label}</p>
                <p className="mt-0.5 truncate text-[12.5px] text-foreground" title={f.value}>
                  {f.value}
                </p>
              </div>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-2.5 text-[11.5px] text-muted-foreground">
            <ShieldCheck className="h-3.5 w-3.5 text-positive" />
            Nothing on this screen can be edited. The ledger is append-only and every entry carries its author and time.
            <Link
              to="/borrowers/$slug"
              params={{ slug: memo.slug }}
              className="inline-flex items-center gap-1 text-primary hover:underline"
            >
              Open the borrower dossier <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          {/* timeline */}
          <Panel
            title="Decision timeline"
            subtitle={`${shown.length} of ${events.length} events · ${memo.issued}`}
            action={
              <div className="flex flex-wrap gap-1">
                {FILTERS.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setFilter(f.id)}
                    className={cn(
                      "rounded border px-2 py-1 text-[11.5px]",
                      filter === f.id
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-border bg-surface text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {f.label}
                  </button>
                ))}
              </div>
            }
          >
            <ol className="divide-y divide-border">
              {shown.map((e) => (
                <TimelineRow
                  key={e.id}
                  event={e}
                  memo={memo}
                  open={openEvent === e.id}
                  onToggle={() => setOpenEvent(openEvent === e.id ? null : e.id)}
                />
              ))}
              {shown.length === 0 && (
                <li className="px-4 py-6 text-[12.5px] text-muted-foreground">
                  No events of this type on {memo.reference}. On a clean run that is the expected answer, not a gap.
                </li>
              )}
            </ol>
          </Panel>

          {/* trace panel */}
          <div className="space-y-4">
            <Panel title="Trace panel" subtitle="Pick a figure from the final memo and walk it back to the source it came from.">
              <div className="divide-y divide-border">
                {traces.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTraceId(traceId === t.id ? null : t.id)}
                    className={cn(
                      "block w-full px-4 py-2.5 text-left hover:bg-muted",
                      traceId === t.id && "bg-muted",
                    )}
                  >
                    <p className="text-[12.5px] font-medium text-foreground">{t.label}</p>
                    <p className="mt-0.5 text-[12px] text-muted-foreground">
                      {t.value} · {t.steps.length} steps · {t.section}
                    </p>
                  </button>
                ))}
              </div>
              {trace && (
                <div className="border-t border-border bg-surface-muted/40 px-4 py-3">
                  <p className="flex items-center gap-1.5 text-[12.5px] font-semibold text-foreground">
                    <Fingerprint className="h-3.5 w-3.5 text-primary" /> {trace.label} — {trace.value}
                  </p>
                  <ol className="mt-3 space-y-3">
                    {trace.steps.map((s, i) => (
                      <TraceRow key={i} step={s} last={i === trace.steps.length - 1} appraisalId={memo.appraisalId} />
                    ))}
                  </ol>
                </div>
              )}
            </Panel>

            <Panel title="Human changes on this memo" subtitle={`${changes.length} recorded · each attributed`}>
              <ul className="divide-y divide-border">
                {changes.map((c) => (
                  <li key={c.id} className="px-4 py-2.5">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-[12.5px] text-foreground">{c.title}</p>
                      <span className={cn("shrink-0 rounded border px-1.5 py-0.5 text-[10.5px]", KIND_TONE[c.kind])}>
                        {KIND_LABEL[c.kind]}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11.5px] text-muted-foreground">
                      {c.actor} · {c.actorRole} · {c.at}
                    </p>
                    {c.reason && <p className="mt-1 text-[12px] text-muted-foreground">Reason: {c.reason}</p>}
                  </li>
                ))}
                {changes.length === 0 && (
                  <li className="px-4 py-4 text-[12.5px] text-muted-foreground">No human changes recorded.</li>
                )}
              </ul>
            </Panel>

            <Panel title="Examiner exports" subtitle="Tamper-evident copies generated from this ledger.">
              <ul className="divide-y divide-border">
                {memoExports.map((x) => (
                  <li key={x.reference} className="flex items-start gap-2 px-4 py-2.5">
                    <FileCheck2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-positive" />
                    <div className="min-w-0">
                      <p className="text-[12.5px] text-foreground">{x.reference}</p>
                      <p className="mt-0.5 break-all text-[11.5px] text-muted-foreground">
                        {x.at} · {x.pages} pages · digest {x.digest}
                      </p>
                    </div>
                  </li>
                ))}
                {memoExports.length === 0 && (
                  <li className="px-4 py-3 text-[12.5px] text-muted-foreground">
                    None yet for {memo.reference}. The export writes the full ledger to an examiner's file and seals it with a content digest.
                  </li>
                )}
              </ul>
            </Panel>

            <div className="rounded border border-border bg-surface p-4">
              <p className="flex items-center gap-1.5 text-[12.5px] font-semibold">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Ask the copilot
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                "Walk me through how the turnover figure was arrived at" and "List every human override in this memo" —
                answered strictly from this record, with nothing inferred.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TimelineRow({
  event,
  memo,
  open,
  onToggle,
}: {
  event: AuditEvent;
  memo: AuditMemo;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <li>
      <button onClick={onToggle} className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-muted">
        <span className="w-[104px] shrink-0 pt-0.5 text-[11.5px] tabular-nums text-muted-foreground">{event.at}</span>
        <span className="relative flex w-3 shrink-0 justify-center self-stretch">
          <span className="absolute inset-y-0 w-px bg-border" />
          <span
            className={cn(
              "relative mt-1 h-2 w-2 rounded-full",
              event.human ? "bg-flag ring-2 ring-flag-soft" : "bg-muted-foreground/50",
            )}
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-[13px] font-medium text-foreground">{event.title}</span>
            <span className={cn("rounded border px-1.5 py-0.5 text-[10.5px]", KIND_TONE[event.kind])}>
              {KIND_LABEL[event.kind]}
            </span>
          </span>
          <span className="mt-0.5 block text-[11.5px] text-muted-foreground">
            {event.actor} · {event.actorRole}
          </span>
          {!open && <span className="mt-1 line-clamp-2 block text-[12.5px] text-muted-foreground">{event.detail}</span>}
        </span>
      </button>
      {open && (
        <div className="border-t border-border bg-surface-muted/40 px-4 py-3 lg:pl-[136px]">
          <p className="text-[12.5px] leading-relaxed text-foreground">{event.detail}</p>
          {(event.original || event.replacement) && (
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              {event.original && (
                <div className="rounded border border-border bg-surface p-2.5">
                  <p className="field-label">Original value retained</p>
                  <p className="mt-1 text-[12px] text-muted-foreground">{event.original}</p>
                </div>
              )}
              {event.replacement && (
                <div className="rounded border border-flag/35 bg-flag-soft p-2.5">
                  <p className="field-label">Human value</p>
                  <p className="mt-1 text-[12px] text-flag-foreground">{event.replacement}</p>
                </div>
              )}
            </div>
          )}
          {event.reason && (
            <p className="mt-2 rounded border border-border bg-surface p-2.5 text-[12px] text-muted-foreground">
              <span className="font-medium text-foreground">Recorded reason: </span>
              {event.reason}
            </p>
          )}
          {event.meta && (
            <dl className="mt-2 grid gap-x-6 gap-y-1 2xl:grid-cols-2">
              {event.meta.map((m) => (
                <div key={m.label} className="flex gap-2 text-[12px]">
                  <dt className="w-24 shrink-0 text-muted-foreground">{m.label}</dt>
                  <dd className="min-w-0 flex-1 text-foreground">{m.value}</dd>
                </div>
              ))}
            </dl>
          )}
          <div className="mt-2.5 flex flex-wrap items-center gap-2">
            {event.links?.map((l, i) => <RecordLink key={i} link={l} appraisalId={memo.appraisalId} />)}
            <span className="text-[11px] text-muted-foreground">Entry hash {event.hash}</span>
          </div>
        </div>
      )}
    </li>
  );
}

function TraceRow({ step, last, appraisalId }: { step: TraceStep; last: boolean; appraisalId: string }) {
  return (
    <li className="flex gap-3">
      <div className="flex w-16 shrink-0 flex-col items-end">
        <span className="rounded border border-border bg-surface px-1.5 py-0.5 text-[10.5px] text-muted-foreground">
          {step.stage}
        </span>
        {!last && <span className="mt-1 w-px flex-1 bg-border" />}
      </div>
      <div className="min-w-0 flex-1 pb-1">
        <p className="text-[12.5px] font-medium text-foreground">{step.title}</p>
        <p className="mt-0.5 text-[12px] leading-relaxed text-muted-foreground">{step.detail}</p>
        <p className="mt-1 text-[11.5px] text-muted-foreground">
          {step.actor} · {step.at}
        </p>
        {step.link && (
          <div className="mt-1.5">
            <RecordLink link={step.link} appraisalId={appraisalId} />
          </div>
        )}
      </div>
    </li>
  );
}
