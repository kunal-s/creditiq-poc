import { Eye } from "lucide-react";
import { useState } from "react";
import type { BankConduct, ConductFlag, TxnSummary } from "@/api/types";
import { Chip, type Tone } from "@/components/common/Panel";
import { RailPanel, RailRows } from "@/components/common/RailPanel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { evidenceRequest, useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { formatDate, useCase } from "@/domain/cases";
import { lakh, monthLabel, rupees, useBankConduct, useTxnSummary } from "@/domain/transactions";
import { cn } from "@/lib/utils";
import { Block } from "./Block";
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
    <div className="space-y-3" data-testid="banking">
      <Flags caseId={caseId} flags={conduct.data.flags} />
      <MonthTable conduct={conduct.data} />
      <CategoryTable summary={summary.data} />
      <RoundTrips caseId={caseId} conduct={conduct.data} />
      <Balances conduct={conduct.data} />
      <TransactionsTable caseId={caseId} summary={summary.data} />
    </div>
  );
}

/** The right rail of the Banking tab, where the other tabs show the spread's status: how the transactions were
 * classified and what the observations number. */
export function BankingRail({ caseId }: { caseId: string }) {
  const summary = useTxnSummary(caseId);
  const conduct = useBankConduct(caseId);
  const header = useCase(caseId);
  const s = summary.data;
  const flags = conduct.data?.flags ?? [];
  const by = (sev: ConductFlag["severity"]) => flags.filter((f) => f.severity === sev).length;
  const months = s?.months ?? [];
  return (
    <>
      <RailPanel
        title={t("banking.rail.title")}
        subtitle={header.data?.borrower}
        testId="banking-counts"
      >
        {s ? (
          <>
            <div className="mt-2 grid grid-cols-2 divide-x divide-border border-y border-border">
              <div className="px-4 py-3" data-testid="banking-count-total">
                <p className="tabular text-[22px] font-semibold leading-none">
                  {s.total.toLocaleString("en-IN")}
                </p>
                <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                  {t("banking.counts.total")}
                </p>
              </div>
              <div className="px-4 py-3" data-testid="banking-count-open">
                <p
                  className={cn(
                    "tabular text-[22px] font-semibold leading-none",
                    s.unsettled > 0 && "text-flag-foreground",
                  )}
                >
                  {s.unsettled.toLocaleString("en-IN")}
                </p>
                <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                  {t("banking.counts.open")}
                </p>
              </div>
            </div>
            <dl className="divide-y divide-border">
              {(
                [
                  ["rule", s.by_rule],
                  ["model", s.by_model],
                  ["person", s.by_person],
                ] as const
              ).map(([k, n]) => (
                <div
                  key={k}
                  className="flex items-baseline justify-between gap-3 px-4 py-2"
                  data-testid={`banking-count-${k}`}
                >
                  <dt className="text-[12px] text-muted-foreground">{t(`banking.counts.${k}`)}</dt>
                  <dd className="tabular text-right text-[12.5px] text-foreground">{n}</dd>
                </div>
              ))}
            </dl>
            <RailRows
              rows={[
                { label: t("banking.rail.accounts"), value: s.accounts.length },
                ...(months.length > 0
                  ? [
                      {
                        label: t("banking.rail.period"),
                        value: `${monthLabel(months[0]!.month)} – ${monthLabel(months[months.length - 1]!.month)}`,
                      },
                    ]
                  : []),
                {
                  label: t("banking.rail.observations"),
                  value: t("banking.rail.observationCounts", {
                    concern: by("concern"),
                    watch: by("watch"),
                    info: by("info"),
                  }),
                },
              ]}
            />
            {s.unsettled > 0 && (
              <p className="border-t border-border px-4 py-2 text-[12px] text-muted-foreground">
                {t("banking.openNote")}
              </p>
            )}
            {s.model_error && (
              <p
                className="border-t border-flag/40 bg-flag-soft px-4 py-2 text-[12px] text-flag-foreground"
                role="status"
                data-testid="banking-model-error"
              >
                {t("banking.modelError", { error: s.model_error })}
              </p>
            )}
          </>
        ) : (
          <p className="px-4 py-4 text-[12px] text-muted-foreground">{t("state.loading")}</p>
        )}
      </RailPanel>
      {conduct.data && <CustomersRail conduct={conduct.data} />}
    </>
  );
}

