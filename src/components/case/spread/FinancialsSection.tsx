import { Link } from "@tanstack/react-router";
import { AlertCircle, ArrowRight, Eye, FileText } from "lucide-react";
import { useState } from "react";
import type { CaseDetail, CrossVerificationView, Spread } from "@/api/types";
import { BankingPanel, BankingRail } from "@/components/case/banking/BankingPanel";
import { RailPanel, RailRows, RailStats } from "@/components/common/RailPanel";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QueryView } from "@/components/common/States";
import { evidenceRequest, useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatDate, useCase } from "@/domain/cases";
import { useCrossVerification } from "@/domain/crossVerification";
import { useCaseDocuments, useDocumentTypes } from "@/domain/documents";
import { useFacts, useSpread } from "@/domain/findings";
import { FINANCIALS_HEADING_ID, FINANCIALS_SECTION_ID } from "@/domain/policy";
import { useTxnSummary } from "@/domain/transactions";
import {
  differingFigures,
  manualFigures,
  openTurnoverDiscrepancies,
  turnoverYears,
} from "@/domain/spread";
import { cn } from "@/lib/utils";
import { TrendNotes } from "./SpreadRatios";
import { FigureWorking } from "./FigureWorking";
import { Reconciliation } from "./Reconciliation";
import { StatementTable, TurnoverByYear, pickedNow, type Picked } from "./SpreadTables";
import { WorkingCapital } from "./WorkingCapital";

// The Financials section of the Financials and Policy tab (F-22, F-18.1): the audited years line
// by line, turnover from every source year by year coloured by what the cross-checks concluded,
// and the working-capital assessment, with a rail that says how much of the spread is traced and
// where the selected figure was read from. The ratios are tested in the norms below it.
//
// Test ids:
//   financials              the section (element id `financials`)
//   spread-period           the year picker; spread-period-<fy> each year
//   spread-banner           an open turnover discrepancy, with the way to it on Cross-checks
//   financials-tabs         the tables and the Banking view, one at a time: financials-tab-<turnover|
//                           profit_and_loss|balance_sheet|banking> each, with financials-tab-count
//   spread-turnover         turnover by year: spread-turnover-row (data-source) and
//                           spread-turnover-cell (data-fy, data-verdict)
//   spread-profit_and_loss, spread-balance_sheet   the statements; spread-row (data-row)
//   spread-figure           any figure (data-selected); spread-manual-note a person's entry
//   working-capital         the assessment: wc-step each, wc-verdict
//   spread-trends           spread-trend-turnover, spread-trend-cycle
//   spread-status, spread-source   the rail

/** The tables of the section, one per tab, in this order. */
const TABS = ["turnover", "profit_and_loss", "balance_sheet", "banking"] as const;

export function FinancialsSection({
  caseId,
  period,
}: {
  caseId: string;
  /** The year the policy assessed, for the rail. */
  period: string | null;
}) {
  const spread = useSpread(caseId);
  return (
    <section
      id={FINANCIALS_SECTION_ID}
      aria-labelledby={FINANCIALS_HEADING_ID}
      className="min-w-0 scroll-mt-4 space-y-3"
      data-testid="financials"
    >
      <header className="border-b border-border pb-2">
        <h2
          id={FINANCIALS_HEADING_ID}
          tabIndex={-1}
          className="rounded-sm text-[16px] font-semibold tracking-tight text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {t("spreadPage.title")}
        </h2>
        <p className="mt-0.5 text-[12px] text-muted-foreground">{t("spreadPage.purpose")}</p>
      </header>
      <QueryView
        query={spread}
        isEmpty={(s) => s.columns.length === 0}
        empty={{
          title: t("spreadPage.emptyTitle"),
          description: t("spreadPage.emptyDescription"),
        }}
        compact
      >
        {(s) => <FinancialsBody caseId={caseId} spread={s} period={period} />}
      </QueryView>
    </section>
  );
}

/** What the badge on a tab counts. */
function tabCountKey(key: (typeof TABS)[number]): string {
  return key === "turnover"
    ? "spreadPage.tabs.differing"
    : key === "banking"
      ? "spreadPage.tabs.bankingOpen"
      : "spreadPage.tabs.manual";
}

