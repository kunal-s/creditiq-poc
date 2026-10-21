"""The final label of each statement transaction: the rules' reading, the model's answer where the rules left the row
open, and a person's decision over both. One function, used by the Banking view and by the facts the cross-checks read,
so the two can never disagree. It reads stored answers and decisions but writes nothing."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from .configstore.schema import TxnClassificationSection
from .txn_intel import Context, Label, Txn, classify, cluster_key

MethodName = str


@dataclass
class Final:
    txn_id: str
    category: str
    status: str                     # matched | ambiguous | unmatched
    method: MethodName              # rule | model | manual
    rule_id: str | None
    confidence: float
    settled: bool
    reason: str | None = None
    channel: str | None = None
    counterparty: str | None = None
    counterparty_key: str | None = None
    candidates: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    paired_with: str | None = None
    needs_model: bool = False


def load_state(conn: sqlite3.Connection, case_id: str, config_version: str) -> tuple[dict, dict]:
    """The model's answers kept under this configuration, and the person's decisions, for one case."""
    models = {(r["cluster_key"], r["direction"]): r for r in conn.execute(
        "SELECT * FROM txn_model_labels WHERE case_id = ? AND config_version = ?", (case_id, config_version))}
    overrides = {r["txn_id"]: r for r in conn.execute("SELECT * FROM txn_class_overrides WHERE case_id = ?", (case_id,))}
    return models, overrides


def apply_model(cfg: TxnClassificationSection, lab: Label, credit: bool, answer) -> str | None:
    """Put the model's answer on a row the rules left open. Returns what the model relied on, if it read the row."""
    cats = {c.id: c for c in cfg.categories}
    cat = cats.get(answer["category"])
    if cat is None or cat.direction != ("credit" if credit else "debit"):   # 'unknown', or a category since removed
        return answer["reason"] or None
    sure = answer["confidence"] == "high" or cat.id not in cfg.model.high_only
    if answer["confidence"] in cfg.model.accept and sure:
        lab.category, lab.status, lab.rule_id, lab.candidates = cat.id, "matched", None, []
        lab.confidence, lab.needs_model, lab.method = cfg.model.confidence[answer["confidence"]], False, "model"
    else:
        lab.candidates = [cat.id]                      # a suggestion for a person; the row stays open
    return answer["reason"] or None


def label_case(cfg: TxnClassificationSection, rows: list[Txn], ctx: Context, models: dict | None = None,
               overrides: dict | None = None) -> list[Final]:
    """Label `rows` in order. `overrides` maps a row id to the person's decision (a row with a `category`)."""
    models, overrides = models or {}, overrides or {}
    out: list[Final] = []
    for t, lab in zip(rows, classify(cfg, rows, ctx)):
        credit = bool(t.credit)
        reason = None
        if lab.needs_model:
            answer = models.get((cluster_key(t.narration), "credit" if credit else "debit"))
            reason = apply_model(cfg, lab, credit, answer) if answer else None
        o = overrides.get(t.id)
        if o is not None:
            out.append(Final(t.id, o["category"], "matched", "manual", None, 1.0, True, reason, lab.channel, lab.counterparty,
                             lab.counterparty_key, [], lab.flags, lab.paired_with))
            continue
        out.append(Final(t.id, lab.category, lab.status, lab.method, lab.rule_id, lab.confidence,
                         lab.status == "matched" and not lab.needs_model, reason, lab.channel, lab.counterparty,
                         lab.counterparty_key, lab.candidates, lab.flags, lab.paired_with, lab.needs_model))
    return out