function Flags({ caseId, flags }: { caseId: string; flags: ConductFlag[] }) {
  const [all, setAll] = useState(false);
  const viewer = useDocViewer();
  const shown = all ? flags : flags.slice(0, FLAGS_SHOWN);
  return (
    <Block
      title={t("banking.flags.title")}
      subtitle={t("banking.flags.subtitle")}
      testId="banking-flags"
    >
      {flags.length === 0 ? (
        <p className="px-4 py-3 text-[13px] text-muted-foreground" data-testid="banking-flags-none">
          {t("banking.flags.none")}
        </p>
      ) : (
        <ul className="divide-y divide-border/60">
          {shown.map((f, i) => (
            <li
              key={i}
              className="flex items-start gap-3 px-4 py-1.5"
              data-testid="banking-flag"
              data-kind={f.kind}
              data-severity={f.severity}
            >
              <span className="w-[5.25rem] shrink-0">
                <Chip tone={SEVERITY_TONE[f.severity]}>{t(`banking.severity.${f.severity}`)}</Chip>
              </span>
              <p className="min-w-0 flex-1 text-[13px] leading-snug text-foreground">{f.message}</p>
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
        <div className="border-t border-border px-4 py-1.5 text-center">
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
    </Block>
  );
}

function MonthTable({ conduct }: { conduct: BankConduct }) {
  const dash = <span className="text-muted-foreground">—</span>;
  return (
    <Block
      title={t("banking.months.title")}
      subtitle={t("banking.months.subtitle")}
      testId="banking-months"
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-3 py-1.5 text-left font-medium">
                {t("banking.months.month")}
              </th>
              {(["credits", "business", "cash", "returns", "salary", "promoters"] as const).map(
                (k) => (
                  <th key={k} scope="col" className={th}>
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
                  className="whitespace-nowrap px-3 py-1.5 text-left font-medium text-foreground"
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
    </Block>
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
        className="sticky left-0 z-10 whitespace-nowrap bg-surface px-3 py-1.5 text-left font-medium text-foreground"
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
    <Block
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
                className="sticky left-0 z-10 bg-surface px-3 py-1.5 text-left font-medium"
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
    </Block>
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
          className="px-3 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground"
        >
          {title}
        </td>
      </tr>
      {children}
    </>
  );
}

/** The customers receipts came from, in the rail: a name and a share on each line. */
function CustomersRail({ conduct }: { conduct: BankConduct }) {
  const top1 = conduct.customer_top1_pct;
  return (
    <RailPanel
      title={t("banking.customers.title")}
      subtitle={
        top1 !== null && top1 !== undefined
          ? `${t("banking.customers.top1", { pct: top1 })} · ${t("banking.customers.top5", { pct: conduct.customer_top5_pct ?? 0 })}`
          : t("banking.customers.subtitle")
      }
      testId="banking-customers"
    >
      {conduct.customers.length === 0 ? (
        <p className="px-4 py-3 text-[12.5px] text-muted-foreground">
          {t("banking.customers.none")}
        </p>
      ) : (
        <dl className="mt-2 divide-y divide-border border-t border-border">
          {conduct.customers.slice(0, 6).map((c) => (
            <div
              key={c.party}
              className="flex items-baseline justify-between gap-3 px-4 py-1.5"
              data-testid="banking-customer"
            >
              <dt
                className="min-w-0 truncate text-[12.5px] font-medium text-foreground"
                title={c.party}
              >
                {c.party}
              </dt>
              <dd className="tabular shrink-0 text-right text-[12.5px] text-foreground">
                {lakh(c.amount)}
                <span className="ml-1.5 text-[11.5px] text-muted-foreground">
                  {c.share_pct.toFixed(1)}%
                </span>
              </dd>
            </div>
          ))}
        </dl>
      )}
    </RailPanel>
  );
}

function RoundTrips({ caseId, conduct }: { caseId: string; conduct: BankConduct }) {
  const viewer = useDocViewer();
  return (
    <Block
      title={t("banking.trips.title")}
      subtitle={t("banking.trips.subtitle")}
      testId="banking-trips"
    >
      {conduct.round_trips.length === 0 ? (
        <p className="px-4 py-3 text-[13px] text-muted-foreground" data-testid="banking-trips-none">
          {t("banking.trips.none")}
        </p>
      ) : (
        <table className="w-full text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-3 py-1.5 text-left font-medium">
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
                <th scope="row" className="px-3 py-1.5 text-left font-medium text-foreground">
                  {r.party}
                </th>
                <td className={td}>
                  {rupees(r.out_amount)}
                  <span className="block whitespace-nowrap text-[11.5px] text-muted-foreground">
                    {formatDate(r.out_date)}
                  </span>
                </td>
                <td className={td}>
                  {rupees(r.in_amount)}
                  <span className="block whitespace-nowrap text-[11.5px] text-muted-foreground">
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
    </Block>
  );
}

function Balances({ conduct }: { conduct: BankConduct }) {
  if (conduct.balances.length === 0) return null;
  return (
    <details className="rounded border border-border bg-surface" data-testid="banking-balances">
      <summary className="cursor-pointer px-4 py-2 text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
        {t("banking.balances.title")}
        <span className="ml-2 font-normal normal-case tracking-normal">
          {t("banking.balances.subtitle")}
        </span>
      </summary>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[13px]">
          <thead>
            <tr className={TH}>
              <th scope="col" className="px-3 py-1.5 text-left font-medium">
                {t("banking.balances.account")}
              </th>
              <th scope="col" className="px-3 py-1.5 text-left font-medium">
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
                    className="whitespace-nowrap px-3 py-1.5 text-left font-medium text-foreground"
                  >
                    {a.account}
                  </th>
                  <td className="whitespace-nowrap px-3 py-1.5">{monthLabel(m.month)}</td>
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
