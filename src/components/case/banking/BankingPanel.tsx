import { Eye } from "lucide-react";
import { useState } from "react";
import type { BankConduct, ConductFlag, TxnSummary } from "@/api/types";
import { Chip, Panel, type Tone } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { evidenceRequest, useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatDate } from "@/domain/cases";
import { lakh, monthLabel, rupees, useBankConduct, useTxnSummary } from "@/domain/transactions";
import { cn } from "@/lib/utils";
import { TH, td, th } from "./styles";
import { TransactionsTable } from "./TransactionsTable";

// The Banking view of the Financials section: the case's statement transactions each filed under a category, how it
// was read (a rule, the model, a person), and what the accounts show: cash, returns, concentration, round trips,
// balances, salary and statutory payments, promoters, unusual entries, and the statements' own integrity. It is laid
// out as the other tabs are: compact tables, small uppercase headers, dates as `03 Apr 2025`, summary figures in
// INR lakh and the register in whole rupees. The screen arranges; the engine decides nothing here.
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
        <RoundTrips caseId={caseId} conduct={conduct.data} />
      </div>
      <Balances conduct={conduct.data} />
      <TransactionsTable caseId={caseId} summary={summary.data} />
    </div>
  );
}

/** How the transactions were classified, in one strip. */
function Counts({ summary }: { summary: TxnSummary }) {
  const stats: [string, number][] = [
    ["total", summary.total],
    ["rule", summary.by_rule],
    ["model", summary.by_model],
    ["person", summary.by_person],
    ["open", summary.unsettled],
  ];
  return (
    <section
      className="rounded border border-border bg-surface px-4 py-3"
      data-testid="banking-counts"
    >
      <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3 lg:grid-cols-5">
        {stats.map(([k, n]) => (
          <div key={k} data-testid={`banking-count-${k}`}>
            <dt className="text-[11px] uppercase tracking-wide text-muted-foreground">
              {t(`banking.counts.${k}`)}
            </dt>
            <dd
              className={cn(
                "tabular mt-0.5 text-[20px] font-semibold leading-tight",
                k === "open" && n > 0 ? "text-flag-foreground" : "text-foreground",
              )}
            >
              {n.toLocaleString("en-IN")}
            </dd>
          </div>
        ))}
      </dl>
      {summary.unsettled > 0 && (
        <p className="mt-2.5 border-t border-border pt-2 text-[12px] text-muted-foreground">
          {t("banking.openNote")}
        </p>
      )}
      {summary.model_error && (
        <p
          className="mt-2 rounded border border-flag/40 bg-flag-soft px-3 py-2 text-[12.5px] text-flag-foreground"
          role="status"
          data-testid="banking-model-error"
        >
          {t("banking.modelError", { error: summary.model_error })}
        </p>
      )}
    </section>
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
              <span className="w-[5.5rem] shrink-0">
                <Chip tone={SEVERITY_TONE[f.severity]}>{t(`banking.severity.${f.severity}`)}</Chip>
              </span>
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

function MonthTable({ conduct }: { conduct: BankConduct }) {
  const dash = <span className="text-muted-foreground">—</span>;
  return (
    <Panel
      title={t("banking.months.title")}
      subtitle={t("banking.months.subtitle")}
      testId="banking-months"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-4 py-2 text-left font-medium">
                {t("banking.months.month")}
              </th>
              {(["credits", "business", "cash", "returns", "salary", "promoters"] as const).map(
                (k) => (
                  <th key={k} scope="col" className={cn(th, "whitespace-nowrap")}>
                    {t(`banking.months.${k}`)}
                  </th>
                ),
              )}
            </tr>
          </thead>
          <tbody>
            {conduct.months.map((m) => (
              <tr
                key={m.month}
                className="border-b border-border/60 last:border-b-0"
                data-testid="banking-month"
                data-month={m.month}
              >
                <th
                  scope="row"
                  className="whitespace-nowrap px-4 py-2 text-left font-medium text-foreground"
                >
                  {monthLabel(m.month)}
                </th>
                <td className={td}>{lakh(m.credits)}</td>
                <td className={td}>{lakh(m.business_credits)}</td>
                <td className={td}>
                  {m.cash_deposits > 0 ? (
                    <>
                      {lakh(m.cash_deposits)}
                      <span className="ml-1 text-[11.5px] text-muted-foreground">
                        ({m.cash_share_pct.toFixed(0)}%)
                      </span>
                    </>
                  ) : (
                    dash
                  )}
                </td>
                <td className={td}>
                  {m.returns_count > 0 ? (
                    <>
                      {lakh(m.returns_amount)}
                      <span className="ml-1 text-[11.5px] text-muted-foreground">
                        ({m.returns_count})
                      </span>
                    </>
                  ) : (
                    dash
                  )}
                </td>
                <td className={td}>{m.salary > 0 ? lakh(m.salary) : dash}</td>
                <td className={td}>{m.promoter_out > 0 ? lakh(m.promoter_out) : dash}</td>
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
      <th
        scope="row"
        className="sticky left-0 z-10 whitespace-nowrap bg-surface px-4 py-2 text-left font-medium text-foreground"
      >
        {c.label}
      </th>
      <td className={cn(td, "font-semibold text-foreground")}>{lakh(c.amount)}</td>
      {months.map((m) => (
        <td key={m.month} className={cn(td, "text-muted-foreground")}>
          {m.by_category[c.category] ? lakh(m.by_category[c.category]!) : "—"}
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
          className="w-full text-[13px]"
          style={{ minWidth: `${16 + months.length * 5.5}rem` }}
        >
          <thead>
            <tr className={TH}>
              <th
                scope="col"
                className="sticky left-0 z-10 bg-surface px-4 py-2 text-left font-medium"
              >
                {t("banking.categories.category")}
              </th>
              <th scope="col" className={cn(th, "whitespace-nowrap")}>
                {t("banking.categories.total")}
              </th>
              {months.map((m) => (
                <th key={m.month} scope="col" className={cn(th, "whitespace-nowrap")}>
                  {monthLabel(m.month)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {(["credit", "debit"] as const).map((d) => (
              <Group key={d} title={t(`banking.categories.${d}s`)} span={2 + months.length}>
                {summary.categories.filter((c) => c.direction === d).map(row)}
              </Group>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function Group({
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
          className="px-4 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
        >
          {title}
        </td>
      </tr>
      {children}
    </>
  );
}

function Customers({ conduct }: { conduct: BankConduct }) {
  const top1 = conduct.customer_top1_pct;
  return (
    <Panel
      title={t("banking.customers.title")}
      subtitle={
        top1 !== null && top1 !== undefined
          ? `${t("banking.customers.top1", { pct: top1 })} · ${t("banking.customers.top5", { pct: conduct.customer_top5_pct ?? 0 })}`
          : t("banking.customers.subtitle")
      }
      testId="banking-customers"
    >
      {conduct.customers.length === 0 ? (
        <p className="px-4 py-5 text-[13px] text-muted-foreground">{t("banking.customers.none")}</p>
      ) : (
        <table className="w-full text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-4 py-2 text-left font-medium">
                {t("banking.customers.party")}
              </th>
              <th scope="col" className={th}>
                {t("banking.customers.amount")}
              </th>
              <th scope="col" className={th}>
                {t("banking.customers.share")}
              </th>
            </tr>
          </thead>
          <tbody>
            {conduct.customers.slice(0, 8).map((c) => (
              <tr
                key={c.party}
                className="border-b border-border/60 last:border-b-0"
                data-testid="banking-customer"
              >
                <th scope="row" className="px-4 py-2 text-left font-medium text-foreground">
                  {c.party}
                </th>
                <td className={td}>{lakh(c.amount)}</td>
                <td className={td}>{c.share_pct.toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Panel>
  );
}

function RoundTrips({ caseId, conduct }: { caseId: string; conduct: BankConduct }) {
  const viewer = useDocViewer();
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
        <table className="w-full text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-4 py-2 text-left font-medium">
                {t("banking.trips.party")}
              </th>
              <th scope="col" className={th}>
                {t("banking.trips.paid")}
              </th>
              <th scope="col" className={th}>
                {t("banking.trips.received")}
              </th>
              <th scope="col" className="w-8" />
            </tr>
          </thead>
          <tbody>
            {conduct.round_trips.map((r, i) => (
              <tr
                key={i}
                className="border-b border-border/60 last:border-b-0"
                data-testid="banking-trip"
              >
                <th scope="row" className="px-4 py-2 text-left font-medium text-foreground">
                  {r.party}
                </th>
                <td className={td}>
                  {rupees(r.out_amount)}
                  <span className="block text-[11.5px] text-muted-foreground">
                    {formatDate(r.out_date)}
                  </span>
                </td>
                <td className={td}>
                  {rupees(r.in_amount)}
                  <span className="block text-[11.5px] text-muted-foreground">
                    {formatDate(r.in_date)}
                  </span>
                </td>
                <td className="pr-4 text-right">
                  {(r.evidence ?? []).length > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        const request = evidenceRequest(caseId, r.evidence ?? []);
                        if (request) viewer.open(request);
                      }}
                      className="inline-flex items-center text-muted-foreground hover:text-primary"
                      aria-label={t("banking.flags.open")}
                      title={t("banking.flags.open")}
                    >
                      <Eye className="h-4 w-4" aria-hidden />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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
        <span className="ml-2 font-normal normal-case tracking-normal">
          {t("banking.balances.subtitle")}
        </span>
      </summary>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-4 py-2 text-left font-medium">
                {t("banking.balances.account")}
              </th>
              <th scope="col" className="px-4 py-2 text-left font-medium">
                {t("banking.balances.month")}
              </th>
              <th scope="col" className={th}>
                {t("banking.balances.average")}
              </th>
              <th scope="col" className={th}>
                {t("banking.balances.minimum")}
              </th>
              <th scope="col" className={th}>
                {t("banking.balances.monthEnd")}
              </th>
            </tr>
          </thead>
          <tbody>
            {conduct.balances.flatMap((a) =>
              a.months.map((m) => (
                <tr
                  key={`${a.account}${m.month}`}
                  className="border-b border-border/60 last:border-b-0"
                >
                  <th
                    scope="row"
                    className="whitespace-nowrap px-4 py-2 text-left font-medium text-foreground"
                  >
                    {a.account}
                  </th>
                  <td className="whitespace-nowrap px-4 py-2">{monthLabel(m.month)}</td>
                  <td className={td}>{lakh(m.average)}</td>
                  <td className={td}>{lakh(m.minimum)}</td>
                  <td className={td}>
                    {m.month_end === null || m.month_end === undefined ? "—" : lakh(m.month_end)}
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
