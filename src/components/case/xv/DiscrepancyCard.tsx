import { useId, useState } from "react";
import { ChevronDown, Columns2, Lock } from "lucide-react";
import type { Finding, GapLeg, XvItem } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { Details } from "@/components/common/Details";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import {
  cardElementId,
  columnValue,
  comparedColumns,
  comparesText,
  factValue,
  findingTitle,
  joinList,
  ownerName,
} from "@/domain/crossVerification";
import { cn } from "@/lib/utils";
import { Adjudication } from "./Adjudication";
import { EvidencePanel } from "./EvidencePanel";
import { LineByLine } from "./LineByLine";
import { SourceColumns } from "./SourceColumns";
import { DECISION_TONE, SEVERITY_BAR, SEVERITY_TONE } from "./styles";

/** One discrepancy, ranked. Collapsed: what it is and how serious. Expanded: the rule, the
 * sources side by side, the gap on each leg, the rows behind a source, the line-by-line
 * comparison and the decision. */
export function DiscrepancyCard({
  caseId,
  item,
  expanded,
  onToggle,
}: {
  caseId: string;
  item: XvItem;
  expanded: boolean;
  onToggle: () => void;
}) {
  const f = item.finding;
  const [active, setActive] = useState<string | null>(null);
  const bodyId = useId();
  const blockingOpen = f.blocking && !item.adjudicated;
  const escalatedOpen = Boolean(item.escalation) && !item.adjudicated;
  const column = (f.columns ?? []).find((c) => c.key === active);
  const detail = f.detail && f.detail.rows.length > 0 ? f.detail : null;
  return (
    <section
      id={cardElementId(f.id)}
      className={cn(
        "scroll-mt-4 overflow-hidden rounded border bg-surface",
        blockingOpen
          ? "border-destructive/40 shadow-[0_0_0_1px_var(--critical-soft)]"
          : "border-border",
      )}
      data-testid={`xv-card-${f.id}`}
      data-expanded={expanded ? "true" : "false"}
      data-rule={f.rule_id}
      data-severity={f.severity}
      data-rank={item.rank ?? undefined}
      data-adjudicated={item.adjudicated ? "true" : "false"}
    >
      <div className="flex items-stretch">
        <div className={cn("w-1 shrink-0", SEVERITY_BAR[f.severity])} aria-hidden />
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-controls={expanded ? bodyId : undefined}
          className="flex min-w-0 flex-1 items-start gap-3 px-4 py-3 text-left hover:bg-surface-muted"
          data-testid="xv-card-toggle"
        >
          <span
            className="tabular mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded bg-surface-muted text-[11.5px] font-semibold text-muted-foreground"
            data-testid="xv-rank"
          >
            {item.rank}
          </span>
          <span className="min-w-0 flex-1">
            <span className="flex flex-wrap items-center gap-2">
              <Chip tone={SEVERITY_TONE[f.severity]}>{t(`severity.${f.severity}`)}</Chip>
              {blockingOpen && (
                <span className="inline-flex shrink-0 items-center gap-1 rounded bg-destructive px-1.5 py-0.5 text-[10.5px] font-medium text-destructive-foreground">
                  <Lock className="h-3 w-3" aria-hidden />{" "}
                  {t("crossVerification.card.blocksSubmission")}
                </span>
              )}
              {item.decision && (
                <Chip tone={DECISION_TONE[item.decision.decision]}>
                  {t(`crossVerification.decided.${item.decision.decision}`)}
                </Chip>
              )}
              {escalatedOpen && (
                <Chip tone={DECISION_TONE.escalate}>{t("crossVerification.decided.escalate")}</Chip>
              )}
              <span className="min-w-0 break-words font-mono text-[11px] text-muted-foreground">
                {[f.ref, f.rule_id, f.scope].filter(Boolean).join(" · ")}
              </span>
            </span>
            <span className="mt-1 block break-words text-[14px] font-semibold text-foreground">
              {findingTitle(f)}
            </span>
            {!expanded && <CardFigures finding={f} />}
            {f.explanation && (
              <span className="mt-1 block max-w-4xl break-words text-[12.5px] leading-relaxed text-muted-foreground">
                {f.explanation}
              </span>
            )}
          </span>
          <ChevronDown
            className={cn(
              "mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform",
              expanded && "rotate-180",
            )}
            aria-hidden
          />
        </button>
      </div>

      {expanded && (
        <div id={bodyId} className="border-t border-border">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-border px-4 py-2">
            <RuleLine item={item} />
            <ComparePages caseId={caseId} finding={f} />
          </div>
          <SourceColumns
            caseId={caseId}
            finding={f}
            active={active}
            onToggle={(key) => setActive(active === key ? null : key)}
          />
          <GapRow finding={f} />
          {column && (
            <EvidencePanel caseId={caseId} column={column} onClose={() => setActive(null)} />
          )}
          {detail && (
            <div className="border-b border-border px-4 py-3">
              <Details
                title={t("crossVerification.lineByLine", { n: detail.rows.length })}
                testId="xv-line-by-line"
              >
                <LineByLine detail={detail} />
              </Details>
            </div>
          )}
          <Adjudication caseId={caseId} item={item} />
        </div>
      )}
    </section>
  );
}

