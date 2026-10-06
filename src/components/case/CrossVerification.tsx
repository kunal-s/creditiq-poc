import { useMemo, useState } from "react";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  FileText,
  MinusCircle,
  User,
} from "lucide-react";
import type {
  CaseFacts,
  Evidence,
  Finding,
  FindingOutcome,
  FindingSide,
  ReviewItem,
} from "@/api/types";
import { Chip, Panel } from "@/components/common/Panel";
import { Details } from "@/components/common/Details";
import { QueryView } from "@/components/common/States";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { decisionButton } from "@/components/review/styles";
import { t } from "@/config/terminology";
import { formatInr } from "@/domain/cases";
import { useDocumentTypes } from "@/domain/documents";
import { countOutcomes, OUTCOMES, useFacts, useFindings } from "@/domain/findings";
import { useDecideReview, useReviewQueue } from "@/domain/review";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";

// The Cross-verification tab (FRD §6, F-19 mock): every rule's outcome, the
// failures first with both sides' values and evidence, then the aligned
// facts the rules compared (F-18).

const OUTCOME_ICON = {
  fail: AlertTriangle,
  incomplete: CircleDashed,
  pass: CheckCircle2,
  not_applicable: MinusCircle,
} as const;

const SEVERITY_TONE = {
  serious: "text-destructive",
  moderate: "text-flag-foreground",
  mild: "text-info",
} as const;

function value(v: FindingSide["value"]): string {
  if (v === null || v === undefined || v === "") return "—";
  return typeof v === "number" ? formatInr(v) : String(v);
}

function EvidenceLinks({ caseId, evidence }: { caseId: string; evidence: Evidence[] }) {
  const viewer = useDocViewer();
  if (evidence.length === 0) return null;
  const shown = evidence.slice(0, 3);
  return (
    <span className="inline-flex flex-wrap items-center gap-1">
      {shown.map((e, i) => (
        <button
          key={`${e.document_id}-${e.page}-${i}`}
          type="button"
          onClick={() =>
            viewer.open({ caseId, documentId: e.document_id, page: e.page, bbox: e.bbox ?? null })
          }
          className="inline-flex items-center gap-0.5 rounded border border-border px-1.5 py-0.5 text-[11px] font-medium text-primary hover:bg-muted"
          data-testid="finding-evidence"
        >
          <FileText className="h-3 w-3" /> p{e.page}
        </button>
      ))}
      {evidence.length > shown.length && (
        <span className="text-[11px] text-muted-foreground">
          {t("crossCheck.morePages", { n: evidence.length - shown.length })}
        </span>
      )}
    </span>
  );
}

/** Confirm a failed check as valid, or waive it with the reason. */
function FindingDecision({ item }: { item: ReviewItem }) {
  const canDecide = useCan("review.decide");
  const decide = useDecideReview();
  const [waiving, setWaiving] = useState(false);
  const [reason, setReason] = useState("");
  if (item.status === "decided") {
    return (
      <p className="text-[11.5px] text-muted-foreground" data-testid="finding-decided">
        {item.decision === "confirm"
          ? t("crossCheck.decidedValid", { who: item.decided_by ?? "" })
          : t("crossCheck.decidedNotValid", {
              who: item.decided_by ?? "",
              reason: item.reason ?? "",
            })}
      </p>
    );
  }
  if (!canDecide) return null;
  const send = (decision: "confirm" | "waive") =>
    decide.mutate(
      {
        id: item.id,
        body: { decision, value: null, reason: decision === "waive" ? reason.trim() : null },
      },
      {
        onSuccess: () => toast.success(t("review.recorded")),
        onError: (error) => toast.error(error instanceof Error ? error.message : String(error)),
      },
    );
  return (
    <div className="flex flex-wrap items-center gap-1.5" data-testid="finding-decision">
      <button
        type="button"
        disabled={decide.isPending}
        onClick={() => send("confirm")}
        className={`${decisionButton} border-positive/40 bg-surface text-positive hover:bg-positive-soft`}
        data-testid="finding-valid"
      >
        {t("crossCheck.valid")}
      </button>
      {!waiving ? (
        <button
          type="button"
          onClick={() => setWaiving(true)}
          className={`${decisionButton} border-border bg-surface text-foreground hover:bg-muted`}
          data-testid="finding-not-valid"
        >
          {t("crossCheck.notValid")}
        </button>
      ) : (
        <>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder={t("crossCheck.reason")}
            aria-label={t("crossCheck.reason")}
            className="h-7 min-w-[16rem] flex-1 rounded border border-border bg-surface px-2 text-[12px] outline-none focus:border-primary/60"
            data-testid="finding-reason"
            autoFocus
          />
          <button
            type="button"
            disabled={decide.isPending || reason.trim() === ""}
            onClick={() => send("waive")}
            className="h-7 rounded bg-primary px-2.5 text-[11.5px] font-medium text-primary-foreground disabled:opacity-40"
            data-testid="finding-waive"
          >
            {t("crossCheck.saveNotValid")}
          </button>
        </>
      )}
    </div>
  );
}

