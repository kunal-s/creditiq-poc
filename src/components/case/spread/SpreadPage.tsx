import { Link, useNavigate } from "@tanstack/react-router";
import { AlertCircle, ArrowLeft, ArrowRight, FileText } from "lucide-react";
import { useState } from "react";
import type { CaseDetail, CrossVerificationView, Spread } from "@/api/types";
import { PageHeader, PrimaryAction, SecondaryAction } from "@/components/common/PageHeader";
import { RailPanel, RailRows, RailStats } from "@/components/common/RailPanel";
import { QueryView } from "@/components/common/States";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatDate, useCase } from "@/domain/cases";
import { useCrossVerification } from "@/domain/crossVerification";
import { useCaseDocuments, useDocumentTypes } from "@/domain/documents";
import { useFacts, useSpread } from "@/domain/findings";
import { usePolicy } from "@/domain/policy";
import { openTurnoverDiscrepancies, turnoverYears } from "@/domain/spread";
import { cn } from "@/lib/utils";
import { RatioTiles, TrendNotes } from "./SpreadRatios";
import { StatementTable, TurnoverByYear, type Picked } from "./SpreadTables";

// The Spread tab (F-22, F-18.1, F-20): the audited years line by line, turnover from every source
// year by year, and the ratios against the policy norms, with a rail that says how much of the
// spread is traced and where the selected figure was read from.
//
// Test ids:
//   spread-page             the tab
//   spread-period           the year picker; spread-period-<fy> each year
//   spread-banner           an open turnover discrepancy, with the way to it on Cross-checks
//   spread-turnover         turnover by year: spread-turnover-row (data-source) and
//                           spread-turnover-cell (data-fy, data-verdict)
//   spread-profit_and_loss, spread-balance_sheet   the statements; spread-row (data-row)
//   spread-figure           any figure (data-selected); spread-manual-note a person's entry
//   spread-ratios           spread-ratio tiles (data-ratio, data-band)
//   spread-trends           spread-trend-turnover, spread-trend-cycle
//   spread-status, spread-source   the rail

export function SpreadPage({ caseId }: { caseId: string }) {
  const spread = useSpread(caseId);
  return (
    <div className="min-w-0 pb-10" data-testid="spread-page">
      <QueryView
        query={spread}
        isEmpty={(s) => s.columns.length === 0}
        empty={{
          title: t("spreadPage.emptyTitle"),
          description: t("spreadPage.emptyDescription"),
        }}
      >
        {(s) => <SpreadBody caseId={caseId} spread={s} />}
      </QueryView>
    </div>
  );
}

function SpreadBody({ caseId, spread }: { caseId: string; spread: Spread }) {
  const navigate = useNavigate();
  const facts = useFacts(caseId);
  const policy = usePolicy(caseId);
  const board = useCrossVerification(caseId);
  const header = useCase(caseId);
  const latest = spread.columns[spread.columns.length - 1]!;
  const [period, setPeriod] = useState(latest.fy);
  const [picked, setPicked] = useState<Picked | null>(null);
  const column = spread.columns.find((c) => c.fy === period) ?? latest;
  const years = facts.data ? turnoverYears(facts.data) : [];

  return (
    <>
      <PageHeader
        kicker={t("spreadPage.kicker", { id: caseId })}
        title={t("spreadPage.title")}
        purpose={t("spreadPage.purpose")}
        actions={
          <>
            <SecondaryAction
              onClick={() =>
                void navigate({ to: "/appraisals/$caseId/cross-verification", params: { caseId } })
              }
              testId="spread-back"
            >
              <ArrowLeft className="h-4 w-4" aria-hidden />
              {t("spreadPage.back")}
            </SecondaryAction>
            <PrimaryAction
              onClick={() =>
                void navigate({
                  to: "/appraisals/$caseId/outputs",
                  params: { caseId },
                  search: { view: "cam" },
                })
              }
              testId="spread-continue"
            >
              {t("spreadPage.continue")}
              <ArrowRight className="h-4 w-4" aria-hidden />
            </PrimaryAction>
          </>
        }
      />
      <div className="grid min-w-0 grid-cols-1 gap-4 px-4 py-5 sm:px-6 xl:grid-cols-[minmax(0,1fr)_19rem]">
        <div className="min-w-0 space-y-4">
          <PeriodPicker spread={spread} period={column.fy} onPick={setPeriod} />
          <TurnoverBanner caseId={caseId} board={board.data} />
          <TurnoverByYear
            years={years}
            board={board.data}
            selected={column.fy}
            picked={picked?.id ?? null}
            onPick={setPicked}
          />
          <StatementTable
            spread={spread}
            section="profit_and_loss"
            selected={column.fy}
            picked={picked?.id ?? null}
            onPick={setPicked}
          />
          <StatementTable
            spread={spread}
            section="balance_sheet"
            selected={column.fy}
            picked={picked?.id ?? null}
            onPick={setPicked}
          />
          {policy.data && <RatioTiles spread={spread} policy={policy.data} />}
          <TrendNotes spread={spread} />
        </div>
        <aside className="order-first grid min-w-0 grid-cols-1 content-start gap-4 sm:grid-cols-2 xl:sticky xl:top-4 xl:order-none xl:grid-cols-1 xl:self-start">
          <StatusPanel spread={spread} header={header.data} period={policy.data?.period ?? null} />
          <SourcePanel caseId={caseId} picked={picked} />
        </aside>
      </div>
    </>
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
                onClick={() =>
                  viewer.open({
                    caseId,
                    documentId: e.document_id,
                    page: e.page,
                    bbox: e.bbox ?? null,
                  })
                }
                className="mt-2 text-[12.5px] font-medium text-primary hover:underline"
                data-testid="spread-source-open"
              >
                {t("spreadPage.source.open")}
              </button>
            </div>
          ) : (
            <p className="text-[12px] text-muted-foreground">{t("spreadPage.source.noPage")}</p>
          )}
        </div>
      )}
    </RailPanel>
  );
}
