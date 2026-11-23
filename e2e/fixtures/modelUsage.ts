// Model usage (Administration): what the engine's /api/admin/model-usage answers for a week of
// calls by the three services. The compact model has a price; the case assistant's model has none,
// so the cost leaves it out and says so.
import type { ModelCall, ModelUsageRow, ModelUsageSummary } from "../../src/api/types";

export const USAGE_FROM = "2026-11-07";
export const USAGE_TO = "2026-11-13";

function row(
  day: string,
  service: string,
  task: string,
  model: string,
  p: Partial<ModelUsageRow>,
): ModelUsageRow {
  return {
    day,
    service,
    task,
    model,
    calls: 0,
    ok: 0,
    errors: {},
    input_tokens: 0,
    output_tokens: 0,
    cached_tokens: 0,
    latency_ms_p50: null,
    latency_ms_p95: null,
    live_calls: 0,
    replay_hits: 0,
    replay_misses: 0,
    cost: null,
    price_set: false,
    ...p,
  };
}

const PRICED = { price_set: true };

export const USAGE_ROWS: ModelUsageRow[] = [
  row("2026-11-08", "ingestion", "classify", "gpt-5.4-nano", {
    ...PRICED,
    calls: 6,
    ok: 6,
    input_tokens: 4200,
    output_tokens: 300,
    cached_tokens: 1200,
    latency_ms_p50: 820,
    latency_ms_p95: 1400,
    live_calls: 6,
    cost: 0.0012,
  }),
  row("2026-11-10", "ingestion", "extract", "gpt-5.4-nano", {
    ...PRICED,
    calls: 14,
    ok: 12,
    errors: { rate_limit_minute: 2 },
    input_tokens: 21000,
    output_tokens: 3600,
    latency_ms_p50: 1900,
    latency_ms_p95: 3200,
    live_calls: 14,
    cost: 0.0068,
  }),
  row("2026-11-12", "cam", "cam_section", "gpt-5.4-nano", {
    ...PRICED,
    calls: 3,
    ok: 2,
    errors: { server_unavailable: 1 },
    input_tokens: 5100,
    output_tokens: 1400,
    latency_ms_p50: 2600,
    latency_ms_p95: 4100,
    live_calls: 3,
    cost: 0.0019,
  }),
  row("2026-11-13", "copilot", "runner", "gpt-4.1-mini", {
    calls: 4,
    ok: 3,
    errors: { quota: 1 },
    input_tokens: 3000,
    output_tokens: 900,
    latency_ms_p50: 1500,
    latency_ms_p95: 2100,
    live_calls: 2,
    replay_hits: 2,
  }),
  row("2026-11-13", "ingestion", "extract", "gpt-5.4-nano", {
    ...PRICED,
    calls: 12,
    ok: 0,
    errors: { replay_miss: 12 },
    replay_misses: 12,
    cost: 0,
  }),
];

export function usageSummary(
  rows: ModelUsageRow[] = USAGE_ROWS,
  unavailable: string[] = [],
): ModelUsageSummary {
  return {
    from_date: USAGE_FROM,
    to_date: USAGE_TO,
    timezone: "Asia/Kolkata",
    currency: "USD",
    default_days: 7,
    rows,
    unavailable,
  };
}

/** One call log row per call the summary counts, newest first. */
export function usageCalls(rows: ModelUsageRow[] = USAGE_ROWS): ModelCall[] {
  const out: ModelCall[] = [];
  let n = 0;
  for (const r of rows) {
    const failed = Object.entries(r.errors ?? {}).flatMap(([kind, k]) =>
      Array<string>(k).fill(kind),
    );
    for (let i = 0; i < r.calls; i++) {
      const kind = i < r.calls - failed.length ? null : failed[i - (r.calls - failed.length)]!;
      const source =
        kind === "replay_miss" ? "replay_miss" : i < r.replay_hits ? "replay_hit" : "live";
      out.push({
        id: `call-${++n}`,
        at: `${r.day}T${String(4 + (i % 12)).padStart(2, "0")}:${String((i * 7) % 60).padStart(2, "0")}:00+00:00`,
        service: r.service,
        task: r.task ?? null,
        provider: "openai",
        model: r.model ?? null,
        mode: source === "live" ? "record" : "replay",
        source,
        case_ref: r.service === "copilot" ? null : "BBG-2026-000021",
        run_id: null,
        request_key: null,
        attempt: 1,
        status: kind ? "error" : "ok",
        error_code: kind ? (kind === "replay_miss" ? "replay_miss" : "http") : null,
        kind,
        http_status: kind && kind !== "replay_miss" ? 429 : source === "live" ? 200 : null,
        latency_ms: source === "live" ? 900 + i * 40 : 0,
        input_tokens: kind ? null : Math.round(r.input_tokens / Math.max(1, r.ok)),
        output_tokens: kind ? null : Math.round(r.output_tokens / Math.max(1, r.ok)),
        total_tokens: null,
        cached_tokens: null,
        ratelimit_remaining_tokens: null,
        ratelimit_remaining_requests: null,
        retry_after_s: null,
        message: null,
        cost: null,
        price_set: !!r.price_set,
      });
    }
  }
  return out.sort((a, b) => b.at.localeCompare(a.at));
}
