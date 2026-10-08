import { useMemo, useState } from "react";
import { Link } from "@tanstack/react-router";
import { toast } from "sonner";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  Columns2,
  FileText,
  MinusCircle,
  User,
} from "lucide-react";
import type {
  CaseFacts,
  Evidence,
  FactValue,
  Finding,
  FindingArea,
  FindingDetail,
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
import { useFields } from "@/domain/extraction";
import { countOutcomes, OUTCOMES, useFacts, useFindings } from "@/domain/findings";
import { useDecideReview, useReviewQueue } from "@/domain/review";
import { useCan } from "@/domain/session";
import { cn } from "@/lib/utils";

// The Cross-verification tab (FRD §6, F-19 mock; docs/cross-verification-plan.md):
// four outcome tiles, then each area of the file with what its checks found,
// then the checks themselves grouped by area — the failures first, each with
// its sources side by side, the value that differs highlighted, the
// line-by-line detail and the pages behind it — and the aligned facts (F-18).

const AREAS: FindingArea[] = [
  "identity",
  "authority",
  "turnover",
  "tax",
  "financials",
  "accounts",
  "obligations",
];

const OUTCOME_ICON = {
  fail: AlertTriangle,
  incomplete: CircleDashed,
  pass: CheckCircle2,
  not_applicable: MinusCircle,
} as const;

const OUTCOME_TONE = {
  fail: "text-destructive",
  incomplete: "text-flag-foreground",
  pass: "text-positive",
  not_applicable: "text-muted-foreground",
} as const;

const SEVERITY_TONE = {
  serious: "text-destructive",
  moderate: "text-flag-foreground",
  mild: "text-info",
} as const;

const areaOf = (f: Finding): FindingArea => f.area ?? "identity";

function value(v: FindingSide["value"] | undefined): string {
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

// --- The checks ---

export function FindingsPanel({ caseId }: { caseId: string }) {
  const findings = useFindings(caseId);
  const review = useReviewQueue({ caseId, includeDecided: true });
  const [filter, setFilter] = useState<FindingOutcome>("fail");
  const [area, setArea] = useState<FindingArea | null>(null);
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
        const blocking = list.filter((f) => f.outcome === "fail" && f.blocking).length;
        const toDecide = list.filter(
          (f) => f.outcome === "fail" && items.get(`finding:${f.id}`)?.status !== "decided",
        ).length;
        const shown = list.filter(
          (f) => f.outcome === current && (area === null || areaOf(f) === area),
        );
        return (
          <div className="space-y-4">
            <OutcomeTiles
              counts={counts}
              current={current}
              onSelect={setFilter}
              blocking={blocking}
              toDecide={toDecide}
            />
            <AreaGrid list={list} selected={area} onSelect={setArea} />
            <Panel
              title={t("crossCheck.title")}
              subtitle={t("crossCheck.summary", {
                rules: new Set(list.map((f) => f.rule_id)).size,
                fail: counts.fail,
                incomplete: counts.incomplete,
                pass: counts.pass,
              })}
              action={
                area && (
                  <button
                    type="button"
                    onClick={() => setArea(null)}
                    className="text-[11.5px] font-medium text-primary hover:underline"
                    data-testid="findings-all-areas"
                  >
                    {t("crossCheck.allAreas")}
                  </button>
                )
              }
              testId="findings"
            >
              {area && (
                <p className="border-b border-border px-4 py-1.5 text-[11.5px] text-muted-foreground">
                  {t("crossCheck.showingArea", { area: t(`crossCheck.area.${area}`) })}
                </p>
              )}
              {shown.length === 0 ? (
                <p className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">
                  {t("crossCheck.noneHere")}
                </p>
              ) : (
                <div className="divide-y divide-border">
                  {AREAS.filter((a) => shown.some((f) => areaOf(f) === a)).map((a) => {
                    const inArea = shown.filter((f) => areaOf(f) === a);
                    return (
                      <section key={a} data-testid="finding-area" data-area={a}>
                        <h3 className="flex items-center gap-2 bg-surface-muted/60 px-4 py-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                          {t(`crossCheck.area.${a}`)}
                          <span className="tabular font-normal normal-case">({inArea.length})</span>
                        </h3>
                        <ul className="divide-y divide-border">
                          {inArea.map((f) => (
                            <FindingRow
                              key={f.id}
                              caseId={caseId}
                              finding={f}
                              item={items.get(`finding:${f.id}`)}
                            />
                          ))}
                        </ul>
                      </section>
                    );
                  })}
                </div>
              )}
            </Panel>
          </div>
        );
      }}
    </QueryView>
  );
}

