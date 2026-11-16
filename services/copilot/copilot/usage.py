"""Reads of the model call log (`model_log`) for the Administration's Model usage section: a summary by
day, service, task and model, and a filtered list of calls. Days are calendar days in the zone the caller
names (the bank's), so a call at 01:00 local time counts on the local day. Read-only."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

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
