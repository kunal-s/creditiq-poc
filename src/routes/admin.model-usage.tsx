import { useMemo, useState } from "react";
import { createFileRoute, Link, Navigate } from "@tanstack/react-router";
import { TriangleAlert } from "lucide-react";
import type { ModelCall, ModelUsageSummary } from "@/api/types";
import { DailyBars } from "@/components/admin/DailyBars";
import { Chip, Kpi, Panel } from "@/components/common/Panel";
import { StackTable } from "@/components/common/StackTable";
import { LoadingBlock, QueryView } from "@/components/common/States";
import { t } from "@/config/terminology";
import { formatWhen } from "@/domain/admin";
import { useFeatureState } from "@/domain/features";
import {
  byServiceTask,
  caseOf,
  daily,
  errorsByKind,
  formatCost,
  formatTokens,
  kindLabel,
  modelLabel,
  PAGE,
  REACHABLE,
  serviceLabel,
  SERVICES,
  sourceLabel,
  taskLabel,
  totals,
  useModelCalls,
  useModelUsage,
  type UsageFilters,
} from "@/domain/modelUsage";
import { useCan } from "@/domain/session";

// Administration > Model usage: every request the system made to a language model (the document
// service, the memo copilot, the case assistant), by day, with its tokens, its cost at the configured
// prices and what failed. Only where the deployment has it on (features.model_usage) and only for a
// role with model_usage.read; otherwise the address leads back to Administration.
// Test ids: model-usage, usage-filters, usage-unavailable, usage-kpi-{calls,tokens,cost,latency},
// usage-tokens-chart, usage-cost-chart, usage-by-service, usage-group, usage-by-kind, usage-kind,
// usage-calls, usage-call, usage-page-prev, usage-page-next.

export const Route = createFileRoute("/admin/model-usage")({ component: ModelUsageRoute });

const control =
  "h-8 min-w-0 rounded border border-border bg-surface px-2 text-[12.5px] text-foreground outline-none focus:border-primary/60";
const th = "px-3 py-2 font-medium";
const num = "tabular whitespace-nowrap px-3 py-2 text-right";

function ModelUsageRoute() {
  const on = useFeatureState("model_usage");
  const can = useCan("model_usage.read");
  if (on === false || (on && !can)) return <Navigate to="/admin" replace />;
  return (
    <div className="space-y-4 px-4 py-5 sm:px-6" data-testid="model-usage">
      {on ? <ModelUsage /> : <LoadingBlock />}
    </div>
  );
}

function ModelUsage() {
  // The range, service and task shape every figure; outcome, failure and appraisal narrow the call list.
  const [range, setRange] = useState<UsageFilters>({});
  const [list, setList] = useState<UsageFilters>({});
  const [offset, setOffset] = useState(0);
  const summary = useModelUsage(range);
  const calls = useModelCalls({ ...range, ...list }, offset);

  const narrow = (patch: UsageFilters) => {
    setRange((f) => ({ ...f, ...patch }));
    setOffset(0);
  };
  const narrowList = (patch: UsageFilters) => {
    setList((f) => ({ ...f, ...patch }));
    setOffset(0);
  };

  return (
    <>
      <p className="max-w-3xl text-[12.5px] text-muted-foreground">
        {t("admin.modelUsage.purpose")}
      </p>
      <QueryView query={summary}>
        {(s) => (
          <>
            <Filters summary={s} filters={range} onChange={narrow} />
            <Unavailable names={s.unavailable ?? []} />
            {!s.rows?.length ? (
              <Panel title={t("admin.modelUsage.calls")}>
                <div className="px-4 py-10 text-center" data-testid="usage-empty">
                  <p className="text-[14px] font-medium text-foreground">
                    {t("admin.modelUsage.empty")}
                  </p>
                  <p className="mx-auto mt-1 max-w-md text-[12.5px] text-muted-foreground">
                    {t("admin.modelUsage.emptyHelp")}
                  </p>
                </div>
              </Panel>
            ) : (
              <Figures summary={s} />
            )}
          </>
        )}
      </QueryView>
      {!!summary.data?.rows?.length && (
        <CallList
          query={calls}
          summary={summary.data}
          filters={list}
          onChange={narrowList}
          offset={offset}
          onPage={setOffset}
        />
      )}
    </>
  );
}