function FindingRow({
  caseId,
  finding,
  item,
}: {
  caseId: string;
  finding: Finding;
  item: ReviewItem | undefined;
}) {
  const Icon = OUTCOME_ICON[finding.outcome];
  const failed = finding.outcome === "fail";
  return (
    <li
      className="space-y-2 px-4 py-3"
      data-testid="finding"
      data-rule={finding.rule_id}
      data-outcome={finding.outcome}
    >
      <div className="flex flex-wrap items-start gap-2">
        <Icon
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0",
            failed
              ? SEVERITY_TONE[finding.severity]
              : finding.outcome === "pass"
                ? "text-positive"
                : "text-muted-foreground",
          )}
        />
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 text-[13px] font-medium text-foreground">
            {finding.title}
            {failed && (
              <Chip tone={finding.severity === "serious" ? "critical" : "flag"}>
                {t(`severity.${finding.severity}`)}
              </Chip>
            )}
            {failed && finding.blocking && (
              <Chip tone="critical" upper>
                {t("checklist.blocking")}
              </Chip>
            )}
          </p>
          {finding.explanation && (
            <p
              className="mt-0.5 text-[12.5px] text-muted-foreground"
              data-testid="finding-explanation"
            >
              {finding.explanation}
            </p>
          )}
        </div>
      </div>

      {finding.sides.length > 0 && (failed || finding.outcome === "incomplete") && (
        <dl className="ml-6 space-y-1 rounded border border-border bg-surface-muted/40 px-3 py-2 text-[12px]">
          {finding.sides.map((side, i) => (
            <div
              key={`${side.label}-${i}`}
              className="flex flex-wrap items-center gap-x-3 gap-y-1"
              data-testid="finding-side"
            >
              <dt className="min-w-[12rem] text-muted-foreground">{side.label}</dt>
              <dd className="tabular min-w-0 flex-1 break-words font-medium text-foreground">
                {value(side.value)}
              </dd>
              {side.relies_on_manual && (
                <Chip tone="flag">
                  <User className="h-3 w-3" /> {t("crossCheck.manual")}
                </Chip>
              )}
              <EvidenceLinks caseId={caseId} evidence={side.evidence ?? []} />
            </div>
          ))}
        </dl>
      )}
      {finding.sides.length > 0 && (failed || finding.outcome === "incomplete") && (
        <div className="ml-6">
          <Details testId="finding-details">
            <dl className="space-y-1 text-[12px]">
              <div className="flex gap-2">
                <dt className="w-24 shrink-0 text-muted-foreground">{t("crossCheck.check")}</dt>
                <dd className="tabular">{finding.rule_id}</dd>
              </div>
              {finding.tolerance && (
                <div className="flex gap-2">
                  <dt className="w-24 shrink-0 text-muted-foreground">
                    {t("crossCheck.allowedDifference")}
                  </dt>
                  <dd>{finding.tolerance}</dd>
                </div>
              )}
            </dl>
          </Details>
        </div>
      )}
      {failed && item && (
        <div className="ml-6">
          <FindingDecision item={item} />
        </div>
      )}
    </li>
  );
}

