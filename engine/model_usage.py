"""Model usage (the Administration's Model usage section): the model call logs of the document-processing
service, the engine's CAM copilot and the case assistant, read together. The engine reads its own log;
the service's is asked over its API (engine/ingest_client.py), the assistant's with the reader's own
sign-in. A source that cannot be read leaves partial data and is named in `unavailable`, never an error.

Cost is tokens times the price per million configured for the model (config/app.yaml `model_usage.prices`),
cached input at its own price; a replay costs nothing (it has no tokens). A model whose price is not set
has no cost, never 0. Days are calendar days in the configured zone (the bank's)."""

from __future__ import annotations

import json
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .config import load_app_config
from .contracts import ModelCall, ModelCalls, ModelUsageRow, ModelUsageSummary
from .ingest_client import get_client
from .model_log import COLUMNS

SOURCES = ("ingestion", "cam", "copilot")
TIMEOUT_S = 10


LIMIT_MAX = 500


def _zone(tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(tz or "UTC")
    except Exception:  # noqa: BLE001 - an unknown zone reads as UTC
        return ZoneInfo("UTC")


def _bounds(start: date, end: date, zone: ZoneInfo) -> tuple[datetime, datetime]:
    lo = datetime.combine(start, time.min, zone).astimezone(timezone.utc)
    hi = datetime.combine(end + timedelta(days=1), time.min, zone).astimezone(timezone.utc)
    return lo, hi


def _at(row: dict) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(row["at"]))
    except (TypeError, ValueError):
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def in_range(rows: Iterable[dict], start: date, end: date, tz: str | None) -> list[tuple[datetime, dict]]:
    """The rows whose start falls on a day from `start` to `end` (inclusive) in the zone, with their time."""
    zone = _zone(tz)
    lo, hi = _bounds(start, end, zone)
    out = []
    for r in rows:
        at = _at(r)
        if at is not None and lo <= at < hi:
            out.append((at, r))
    return out


def _pct(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return round(s[lo] + (s[hi] - s[lo]) * (k - lo), 1)


def window(start: date, end: date) -> tuple[str, str]:
    """A UTC ISO window wide enough for any zone, to narrow the rows read before the exact day filter."""
    lo = datetime.combine(start - timedelta(days=1), time.min, timezone.utc)
    hi = datetime.combine(end + timedelta(days=2), time.min, timezone.utc)
    return lo.isoformat(), hi.isoformat()


def summary(rows: Iterable[dict], start: date, end: date, tz: str | None) -> list[dict]:
    """One row per (day, service, task, model): calls, ok, errors by kind (or code), tokens, latency of the
    live calls (p50, p95), and live calls, replay hits and misses counted apart."""
    zone = _zone(tz)
    groups: dict[tuple, dict] = {}
    latencies: dict[tuple, list[float]] = {}
    for at, r in in_range(rows, start, end, tz):
        key = (at.astimezone(zone).date().isoformat(), r.get("service"), r.get("task"), r.get("model"))
        g = groups.setdefault(key, {"day": key[0], "service": key[1], "task": key[2], "model": key[3], "calls": 0, "ok": 0,
                                    "errors": {}, "input_tokens": 0, "output_tokens": 0, "cached_tokens": 0,
                                    "live_calls": 0, "replay_hits": 0, "replay_misses": 0})
        g["calls"] += 1
        if r.get("status") == "ok":
            g["ok"] += 1
        else:
            name = r.get("kind") or r.get("error_code") or "unknown"
            g["errors"][name] = g["errors"].get(name, 0) + 1
        for f in ("input_tokens", "output_tokens", "cached_tokens"):
            g[f] += int(r.get(f) or 0)
        source = r.get("source")
        if source == "replay_hit":
            g["replay_hits"] += 1
        elif source == "replay_miss":
            g["replay_misses"] += 1
        else:
            g["live_calls"] += 1
            if r.get("latency_ms") is not None:
                latencies.setdefault(key, []).append(float(r["latency_ms"]))
    out = []
    for key, g in sorted(groups.items()):
        lat = latencies.get(key, [])
        out.append({**g, "latency_ms_p50": _pct(lat, 0.5), "latency_ms_p95": _pct(lat, 0.95)})
    return out


def calls(rows: Iterable[dict], start: date, end: date, tz: str | None, *, status: str | None = None,
          kind: str | None = None, task: str | None = None, case_ref: str | None = None, limit: int = 50,
          offset: int = 0) -> dict:
    """The calls in the range that match, newest first: {total, rows}."""
    picked = []
    for at, r in in_range(rows, start, end, tz):
        if status and r.get("status") != status:
            continue
        if kind and (r.get("kind") or r.get("error_code")) != kind:
            continue
        if task and r.get("task") != task:
            continue
        if case_ref and r.get("case_ref") != case_ref:
            continue
        picked.append((at, r))
    picked.sort(key=lambda x: x[0], reverse=True)
    limit = max(1, min(int(limit), LIMIT_MAX))
    offset = max(0, int(offset))
    return {"total": len(picked), "rows": [r for _, r in picked[offset:offset + limit]]}


# --- configuration and cost ---------------------------------------------------------------------


def settings() -> dict:
    cfg = load_app_config().get("model_usage") or {}
    return {"default_days": int(cfg.get("default_days") or 7), "currency": str(cfg.get("currency") or ""),
            "timezone": str(cfg.get("timezone") or "UTC"), "prices": dict(cfg.get("prices") or {})}


def price_of(prices: dict, model: str | None) -> dict | None:
    """The model's prices per million tokens, or None when any of them is not set."""
    p = prices.get(model or "") or {}
    if any(p.get(k) is None for k in ("input", "cached_input", "output")):
        return None
    return {k: float(p[k]) for k in ("input", "cached_input", "output")}


def cost(prices: dict, model: str | None, input_tokens: int | None, cached_tokens: int | None,
         output_tokens: int | None) -> tuple[float | None, bool]:
    """(cost, price set): cached input at its own price, the rest of the input at the input price."""
    p = price_of(prices, model)
    if p is None:
        return None, False
    inp, cached, out = int(input_tokens or 0), int(cached_tokens or 0), int(output_tokens or 0)
    cached = min(cached, inp)
    return round(((inp - cached) * p["input"] + cached * p["cached_input"] + out * p["output"]) / 1_000_000, 6), True


def default_range(cfg: dict, start: date | None, end: date | None) -> tuple[date, date]:
    """The range asked, else the last `default_days` days to today in the configured zone."""
    if end is None:
        end = datetime.now(_zone(cfg["timezone"])).date()   # a display default, not a decision rule
    if start is None:
        start = end - timedelta(days=cfg["default_days"] - 1)
    return start, end


# --- the three sources --------------------------------------------------------------------------


def _own_rows(conn: sqlite3.Connection, start: date, end: date) -> list[dict]:
    lo, hi = window(start, end)
    cur = conn.execute(f"SELECT {','.join(COLUMNS)} FROM model_log WHERE at >= ? AND at < ? ORDER BY at, rowid", (lo, hi))
    return [dict(zip(COLUMNS, tuple(r))) for r in cur.fetchall()]


def copilot_url() -> str:
    return (os.environ.get("CREDITIQ_COPILOT_URL") or load_app_config().get("services", {}).get("copilot_url")
            or "").rstrip("/")


def _copilot(path: str, params: dict, token: str | None) -> Any:
    url = f"{copilot_url()}{path}?{urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, '')})}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"} if token else {})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read())


