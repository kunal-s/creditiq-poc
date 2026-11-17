import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { t, tOr } from "@/config/terminology";
import type { ModelCall, ModelUsageRow } from "@/api/types";
import { useFeature } from "./features";
import { useCan } from "./session";

// Model usage (Administration): the model call logs of the document service, the engine's memo copilot
// and the case assistant, read together by the engine (/api/admin/model-usage). Only an administrator
// with model_usage.read sees it, and only where the deployment has it switched on (features.model_usage).

export type UsageFilters = {
  from?: string | undefined;
  to?: string | undefined;
  service?: string | undefined;
  task?: string | undefined;
  status?: string | undefined;
  kind?: string | undefined;
  case_ref?: string | undefined;
};

export const SERVICES = ["ingestion", "cam", "copilot"] as const;
export const PAGE = 25;
/** The newest calls the list can page through (each source answers at most this many at once). */
export const REACHABLE = 500;

export function useModelUsageAllowed(): boolean {
  // Both hooks run on every render; only then are they combined.
  const on = useFeature("model_usage");
  const can = useCan("model_usage.read");
  return on && can;
}

export function useModelUsage(f: UsageFilters) {
  const allowed = useModelUsageAllowed();
  return useQuery({
    queryKey: ["admin", "model-usage", "summary", f.from, f.to, f.service, f.task],
    queryFn: () =>
      api.modelUsageSummary({ from: f.from, to: f.to, service: f.service, task: f.task }),
    enabled: allowed,
  });
}

export function useModelCalls(f: UsageFilters, offset: number, limit = PAGE) {
  const allowed = useModelUsageAllowed();
  return useQuery({
    queryKey: ["admin", "model-usage", "calls", f, offset, limit],
    queryFn: () => api.modelUsageCalls({ ...f, offset, limit }),
    enabled: allowed,
  });
}

export type Totals = {
  calls: number;
  ok: number;
  errors: number;
  live: number;
  replayHits: number;
  replayMisses: number;
  input: number;
  output: number;
  cached: number;
  cost: number;
  /** Some of the cost could not be counted: a model's price is not set. */
  costPartial: boolean;
  /** No row had a price: the cost is not known at all. */
  costUnknown: boolean;
  p95: number | null;
};

export function totals(rows: ModelUsageRow[]): Totals {
  const t: Totals = {
    calls: 0,
    ok: 0,
    errors: 0,
    live: 0,
    replayHits: 0,
    replayMisses: 0,
    input: 0,
    output: 0,
    cached: 0,
    cost: 0,
    costPartial: false,
    costUnknown: true,
    p95: null,
  };
  for (const r of rows) {
    t.calls += r.calls;
    t.ok += r.ok;
    t.errors += r.calls - r.ok;
    t.live += r.live_calls ?? 0;
    t.replayHits += r.replay_hits ?? 0;
    t.replayMisses += r.replay_misses ?? 0;
    t.input += r.input_tokens ?? 0;
    t.output += r.output_tokens ?? 0;
    t.cached += r.cached_tokens ?? 0;
    if (r.price_set && r.cost != null) {
      t.cost += r.cost;
      t.costUnknown = false;
    } else if ((r.input_tokens ?? 0) + (r.output_tokens ?? 0) > 0) {
      t.costPartial = true;
    }
    // The highest daily p95 of the live calls: a bound, not a merged percentile.
    if (r.latency_ms_p95 != null) t.p95 = Math.max(t.p95 ?? 0, r.latency_ms_p95);
  }
  return t;
}

export type Day = { day: string; input: number; output: number; cost: number | null };

/** Every day of the range, in order, with its tokens and cost (a day with nothing logged reads 0). */
export function daily(rows: ModelUsageRow[], from: string, to: string): Day[] {
  const by = new Map<string, Day>();
  for (
    let d = new Date(`${from}T00:00:00Z`);
    d <= new Date(`${to}T00:00:00Z`);
    d.setUTCDate(d.getUTCDate() + 1)
  ) {
    const key = d.toISOString().slice(0, 10);
    by.set(key, { day: key, input: 0, output: 0, cost: null });
  }
  for (const r of rows) {
    const d = by.get(r.day) ?? { day: r.day, input: 0, output: 0, cost: null };
    d.input += r.input_tokens ?? 0;
    d.output += r.output_tokens ?? 0;
    if (r.price_set && r.cost != null) d.cost = (d.cost ?? 0) + r.cost;
    by.set(r.day, d);
  }
  return [...by.values()].sort((a, b) => a.day.localeCompare(b.day));
}

