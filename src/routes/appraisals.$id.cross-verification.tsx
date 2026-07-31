import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ExternalLink,
  FileSearch,
  Info,
  Lock,
  MessageSquarePlus,
  Sparkles,
  UserRoundCog,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/shell/PlaceholderPage";
import { Panel, SourceChip } from "@/components/identity/chips";
import { CURRENT_USER, getAppraisal } from "@/data/seed";
import {
  FLAGS,
  OUTCOME_LABEL,
  OUTCOME_TONE,
  REVIEWERS,
  SEVERITY_BAR,
  SEVERITY_LABEL,
  SEVERITY_TONE,
  addNote,
  adjudicate,
  isBlocked,
  ownerOf,
  reassignFlag,
  reopenFlag,
  useXVState,
  type EvidenceFigure,
  type Flag,
  type Outcome,
  type Severity,
} from "@/data/crossverify";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/appraisals/$id/cross-verification")({
  head: ({ params }) => {
    const a = getAppraisal(params.id);
    const title = `Cross-verification — ${a?.borrower ?? "Appraisal"} — CreditIQ`;
    const description =
      "Every cross-source contradiction for the borrower, ranked by severity, with the evidence attached and a human adjudication required on each before the memo can be submitted.";
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
  component: CrossVerificationBoard,
});

const OUTCOMES: { value: Outcome; label: string; help: string }[] = [
  {
    value: "resolved",
    label: "Resolve with evidence",
    help: "The contradiction is explained by evidence on file. It leaves the queue and is recorded with your reasoning.",
  },
  {
    value: "accepted",
    label: "Accept as a genuine risk",
    help: "The finding stands. It carries forward into the memo's risk narrative and the rating rationale.",
  },
  {
    value: "info-requested",
    label: "Request more information",
    help: "Put a query to the borrower or the RM. The flag stays open and keeps its blocking state.",
  },
];