function Filters({
  summary,
  filters,
  onChange,
}: {
  summary: ModelUsageSummary;
  filters: UsageFilters;
  onChange: (patch: UsageFilters) => void;
}) {
  const tasks = useMemo(
    () =>
      [
        ...new Set(
          (summary.rows ?? [])
            .filter((r) => !filters.service || r.service === filters.service)
            .map((r) => r.task ?? "")
            .filter(Boolean),
        ),
      ].sort(),
    [summary.rows, filters.service],
  );
  return (
    <section
      className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap sm:items-end"
      aria-label={t("admin.modelUsage.filters")}
      data-testid="usage-filters"
    >
      <label className="flex min-w-0 flex-col gap-1">
        <span className="field-label">{t("admin.modelUsage.from")}</span>
        <input
          type="date"
          className={control}
          value={filters.from ?? summary.from_date}
          max={filters.to ?? summary.to_date}
          onChange={(e) => onChange({ from: e.target.value || undefined })}
          data-testid="usage-from"
        />
      </label>
      <label className="flex min-w-0 flex-col gap-1">
        <span className="field-label">{t("admin.modelUsage.to")}</span>
        <input
          type="date"
          className={control}
          value={filters.to ?? summary.to_date}
          min={filters.from ?? summary.from_date}
          onChange={(e) => onChange({ to: e.target.value || undefined })}
          data-testid="usage-to"
        />
      </label>
      <label className="flex min-w-0 flex-col gap-1">
        <span className="field-label">{t("admin.modelUsage.service")}</span>
        <select
          className={control}
          value={filters.service ?? ""}
          onChange={(e) => onChange({ service: e.target.value || undefined, task: undefined })}
          data-testid="usage-service"
        >
          <option value="">{t("admin.modelUsage.allServices")}</option>
          {SERVICES.map((s) => (
            <option key={s} value={s}>
              {serviceLabel(s)}
            </option>
          ))}
        </select>
      </label>
      <label className="flex min-w-0 flex-col gap-1">
        <span className="field-label">{t("admin.modelUsage.task")}</span>
        <select
          className={control}
          value={filters.task ?? ""}
          onChange={(e) => onChange({ task: e.target.value || undefined })}
          data-testid="usage-task"
        >
          <option value="">{t("admin.modelUsage.allTasks")}</option>
          {tasks.map((k) => (
            <option key={k} value={k}>
              {taskLabel(k)}
            </option>
          ))}
        </select>
      </label>
    </section>
  );
}

function Unavailable({ names }: { names: string[] }) {
  if (!names.length) return null;
  return (
    <p
      className="flex items-start gap-2 rounded border border-flag/35 bg-flag-soft px-3 py-2 text-[12.5px] text-flag-foreground"
      role="status"
      data-testid="usage-unavailable"
    >
      <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      {t("admin.modelUsage.unavailable", { names: names.map(serviceLabel).join(", ") })}
    </p>
  );
}