/** "Rule TO-01 — what it compares, tolerance 10% · owner …" */
/** A collapsed card's amounts, from the key-figure lines the engine wrote for it: the figures it
 * compared, large, the differing one red, each over its source, then how far apart they are. Only
 * lines with amounts (the turnover checks, a lender's sanctioned amounts); open, the card's source
 * columns show the same figures. */
function CardFigures({ finding }: { finding: Finding }) {
  const lines = (finding.highlights ?? [])
    .filter((line) => (line.facts ?? []).some((fact) => fact.unit === "inr"))
    .slice(0, 2);
  if (lines.length === 0) return null;
  // A turnover line's label repeats the card's title and year; a lender's names the lender.
  const labelled = finding.area !== "turnover";
  return (
    <span className="mt-2 block space-y-2" data-testid="xv-card-figures">
      {lines.map((line, i) => (
        <span key={`${line.label}-${i}`} className="block">
          {labelled && (
            <span className="block break-words text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
              {line.label}
            </span>
          )}
          <span className="flex flex-wrap items-end gap-x-5 gap-y-1.5">
            {(line.facts ?? []).map((fact, j) => (
              <span
                key={j}
                className="flex min-w-0 flex-col"
                data-testid="xv-card-figure"
                data-differs={fact.differs ? "true" : "false"}
              >
                <span
                  className={cn(
                    "tabular text-[18px] font-semibold leading-tight",
                    fact.differs ? "text-destructive" : "text-foreground",
                  )}
                >
                  {factValue(fact)}
                </span>
                {fact.differs && (
                  <span className="sr-only">{t("crossVerification.column.differs")}</span>
                )}
                <span className="break-words text-[11px] text-muted-foreground">{fact.label}</span>
              </span>
            ))}
            {line.note && (
              <span
                className="break-words pb-[15px] text-[12px] font-medium text-foreground/80"
                data-testid="xv-card-figures-note"
              >
                {line.note}
              </span>
            )}
          </span>
        </span>
      ))}
    </span>
  );
}

function RuleLine({ item }: { item: XvItem }) {
  const f = item.finding;
  const tolerance = f.gap_tolerance || f.tolerance;
  const params = {
    rule: f.rule_id,
    compares: comparesText(f),
    owner: ownerName(item) ?? t("crossVerification.ownerUnassigned"),
  };
  return (
    <p
      className="min-w-0 break-words text-[11.5px] text-muted-foreground"
      data-testid="xv-rule-line"
    >
      {tolerance
        ? t("crossVerification.card.ruleLine", { ...params, tolerance })
        : t("crossVerification.card.ruleLineNoTolerance", params)}
      {f.policy_ref && (
        <>
          {" · "}
          {f.policy_ref}
        </>
      )}
    </p>
  );
}

/** The pages the sources were read from, side by side in the viewer (F-16.2). */
function ComparePages({ caseId, finding }: { caseId: string; finding: Finding }) {
  const viewer = useDocViewer();
  const columns = comparedColumns(finding);
  const first = columns[0]?.evidence?.[0];
  if (columns.length < 2 || !first) return null;
  return (
    <button
      type="button"
      onClick={() =>
        viewer.open({
          caseId,
          documentId: first.document_id,
          compare: columns.flatMap((c) => {
            const e = c.evidence?.[0];
            return e
              ? [
                  {
                    documentId: e.document_id,
                    page: e.page,
                    bbox: e.bbox ?? null,
                    label: `${c.label}: ${columnValue(c)}`,
                  },
                ]
              : [];
          }),
        })
      }
      className="inline-flex shrink-0 items-center gap-1 text-[11.5px] font-medium text-primary hover:underline"
      data-testid="xv-compare"
    >
      <Columns2 className="h-3.5 w-3.5" aria-hidden />
      {t("crossVerification.card.compare")}
    </button>
  );
}