/** Every rule's outcome, filterable; fails first (F-19.3). */
export function FindingsPanel({ caseId }: { caseId: string }) {
  const findings = useFindings(caseId);
  const review = useReviewQueue({ caseId, includeDecided: true });
  const [filter, setFilter] = useState<FindingOutcome>("fail");
  const items = useMemo(() => {
    const byRef = new Map<string, ReviewItem>();
    for (const i of review.data ?? []) if (i.kind === "finding") byRef.set(i.ref, i);
    return byRef;
  }, [review.data]);

  return (
    <QueryView
      query={findings}
      isEmpty={(list) => list.length === 0}
      empty={{ title: t("crossCheck.emptyTitle"), description: t("crossCheck.emptyDescription") }}
    >
      {(list) => {
        const counts = countOutcomes(list);
        const current = counts[filter] > 0 || filter !== "fail" ? filter : "incomplete";
        const shown = list.filter((f) => f.outcome === current);
        return (
          <Panel
            title={t("crossCheck.title")}
            subtitle={t("crossCheck.summary", {
              rules: new Set(list.map((f) => f.rule_id)).size,
              fail: counts.fail,
              incomplete: counts.incomplete,
              pass: counts.pass,
            })}
            testId="findings"
          >
            <div className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2">
              {OUTCOMES.map((o) => (
                <button
                  key={o}
                  type="button"
                  aria-pressed={current === o}
                  onClick={() => setFilter(o)}
                  data-testid={`findings-filter-${o}`}
                  className={cn(
                    "rounded border px-2 py-0.5 text-[11.5px] font-medium transition-colors",
                    current === o
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-surface text-muted-foreground hover:bg-muted",
                  )}
                >
                  {t(`crossCheck.filter.${o}`, { n: counts[o] })}
                </button>
              ))}
            </div>
            {shown.length === 0 ? (
              <p className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">
                {t("crossCheck.noneHere")}
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {shown.map((f) => (
                  <FindingRow
                    key={f.id}
                    caseId={caseId}
                    finding={f}
                    item={items.get(`finding:${f.id}`)}
                  />
                ))}
              </ul>
            )}
          </Panel>
        );
      }}
    </QueryView>
  );
}