def _read(name: str, conn: sqlite3.Connection, kind: str, params: dict, token: str | None, client=None):
    """One source's answer (summary rows, or {total, rows} of calls)."""
    start, end, tz = params["from"], params["to"], params["tz"]
    if name == "cam":
        rows = _own_rows(conn, date.fromisoformat(start), date.fromisoformat(end))
        if kind == "summary":
            return summary(rows, date.fromisoformat(start), date.fromisoformat(end), tz)
        return calls(rows, date.fromisoformat(start), date.fromisoformat(end), tz, status=params.get("status"),
                     kind=params.get("kind"), task=params.get("task"), case_ref=params.get("case_ref"),
                     limit=params["limit"], offset=0)
    path = f"/v1/model-log/{kind}"
    if name == "ingestion":
        answer = (client or get_client()).model_log(path, params)
    else:
        answer = _copilot(path, params, token)
    return answer["rows"] if kind == "summary" else answer


def read_summary(conn: sqlite3.Connection, *, start: date | None, end: date | None, service: str | None,
                 task: str | None, token: str | None, client=None) -> ModelUsageSummary:
    cfg = settings()
    start, end = default_range(cfg, start, end)
    params = {"from": start.isoformat(), "to": end.isoformat(), "tz": cfg["timezone"]}
    rows, unavailable = [], []
    for name in SOURCES:
        if service and service != name:
            continue
        try:
            got = _read(name, conn, "summary", params, token, client)
        except Exception:  # noqa: BLE001 - a source that cannot be read is named, never an error
            unavailable.append(name)
            continue
        for r in got:
            if task and r.get("task") != task:
                continue
            c, priced = cost(cfg["prices"], r.get("model"), r.get("input_tokens"), r.get("cached_tokens"),
                             r.get("output_tokens"))
            rows.append(ModelUsageRow(**{**r, "service": r.get("service") or name, "cost": c, "price_set": priced}))
    rows.sort(key=lambda r: (r.day, r.service, r.task or "", r.model or ""))
    return ModelUsageSummary(from_date=params["from"], to_date=params["to"], timezone=cfg["timezone"],
                             currency=cfg["currency"], default_days=cfg["default_days"], rows=rows, unavailable=unavailable)


def read_calls(conn: sqlite3.Connection, *, start: date | None, end: date | None, service: str | None,
               task: str | None, status: str | None, kind: str | None, case_ref: str | None, limit: int,
               offset: int, token: str | None, client=None) -> ModelCalls:
    """The calls of every source that match, newest first, paged across the sources together."""
    cfg = settings()
    start, end = default_range(cfg, start, end)
    limit = max(1, min(int(limit), LIMIT_MAX))
    offset = max(0, int(offset))
    params = {"from": start.isoformat(), "to": end.isoformat(), "tz": cfg["timezone"], "status": status, "kind": kind,
              "task": task, "case_ref": case_ref, "limit": min(offset + limit, LIMIT_MAX), "offset": 0}
    merged, total, unavailable = [], 0, []
    for name in SOURCES:
        if service and service != name:
            continue
        try:
            got = _read(name, conn, "calls", params, token, client)
        except Exception:  # noqa: BLE001 - a source that cannot be read is named, never an error
            unavailable.append(name)
            continue
        total += int(got.get("total") or 0)
        merged += [r for r in got.get("rows") or []]
    merged.sort(key=lambda r: str(r.get("at") or ""), reverse=True)
    out = []
    for r in merged[offset:offset + limit]:
        c, priced = cost(cfg["prices"], r.get("model"), r.get("input_tokens"), r.get("cached_tokens"),
                         r.get("output_tokens"))
        out.append(ModelCall(**{k: v for k, v in r.items() if k in ModelCall.model_fields}, cost=c, price_set=priced))
    return ModelCalls(total=total, rows=out, unavailable=unavailable)
