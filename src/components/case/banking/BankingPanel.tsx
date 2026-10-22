import { Eye } from "lucide-react";
import { useState } from "react";
import type { BankConduct, ConductFlag, TxnSummary } from "@/api/types";
import { Chip, Kpi, Panel, type Tone } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { evidenceRequest, useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { monthLabel, rupees, useBankConduct, useTxnSummary } from "@/domain/transactions";
import { cn } from "@/lib/utils";
import { TransactionsTable } from "./TransactionsTable";

// The Banking view of the Financials section: the case's statement transactions each filed under a category, how it
// was read (a rule, the model, a person), and what the accounts show: cash, returns, concentration, money out and
// back, balances, salary and statutory payments, promoters, unusual entries, and the statements' own integrity.
// The screen arranges; the engine decides nothing here.
//
// Test ids:
//   banking                 the view; banking-counts and banking-count-<total|rule|model|person|open> each
//   banking-flags           the flags; banking-flag (data-kind, data-severity), banking-flag-page
//   banking-months          month by month; banking-categories by category; banking-customers; banking-trips
//   banking-balances        the balances by month
//   banking-transactions    the list: banking-txn (data-category, data-method, data-open), banking-filter-*,
//                           banking-file, banking-file-dialog, banking-txn-page, banking-more

const SEVERITY_TONE: Record<ConductFlag["severity"], Tone> = {
  concern: "critical",
  watch: "flag",
  info: "muted",
};
const FLAGS_SHOWN = 8;

export function BankingPanel({ caseId }: { caseId: string }) {
  const summary = useTxnSummary(caseId);
  const conduct = useBankConduct(caseId);
  if (summary.isPending || conduct.isPending) return <LoadingBlock rows={6} />;
  if (summary.isError)
    return <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />;
  if (conduct.isError)
    return <ErrorState error={conduct.error} onRetry={() => void conduct.refetch()} />;
  if (summary.data.total === 0) {
    return (
      <div
        className="rounded border border-dashed border-border bg-surface px-6 py-10 text-center"
        data-testid="banking-none"
      >
        <p className="text-[14px] font-medium text-foreground">{t("banking.emptyTitle")}</p>
        <p className="mt-1 text-[12.5px] text-muted-foreground">{t("banking.emptyDescription")}</p>
      </div>
    );
  }
  return (
    <div className="space-y-4" data-testid="banking">
      <Counts summary={summary.data} />
      <Flags caseId={caseId} flags={conduct.data.flags} />
      <MonthTable conduct={conduct.data} />
      <CategoryTable summary={summary.data} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Customers conduct={conduct.data} />
        <RoundTrips conduct={conduct.data} />
      </div>
      <Balances conduct={conduct.data} />
      <TransactionsTable caseId={caseId} summary={summary.data} />
    </div>
  );
}

function Counts({ summary }: { summary: TxnSummary }) {
  const tiles: [string, number, "flag" | undefined][] = [
    ["total", summary.total, undefined],
    ["rule", summary.by_rule, undefined],
    ["model", summary.by_model, undefined],
    ["person", summary.by_person, undefined],
    ["open", summary.unsettled, summary.unsettled > 0 ? "flag" : undefined],
  ];
  return (
    <div data-testid="banking-counts">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        {tiles.map(([k, n, tone]) => (
          <Kpi
            key={k}
            label={t(`banking.counts.${k}`)}
            value={n.toLocaleString("en-IN")}
            {...(tone ? { tone } : {})}
            {...(k === "open" && n > 0 ? { note: t("banking.openNote") } : {})}
            testId={`banking-count-${k}`}
          />
        ))}
      </div>
      {summary.model_error && (
        <p
          className="mt-2 rounded border border-flag/40 bg-flag-soft px-3 py-2 text-[12.5px] text-flag-foreground"
          role="status"
          data-testid="banking-model-error"
        >
          {t("banking.modelError", { error: summary.model_error })}
        </p>
      )}
    </div>
  );
}

function Flags({ caseId, flags }: { caseId: string; flags: ConductFlag[] }) {
  const [all, setAll] = useState(false);
  const viewer = useDocViewer();
  const shown = all ? flags : flags.slice(0, FLAGS_SHOWN);
  return (
    <Panel
      title={t("banking.flags.title")}
      subtitle={t("banking.flags.subtitle")}
      testId="banking-flags"
    >
      {flags.length === 0 ? (
        <p className="px-4 py-5 text-[13px] text-muted-foreground" data-testid="banking-flags-none">
          {t("banking.flags.none")}
        </p>
      ) : (
        <ul className="divide-y divide-border/60">
          {shown.map((f, i) => (
            <li
              key={i}
              className="flex items-start gap-3 px-4 py-2.5"
              data-testid="banking-flag"
              data-kind={f.kind}
              data-severity={f.severity}
            >
              <Chip tone={SEVERITY_TONE[f.severity]}>{t(`banking.severity.${f.severity}`)}</Chip>
              <p className="min-w-0 flex-1 text-[13px] text-foreground">{f.message}</p>
              {(f.evidence ?? []).length > 0 && (
                <button
                  type="button"
                  onClick={() => {
                    const request = evidenceRequest(caseId, f.evidence ?? []);
                    if (request) viewer.open(request);
                  }}
                  className="inline-flex shrink-0 items-center text-muted-foreground hover:text-primary"
                  aria-label={t("banking.flags.open")}
                  title={t("banking.flags.open")}
                  data-testid="banking-flag-page"
                >
                  <Eye className="h-4 w-4" aria-hidden />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {flags.length > FLAGS_SHOWN && (
        <div className="border-t border-border px-4 py-2 text-center">
          <button
            type="button"
            onClick={() => setAll((v) => !v)}
            className="text-[12.5px] font-medium text-primary hover:underline"
            data-testid="banking-flags-toggle"
          >
            {all ? t("banking.flags.less") : t("banking.flags.more", { n: flags.length })}
          </button>
        </div>
      )}
    </Panel>
  );
}

const th = "px-3 py-2 text-right font-medium";
const td = "tabular px-3 py-1.5 text-right";

function MonthTable({ conduct }: { conduct: BankConduct }) {
  return (
    <Panel
      title={t("banking.months.title")}
      subtitle={t("banking.months.subtitle")}
      testId="banking-months"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[40rem] text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-4 py-2 text-left font-medium">{t("banking.months.month")}</th>
              <th className={th}>{t("banking.months.credits")}</th>
              <th className={th}>{t("banking.months.business")}</th>
              <th className={th}>{t("banking.months.cash")}</th>
              <th className={th}>{t("banking.months.returns")}</th>
              <th className={th}>{t("banking.months.salary")}</th>
              <th className={th}>{t("banking.months.promoters")}</th>
            </tr>
          </thead>
          <tbody>
            {conduct.months.map((m) => (
              <tr
                key={m.month}
                className="border-b border-border/60"
                data-testid="banking-month"
                data-month={m.month}
              >
                <td className="px-4 py-1.5 font-medium">{monthLabel(m.month)}</td>
                <td className={td}>{rupees(m.credits)}</td>
                <td className={td}>{rupees(m.business_credits)}</td>
                <td className={cn(td, m.cash_deposits > 0 && "text-foreground")}>
                  {m.cash_deposits > 0
                    ? `${rupees(m.cash_deposits)} (${m.cash_share_pct.toFixed(0)}%)`
                    : "—"}
                </td>
                <td className={td}>
                  {m.returns_count > 0 ? `${m.returns_count} · ${rupees(m.returns_amount)}` : "—"}
                </td>
                <td className={td}>{m.salary > 0 ? rupees(m.salary) : "—"}</td>
                <td className={td}>{m.promoter_out > 0 ? rupees(m.promoter_out) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function CategoryTable({ summary }: { summary: TxnSummary }) {
  const months = summary.months;
  const row = (c: TxnSummary["categories"][number]) => (
    <tr
      key={c.category}
      className="border-b border-border/60"
      data-testid="banking-category"
      data-category={c.category}
    >
      <td className="px-4 py-1.5">{c.label}</td>
      <td className={cn(td, "font-medium")}>{rupees(c.amount)}</td>
      {months.map((m) => (
        <td key={m.month} className={cn(td, "text-muted-foreground")}>
          {m.by_category[c.category] ? rupees(m.by_category[c.category]!) : "—"}
        </td>
      ))}
    </tr>
  );
  return (
    <Panel
      title={t("banking.categories.title")}
      subtitle={t("banking.categories.subtitle")}
      testId="banking-categories"
    >
      <div className="overflow-x-auto">
        <table
          className="w-full text-[12.5px]"
          style={{ minWidth: `${14 + months.length * 6}rem` }}
        >
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-4 py-2 text-left font-medium">
                {t("banking.categories.category")}
              </th>
              <th className={th}>{t("banking.categories.total")}</th>
              {months.map((m) => (
                <th key={m.month} className={th}>
                  {monthLabel(m.month)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["credit", "debit"] as const).map((d) => (
              <FragmentRows key={d} title={t(`banking.categories.${d}s`)} span={2 + months.length}>
                {summary.categories.filter((c) => c.direction === d).map(row)}
              </FragmentRows>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function FragmentRows({
  title,
  span,
  children,
}: {
  title: string;
  span: number;
  children: React.ReactNode;
}) {
  return (
    <>
      <tr className="bg-surface-muted/60">
        <td
          colSpan={span}
          className="px-4 py-1 text-[11.5px] font-semibold uppercase tracking-wide text-muted-foreground"
        >
          {title}
        </td>
      </tr>
      {children}
    </>
  );
}

function Customers({ conduct }: { conduct: BankConduct }) {
  return (
    <Panel
      title={t("banking.customers.title")}
      subtitle={
        conduct.customer_top1_pct !== null && conduct.customer_top1_pct !== undefined
          ? `${t("banking.customers.top1", { pct: conduct.customer_top1_pct })} · ${t("banking.customers.top5", { pct: conduct.customer_top5_pct ?? 0 })}`
          : t("banking.customers.subtitle")
      }
      testId="banking-customers"
    >
      {conduct.customers.length === 0 ? (
        <p className="px-4 py-5 text-[13px] text-muted-foreground">{t("banking.customers.none")}</p>
      ) : (
        <table className="w-full text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-4 py-2 text-left font-medium">{t("banking.customers.party")}</th>
              <th className={th}>{t("banking.customers.amount")}</th>
              <th className={th}>{t("banking.customers.share")}</th>
            </tr>
          </thead>
          <tbody>
            {conduct.customers.slice(0, 8).map((c) => (
              <tr
                key={c.party}
                className="border-b border-border/60"
                data-testid="banking-customer"
              >
                <td className="px-4 py-1.5">{c.party}</td>
                <td className={td}>{rupees(c.amount)}</td>
                <td className={td}>{c.share_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function RoundTrips({ conduct }: { conduct: BankConduct }) {
  return (
    <Panel
      title={t("banking.trips.title")}
      subtitle={t("banking.trips.subtitle")}
      testId="banking-trips"
    >
      {conduct.round_trips.length === 0 ? (
        <p className="px-4 py-5 text-[13px] text-muted-foreground" data-testid="banking-trips-none">
          {t("banking.trips.none")}
        </p>
      ) : (
        <ul className="divide-y divide-border/60">
          {conduct.round_trips.map((r, i) => (
            <li
              key={i}
              className="px-4 py-2.5 text-[13px] text-foreground"
              data-testid="banking-trip"
            >
              {t("banking.trips.row", {
                party: r.party,
                out: rupees(r.out_amount),
                outDate: r.out_date,
                in: rupees(r.in_amount),
                inDate: r.in_date,
              })}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function Balances({ conduct }: { conduct: BankConduct }) {
  if (conduct.balances.length === 0) return null;
  return (
    <details className="rounded border border-border bg-surface" data-testid="banking-balances">
      <summary className="cursor-pointer px-4 py-2.5 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
        {t("banking.balances.title")}
      </summary>
      <div className="overflow-x-auto border-t border-border">
        <table className="w-full min-w-[34rem] text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-4 py-2 text-left font-medium">{t("banking.balances.account")}</th>
              <th className="px-3 py-2 text-left font-medium">{t("banking.balances.month")}</th>
              <th className={th}>{t("banking.balances.average")}</th>
              <th className={th}>{t("banking.balances.minimum")}</th>
              <th className={th}>{t("banking.balances.monthEnd")}</th>
            </tr>
          </thead>
          <tbody>
            {conduct.balances.flatMap((a) =>
              a.months.map((m) => (
                <tr key={`${a.account}${m.month}`} className="border-b border-border/60">
                  <td className="px-4 py-1.5">{a.account}</td>
                  <td className="px-3 py-1.5">{monthLabel(m.month)}</td>
                  <td className={td}>{rupees(m.average)}</td>
                  <td className={td}>{rupees(m.minimum)}</td>
                  <td className={td}>
                    {m.month_end === null || m.month_end === undefined ? "—" : rupees(m.month_end)}
                    {m.spike && (
                      <span className="ml-1.5">
                        <Chip tone="critical">{t("banking.balances.spike")}</Chip>
                      </span>
                    )}
                  </td>
                </tr>
              )),
            )}
          </tbody>
        </table>
      </div>
    </details>
  );
}
