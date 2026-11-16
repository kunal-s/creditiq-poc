"""Model usage (the Administration's Model usage section): the model call logs of the document-processing
service, the engine's CAM copilot and the case assistant, summarised by day, and their calls."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ModelUsageRow(BaseModel):
    """One day, service, task and model."""

    day: str
    """The calendar day in the configured zone (YYYY-MM-DD)."""
    service: str
    task: str | None = None
    model: str | None = None
    calls: int
    ok: int
    errors: dict[str, int] = Field(default_factory=dict)
    """Failed attempts by kind of failure (or by error code where no kind was recorded)."""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    latency_ms_p50: float | None = None
    latency_ms_p95: float | None = None
    """Of the live calls only: a replay takes no time."""
    live_calls: int = 0
    replay_hits: int = 0
    replay_misses: int = 0
    cost: float | None = None
    """In the configured currency: tokens times the price per million, cached input at its own price.
    None when the model's price is not set."""
    price_set: bool = False


class ModelUsageSummary(BaseModel):
    from_date: str
    to_date: str
    timezone: str
    currency: str
    default_days: int
    rows: list[ModelUsageRow] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)
    """Sources that could not be read (ingestion, cam, copilot): the rows hold the others."""


class ModelCall(BaseModel):
    """One model call log row: one HTTP attempt or one replay."""

    id: str
    at: str
    service: str
    task: str | None = None
    provider: str | None = None
    model: str | None = None
    mode: str | None = None
    source: str
    case_ref: str | None = None
    run_id: str | None = None
    request_key: str | None = None
    attempt: int | None = None
    status: str
    error_code: str | None = None
    kind: str | None = None
    http_status: int | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_tokens: int | None = None
    ratelimit_remaining_tokens: int | None = None
    ratelimit_remaining_requests: int | None = None
    retry_after_s: float | None = None
    message: str | None = None
    cost: float | None = None
    price_set: bool = False


class ModelCalls(BaseModel):
    total: int
    rows: list[ModelCall] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)