function FinancialsBody({
  caseId,
  spread,
  period: assessed,
}: {
  caseId: string;
  spread: Spread;
  period: string | null;
}) {
  const facts = useFacts(caseId);
  const board = useCrossVerification(caseId);
  const header = useCase(caseId);
  const latest = spread.columns[spread.columns.length - 1]!;
  const [period, setPeriod] = useState(latest.fy);
  const [picked, setPicked] = useState<Picked | null>(null);
  const column = spread.columns.find((c) => c.fy === period) ?? latest;
  const years = facts.data ? turnoverYears(facts.data) : [];
  const [tab, setTab] = useState<string>("turnover");
  const differing = differingFigures(years, board.data);
  const unfiled = useTxnSummary(caseId).data?.unsettled ?? 0;

  return (
    <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
      <div className="min-w-0 space-y-4">
        {tab !== "banking" && (
          <PeriodPicker spread={spread} period={column.fy} onPick={setPeriod} />
        )}
        <TurnoverBanner caseId={caseId} board={board.data} />
        {/* One table at a time, to keep the section short; the year and the picked figure
            carry across the tabs, and a badge says what a tab holds that needs a look. */}
        <Tabs value={tab} onValueChange={setTab} data-testid="financials-tabs">
          <TabsList className="h-auto flex-wrap justify-start gap-1 rounded border border-border bg-surface p-1">
            {TABS.map((key) => {
              const count =
                key === "turnover"
                  ? differing
                  : key === "banking"
                    ? unfiled
                    : manualFigures(spread, key);
              return (
                <TabsTrigger
                  key={key}
                  value={key}
                  className="gap-1.5 rounded px-3 py-1.5 text-[13px] text-muted-foreground data-[state=active]:bg-primary data-[state=active]:text-primary-foreground data-[state=active]:shadow-none"
                  data-testid={`financials-tab-${key}`}
                >
                  {t(`spreadPage.tabs.${key}`)}
                  {count > 0 && (
                    <span
                      className={cn(
                        "tabular rounded-full px-1.5 text-[11px] font-semibold leading-[18px]",
                        key === "turnover"
                          ? "bg-critical-soft text-destructive"
                          : "bg-flag-soft text-flag-foreground",
                      )}
                      data-testid="financials-tab-count"
                      title={t(tabCountKey(key), { n: count })}
                    >
                      {count}
                      <span className="sr-only"> {t(tabCountKey(key), { n: count })}</span>
                    </span>
                  )}
                </TabsTrigger>
              );
            })}
          </TabsList>
          <TabsContent value="turnover">
            <TurnoverByYear
              years={years}
              board={board.data}
              selected={column.fy}
              picked={picked?.id ?? null}
              onPick={setPicked}
            />
          </TabsContent>
          <TabsContent value="banking">
            <BankingPanel caseId={caseId} />
          </TabsContent>
          {(["profit_and_loss", "balance_sheet"] as const).map((section) => (
            <TabsContent key={section} value={section}>
              <StatementTable
                spread={spread}
                section={section}
                selected={column.fy}
                picked={picked?.id ?? null}
                onPick={setPicked}
              />
            </TabsContent>
          ))}
        </Tabs>
        {tab !== "banking" && tab !== "turnover" && (
          <Reconciliation caseId={caseId} spread={spread} />
        )}
        <WorkingCapital caseId={caseId} spread={spread} />
        <TrendNotes spread={spread} />
      </div>
      <aside className="order-first grid min-w-0 grid-cols-1 content-start gap-4 sm:grid-cols-2 xl:sticky xl:top-4 xl:order-none xl:grid-cols-1 xl:self-start">
        {tab === "banking" ? (
          <BankingRail caseId={caseId} />
        ) : (
          <>
            <StatusPanel spread={spread} header={header.data} period={assessed} />
            <SourcePanel caseId={caseId} picked={pickedNow(spread, picked)} />
          </>
        )}
      </aside>
    </div>
  );
}