export type Group = {
  service: string;
  task: string;
  model: string;
  calls: number;
  errors: number;
  input: number;
  output: number;
  cost: number | null;
  priceSet: boolean;
  p95: number | null;
};

/** By service, task and model over the whole range. */
export function byServiceTask(rows: ModelUsageRow[]): Group[] {
  const by = new Map<string, Group>();
  for (const r of rows) {
    const key = `${r.service}|${r.task ?? ""}|${r.model ?? ""}`;
    const g =
      by.get(key) ??
      ({
        service: r.service,
        task: r.task ?? "",
        model: r.model ?? "",
        calls: 0,
        errors: 0,
        input: 0,
        output: 0,
        cost: null,
        priceSet: !!r.price_set,
        p95: null,
      } as Group);
    g.calls += r.calls;
    g.errors += r.calls - r.ok;
    g.input += r.input_tokens ?? 0;
    g.output += r.output_tokens ?? 0;
    if (r.price_set && r.cost != null) g.cost = (g.cost ?? 0) + r.cost;
    if (r.latency_ms_p95 != null) g.p95 = Math.max(g.p95 ?? 0, r.latency_ms_p95);
    by.set(key, g);
  }
  return [...by.values()].sort((a, b) => b.calls - a.calls);
}

/** Failed attempts by kind of failure (or by code where no kind was recorded), most first. */
export function errorsByKind(rows: ModelUsageRow[]): { kind: string; n: number }[] {
  const by = new Map<string, number>();
  for (const r of rows)
    for (const [k, n] of Object.entries(r.errors ?? {})) by.set(k, (by.get(k) ?? 0) + n);
  return [...by.entries()].map(([kind, n]) => ({ kind, n })).sort((a, b) => b.n - a.n);
}

export function formatCost(value: number, currency: string): string {
  return `${currency} ${value.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 4 })}`;
}

export function formatTokens(n: number): string {
  return n.toLocaleString("en-IN");
}

/** The case a call belongs to, when it names one the screens can open. */
export function caseOf(c: ModelCall): string | null {
  return c.case_ref && /^BBG-\d{4}-\d+$/.test(c.case_ref) ? c.case_ref : null;
}

const key = (id: string) => id.replace(/[^A-Za-z0-9]+/g, "_");
const words = (id: string) => id.replace(/[_-]+/g, " ");

export function serviceLabel(service: string): string {
  return tOr(`admin.modelUsage.serviceName.${key(service)}`, words(service));
}

export function taskLabel(task: string | null | undefined): string {
  if (!task) return "";
  return tOr(`admin.modelUsage.taskName.${key(task)}`, words(task));
}

export function sourceLabel(source: string): string {
  return tOr(`admin.modelUsage.sourceName.${key(source)}`, words(source));
}

/** A model by its configured name: the screen never shows a provider's model id. */
export function modelLabel(model: string | null | undefined): string {
  return tOr(
    `admin.modelUsage.modelName.${key(model ?? "")}`,
    t("admin.modelUsage.modelName.other"),
  );
}

/** A kind of failure in plain words; an error code with no kind reads as another failure. */
export function kindLabel(kind: string): string {
  return tOr(`admin.modelUsage.kindName.${key(kind)}`, t("admin.modelUsage.kindName.other"));
}

/** Tokens in a short form for an axis (12k, 1.2M). */
export function shortNumber(n: number): string {
  if (n >= 1_000_000)
    return `${(n / 1_000_000).toLocaleString("en-IN", { maximumFractionDigits: 1 })}M`;
  if (n >= 1_000) return `${(n / 1_000).toLocaleString("en-IN", { maximumFractionDigits: 1 })}k`;
  return n.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

/** A day (YYYY-MM-DD) as "13 Nov". */
export function dayLabel(day: string): string {
  const d = new Date(`${day}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return day;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "UTC" });
}