function Figures({ summary }: { summary: ModelUsageSummary }) {
  const rows = summary.rows ?? [];
  const all = totals(rows);
  const days = daily(rows, summary.from_date, summary.to_date);
  const groups = byServiceTask(rows);
  const kinds = errorsByKind(rows);
  const money = (v: number) => formatCost(v, summary.currency);
  const anyCost = days.some((d) => d.cost != null);

  return (
    <>
      <div className="grid grid-cols-2 gap-3 @min-[56rem]/main:grid-cols-4">
        <Kpi
          testId="usage-kpi-calls"
          label={t("admin.modelUsage.calls")}
          value={formatTokens(all.calls)}
          note={t("admin.modelUsage.callsNote", {
            ok: formatTokens(all.ok),
            errors: formatTokens(all.errors),
          })}
        />
        <Kpi
          testId="usage-kpi-tokens"
          label={t("admin.modelUsage.tokens")}
          value={formatTokens(all.input + all.output)}
          note={t("admin.modelUsage.tokensNote", {
            input: formatTokens(all.input),
            output: formatTokens(all.output),
          })}
        />
        <Kpi
          testId="usage-kpi-cost"
          label={t("admin.modelUsage.cost")}
          value={
            all.costUnknown ? (
              <span className="text-[15px] font-medium text-muted-foreground">
                {t("admin.modelUsage.priceNotSet")}
              </span>
            ) : (
              money(all.cost)
            )
          }
          {...(all.costUnknown
            ? {}
            : {
                note: all.costPartial
                  ? t("admin.modelUsage.costPartial")
                  : t("admin.modelUsage.costNote"),
              })}
        />
        <Kpi
          testId="usage-kpi-latency"
          label={t("admin.modelUsage.latency")}
          value={
            all.p95 == null ? (
              <span className="text-[15px] font-medium text-muted-foreground">
                {t("admin.modelUsage.noLatency")}
              </span>
            ) : (
              t("admin.modelUsage.ms", { n: formatTokens(Math.round(all.p95)) })
            )
          }
          {...(all.p95 == null ? {} : { note: t("admin.modelUsage.latencyNote") })}
        />
      </div>
      <p
        className="tabular flex flex-wrap gap-x-4 gap-y-0.5 text-[12px] text-muted-foreground"
        data-testid="usage-sources"
      >
        <span>
          {t("admin.modelUsage.live")}:{" "}
          <span className="text-foreground">{formatTokens(all.live)}</span>
        </span>
        <span>
          {t("admin.modelUsage.replayHits")}:{" "}
          <span className="text-foreground">{formatTokens(all.replayHits)}</span>
        </span>
        <span>
          {t("admin.modelUsage.replayMisses")}:{" "}
          <span className="text-foreground">{formatTokens(all.replayMisses)}</span>
        </span>
      </p>

      <div className="grid gap-4 @min-[60rem]/main:grid-cols-2">
        <Panel
          title={t("admin.modelUsage.dailyTokens")}
          subtitle={t("admin.modelUsage.dailyTokensHelp")}
        >
          <DailyBars
            testId="usage-tokens-chart"
            title={t("admin.modelUsage.dailyTokens")}
            format={formatTokens}
            series={[
              {
                key: "input",
                label: t("admin.modelUsage.input"),
                className: "fill-usage-input",
                swatch: "bg-usage-input",
              },
              {
                key: "output",
                label: t("admin.modelUsage.output"),
                className: "fill-usage-output",
                swatch: "bg-usage-output",
              },
            ]}
            columns={days.map((d) => ({ day: d.day, values: [d.input, d.output] }))}
          />
        </Panel>
        <Panel
          title={t("admin.modelUsage.dailyCost")}
          subtitle={t("admin.modelUsage.dailyCostHelp")}
        >
          {anyCost ? (
            <DailyBars
              testId="usage-cost-chart"
              title={t("admin.modelUsage.dailyCost")}
              format={money}
              axis={(v) => v.toLocaleString("en-IN", { maximumFractionDigits: 4 })}
              series={[
                {
                  key: "cost",
                  label: t("admin.modelUsage.cost"),
                  className: "fill-usage-input",
                  swatch: "bg-usage-input",
                },
              ]}
              columns={days.map((d) => ({ day: d.day, values: [d.cost ?? 0] }))}
            />
          ) : (
            <p
              className="px-4 py-10 text-center text-[12.5px] text-muted-foreground"
              data-testid="usage-cost-chart-empty"
            >
              {t("admin.modelUsage.noCost")}
            </p>
          )}
        </Panel>
      </div>

      <div className="grid gap-4 @min-[60rem]/main:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Panel
          title={t("admin.modelUsage.byService")}
          subtitle={t("admin.modelUsage.byServiceHelp")}
          testId="usage-by-service"
        >
          <div className="overflow-x-auto">
            <StackTable className="stack-skip-empty w-full min-w-[560px] text-[12.5px]">
              <thead>
                <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
                  <th className="px-4 py-2 font-medium">{t("admin.modelUsage.service")}</th>
                  <th className={th}>{t("admin.modelUsage.task")}</th>
                  <th className={th}>{t("admin.modelUsage.model")}</th>
                  <th className={`${th} text-right`}>{t("admin.modelUsage.calls")}</th>
                  <th className={`${th} text-right`}>{t("admin.modelUsage.errors")}</th>
                  <th className={`${th} text-right`}>{t("admin.modelUsage.input")}</th>
                  <th className={`${th} text-right`}>{t("admin.modelUsage.output")}</th>
                  <th className={`${th} text-right`}>{t("admin.modelUsage.cost")}</th>
                  <th className="px-4 py-2 text-right font-medium">{t("admin.modelUsage.p95")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {groups.map((g) => (
                  <tr key={`${g.service}|${g.task}|${g.model}`} data-testid="usage-group">
                    <td className="px-4 py-2 font-medium">{serviceLabel(g.service)}</td>
                    <td className="px-3 py-2">{taskLabel(g.task)}</td>
                    <td className="px-3 py-2 text-muted-foreground">{modelLabel(g.model)}</td>
                    <td className={num}>{formatTokens(g.calls)}</td>
                    <td className={num}>
                      {g.errors > 0 ? (
                        <span className="text-critical-text">{formatTokens(g.errors)}</span>
                      ) : (
                        "0"
                      )}
                    </td>
                    <td className={num}>{formatTokens(g.input)}</td>
                    <td className={num}>{formatTokens(g.output)}</td>
                    <td className={num}>
                      {g.priceSet && g.cost != null ? (
                        money(g.cost)
                      ) : (
                        <Chip tone="muted">{t("admin.modelUsage.priceNotSet")}</Chip>
                      )}
                    </td>
                    <td className="tabular px-4 py-2 text-right text-muted-foreground">
                      {g.p95 == null
                        ? null
                        : t("admin.modelUsage.ms", { n: formatTokens(Math.round(g.p95)) })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </StackTable>
          </div>
        </Panel>
        <Panel
          title={t("admin.modelUsage.byKind")}
          subtitle={t("admin.modelUsage.byKindHelp")}
          testId="usage-by-kind"
        >
          {kinds.length === 0 ? (
            <p className="px-4 py-6 text-[12.5px] text-muted-foreground">
              {t("admin.modelUsage.noFailures")}
            </p>
          ) : (
            <ul className="divide-y divide-border">
              {kinds.map((k) => (
                <li
                  key={k.kind}
                  className="flex items-center justify-between gap-3 px-4 py-2 text-[12.5px]"
                  data-testid="usage-kind"
                  data-kind={k.kind}
                >
                  <span>{kindLabel(k.kind)}</span>
                  <span className="tabular font-medium">{formatTokens(k.n)}</span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </>
  );
}

function Outcome({ call }: { call: ModelCall }) {
  if (call.status === "ok") return <Chip tone="positive">{t("admin.modelUsage.answered")}</Chip>;
  const kind = call.kind || call.error_code || "other";
  // A missing recording is how replay works, not a fault of the model: it is shown quietly.
  return <Chip tone={kind === "replay_miss" ? "muted" : "critical"}>{kindLabel(kind)}</Chip>;
}

function CallList({
  query,
  summary,
  filters,
  onChange,
  offset,
  onPage,
}: {
  query: ReturnType<typeof useModelCalls>;
  summary: ModelUsageSummary;
  filters: UsageFilters;
  onChange: (patch: UsageFilters) => void;
  offset: number;
  onPage: (offset: number) => void;
}) {
  const kinds = errorsByKind(summary.rows ?? []);
  return (
    <Panel
      title={t("admin.modelUsage.callList")}
      subtitle={t("admin.modelUsage.callListHelp")}
      testId="usage-calls"
      action={
        <div className="grid w-full grid-cols-2 gap-2 sm:flex sm:w-auto sm:flex-wrap">
          <select
            className={control}
            value={filters.status ?? ""}
            onChange={(e) => onChange({ status: e.target.value || undefined })}
            aria-label={t("admin.modelUsage.status")}
            data-testid="usage-status"
          >
            <option value="">{t("admin.modelUsage.allOutcomes")}</option>
            <option value="ok">{t("admin.modelUsage.okOnly")}</option>
            <option value="error">{t("admin.modelUsage.errorsOnly")}</option>
          </select>
          <select
            className={control}
            value={filters.kind ?? ""}
            onChange={(e) => onChange({ kind: e.target.value || undefined })}
            aria-label={t("admin.modelUsage.kind")}
            data-testid="usage-kind-filter"
          >
            <option value="">{t("admin.modelUsage.allKinds")}</option>
            {kinds.map((k) => (
              <option key={k.kind} value={k.kind}>
                {kindLabel(k.kind)}
              </option>
            ))}
          </select>
          <input
            className={`${control} col-span-2 sm:w-44`}
            value={filters.case_ref ?? ""}
            onChange={(e) => onChange({ case_ref: e.target.value.trim() || undefined })}
            placeholder={t("admin.modelUsage.caseRef")}
            aria-label={t("admin.modelUsage.caseRef")}
            data-testid="usage-case"
          />
        </div>
      }
    >
      <QueryView query={query} compact>
        {(page) => (
          <>
            {!!page.unavailable?.length && (
              <p className="border-b border-border bg-flag-soft px-4 py-1.5 text-[12px] text-flag-foreground">
                {t("admin.modelUsage.partialCalls")}
              </p>
            )}
            {!page.rows?.length ? (
              <p
                className="px-4 py-8 text-center text-[12.5px] text-muted-foreground"
                data-testid="usage-calls-none"
              >
                {t("admin.modelUsage.noMatch")}
              </p>
            ) : (
              <div className="overflow-x-auto">
                <StackTable className="stack-skip-empty w-full min-w-[720px] text-[12.5px]">
                  <thead>
                    <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
                      <th className="px-4 py-2 font-medium">{t("admin.modelUsage.when")}</th>
                      <th className={th}>{t("admin.modelUsage.service")}</th>
                      <th className={th}>{t("admin.modelUsage.task")}</th>
                      <th className={th}>{t("admin.modelUsage.outcome")}</th>
                      <th className={th}>{t("admin.modelUsage.model")}</th>
                      <th className={`${th} text-right`}>{t("admin.modelUsage.input")}</th>
                      <th className={`${th} text-right`}>{t("admin.modelUsage.output")}</th>
                      <th className={`${th} text-right`}>{t("admin.modelUsage.latencyCol")}</th>
                      <th className="px-4 py-2 font-medium">{t("admin.modelUsage.appraisal")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {(page.rows ?? []).map((c) => {
                      const ref = caseOf(c);
                      return (
                        <tr key={c.id} data-testid="usage-call" data-status={c.status}>
                          <td className="tabular whitespace-nowrap px-4 py-2 text-muted-foreground">
                            {formatWhen(c.at)}
                          </td>
                          <td className="px-3 py-2">{serviceLabel(c.service)}</td>
                          <td className="px-3 py-2">
                            {taskLabel(c.task)}
                            {c.source !== "replay_miss" && (
                              <span className="block text-[11px] text-muted-foreground">
                                {sourceLabel(c.source)}
                              </span>
                            )}
                          </td>
                          <td className="px-3 py-2">
                            <Outcome call={c} />
                          </td>
                          <td className="px-3 py-2 text-muted-foreground">{modelLabel(c.model)}</td>
                          <td className={num}>
                            {c.input_tokens == null ? null : formatTokens(c.input_tokens)}
                          </td>
                          <td className={num}>
                            {c.output_tokens == null ? null : formatTokens(c.output_tokens)}
                          </td>
                          <td className="tabular px-3 py-2 text-right text-muted-foreground">
                            {c.source === "live" && c.latency_ms != null
                              ? t("admin.modelUsage.ms", {
                                  n: formatTokens(Math.round(c.latency_ms)),
                                })
                              : null}
                          </td>
                          <td className="px-4 py-2">
                            {ref && (
                              <Link
                                to="/appraisals/$caseId"
                                params={{ caseId: ref }}
                                className="rounded border border-border bg-muted/50 px-1.5 py-px text-[11px] text-primary hover:underline"
                              >
                                {ref}
                              </Link>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </StackTable>
              </div>
            )}
            {page.total > 0 && (
              <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-4 py-2 text-[12px] text-muted-foreground">
                <span className="tabular" data-testid="usage-page">
                  {t("admin.modelUsage.shown", {
                    from: formatTokens(Math.min(offset + 1, page.total)),
                    to: formatTokens(Math.min(offset + (page.rows?.length ?? 0), page.total)),
                    total: formatTokens(page.total),
                  })}
                </span>
                <span className="flex gap-2">
                  <button
                    type="button"
                    className="h-8 rounded border border-border bg-surface px-3 text-[12px] font-medium text-foreground hover:bg-muted disabled:opacity-40"
                    disabled={offset === 0}
                    onClick={() => onPage(Math.max(0, offset - PAGE))}
                    data-testid="usage-page-prev"
                  >
                    {t("admin.modelUsage.previous")}
                  </button>
                  <button
                    type="button"
                    className="h-8 rounded border border-border bg-surface px-3 text-[12px] font-medium text-foreground hover:bg-muted disabled:opacity-40"
                    disabled={offset + PAGE >= Math.min(page.total, REACHABLE)}
                    onClick={() => onPage(offset + PAGE)}
                    data-testid="usage-page-next"
                  >
                    {t("admin.modelUsage.next")}
                  </button>
                </span>
              </div>
            )}
          </>
        )}
      </QueryView>
    </Panel>
  );
}
