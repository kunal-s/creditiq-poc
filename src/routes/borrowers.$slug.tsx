import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  Check,
  Clock,
  FileText,
  Minus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  TrendingDown,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel } from "@/components/identity/chips";
import { CURRENT_USER } from "@/data/seed";
import {
  CHANGES,
  CONSENT,
  PRIOR_MEMO,
  REFRESH_ASOF,
  type RefreshChange,
  acceptNoChange,
  completeRefresh,
  getBorrower,
  grantConsent,
  markReviewStarted,
  requestConsent,
  startRefresh,
  useRefreshState,
} from "@/data/portfolio";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/borrowers/$slug")({
  head: ({ params }) => {
    const b = getBorrower(params.slug);
    const title = `${b?.name ?? "Borrower"} dossier — CreditIQ`;
    const description = b
      ? `${b.name}: memo versions, current rating ${b.rating}, next review ${b.nextReview}, and what changed since the last appraisal.`
      : "Borrower dossier with memo history and refresh change highlights.";
    return {
      meta: [
        { title },
        { name: "description", content: description },
        { property: "og:title", content: title },
        { property: "og:description", content: description },
        { property: "og:type", content: "profile" },
        { name: "twitter:card", content: "summary" },
      ],
    };
  },
  component: BorrowerDossier,
});

const SEV_TONE = {
  breach: { chip: "border-critical/40 bg-critical-soft text-critical", label: "Policy breach", icon: ShieldAlert },
  watch: { chip: "border-flag/40 bg-flag-soft text-flag", label: "Watch", icon: AlertTriangle },
  note: { chip: "border-border bg-muted text-muted-foreground", label: "Noted", icon: Minus },
} as const;