function CrossVerificationBoard() {
  const { id } = Route.useParams();
  const a = getAppraisal(id);
  if (!a) throw notFound();

  const s = useXVState();
  const [open, setOpen] = useState<string | null>(FLAGS[0]!.id);
  const [evidence, setEvidence] = useState<Record<string, string | null>>({ "XV-0418-01": "gst" });
  const [monthsOpen, setMonthsOpen] = useState(false);

  const blocked = isBlocked(s);
  const counts = useMemo(() => {
    const byOpen = (sev: Severity) => FLAGS.filter((f) => f.severity === sev && !s.adjudications[f.id]).length;
    return {
      serious: byOpen("serious"),
      moderate: byOpen("moderate"),
      mild: byOpen("mild"),
      adjudicated: FLAGS.filter((f) => s.adjudications[f.id]).length,
    };
  }, [s]);

  const accepted = FLAGS.filter((f) => s.adjudications[f.id]?.outcome === "accepted");

  return (
    <div>
      <PageHeader
        eyebrow={`Appraisal ${a.id} · Cross-verification`}
        title="Cross-verification and discrepancy"
        purpose="Every source lined up against every other. Three contradictions found for this borrower, ranked by credit impact, each with the underlying evidence attached and a decision required from you."
        actions={
          <>
            <Link
              to="/appraisals/$id/spread"
              params={{ id: a.id }}
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              <ArrowLeft className="h-3.5 w-3.5" /> Spread
            </Link>
            <Link
              to="/exceptions"
              className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
            >
              Exception queue
            </Link>
            <Link
              to="/appraisals/$id/draft"
              params={{ id: a.id }}
              aria-disabled={blocked}
              onClick={(e) => {
                if (blocked) {
                  e.preventDefault();
                  toast.error("Submission blocked", {
                    description:
                      "Flag XV-0418-01 is marked blocking. Adjudicate the turnover discrepancy before drafting the memo.",
                  });
                }
              }}
              className={cn(
                "flex h-9 items-center gap-1.5 rounded px-3 text-[12.5px] font-medium",
                blocked
                  ? "cursor-not-allowed border border-border bg-muted text-muted-foreground"
                  : "bg-primary text-primary-foreground hover:bg-primary/90",
              )}
            >
              {blocked ? <Lock className="h-3.5 w-3.5" /> : null}
              Continue to draft <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </>
        }
      />

      <div className="space-y-4 px-6 py-5">
        {blocked ? (
          <div className="flex flex-wrap items-start gap-3 rounded border border-critical/30 bg-critical-soft px-4 py-3">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-critical" />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-critical">
                Submission blocked — one serious discrepancy is unadjudicated
              </p>
              <p className="mt-0.5 text-[12.5px] leading-relaxed text-foreground/80">
                XV-0418-01, declared turnover exceeds independent evidence by INR 22.48 cr against GST
                and INR 20.87 cr against bank credits. CCB CAM template v4.2 rule 4.1 does not permit a
                memo to leave the analyst's desk while a serious cross-source contradiction is open.
              </p>
            </div>
            <button
              type="button"
              onClick={() => {
                setOpen("XV-0418-01");
                document.getElementById("XV-0418-01")?.scrollIntoView({ behavior: "smooth", block: "start" });
              }}
              className="h-8 shrink-0 rounded bg-critical px-3 text-[12.5px] font-medium text-white hover:opacity-90"
            >
              Adjudicate now
            </button>
          </div>
        ) : (
          <div className="flex flex-wrap items-start gap-3 rounded border border-positive/30 bg-positive-soft px-4 py-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-positive" />
            <div className="min-w-0 flex-1">
              <p className="text-[13px] font-semibold text-positive">
                All blocking discrepancies adjudicated — the memo can proceed
              </p>
              <p className="mt-0.5 text-[12.5px] leading-relaxed text-foreground/80">
                {accepted.length > 0
                  ? `${accepted.length} finding${accepted.length > 1 ? "s" : ""} accepted as genuine risk and carried into the draft risk narrative.`
                  : "No finding was accepted as a genuine risk; every contradiction was explained by evidence on file."}
              </p>
            </div>
          </div>
        )}

        {/* Severity summary */}
        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryCard severity="serious" count={counts.serious} caption="Turnover unsupported by independent evidence" blocking />
          <SummaryCard severity="moderate" count={counts.moderate} caption="Lender obligation absent from the declaration" />
          <SummaryCard severity="mild" count={counts.mild} caption="Buyer concentration above the 35% soft cap" />
          <div className="rounded border border-border bg-surface p-3">
            <p className="field-label">Adjudicated</p>
            <p className="mt-1 text-[24px] font-semibold leading-none tabular">
              {counts.adjudicated}
              <span className="text-[14px] font-normal text-muted-foreground"> / {FLAGS.length}</span>
            </p>
            <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-muted">
              <div
                className="h-full rounded bg-primary transition-all"
                style={{ width: `${(counts.adjudicated / FLAGS.length) * 100}%` }}
              />
            </div>
            <p className="mt-2 text-[11.5px] leading-snug text-muted-foreground">
              Run XV-2026-0418 · 14 rules across 7 sources · 31 July 2026, 07:36
            </p>
          </div>
        </section>

        {/* Ranked flags */}
        <div className="space-y-3">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[14px] font-semibold">Ranked discrepancies</h2>
            <p className="text-[11.5px] text-muted-foreground">
              Ordered by credit impact, not by the order they were found
            </p>
          </div>

          {FLAGS.map((f) => (
            <FlagCard
              key={f.id}
              flag={f}
              appraisalId={a.id}
              expanded={open === f.id}
              onToggle={() => setOpen(open === f.id ? null : f.id)}
              evidenceKey={evidence[f.id] ?? null}
              onEvidence={(k) => setEvidence({ ...evidence, [f.id]: evidence[f.id] === k ? null : k })}
              monthsOpen={monthsOpen}
              onMonths={() => setMonthsOpen((v) => !v)}
            />
          ))}
        </div>

        {/* Carry-forward */}
        <Panel
          title="Carries into the memo"
          subtitle="Accepted findings become paragraphs in the draft risk narrative, each keeping its evidence trail."
          action={
            <Link
              to="/appraisals/$id/draft"
              params={{ id: a.id }}
              className="text-[12px] font-medium text-primary hover:underline"
            >
              Open draft risk narrative
            </Link>
          }
        >
          <ul className="divide-y divide-border">
            {FLAGS.map((f) => {
              const adj = s.adjudications[f.id];
              return (
                <li key={f.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-[12.5px]">
                  <span className="w-24 shrink-0 font-mono text-[11.5px] text-muted-foreground">{f.id}</span>
                  <span className="min-w-0 flex-1 text-foreground">{f.memoSection}</span>
                  {adj ? (
                    <span className={cn("rounded border px-1.5 py-0.5 text-[11px] font-medium", OUTCOME_TONE[adj.outcome])}>
                      {OUTCOME_LABEL[adj.outcome]}
                    </span>
                  ) : (
                    <span className="rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[11px] text-muted-foreground">
                      Open — not yet carried
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </Panel>
      </div>
    </div>
  );
}

function SummaryCard({
  severity,
  count,
  caption,
  blocking,
}: {
  severity: Severity;
  count: number;
  caption: string;
  blocking?: boolean;
}) {
  return (
    <div className={cn("rounded border bg-surface p-3", count > 0 ? SEVERITY_TONE[severity].split(" ")[0] : "border-border")}>
      <div className="flex items-center justify-between">
        <p className="field-label">{SEVERITY_LABEL[severity]}</p>
        {blocking && <span className="rounded bg-critical px-1.5 py-0.5 text-[10px] font-medium text-white">Blocking</span>}
      </div>
      <p className="mt-1 flex items-baseline gap-2">
        <span className="text-[24px] font-semibold leading-none tabular">{count}</span>
        <span className={cn("h-2 w-10 rounded", count > 0 ? SEVERITY_BAR[severity] : "bg-muted")} />
      </p>
      <p className="mt-2 text-[11.5px] leading-snug text-muted-foreground">
        {count > 0 ? caption : "Cleared — adjudicated and recorded"}
      </p>
    </div>
  );
}

function FlagCard({
  flag,
  appraisalId,
  expanded,
  onToggle,
  evidenceKey,
  onEvidence,
  monthsOpen,
  onMonths,
}: {
  flag: Flag;
  appraisalId: string;
  expanded: boolean;
  onToggle: () => void;
  evidenceKey: string | null;
  onEvidence: (k: string) => void;
  monthsOpen: boolean;
  onMonths: () => void;
}) {
  const s = useXVState();
  const adj = s.adjudications[flag.id];
  const owner = ownerOf(s, flag);
  const notes = s.notes.filter((n) => n.flagId === flag.id);
  const [outcome, setOutcome] = useState<Outcome | null>(null);
  const [rationale, setRationale] = useState("");
  const [note, setNote] = useState("");
  const [noteOpen, setNoteOpen] = useState(false);
  const [reassignOpen, setReassignOpen] = useState(false);

  const figure = flag.figures.find((f) => f.key === evidenceKey) ?? null;
  const blockingOpen = flag.blocking && !adj;

  const submit = () => {
    if (!outcome || rationale.trim().length < 12) {
      toast.error("A written reason is required", {
        description: "CCB policy records the analyst's reasoning against every adjudicated flag.",
      });
      return;
    }
    adjudicate(flag.id, outcome, rationale.trim(), CURRENT_USER.name);
    setOutcome(null);
    setRationale("");
    toast.success(`${flag.id} adjudicated`, {
      description:
        outcome === "accepted"
          ? `Carried into the memo under "${flag.memoSection}".`
          : outcome === "resolved"
            ? "Closed with evidence. Removed from the exception queue."
            : "Query raised. The flag stays open and keeps its blocking state.",
    });
  };

  const draftNote = () => {
    setOutcome("accepted");
    setRationale(
      flag.id === "XV-0418-01"
        ? "Declared FY2025 turnover of INR 142.31 cr is unsupported: GST outward supplies are INR 119.83 cr and customer credits into the two consented accounts are INR 121.44 cr, a shortfall of INR 22.48 cr and INR 20.87 cr respectively. The two independent sources agree with each other to within INR 1.61 cr, which makes an extraction or classification error unlikely. Pending the borrower's reconciliation, the assessment is run on the lower independently evidenced turnover of INR 121.44 cr and the limit is sized accordingly."
        : flag.id === "XV-0418-02"
          ? "An unsecured NBFC obligation to Crestline Financial Services Ltd of INR 4,37,500 per month, INR 52.50 lakh a year, is evident in twelve of twelve months of the Meridian 4471 statement but absent from the declaration of borrowings. Total debt and debt service are restated to include an implied residual of approximately INR 1.85 cr; DSCR falls from 1.61 to 1.44, which remains above the 1.25 policy floor."
          : "Meridian Auto Systems Ltd is 38.4% of FY2025 sales against CCB's 35% single-buyer soft cap, and the top three buyers are 61.2% against a 60% cap. Mitigants on file are a supply contract running to March 2028 and a clean 45-day payment record. Reported as a soft-cap breach with a covenant to report any loss of the OEM programme within 15 days.",
    );
    toast("Risk note drafted by copilot", {
      description: "Review and edit before you adjudicate — the wording is yours to sign off.",
    });
  };

  return (
    <section
      id={flag.id}
      className={cn(
        "overflow-hidden rounded border bg-surface",
        blockingOpen ? "border-critical/40 shadow-[0_0_0_1px_var(--critical-soft)]" : "border-border",
      )}
    >
      <div className={cn("flex items-stretch", adj && "opacity-95")}>
        <div className={cn("w-1 shrink-0", SEVERITY_BAR[flag.severity])} />
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex min-w-0 flex-1 items-start gap-3 px-4 py-3 text-left hover:bg-surface-muted"
        >
          <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded bg-surface-muted text-[11.5px] font-semibold tabular text-muted-foreground">
            {flag.rank}
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2">
              <span className={cn("rounded border px-1.5 py-0.5 text-[10.5px] font-medium", SEVERITY_TONE[flag.severity])}>
                {SEVERITY_LABEL[flag.severity]}
              </span>
              {blockingOpen && (
                <span className="inline-flex items-center gap-1 rounded bg-critical px-1.5 py-0.5 text-[10.5px] font-medium text-white">
                  <Lock className="h-3 w-3" /> Blocks submission
                </span>
              )}
              {adj && (
                <span className={cn("rounded border px-1.5 py-0.5 text-[10.5px] font-medium", OUTCOME_TONE[adj.outcome])}>
                  {OUTCOME_LABEL[adj.outcome]}
                </span>
              )}
              <span className="font-mono text-[11px] text-muted-foreground">{flag.id}</span>
            </span>
            <span className="mt-1 block text-[14px] font-semibold text-foreground">{flag.title}</span>
            <span className="mt-1 block max-w-4xl text-[12.5px] leading-relaxed text-muted-foreground">
              {flag.summary}
            </span>
            <span className="mt-1.5 block text-[11px] text-muted-foreground">
              {flag.rule} · owner {owner}
            </span>
          </span>
          <ChevronDown className={cn("mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform", expanded && "rotate-180")} />
        </button>
      </div>

      {expanded && (
        <div className="border-t border-border">
          {/* Figures side by side */}
          <div className="grid gap-px bg-border sm:grid-cols-2 lg:grid-cols-3">
            {flag.figures.map((fig) => (
              <FigureCell
                key={fig.key}
                fig={fig}
                appraisalId={appraisalId}
                selected={evidenceKey === fig.key}
                onSelect={() => onEvidence(fig.key)}
              />
            ))}
          </div>

          {/* Gap strip */}
          <dl className="flex flex-wrap gap-x-8 gap-y-2 border-b border-border bg-surface-muted px-4 py-2.5">
            {flag.gaps.map((g) => (
              <div key={g.label}>
                <dt className="field-label">{g.label}</dt>
                <dd className="text-[13px] font-semibold tabular text-foreground">{g.value}</dd>
              </div>
            ))}
          </dl>

          {/* Evidence drawer */}
          {figure && (
            <div className="border-b border-border bg-surface px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[12px] font-semibold text-foreground">{figure.excerptTitle}</p>
                <div className="flex items-center gap-2">
                  <SourceChip source={figure.provenance} />
                  <Link
                    to={figure.to === "spread" ? "/appraisals/$id/spread" : "/appraisals/$id/data"}
                    params={{ id: appraisalId }}
                    hash={figure.anchor ? figure.anchor.slice(1) : ""}
                    className="inline-flex items-center gap-1 text-[12px] font-medium text-primary hover:underline"
                  >
                    Open in {figure.to === "spread" ? "spread" : "data console"}
                    <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              </div>
              <pre className="mt-2 overflow-x-auto rounded border border-border bg-surface-muted px-3 py-2 font-mono text-[11.5px] leading-relaxed text-foreground/85">
                {figure.excerpt.join("\n")}
              </pre>
            </div>
          )}

          {/* Flag-specific detail */}
          {flag.months && (
            <div className="border-b border-border px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-[12px] font-semibold">Month-by-month: where deposits fell short of declared sales</p>
                <button type="button" onClick={onMonths} className="text-[12px] font-medium text-primary hover:underline">
                  {monthsOpen ? "Hide the twelve months" : "Show the twelve months"}
                </button>
              </div>
              <p className="mt-1 text-[12px] leading-relaxed text-muted-foreground">
                GST outward supplies and bank credits track each other closely in every month — never more
                than INR 0.40 cr apart. Neither ever approaches the INR 11.86 cr monthly average implied by
                the audited turnover, so the gap is not a timing difference in one or two months.
              </p>
              {monthsOpen && (
                <div className="mt-2 overflow-x-auto">
                  <table className="w-full min-w-[640px] text-[12.5px]">
                    <thead>
                      <tr className="border-y border-border bg-surface-muted text-left">
                        <th className="px-3 py-1.5 font-medium text-muted-foreground">Month</th>
                        <th className="px-3 py-1.5 text-right font-medium text-muted-foreground">GST outward (cr)</th>
                        <th className="px-3 py-1.5 text-right font-medium text-muted-foreground">Bank credits (cr)</th>
                        <th className="px-3 py-1.5 text-right font-medium text-muted-foreground">Implied by audited (cr)</th>
                        <th className="px-3 py-1.5 text-right font-medium text-muted-foreground">Shortfall (cr)</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {flag.months.map((m) => {
                        const implied = 142.31 / 12;
                        const shortfall = implied - m.credits;
                        return (
                          <tr key={m.month}>
                            <td className="px-3 py-1.5">{m.month}</td>
                            <td className="px-3 py-1.5 text-right tabular">{m.gst.toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-right tabular">{m.credits.toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-right tabular text-muted-foreground">{implied.toFixed(2)}</td>
                            <td className="px-3 py-1.5 text-right tabular font-medium text-critical">
                              {shortfall.toFixed(2)}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot>
                      <tr className="border-t border-border bg-surface-muted font-medium">
                        <td className="px-3 py-1.5">FY2025</td>
                        <td className="px-3 py-1.5 text-right tabular">119.83</td>
                        <td className="px-3 py-1.5 text-right tabular">121.44</td>
                        <td className="px-3 py-1.5 text-right tabular">142.31</td>
                        <td className="px-3 py-1.5 text-right tabular text-critical">20.87</td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
          )}

          {flag.ledger && (
            <div className="border-b border-border px-4 py-3">
              <p className="text-[12px] font-semibold">The recurring debit, as it appears in the statement</p>
              <table className="mt-2 w-full text-[12.5px]">
                <tbody className="divide-y divide-border">
                  {flag.ledger.map((l) => (
                    <tr key={l.date}>
                      <td className="w-28 py-1.5 text-muted-foreground">{l.date}</td>
                      <td className="py-1.5 font-mono text-[11.5px]">{l.narration}</td>
                      <td className="py-1.5 text-right tabular font-medium">{l.amount}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                Four of twelve shown · same amount, same counterparty, same day of month.
              </p>
            </div>
          )}

          {flag.concentration && (
            <div className="border-b border-border px-4 py-3">
              <p className="text-[12px] font-semibold">FY2025 sales by counterparty</p>
              <ul className="mt-2 space-y-1.5">
                {flag.concentration.map((c) => (
                  <li key={c.name} className="flex items-center gap-3 text-[12.5px]">
                    <span className="w-56 shrink-0 truncate text-foreground">{c.name}</span>
                    <span className="h-2 flex-1 overflow-hidden rounded bg-muted">
                      <span
                        className={cn("block h-full rounded", c.share > 35 ? "bg-flag" : "bg-info")}
                        style={{ width: `${c.share}%` }}
                      />
                    </span>
                    <span className="w-14 shrink-0 text-right tabular">{c.share.toFixed(1)}%</span>
                    <span className="w-28 shrink-0 text-right tabular text-muted-foreground">{c.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Copilot reading */}
          <div className="flex gap-2.5 border-b border-border bg-info-soft/50 px-4 py-3">
            <Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
            <div className="min-w-0">
              <p className="text-[12px] font-semibold">Copilot's reading</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-foreground/85">{flag.reading}</p>
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Detected {flag.detected} · {flag.policy}
              </p>
            </div>
          </div>

          {/* Adjudication */}
          <div className="px-4 py-3">
            {adj ? (
              <div className="rounded border border-border bg-surface-muted p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className={cn("rounded border px-1.5 py-0.5 text-[11px] font-medium", OUTCOME_TONE[adj.outcome])}>
                    {OUTCOME_LABEL[adj.outcome]}
                  </p>
                  <p className="text-[11.5px] text-muted-foreground">
                    {adj.by} · {adj.at}
                  </p>
                </div>
                <p className="mt-2 text-[12.5px] leading-relaxed text-foreground/85">{adj.rationale}</p>
                <button
                  type="button"
                  onClick={() => {
                    reopenFlag(flag.id);
                    toast(`${flag.id} reopened`, { description: "The adjudication is retained in the audit trail." });
                  }}
                  className="mt-2 text-[11.5px] font-medium text-primary hover:underline"
                >
                  Reopen this flag
                </button>
              </div>
            ) : (
              <div>
                <p className="field-label">Adjudicate — a decision is required on every flag</p>
                <div className="mt-2 grid gap-2 lg:grid-cols-3">
                  {OUTCOMES.map((o) => (
                    <button
                      key={o.value}
                      type="button"
                      onClick={() => setOutcome(o.value)}
                      className={cn(
                        "rounded border px-3 py-2 text-left transition-colors",
                        outcome === o.value
                          ? "border-primary bg-accent"
                          : "border-border bg-surface hover:border-primary/40 hover:bg-surface-muted",
                      )}
                    >
                      <span className="block text-[12.5px] font-medium text-foreground">{o.label}</span>
                      <span className="mt-0.5 block text-[11.5px] leading-snug text-muted-foreground">{o.help}</span>
                    </button>
                  ))}
                </div>
                <div className="mt-2">
                  <label htmlFor={`r-${flag.id}`} className="field-label">
                    Reason, recorded to the audit trail
                  </label>
                  <textarea
                    id={`r-${flag.id}`}
                    rows={3}
                    value={rationale}
                    onChange={(e) => setRationale(e.target.value)}
                    placeholder="What you concluded and on what evidence…"
                    className="mt-1 w-full resize-y rounded border border-border bg-surface px-3 py-2 text-[12.5px] outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={submit}
                    className="h-8 rounded bg-primary px-3 text-[12.5px] font-medium text-primary-foreground hover:bg-primary/90"
                  >
                    Record adjudication
                  </button>
                  <button
                    type="button"
                    onClick={draftNote}
                    className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
                  >
                    <Sparkles className="h-3.5 w-3.5 text-primary" /> Draft the risk note
                  </button>
                  <button
                    type="button"
                    onClick={() => setReassignOpen((v) => !v)}
                    className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
                  >
                    <UserRoundCog className="h-3.5 w-3.5" /> Reassign
                  </button>
                  <button
                    type="button"
                    onClick={() => setNoteOpen((v) => !v)}
                    className="inline-flex h-8 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium hover:bg-muted"
                  >
                    <MessageSquarePlus className="h-3.5 w-3.5" /> Add a note
                  </button>
                </div>

                {reassignOpen && (
                  <div className="mt-2 flex flex-wrap items-center gap-2 rounded border border-border bg-surface-muted p-2.5">
                    <span className="text-[12px] text-muted-foreground">Owner</span>
                    <select
                      value={owner}
                      onChange={(e) => {
                        reassignFlag(flag.id, e.target.value);
                        setReassignOpen(false);
                        toast(`${flag.id} reassigned`, { description: `Now owned by ${e.target.value}.` });
                      }}
                      className="h-8 rounded border border-border bg-surface px-2 text-[12.5px]"
                    >
                      {REVIEWERS.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {noteOpen && (
                  <div className="mt-2 rounded border border-border bg-surface-muted p-2.5">
                    <textarea
                      rows={2}
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="A note for whoever picks this up next…"
                      className="w-full resize-y rounded border border-border bg-surface px-2.5 py-1.5 text-[12.5px] outline-none focus:ring-1 focus:ring-ring"
                    />
                    <button
                      type="button"
                      disabled={!note.trim()}
                      onClick={() => {
                        addNote(flag.id, note.trim(), CURRENT_USER.name);
                        setNote("");
                        setNoteOpen(false);
                        toast("Note added", { description: `Visible to everyone working ${flag.id}.` });
                      }}
                      className="mt-1.5 h-7 rounded bg-primary px-2.5 text-[12px] font-medium text-primary-foreground disabled:opacity-40"
                    >
                      Save note
                    </button>
                  </div>
                )}
              </div>
            )}

            {notes.length > 0 && (
              <ul className="mt-3 space-y-1.5 border-t border-border pt-2.5">
                {notes.map((n) => (
                  <li key={n.id} className="text-[12px] leading-relaxed text-foreground/85">
                    <span className="font-medium">{n.by}</span>{" "}
                    <span className="text-muted-foreground">· {n.at}</span>
                    <span className="block text-muted-foreground">{n.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

function FigureCell({
  fig,
  appraisalId,
  selected,
  onSelect,
}: {
  fig: EvidenceFigure;
  appraisalId: string;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <div className={cn("bg-surface p-3", selected && "bg-accent")}>
      <button type="button" onClick={onSelect} className="block w-full text-left">
        <span className="flex items-center justify-between gap-2">
          <span className="field-label">{fig.label}</span>
          {fig.independent ? (
            <span className="inline-flex items-center gap-1 rounded border border-positive/30 bg-positive-soft px-1.5 py-0.5 text-[10px] font-medium text-positive">
              <CheckCircle2 className="h-2.5 w-2.5" /> Independent
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
              <Info className="h-2.5 w-2.5" /> Borrower-supplied
            </span>
          )}
        </span>
        <span className="mt-1 block text-[19px] font-semibold leading-none tabular text-foreground">{fig.value}</span>
        <span className="mt-1.5 block text-[11.5px] leading-snug text-muted-foreground">{fig.basis}</span>
        <span className="mt-1.5 inline-flex items-center gap-1 text-[11.5px] font-medium text-primary">
          <FileSearch className="h-3 w-3" /> {selected ? "Hide evidence" : "Open the evidence"}
        </span>
      </button>
      <Link
        to={fig.to === "spread" ? "/appraisals/$id/spread" : "/appraisals/$id/data"}
        params={{ id: appraisalId }}
        hash={fig.anchor ? fig.anchor.slice(1) : ""}
        className="mt-1 inline-flex items-center gap-1 text-[11.5px] text-muted-foreground hover:text-primary hover:underline"
      >
        Trace to {fig.to === "spread" ? "the spread" : "the source"} <ExternalLink className="h-2.5 w-2.5" />
      </Link>
    </div>
  );
}