function PeriodPicker({
  spread,
  period,
  onPick,
}: {
  spread: Spread;
  period: string;
  onPick: (fy: string) => void;
}) {
  const column = spread.columns.find((c) => c.fy === period)!;
  return (
    <section
      className="rounded border border-border bg-surface px-4 py-3"
      data-testid="spread-period"
    >
      <div className="flex flex-wrap items-center gap-3">
        <span className="field-label">{t("spreadPage.period")}</span>
        <div className="flex flex-wrap overflow-hidden rounded border border-border" role="group">
          {spread.columns.map((c) => (
            <button
              key={c.key}
              type="button"
              onClick={() => onPick(c.fy)}
              aria-pressed={c.fy === period}
              className={cn(
                "border-r border-border px-3 py-1.5 text-[13px] font-medium last:border-r-0 transition-colors",
                c.fy === period
                  ? "bg-primary text-primary-foreground"
                  : "bg-surface text-foreground hover:bg-surface-muted",
              )}
              data-testid={`spread-period-${c.fy}`}
            >
              {c.fy}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-2 text-[12px] text-muted-foreground">
        {t("spreadPage.periodNote", {
          date: formatDate(column.period_end),
          basis: t(`spreadPage.basis.${column.basis}`),
        })}
      </p>
    </section>
  );
}

/** The turnover discrepancy of greatest impact still open on Cross-checks, in its own words. */
function TurnoverBanner({
  caseId,
  board,
}: {
  caseId: string;
  board: CrossVerificationView | undefined;
}) {
  const open = openTurnoverDiscrepancies(board);
  const first = open[0]?.finding;
  if (!first) return null;
  return (
    <section
      className="rounded border border-flag/40 bg-flag-soft px-4 py-3.5 text-flag-foreground"
      data-testid="spread-banner"
    >
      <p className="flex items-start gap-2 text-[13.5px] font-semibold">
        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
        {first.finding_title || first.title}
        {open.length > 1 && (
          <span className="font-normal">
            {" "}
            {t("spreadPage.banner.more", { n: open.length - 1 })}
          </span>
        )}
      </p>
      <p className="mt-1.5 text-[12.5px] leading-relaxed">{first.explanation}</p>
      <div className="mt-2.5 flex flex-wrap items-center gap-2">
        {first.sides.map((s) => (
          <span
            key={s.label}
            className="rounded border border-flag/40 bg-surface px-2 py-0.5 text-[12px] font-medium text-foreground"
          >
            {s.label} — {typeof s.value === "number" ? `${(s.value / 1e7).toFixed(2)} cr` : s.value}
          </span>
        ))}
        <Link
          to="/appraisals/$caseId/cross-verification"
          params={{ caseId }}
          search={{ finding: first.ref ?? first.id }}
          className="inline-flex items-center gap-1 text-[12.5px] font-medium text-primary hover:underline"
          data-testid="spread-banner-open"
        >
          {t("spreadPage.banner.open")}
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </Link>
      </div>
    </section>
  );
}

function StatusPanel({
  spread,
  header,
  period,
}: {
  spread: Spread;
  header: CaseDetail | undefined;
  period: string | null;
}) {
  const figures = spread.rows.flatMap((r) => r.cells).filter((c) => c.value !== null);
  const traced = spread.rows.filter((r) =>
    r.cells.every((c) => c.value === null || (c.evidence?.length ?? 0) > 0),
  ).length;
  const manual = figures.filter((c) => c.relies_on_manual).length;
  return (
    <RailPanel
      title={t("spreadPage.status.title")}
      subtitle={header?.borrower}
      testId="spread-status"
    >
      <RailStats
        stats={[
          { value: traced, label: t("spreadPage.status.traced") },
          {
            value: manual,
            label: t("spreadPage.status.manual"),
            ...(manual > 0 ? { tone: "text-flag-foreground" } : {}),
          },
        ]}
      />
      <RailRows
        rows={[
          {
            label: t("spreadPage.status.periods"),
            value: spread.columns.map((c) => c.fy).join(" · "),
          },
          {
            label: t("spreadPage.status.layout"),
            value: t(spread.interim ? "spreadPage.status.interim" : "spreadPage.status.template"),
          },
          ...(period ? [{ label: t("spreadPage.status.assessed"), value: period }] : []),
        ]}
      />
    </RailPanel>
  );
}

/** Where the selected figure was read from: its document and page, and the way to the page. */
function SourcePanel({ caseId, picked }: { caseId: string; picked: Picked | null }) {
  const viewer = useDocViewer();
  const documents = useCaseDocuments(caseId);
  const types = useDocumentTypes();
  const e = picked?.evidence[0];
  const doc = e ? documents.data?.find((d) => d.id === e.document_id) : undefined;
  return (
    <RailPanel
      title={t("spreadPage.source.title")}
      subtitle={picked ? `${picked.label} · ${picked.fy}` : t("spreadPage.source.hint")}
      testId="spread-source"
    >
      {picked && (
        <div className="space-y-3 px-4 pb-4 pt-3">
          <p className="flex items-baseline justify-between gap-2">
            <span className="tabular text-[26px] font-semibold leading-none text-foreground">
              {picked.text}
            </span>
            <span className="text-[12px] text-muted-foreground">{picked.unit}</span>
          </p>
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11.5px] font-medium",
              picked.manual
                ? "border-flag/40 bg-flag-soft text-flag-foreground"
                : "border-positive/30 bg-positive-soft text-positive",
            )}
          >
            <span
              className={cn("h-1.5 w-1.5 rounded-full", picked.manual ? "bg-flag" : "bg-positive")}
              aria-hidden
            />
            {t(picked.manual ? "spreadPage.source.manual" : "spreadPage.source.read")}
          </span>
          {e ? (
            <div className="rounded border border-border bg-surface-muted/50 px-3 py-2.5">
              <p className="flex items-start gap-2 text-[12.5px] font-medium text-foreground">
                <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden />
                {doc?.classification?.types[0]
                  ? types.name(doc.classification.types[0])
                  : e.document_id}
              </p>
              <p className="mt-1 text-[12px] text-muted-foreground">
                {t("spreadPage.source.page", { page: e.page })}
                {picked.evidence.length > 1 &&
                  ` · ${t("spreadPage.source.more", { n: picked.evidence.length - 1 })}`}
              </p>
              <button
                type="button"
                onClick={() => {
                  const request = evidenceRequest(caseId, picked.evidence);
                  if (request) viewer.open(request);
                }}
                className="mt-2 inline-flex items-center gap-1 text-[12.5px] font-medium text-primary hover:underline"
                data-testid="spread-source-open"
              >
                <Eye className="h-3.5 w-3.5" aria-hidden />
                {t("spreadPage.source.open")}
              </button>
            </div>
          ) : (
            <p className="text-[12px] text-muted-foreground">{t("spreadPage.source.noPage")}</p>
          )}
          {picked.working && (
            <div className="border-t border-border pt-3">
              <p className="mb-2 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground">
                {t("spreadPage.working.title")}
              </p>
              <FigureWorking
                caseId={caseId}
                label={picked.label}
                fy={picked.fy}
                working={picked.working}
              />
            </div>
          )}
        </div>
      )}
    </RailPanel>
  );
}