/** The four outcomes as large tiles; each is also the list's filter. */
function OutcomeTiles({
  counts,
  current,
  onSelect,
  blocking,
  toDecide,
}: {
  counts: Record<FindingOutcome, number>;
  current: FindingOutcome;
  onSelect: (o: FindingOutcome) => void;
  blocking: number;
  toDecide: number;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="outcome-tiles">
      {OUTCOMES.map((o) => {
        const Icon = OUTCOME_ICON[o];
        const active = current === o;
        return (
          <button
            key={o}
            type="button"
            aria-pressed={active}
            aria-label={t(`crossCheck.filter.${o}`, { n: counts[o] })}
            onClick={() => onSelect(o)}
            data-testid={`findings-filter-${o}`}
            className={cn(
              "min-w-0 rounded border bg-surface px-4 py-3 text-left transition-colors hover:bg-muted/50",
              active ? "border-primary ring-1 ring-primary" : "border-border",
            )}
          >
            <span className="flex items-center gap-1.5">
              <Icon className={cn("h-4 w-4", OUTCOME_TONE[o])} />
              <span className="field-label">{t(`crossCheck.tile.${o}`)}</span>
            </span>
            <span
              className={cn(
                "tabular mt-1 block text-[24px] font-semibold leading-none",
                counts[o] > 0 ? OUTCOME_TONE[o] : "text-muted-foreground",
              )}
            >
              {counts[o]}
            </span>
            <span className="mt-1.5 block text-[11.5px] text-muted-foreground">
              {o === "fail"
                ? t("crossCheck.tileNote.fail", { blocking, open: toDecide })
                : t(`crossCheck.tileNote.${o}`)}
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** One card per area of the file, coloured by its worst outcome. */
function AreaGrid({
  list,
  selected,
  onSelect,
}: {
  list: Finding[];
  selected: FindingArea | null;
  onSelect: (a: FindingArea | null) => void;
}) {
  return (
    <Panel
      title={t("crossCheck.areasTitle")}
      subtitle={t("crossCheck.areasHelp")}
      testId="area-grid"
    >
      <div className="grid gap-px bg-border sm:grid-cols-2 xl:grid-cols-4">
        {AREAS.map((a) => {
          const inArea = list.filter((f) => areaOf(f) === a);
          const c = countOutcomes(inArea);
          const worst: FindingOutcome =
            c.fail > 0
              ? "fail"
              : c.incomplete > 0
                ? "incomplete"
                : c.pass > 0
                  ? "pass"
                  : "not_applicable";
          const Icon = OUTCOME_ICON[worst];
          const active = selected === a;
          return (
            <button
              key={a}
              type="button"
              aria-pressed={active}
              onClick={() => onSelect(active ? null : a)}
              data-testid="area-card"
              data-area={a}
              data-state={worst}
              className={cn(
                "flex min-w-0 items-start gap-2.5 bg-surface px-4 py-3 text-left transition-colors last:sm:col-span-2 hover:bg-muted/50",
                active && "bg-primary/5 ring-1 ring-inset ring-primary",
                worst === "fail" && "border-l-4 border-l-destructive",
                worst === "incomplete" && "border-l-4 border-l-flag",
                worst === "pass" && "border-l-4 border-l-positive",
              )}
            >
              <Icon className={cn("mt-0.5 h-4 w-4 shrink-0", OUTCOME_TONE[worst])} />
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold text-foreground">
                  {t(`crossCheck.area.${a}`)}
                </span>
                <span className="block text-[11.5px] text-muted-foreground">
                  {t(`crossCheck.areaHelp.${a}`)}
                </span>
                <span className="mt-1 flex flex-wrap gap-1">
                  {c.fail > 0 && (
                    <Chip tone="critical">
                      {c.fail === 1
                        ? t("crossCheck.areaState.failOne")
                        : t("crossCheck.areaState.fail", { n: c.fail })}
                    </Chip>
                  )}
                  {c.incomplete > 0 && (
                    <Chip tone="flag">
                      {t("crossCheck.areaState.incomplete", { n: c.incomplete })}
                    </Chip>
                  )}
                  {c.pass > 0 && (
                    <Chip tone="positive">{t("crossCheck.areaState.pass", { n: c.pass })}</Chip>
                  )}
                  {c.fail + c.incomplete + c.pass === 0 && (
                    <Chip tone="muted">{t("crossCheck.areaState.none")}</Chip>
                  )}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </Panel>
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
  const viewer = useDocViewer();
  const Icon = OUTCOME_ICON[finding.outcome];
  const failed = finding.outcome === "fail";
  const open = failed || finding.outcome === "incomplete";
  const sides = finding.sides;
  const comparable = sides.filter((s) => (s.evidence ?? []).length > 0);
  const detail = finding.detail ?? null;
  const missing = finding.missing ?? [];
  return (
    <li
      className={cn(
        "space-y-2 px-4 py-3",
        failed && "border-l-4 border-l-destructive/70",
        finding.outcome === "incomplete" && "border-l-4 border-l-flag/70",
      )}
      data-testid="finding"
      data-rule={finding.rule_id}
      data-outcome={finding.outcome}
    >
      <div className="flex flex-wrap items-start gap-2">
        <Icon
          className={cn(
            "mt-0.5 h-4 w-4 shrink-0",
            failed ? SEVERITY_TONE[finding.severity] : OUTCOME_TONE[finding.outcome],
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
              className={cn(
                "mt-0.5 text-[12.5px]",
                failed ? "text-foreground" : "text-muted-foreground",
              )}
              data-testid="finding-explanation"
            >
              {finding.explanation}
            </p>
          )}
        </div>
        <span className="tabular shrink-0 text-[11px] text-muted-foreground">
          {finding.rule_id}
        </span>
      </div>

      {missing.length > 0 && (
        <div
          className="ml-6 flex flex-wrap items-center gap-1.5 text-[11.5px]"
          data-testid="finding-missing"
        >
          <span className="text-muted-foreground">{t("crossCheck.notOnFile")}:</span>
          {missing.map((m) => (
            <Chip key={m} tone="flag">
              {m}
            </Chip>
          ))}
          <Link
            to="/appraisals/$caseId/documents"
            params={{ caseId }}
            className="font-medium text-primary hover:underline"
          >
            {t("crossCheck.addDocuments")} →
          </Link>
        </div>
      )}

      {sides.length > 0 &&
        (open ? (
          <SidesTable caseId={caseId} sides={sides} />
        ) : (
          <div className="ml-6">
            <Details title={t("crossCheck.sources", { n: sides.length })} testId="finding-sources">
              <SidesTable caseId={caseId} sides={sides} bare />
            </Details>
          </div>
        ))}

      {detail && detail.rows.length > 0 && (
        <div className="ml-6">
          <Details
            title={t("crossCheck.lineByLine", { n: detail.rows.length })}
            testId="finding-detail"
            open={failed && detail.rows.length <= 12}
          >
            <DetailTable detail={detail} />
          </Details>
        </div>
      )}

      {open && (
        <div className="ml-6 flex flex-wrap items-center gap-2">
          {comparable.length >= 2 && (
            <button
              type="button"
              onClick={() =>
                viewer.open({
                  caseId,
                  documentId: comparable[0]!.evidence![0]!.document_id,
                  compare: comparable.slice(0, 3).map((s) => ({
                    documentId: s.evidence![0]!.document_id,
                    page: s.evidence![0]!.page,
                    bbox: s.evidence![0]!.bbox ?? null,
                    label: `${s.label}: ${value(s.value)}`,
                  })),
                })
              }
              className={`${decisionButton} inline-flex items-center gap-1 border-border bg-surface text-foreground hover:bg-muted`}
              data-testid="finding-compare"
            >
              <Columns2 className="h-3.5 w-3.5" /> {t("crossCheck.compare")}
            </button>
          )}
          {(finding.tolerance || sides.length > 0) && (
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
          )}
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

/** The sources a check compared, one row each; the value that differs stands out. */
function SidesTable({
  caseId,
  sides,
  bare,
}: {
  caseId: string;
  sides: FindingSide[];
  bare?: boolean;
}) {
  return (
    <div className={cn(!bare && "ml-6", "overflow-x-auto")}>
      <table className="w-full min-w-[32rem] border-collapse rounded border border-border text-[12px]">
        <thead>
          <tr className="bg-surface-muted/60 text-left text-[11px] text-muted-foreground">
            <th className="w-[40%] px-3 py-1.5 font-medium">{t("crossCheck.source")}</th>
            <th className="px-3 py-1.5 font-medium">{t("crossCheck.value")}</th>
            <th className="px-3 py-1.5 text-right font-medium">{t("crossCheck.pages")}</th>
          </tr>
        </thead>
        <tbody>
          {sides.map((side, i) => (
            <tr
              key={`${side.label}-${i}`}
              className={cn("border-t border-border align-top", side.differs && "bg-destructive/5")}
              data-testid="finding-side"
              data-differs={side.differs ? "true" : "false"}
            >
              <td className="px-3 py-1.5 text-muted-foreground">{side.label}</td>
              <td className="px-3 py-1.5">
                <span
                  className={cn(
                    "tabular break-words font-medium",
                    side.differs ? "text-destructive" : "text-foreground",
                  )}
                >
                  {value(side.value)}
                </span>
                <span className="ml-1.5 inline-flex flex-wrap gap-1 align-middle">
                  {side.differs && <Chip tone="critical">{t("crossCheck.differs")}</Chip>}
                  {side.relies_on_manual && (
                    <Chip tone="flag">
                      <User className="h-3 w-3" /> {t("crossCheck.manual")}
                    </Chip>
                  )}
                  {side.awaiting_review && <ReviewValue caseId={caseId} side={side} />}
                </span>
              </td>
              <td className="px-3 py-1.5 text-right">
                <EvidenceLinks caseId={caseId} evidence={side.evidence ?? []} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** A side waiting for review (F-17.2): opens the value at its page, to confirm or correct. */
function ReviewValue({ caseId, side }: { caseId: string; side: FindingSide }) {
  const viewer = useDocViewer();
  const fields = useFields(caseId);
  const field = fields.data?.find((f) => (side.field_ids ?? []).includes(f.id));
  const evidence = side.evidence?.[0];
  return (
    <button
      type="button"
      onClick={() =>
        evidence &&
        viewer.open({
          caseId,
          documentId: field?.document_id ?? evidence.document_id,
          page: evidence.page,
          bbox: evidence.bbox ?? null,
          ...(field ? { field } : {}),
        })
      }
      className="inline-flex items-center gap-1 rounded border border-flag/35 bg-flag-soft px-1.5 py-0.5 text-[10.5px] font-medium text-flag-foreground hover:bg-flag/20"
      data-testid="finding-awaiting-review"
    >
      {t("crossCheck.awaitingReview")} · {t("crossCheck.reviewValue")}
    </button>
  );
}

/** The line-by-line comparison behind a finding: months, people, years. */
function DetailTable({ detail }: { detail: FindingDetail }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12px]" data-testid="finding-detail-table">
        <thead>
          <tr className="text-left text-[11px] text-muted-foreground">
            <th className="px-2 py-1 font-medium" />
            {detail.columns.map((c) => (
              <th key={c} className="px-2 py-1 text-right font-medium">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {detail.rows.map((r, i) => (
            <tr
              key={`${r.label}-${i}`}
              className={cn("border-t border-border", r.flagged && "bg-destructive/5")}
              data-flagged={r.flagged ? "true" : "false"}
            >
              <td className={cn("px-2 py-1", r.flagged ? "font-semibold text-destructive" : "")}>
                {r.flagged && <AlertTriangle className="mr-1 inline h-3 w-3" />}
                {r.label}
              </td>
              {r.cells.map((c, j) => (
                <td
                  key={j}
                  className={cn(
                    "tabular px-2 py-1 text-right",
                    c === "—" && "text-destructive",
                    c === "✓" && "text-positive",
                  )}
                >
                  {value(c)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
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

// --- The facts behind the checks (F-18) ---

export function FactsPanels({ caseId }: { caseId: string }) {
  const facts = useFacts(caseId);
  return (
    <QueryView query={facts}>
      {(f) => (
        <div className="grid gap-4 xl:grid-cols-2">
          <IdentityPanel facts={f} caseId={caseId} />
          <PeoplePanel facts={f} caseId={caseId} />
          <AuthorityPanel facts={f} caseId={caseId} />
          <TaxPanel facts={f} caseId={caseId} />
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

const IDENTIFIERS = ["entity_pan", "gstin", "cin", "legal_name"] as const;

/** Each identifier with its distinct values and the documents stating each. */
function IdentityPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const rows = IDENTIFIERS.map((key) => {
    const values = (facts.identities[key] ?? []) as FactValue[];
    const groups = new Map<string, FactValue[]>();
    for (const v of values) {
      const k = key === "legal_name" ? String(v.value).toLowerCase() : String(v.value);
      groups.set(k, [...(groups.get(k) ?? []), v]);
    }
    return { key, groups: [...groups.values()] };
  }).filter((r) => r.groups.length > 0);
  return (
    <Panel title={t("facts.identity")} subtitle={t("facts.identityHelp")} testId="facts-identity">
      {rows.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <ul className="divide-y divide-border text-[12px]">
          {rows.map(({ key, groups }) => (
            <li key={key} className="flex gap-3 px-4 py-2">
              <span className="w-20 shrink-0 font-medium text-muted-foreground">
                {t(`facts.identifier.${key}`)}
              </span>
              <ul className="min-w-0 flex-1 space-y-1">
                {groups.map((g, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                    <span
                      className={cn(
                        "tabular font-medium",
                        groups.length > 1 && key !== "legal_name"
                          ? "text-destructive"
                          : "text-foreground",
                      )}
                    >
                      {String(g[0]!.value)}
                    </span>
                    <span className="text-muted-foreground">
                      {[...new Set(g.map((v) => v.label))].join(" · ")}
                    </span>
                    <EvidenceLinks
                      caseId={caseId}
                      evidence={g.flatMap((v) => (v.evidence ?? []).slice(0, 1))}
                    />
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

/** Each person against each source that names them. */
function PeoplePanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const sets = facts.persons;
  const people: {
    name: string;
    din: string | null | undefined;
    pan: string | null | undefined;
    evidence: Evidence[];
  }[] = [];
  const key = (n: string) => n.toLowerCase().replace(/[^a-z]/g, "");
  for (const s of sets)
    for (const e of s.entries ?? [])
      if (!people.some((p) => key(p.name) === key(e.name)))
        people.push({ name: e.name, din: e.din, pan: e.pan, evidence: e.evidence ?? [] });
      else {
        const p = people.find((q) => key(q.name) === key(e.name))!;
        p.din = p.din ?? e.din;
        p.pan = p.pan ?? e.pan;
      }
  return (
    <Panel title={t("facts.people")} subtitle={t("facts.peopleHelp")} testId="facts-people">
      {people.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[11px] text-muted-foreground">
                <th className="px-4 py-1.5 font-medium">{t("facts.person")}</th>
                <th className="px-2 py-1.5 font-medium">{t("facts.din")}</th>
                <th className="px-2 py-1.5 font-medium">{t("facts.pan")}</th>
                {sets.map((s) => (
                  <th key={s.label} className="px-2 py-1.5 text-center font-medium">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {people.map((p) => (
                <tr key={p.name} className="border-t border-border">
                  <td className="px-4 py-1.5 font-medium">
                    {p.name} <EvidenceLinks caseId={caseId} evidence={p.evidence.slice(0, 1)} />
                  </td>
                  <td className="tabular px-2 py-1.5">{p.din ?? "—"}</td>
                  <td className="tabular px-2 py-1.5">{p.pan ?? "—"}</td>
                  {sets.map((s) => {
                    const named = (s.entries ?? []).some((e) => key(e.name) === key(p.name));
                    return (
                      <td
                        key={s.label}
                        className={cn(
                          "px-2 py-1.5 text-center",
                          named ? "text-positive" : "text-destructive",
                        )}
                      >
                        {named ? "✓" : "—"}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function FactLine({
  label,
  fact,
  caseId,
  tone,
}: {
  label: string;
  fact?: FactValue | null | undefined;
  caseId: string;
  tone?: "critical" | undefined;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 px-4 py-1.5 text-[12px]">
      <span className="w-40 shrink-0 text-muted-foreground">{label}</span>
      <span className={cn("tabular font-medium", tone === "critical" && "text-destructive")}>
        {value(fact?.value)}
      </span>
      {fact && <EvidenceLinks caseId={caseId} evidence={(fact.evidence ?? []).slice(0, 1)} />}
    </div>
  );
}

/** The board resolution's terms against the request. */
function AuthorityPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const resolutions = facts.authority ?? [];
  const requested = facts.requested_amount ?? null;
  return (
    <Panel
      title={t("facts.authority")}
      subtitle={t("facts.authorityHelp")}
      testId="facts-authority"
    >
      {resolutions.length === 0 ? (
        <Empty text={t("facts.noResolution")} />
      ) : (
        <div className="divide-y divide-border">
          {resolutions.map((a) => {
            const short =
              a.borrowing_limit &&
              requested &&
              Number(a.borrowing_limit.value) < Number(requested.value);
            return (
              <div key={a.document_id} className="py-1">
                <FactLine
                  label={t("facts.borrowingLimit")}
                  fact={a.borrowing_limit}
                  caseId={caseId}
                  tone={short ? "critical" : undefined}
                />
                <FactLine label={t("facts.amountRequested")} fact={requested} caseId={caseId} />
                <FactLine label={t("facts.lender")} fact={a.lender} caseId={caseId} />
                <FactLine
                  label={t("facts.resolutionDate")}
                  fact={a.resolution_date}
                  caseId={caseId}
                />
                <div className="flex flex-wrap items-center gap-x-3 px-4 py-1.5 text-[12px]">
                  <span className="w-40 shrink-0 text-muted-foreground">
                    {t("facts.signatories")}
                  </span>
                  <span className="font-medium">
                    {(a.signatories ?? []).map((s) => s.name).join(", ") || "—"}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

/** Each financial year: audited figures beside its income tax return. */
function TaxPanel({ facts, caseId }: { facts: CaseFacts; caseId: string }) {
  const years = facts.financial_years ?? [];
  const tax = new Map((facts.tax_years ?? []).map((y) => [y.fy, y]));
  const fys = [...new Set([...years.map((y) => y.fy), ...tax.keys()])].sort().reverse();
  return (
    <Panel title={t("facts.tax")} subtitle={t("facts.taxHelp")} testId="facts-tax">
      {fys.length === 0 ? (
        <Empty text={t("facts.none")} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-[11px] text-muted-foreground">
                <th className="px-4 py-1.5 font-medium">{t("facts.year")}</th>
                <th className="px-2 py-1.5 text-right font-medium">{t("facts.revenue")}</th>
                <th className="px-2 py-1.5 text-right font-medium">{t("facts.profitBeforeTax")}</th>
                <th className="px-2 py-1.5 text-right font-medium">{t("facts.returnProfit")}</th>
                <th className="px-2 py-1.5 text-center font-medium">{t("facts.returnFiled")}</th>
              </tr>
            </thead>
            <tbody>
              {fys.map((fy) => {
                const y = years.find((v) => v.fy === fy);
                const r = tax.get(fy);
                const revenue = y?.current?.["revenue_from_operations"];
                const pbt = y?.current?.["profit_before_tax"];
                const filed = r?.lines?.["profit_before_tax"];
                return (
                  <tr key={fy} className="border-t border-border">
                    <td className="px-4 py-1.5 font-medium">{fy}</td>
                    <td className="tabular px-2 py-1.5 text-right">{value(revenue?.value)}</td>
                    <td className="tabular px-2 py-1.5 text-right">{value(pbt?.value)}</td>
                    <td className="tabular px-2 py-1.5 text-right">{value(filed?.value)}</td>
                    <td
                      className={cn(
                        "px-2 py-1.5 text-center",
                        r ? "text-positive" : "text-muted-foreground",
                      )}
                    >
                      {r ? (
                        <EvidenceLinks caseId={caseId} evidence={(r.evidence ?? []).slice(0, 1)} />
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
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