/** One leg: "INR 22.48 cr · 15.8% of audited", parts the engine did not give left out. */
function legText(g: GapLeg): string {
  const parts: string[] = [];
  if (g.amount !== null && g.amount !== undefined) parts.push(formatInr(g.amount));
  if (g.pct !== null && g.pct !== undefined) {
    parts.push(
      g.base
        ? t("crossVerification.gap.pctOf", { pct: g.pct, base: g.base })
        : t("crossVerification.gap.pct", { pct: g.pct }),
    );
  }
  return parts.join(" · ") || "—";
}

/** The gap on each leg, as the engine measured it, and the tolerance it breached; for a check
 * without amounts, the difference in words. Only a leg measured as a percentage is said to breach
 * the percentage tolerance; a leg without one (a lender not declared at all) states its problem
 * in its own label. */
function GapRow({ finding }: { finding: Finding }) {
  const gaps = finding.gaps ?? [];
  if (gaps.length === 0) {
    return finding.mismatch ? (
      <p
        className="break-words border-b border-border bg-surface-muted px-4 py-2.5 text-[12.5px] font-medium text-foreground"
        data-testid="xv-mismatch"
      >
        {finding.mismatch}
      </p>
    ) : null;
  }
  const breached = gaps.filter((g) => g.breached && g.pct !== null && g.pct !== undefined);
  return (
    <dl
      className="flex flex-wrap gap-x-8 gap-y-2 border-b border-border bg-surface-muted px-4 py-2.5"
      data-testid="xv-gap-row"
    >
      {gaps.map((g, i) => (
        <div
          key={`${g.label}-${i}`}
          className="min-w-0"
          data-testid="xv-gap-leg"
          data-breached={g.breached ? "true" : "false"}
        >
          <dt className="field-label break-words">{g.label}</dt>
          <dd
            className={cn(
              "tabular break-words text-[13px] font-semibold",
              g.breached ? "text-destructive" : "text-foreground",
            )}
          >
            {legText(g)}
          </dd>
        </div>
      ))}
      {finding.gap_tolerance && breached.length > 0 && (
        <div className="min-w-0" data-testid="xv-tolerance-line">
          <dt className="field-label">
            {t("crossVerification.gap.tolerance", { bank: t("tenant.bank.short") })}
          </dt>
          <dd className="break-words text-[13px] font-semibold text-foreground">
            {t("crossVerification.gap.breachedOn", {
              tolerance: finding.gap_tolerance,
              legs: joinList([...new Set(breached.map((g) => g.legs))]),
            })}
          </dd>
        </div>
      )}
    </dl>
  );
}

/** A check that is not a discrepancy, as the turnover panel shows it beside the figures: where it
 * stands, what it compared, the sources side by side with the rows behind each, and the gap; no
 * decision, since there is nothing to decide. */
export function CheckPanel({ caseId, item }: { caseId: string; item: XvItem }) {
  const f = item.finding;
  const [active, setActive] = useState<string | null>(null);
  const column = (f.columns ?? []).find((c) => c.key === active);
  return (
    <section
      className="overflow-hidden rounded border border-border bg-surface"
      data-testid="xv-check-panel"
      data-finding={f.id}
      data-outcome={f.outcome}
    >
      <div className="px-4 py-3">
        <span className="flex flex-wrap items-center gap-2">
          <Chip
            tone={f.outcome === "pass" ? "positive" : f.outcome === "incomplete" ? "flag" : "muted"}
          >
            {t(
              `crossVerification.figures.${f.outcome === "pass" ? "matches" : f.outcome === "incomplete" ? "incomplete" : "notApplicable"}`,
            )}
          </Chip>
          <span className="min-w-0 break-words font-mono text-[11px] text-muted-foreground">
            {[f.ref, f.rule_id, f.scope].filter(Boolean).join(" · ")}
          </span>
        </span>
        <span className="mt-1 block break-words text-[14px] font-semibold text-foreground">
          {comparesText(f)}
        </span>
        {f.explanation && (
          <span className="mt-1 block break-words text-[12.5px] leading-relaxed text-muted-foreground">
            {f.explanation}
          </span>
        )}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-y border-border px-4 py-2">
        <RuleLine item={item} />
        <ComparePages caseId={caseId} finding={f} />
      </div>
      <SourceColumns
        caseId={caseId}
        finding={f}
        active={active}
        onToggle={(key) => setActive(active === key ? null : key)}
      />
      <GapRow finding={f} />
      {column && <EvidencePanel caseId={caseId} column={column} onClose={() => setActive(null)} />}
    </section>
  );
}