/** The aligned facts the checks compared (F-18 acceptance: inspectable). */
export function FactsPanels({ caseId }: { caseId: string }) {
  const facts = useFacts(caseId);
  return (
    <QueryView query={facts}>
      {(f) => (
        <div className="grid gap-4 xl:grid-cols-2">
          <TurnoverPanel facts={f} caseId={caseId} />
          <CreditsPanel facts={f} caseId={caseId} />
          <ObligationsPanel facts={f} caseId={caseId} />
          <AccountsPanel facts={f} caseId={caseId} />
        </div>
      )}
    </QueryView>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="px-4 py-4 text-[12.5px] text-muted-foreground">{text}</p>;
}

function TurnoverPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  return (
    <Panel title={t("facts.turnover")} subtitle={t("facts.turnoverHelp")} testId="facts-turnover">
      {facts.turnover.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <div className="divide-y divide-border">
          {facts.turnover.map((y) => (
            <div key={y.fy} className="px-4 py-2.5">
              <p className="text-[12.5px] font-semibold">{y.fy}</p>
              <ul className="mt-1 space-y-1 text-[12px]">
                {y.figures.map((fig) => (
                  <li key={fig.source} className="flex flex-wrap items-center gap-x-3">
                    <span className="min-w-[14rem] text-muted-foreground">{fig.label}</span>
                    <span className="tabular font-medium">{value(fig.value)}</span>
                    {fig.months_covered !== null && fig.months_covered !== undefined && (
                      <span
                        className={cn(
                          "text-[11px]",
                          fig.months_covered < 12
                            ? "text-flag-foreground"
                            : "text-muted-foreground",
                        )}
                      >
                        {t("facts.months", { n: fig.months_covered })}
                      </span>
                    )}
                    <EvidenceLinks caseId={caseId} evidence={fig.evidence ?? []} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function CreditsPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  return (
    <Panel title={t("facts.credits")} subtitle={t("facts.creditsHelp")} testId="facts-credits">
      {facts.credits.length === 0 ? (
        <Empty text={t("facts.noTransactions")} />
      ) : (
        <div className="divide-y divide-border">
          {facts.credits.map((c) => (
            <div key={c.account} className="px-4 py-2.5 text-[12px]">
              <p className="text-[12.5px] font-semibold">{c.account}</p>
              <p className="tabular mt-0.5 text-muted-foreground">
                {t("facts.creditsLine", {
                  gross: formatInr(c.gross),
                  excluded: formatInr(c.excluded),
                  net: formatInr(c.net),
                })}
              </p>
              {c.exclusions.length > 0 && (
                <ul className="mt-1.5 space-y-0.5">
                  {c.exclusions.slice(0, 8).map((e, i) => (
                    <li
                      key={i}
                      className="flex flex-wrap items-center gap-x-2"
                      data-testid="exclusion"
                    >
                      <Chip tone="muted">{e.label}</Chip>
                      <span className="tabular">{formatInr(e.amount)}</span>
                      <span className="min-w-0 flex-1 truncate text-muted-foreground">
                        {e.date} · {e.narration}
                      </span>
                      <EvidenceLinks caseId={caseId} evidence={e.evidence ?? []} />
                    </li>
                  ))}
                  {c.exclusions.length > 8 && (
                    <li className="text-muted-foreground">
                      {t("crossCheck.morePages", { n: c.exclusions.length - 8 })}
                    </li>
                  )}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function ObligationsPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  return (
    <Panel
      title={t("facts.obligations")}
      subtitle={t("facts.obligationsHelp")}
      testId="facts-obligations"
    >
      {facts.obligations.length === 0 && facts.facilities.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <div className="divide-y divide-border text-[12px]">
          {facts.obligations.map((o) => (
            <div
              key={`${o.lender}-${o.account}`}
              className="flex flex-wrap items-center gap-x-3 px-4 py-2"
            >
              <span className="font-medium">{o.lender}</span>
              <span className="tabular">
                {t("facts.emiLine", { amount: formatInr(o.typical_amount), n: o.months.length })}
              </span>
              <span className="text-muted-foreground">{o.account}</span>
              <EvidenceLinks caseId={caseId} evidence={o.evidence ?? []} />
            </div>
          ))}
          {facts.facilities.map((f, i) => (
            <div key={`${f.label}-${i}`} className="flex flex-wrap items-center gap-x-3 px-4 py-2">
              <span className="font-medium">{f.lender}</span>
              <span className="text-muted-foreground">
                {[f.facility, f.amount ? formatInr(f.amount) : null].filter(Boolean).join(" · ")}
              </span>
              <Chip tone="muted">{f.label}</Chip>
              <EvidenceLinks caseId={caseId} evidence={f.evidence ?? []} />
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

function AccountsPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const types = useDocumentTypes();
  return (
    <Panel title={t("facts.accounts")} subtitle={t("facts.accountsHelp")} testId="facts-accounts">
      {facts.accounts.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <ul className="divide-y divide-border text-[12px]">
          {facts.accounts.map((a) => (
            <li key={a.label} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2">
              <span className="min-w-[10rem] font-medium">{a.label}</span>
              <Chip tone={a.declared ? "positive" : "flag"}>
                {a.declared ? t("facts.declared") : t("facts.notDeclared")}
              </Chip>
              <Chip tone={a.has_statement ? "positive" : "flag"}>
                {a.has_statement ? t("facts.statement") : t("facts.noStatement")}
              </Chip>
              <span className="min-w-0 flex-1 text-muted-foreground">
                {a.sources.map(types.name).join(", ")}
              </span>
              <EvidenceLinks caseId={caseId} evidence={a.evidence ?? []} />
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