function BorrowerDossier() {
  const { slug } = Route.useParams();
  const b = getBorrower(slug);
  if (!b) throw notFound();

  const r = useRefreshState();
  const [open, setOpen] = useState<string | null>("CHG-01");
  const [compare, setCompare] = useState(false);

  const isNorthwind = b.slug === "northwind-manufacturing";
  const changes = isNorthwind ? CHANGES : [];
  const material = changes.filter((c) => c.severity !== "note");
  const breach = changes.find((c) => c.severity === "breach");

  const run = () => {
    startRefresh();
    window.setTimeout(() => {
      completeRefresh();
      toast.success("Refresh complete", {
        description: `${material.length} material changes against ${b.versions[0]!.version}. Bank figures are as at 1 July 2026 — consent expired.`,
      });
    }, 1100);
  };

  return (
    <div className="pb-10">
      <PageHeader
        eyebrow={`Borrower dossier · ${b.sector}`}
        title={b.name}
        purpose={`${b.branch} · Relationship manager ${b.rm} · Analyst ${b.analyst} · ${b.memos} memos on record since 2023.`}
        actions={
          <>
            <Link
              to="/memos"
              className="flex h-8 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              Memo library
            </Link>
            <Link
              to="/appraisals/$id/draft"
              params={{ id: b.appraisalId }}
              className="flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90"
              onClick={() => markReviewStarted()}
            >
              Review the memo <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </>
        }
      />

      {/* borrower header facts */}
      <div className="grid gap-px border-b border-border bg-border sm:grid-cols-2 xl:grid-cols-5">
        {[
          ["PAN", b.pan],
          ["GSTIN", b.gstin],
          ["Exposure", `${b.exposure} · ${b.facilities}`],
          ["Current rating", `${b.rating} · ${b.ratingLabel}`],
          ["Next review", b.nextReview],
        ].map(([label, value], i) => (
          <div key={label} className="bg-surface px-5 py-3">
            <p className="field-label">{label}</p>
            <p className={cn("mt-0.5 text-[13px] tabular text-foreground", i === 3 && "font-semibold text-flag", i === 4 && "font-medium")}>
              {value}
            </p>
          </div>
        ))}
      </div>

      <div className="grid gap-4 px-6 py-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="space-y-4">
          {/* consent state */}
          {isNorthwind && (
            <div
              className={cn(
                "flex flex-col gap-3 rounded border px-4 py-3 lg:flex-row lg:items-start",
                r.consent === "granted"
                  ? "border-positive/35 bg-positive-soft/50"
                  : r.consent === "requested"
                    ? "border-info/35 bg-info-soft/50"
                    : "border-flag/35 bg-flag-soft/50",
              )}
            >
              <Clock className={cn("mt-0.5 hidden h-4 w-4 shrink-0 lg:block", r.consent === "granted" ? "text-positive" : r.consent === "requested" ? "text-info" : "text-flag")} />
              <div className="min-w-0 flex-1 basis-[420px]">
                <p className="text-[13px] font-medium text-foreground">
                  {r.consent === "granted"
                    ? `Fresh consent granted — bank figures re-pulled ${r.bankRefreshedAt}`
                    : r.consent === "requested"
                      ? "Consent request sent to Rajesh Malhotra, Managing Director"
                      : `Bank-data consent ${CONSENT.reference} expired on ${CONSENT.expiredOn}`}
                </p>
                <p className="mt-0.5 text-[12.5px] text-muted-foreground">
                  {r.consent === "granted"
                    ? "Meridian Bank 4471 and 8802 statements are current to 30 July 2026. The Crestline instalment is confirmed at INR 6,12,000 a month on live data."
                    : r.consent === "requested"
                      ? "Sent to the registered mobile and email on the borrower's Account Aggregator handle. Bank figures below stay as at 1 July 2026 until the borrower approves."
                      : CONSENT.effect}
                </p>
                <p className="mt-1 text-[11.5px] text-muted-foreground">
                  {CONSENT.scope} · granted {CONSENT.grantedOn} · {CONSENT.window} · signed by {CONSENT.signatory}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
                {r.consent === "expired" && (
                  <button
                    type="button"
                    onClick={() => {
                      requestConsent();
                      toast.success("Consent request sent", { description: "Rajesh Malhotra has a secure link valid for 72 hours." });
                    }}
                    className="flex h-8 items-center rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90"
                  >
                    Request fresh consent
                  </button>
                )}
                {r.consent === "requested" && (
                  <button
                    type="button"
                    onClick={() => {
                      grantConsent();
                      toast.success("Consent granted by the borrower", { description: "Bank statements re-pulled to 30 July 2026." });
                    }}
                    className="flex h-8 items-center rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90"
                  >
                    Borrower approved — pull now
                  </button>
                )}
                <Link
                  to="/appraisals/$id/consent"
                  params={{ id: b.appraisalId }}
                  className="flex h-8 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
                >
                  Open consent journey
                </Link>
              </div>
            </div>
          )}

          {/* refresh panel */}
          <Panel
            title="Refresh against the last memo"
            subtitle={`Prior memo: ${PRIOR_MEMO}`}
            action={
              <div className="flex items-center gap-2">
                {r.status === "done" && (
                  <button
                    type="button"
                    onClick={() => setCompare((v) => !v)}
                    className="flex h-8 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
                  >
                    {compare ? "Hide version comparison" : "Compare versions"}
                  </button>
                )}
                <button
                  type="button"
                  onClick={run}
                  disabled={!b.refreshable || r.status === "running"}
                  className={cn(
                    "flex h-8 items-center gap-1.5 rounded px-3 text-[12.5px] font-medium",
                    b.refreshable && r.status !== "running"
                      ? "bg-primary text-primary-foreground hover:opacity-90"
                      : "cursor-not-allowed bg-muted text-muted-foreground",
                  )}
                >
                  <RefreshCw className={cn("h-3.5 w-3.5", r.status === "running" && "animate-spin")} />
                  {r.status === "running" ? "Re-pulling sources…" : r.status === "done" ? "Run refresh again" : "Run refresh"}
                </button>
              </div>
            }
          >
            {!b.refreshable ? (
              <p className="px-4 py-6 text-[13px] text-muted-foreground">
                This borrower has no issued memo to refresh against. The appraisal in flight is its first.
              </p>
            ) : r.status === "idle" ? (
              <div className="px-4 py-6">
                <p className="max-w-2xl text-[13px] text-muted-foreground">
                  A refresh re-pulls GST, bureau, registry and consented bank data, re-runs the spread and the cross-verification, and lists only what moved
                  against {b.versions[0]!.version}. Nothing is written to the memo until you review it.
                </p>
                <dl className="mt-3 grid gap-x-8 gap-y-1.5 text-[12.5px] sm:grid-cols-2">
                  {[
                    ["Sources in scope", "GSTN, TransUnion CIBIL, MCA and CERSAI, Account Aggregator, branch provisionals"],
                    ["Last refreshed", "24 June 2026, at the start of this appraisal"],
                    ["Consent state", `${CONSENT.reference} expired ${CONSENT.expiredOn} — bank figures will lag`],
                    ["Review due", `${b.nextReview} · ${b.rating} watch grade`],
                  ].map(([k, v]) => (
                    <div key={k} className="flex gap-2">
                      <dt className="w-40 shrink-0 text-muted-foreground">{k}</dt>
                      <dd className="text-foreground">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : r.status === "running" ? (
              <ul className="divide-y divide-border text-[13px]">
                {["GSTR-3B, April to June 2026", "TransUnion CIBIL Commercial", "MCA and CERSAI charge index", "Meridian Bank statements (consent expired)", "Branch provisional financials"].map(
                  (s) => (
                    <li key={s} className="flex items-center gap-2 px-4 py-2.5 text-muted-foreground">
                      <RefreshCw className="h-3.5 w-3.5 animate-spin text-info" /> {s}
                    </li>
                  ),
                )}
              </ul>
            ) : (
              <div>
                <div className="grid gap-px border-b border-border bg-border sm:grid-cols-3">
                  {[
                    ["Material changes", `${material.length} of ${changes.length}`, "text-foreground"],
                    ["Policy breaches", "1 · current ratio below 1.20x", "text-critical"],
                    ["Data as at", REFRESH_ASOF, "text-muted-foreground"],
                  ].map(([k, v, tone]) => (
                    <div key={k} className="bg-surface px-4 py-2.5">
                      <p className="field-label">{k}</p>
                      <p className={cn("mt-0.5 text-[13px] font-medium", tone)}>{v}</p>
                    </div>
                  ))}
                </div>

                {breach && (
                  <div className="flex items-start gap-2 border-b border-border bg-critical-soft/40 px-4 py-3">
                    <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0 text-critical" />
                    <p className="text-[12.5px] text-foreground">
                      <span className="font-medium">Current ratio has slipped from 1.28x to 1.19x</span>, below CCB's 1.20x minimum. This is an early-warning
                      condition on a CCB-4 borrower already carrying an open turnover finding, and it should be reflected in the memo before the committee sits.
                    </p>
                  </div>
                )}

                <ul className="divide-y divide-border">
                  {changes.map((c) => (
                    <ChangeRow
                      key={c.id}
                      c={c}
                      appraisalId={b.appraisalId}
                      open={open === c.id}
                      stale={Boolean(c.needsBankData) && r.consent !== "granted"}
                      onToggle={() => setOpen(open === c.id ? null : c.id)}
                    />
                  ))}
                </ul>

                <div className="flex flex-wrap items-center gap-2 border-t border-border px-4 py-3">
                  <Link
                    to="/appraisals/$id/draft"
                    params={{ id: b.appraisalId }}
                    onClick={() => markReviewStarted()}
                    className="flex h-8 items-center gap-1.5 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:opacity-90"
                  >
                    Review the refreshed memo <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                  <button
                    type="button"
                    disabled={material.length > 0}
                    onClick={() => {
                      acceptNoChange(CURRENT_USER.name);
                      toast.success("Accepted without change");
                    }}
                    title={material.length > 0 ? "Two material changes and one policy breach must be carried into the memo." : undefined}
                    className={cn(
                      "flex h-8 items-center rounded border px-3 text-[12.5px] font-medium",
                      material.length > 0
                        ? "cursor-not-allowed border-border bg-muted text-muted-foreground"
                        : "border-border bg-surface text-foreground hover:bg-muted",
                    )}
                  >
                    Accept, nothing material changed
                  </button>
                  <Link
                    to="/appraisals/$id/cross-verification"
                    params={{ id: b.appraisalId }}
                    className="flex h-8 items-center rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
                  >
                    Open the discrepancy board
                  </Link>
                  <p className="text-[11.5px] text-muted-foreground">
                    Refresh run by {CURRENT_USER.name} · {CURRENT_USER.role}
                  </p>
                </div>
              </div>
            )}
          </Panel>

          {compare && r.status === "done" && <Comparison versions={b.versions} />}

          {/* version timeline */}
          <Panel title="Memo versions" subtitle="Every issued memo for this borrower, most recent first">
            <ol className="divide-y divide-border">
              {b.versions.map((v) => (
                <li key={v.version} className="flex gap-3 px-4 py-3">
                  <div className="flex w-12 shrink-0 flex-col items-center">
                    <span
                      className={cn(
                        "flex h-7 w-7 items-center justify-center rounded-full border text-[11.5px] font-semibold",
                        v.current ? "border-primary bg-primary text-primary-foreground" : "border-border bg-muted text-muted-foreground",
                      )}
                    >
                      {v.version}
                    </span>
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                      <Link
                        to="/appraisals/$id/draft"
                        params={{ id: b.appraisalId }}
                        className="text-[13px] font-medium text-foreground hover:text-primary"
                      >
                        {v.reference}
                      </Link>
                      <span className="text-[12px] text-muted-foreground">{v.issued}</span>
                      <span className="text-border">|</span>
                      <span className="text-[12px] text-muted-foreground">{v.status}</span>
                      <span className="rounded border border-border bg-muted px-1.5 py-0.5 text-[11px] font-medium text-foreground">{v.rating}</span>
                      {v.current && <span className="rounded border border-info/35 bg-info-soft px-1.5 py-0.5 text-[11px] font-medium text-info">Current</span>}
                    </div>
                    <p className="mt-1 text-[12.5px] text-muted-foreground">{v.summary}</p>
                    <p className="mt-1 text-[11.5px] text-muted-foreground">
                      {v.facilities} · authored by {v.author}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
        </div>

        {/* right column */}
        <aside className="space-y-3">
          <Panel title="What this dossier watches">
            <ul className="divide-y divide-border text-[12.5px]">
              {[
                ["Review date", b.nextReview, "text-flag"],
                ["Open findings", isNorthwind ? "3 cross-verification findings, 1 serious" : "None", "text-foreground"],
                ["Consent", r.consent === "granted" ? "Current to 30 July 2026" : `Expired ${CONSENT.expiredOn}`, r.consent === "granted" ? "text-positive" : "text-flag"],
                ["Early-warning trigger", isNorthwind ? "Current ratio below 1.20x" : "None active", isNorthwind ? "text-critical" : "text-muted-foreground"],
              ].map(([k, v, tone]) => (
                <li key={k} className="flex items-start justify-between gap-3 px-4 py-2.5">
                  <span className="text-muted-foreground">{k}</span>
                  <span className={cn("text-right font-medium", tone)}>{v}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Copilot on this borrower">
            <div className="space-y-2 px-4 py-3 text-[12.5px] text-muted-foreground">
              <p className="flex items-start gap-1.5">
                <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
                Ask the rail what deteriorated since the last review, or have it draft an early-warning note for the current-ratio breach. Every answer cites the
                filing or statement it came from.
              </p>
            </div>
          </Panel>

          <Panel title="Where this goes next">
            <ul className="divide-y divide-border text-[12.5px]">
              {[
                { label: "Draft and Review", detail: "Carry the changes into the memo", to: "draft" as const },
                { label: "Financial Spread", detail: "See the restated ratios in context", to: "spread" as const },
                { label: "Cross-Verification", detail: "The Crestline finding, now larger", to: "cross-verification" as const },
              ].map((l) => (
                <li key={l.label}>
                  <Link
                    to={`/appraisals/$id/${l.to}`}
                    params={{ id: b.appraisalId }}
                    className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-muted"
                  >
                    <span>
                      <span className="block font-medium text-foreground">{l.label}</span>
                      <span className="text-muted-foreground">{l.detail}</span>
                    </span>
                    <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  </Link>
                </li>
              ))}
            </ul>
          </Panel>
        </aside>
      </div>
    </div>
  );
}

function ChangeRow({
  c,
  appraisalId,
  open,
  stale,
  onToggle,
}: {
  c: RefreshChange;
  appraisalId: string;
  open: boolean;
  stale: boolean;
  onToggle: () => void;
}) {
  const tone = SEV_TONE[c.severity];
  const Icon = c.direction === "worse" ? TrendingDown : c.direction === "flat" ? Minus : Check;
  return (
    <li className={cn(open && "bg-muted/30")}>
      <button type="button" onClick={onToggle} className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-muted/50">
        <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", c.severity === "breach" ? "text-critical" : c.severity === "watch" ? "text-flag" : "text-muted-foreground")} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-[13px] font-medium text-foreground">{c.metric}</span>
            <span className={cn("rounded border px-1.5 py-0.5 text-[11px] font-medium", tone.chip)}>{tone.label}</span>
            <span className="text-[11.5px] text-muted-foreground">{c.area}</span>
            {stale && (
              <span className="rounded border border-flag/35 bg-flag-soft px-1.5 py-0.5 text-[11px] font-medium text-flag">On expired consent</span>
            )}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[12.5px] tabular">
            <span className="text-muted-foreground line-through">{c.prior}</span>
            <ArrowRight className="h-3 w-3 text-muted-foreground" />
            <span className={cn("font-semibold", c.severity === "breach" ? "text-critical" : c.severity === "watch" ? "text-flag" : "text-foreground")}>{c.now}</span>
            <span className="text-muted-foreground">· {c.delta}</span>
          </div>
        </div>
        <span className="mt-0.5 shrink-0 text-[11.5px] text-muted-foreground">{open ? "Hide evidence" : "Evidence"}</span>
      </button>
      {open && (
        <div className="grid gap-3 border-t border-border px-4 py-3 lg:grid-cols-[minmax(0,1fr)_300px]">
          <p className="text-[12.5px] leading-relaxed text-foreground">{c.narrative}</p>
          <div className="rounded border border-border bg-background px-3 py-2.5">
            <p className="field-label">Evidence</p>
            <p className="mt-1 text-[12.5px] font-medium text-foreground">{c.evidence.source}</p>
            <p className="mt-1 text-[12px] text-muted-foreground">{c.evidence.detail}</p>
            <p className="mt-1 text-[11.5px] text-muted-foreground">Pulled {c.evidence.pulled}</p>
            <Link
              to={`/appraisals/$id/${c.to.kind}`}
              params={{ id: appraisalId }}
              {...(c.to.anchor ? { hash: c.to.anchor.replace("#", "") } : {})}
              className="mt-2 inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
            >
              <FileText className="h-3 w-3" /> Open the source
            </Link>
          </div>
        </div>
      )}
    </li>
  );
}

function Comparison({ versions }: { versions: { version: string; reference: string; issued: string; rating: string; facilities: string }[] }) {
  const [a, bV] = [versions[0]!, versions[1]!];
  const rows: [string, string, string, boolean][] = [
    ["Turnover", "INR 117.60 cr (FY2025 provisional)", "INR 142.31 cr declared, INR 121.44 cr evidenced", true],
    ["Current ratio", "1.31x", "1.19x on June 2026 provisionals", true],
    ["DSCR", "1.72x", "1.54x", true],
    ["TOL/TNW", "2.18x", "2.34x", true],
    ["Non-bank obligations", "None declared", "Crestline Financial Services, INR 73.44 lakh a year", true],
    ["Buyer concentration", "33.1%", "38.4%", true],
    ["Bureau rank", "CMR-4", "CMR-4", false],
    ["Rating", bV.rating, a.rating, true],
  ];
  return (
    <Panel title="Version comparison" subtitle={`${bV.reference} (${bV.issued}) against ${a.reference} (${a.issued})`}>
      <table className="w-full text-[12.5px]">
        <thead>
          <tr className="border-b border-border text-left text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-2 font-medium">Measure</th>
            <th className="px-4 py-2 font-medium">{bV.version} · {bV.issued}</th>
            <th className="px-4 py-2 font-medium">{a.version} · refreshed</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {rows.map(([m, prior, now, moved]) => (
            <tr key={m} className={cn(moved && "bg-flag-soft/25")}>
              <td className="px-4 py-2 text-muted-foreground">{m}</td>
              <td className="px-4 py-2 tabular text-foreground">{prior}</td>
              <td className={cn("px-4 py-2 tabular", moved ? "font-medium text-foreground" : "text-muted-foreground")}>{now}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="border-t border-border px-4 py-2 text-[11.5px] text-muted-foreground">
        Shaded rows moved between versions. <X className="inline h-3 w-3" /> nothing in this comparison is written to the memo until you review it.
      </p>
    </Panel>
  );
}
