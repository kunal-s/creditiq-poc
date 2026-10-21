"""Classified bank-statement transactions of a case: kept, summarised and corrected.

`refresh` reads the case's statement rows, labels them with the deterministic pass
(engine/txn_intel, configuration config/txn_classification.yaml) and keeps the result in `txn_class`. The
labels are derived: they are rewritten whenever a statement, a name the narrations may mention or the
published configuration changes. A person's decision on a row is kept apart (`txn_class_overrides`) and
always wins; nothing a person decides changes the rules. Rows nothing has settled raise one review item per
statement, which closes itself when none is left.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from . import facts
from .configstore import reader
from .configstore.schema import TxnClassificationSection
from .contracts import CaseDetail, Evidence, TxnMonthTotal, TxnPage, TxnRow, TxnSummary
from .contracts.transactions import TxnCategoryTotal
from .db import log_decision, transaction
from .review_items import close_item, raise_item
from .txn_intel import Context, Txn, classify
from .util import dumps, now_iso

REVIEW_KIND = "transactions"
SYSTEM = "system"


class TxnError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _basis(cfg_version: str, inputs: facts.StatementInputs) -> str:
    payload = {
        "config": cfg_version,
        "context": [inputs.borrower, sorted(inputs.own_account_last4), inputs.lender_names, inputs.director_names,
                    inputs.emi_min_months, inputs.emi_tolerance_pct],
        "rows": [[t.ref, t.account, t.date.isoformat() if t.date else None, t.narration, t.debit, t.credit, t.doc.id]
                 for t in inputs.txns],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _last4(account: str) -> str | None:
    return account.rsplit("·", 1)[-1] if "·" in account else None


def refresh(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> dict:
    """Bring the case's classified transactions up to date. Returns {"rows", "unsettled", "rewritten"}."""
    cfg_version = reader.published_version(root)["version"]
    inputs = facts.statement_inputs(conn, root, case)
    rows = [t for t in inputs.txns if t.ref]
    basis = _basis(cfg_version, inputs)
    known = conn.execute("SELECT basis FROM txn_class_basis WHERE case_id = ?", (case.id,)).fetchone()
    rewritten = known is None or known["basis"] != basis
    if rewritten:
        cfg = reader.load_txn_classification(root)
        ctx = Context(borrower_name=inputs.borrower, own_account_last4=inputs.own_account_last4,
                      lender_names=inputs.lender_names, director_names=inputs.director_names,
                      emi_min_months=inputs.emi_min_months, emi_tolerance_pct=inputs.emi_tolerance_pct)
        labels = classify(
            cfg,
            [Txn(t.ref, t.account, t.date, t.narration, t.debit, t.credit, _last4(t.account)) for t in rows],
            ctx,
        )
        with transaction(conn):
            conn.execute("DELETE FROM txn_class WHERE case_id = ?", (case.id,))
            for t, lab in zip(rows, labels):
                conn.execute(
                    """INSERT INTO txn_class (case_id, txn_id, document_id, account, seq, date, narration, debit, credit,
                       category, status, method, rule_id, confidence, channel, counterparty, counterparty_key, candidates,
                       flags, paired_with, needs_model, evidence)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'rule', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (case.id, t.ref, t.doc.id, t.account, t.seq, t.date.isoformat() if t.date else None, t.narration,
                     t.debit, t.credit, lab.category, lab.status, lab.rule_id, lab.confidence, lab.channel,
                     lab.counterparty, lab.counterparty_key, dumps(lab.candidates), dumps(lab.flags), lab.paired_with,
                     int(lab.needs_model), dumps([e.model_dump(mode="json") for e in t.evidence])),
                )
            conn.execute(
                """INSERT INTO txn_class_basis (case_id, basis, config_version, classified_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(case_id) DO UPDATE SET basis = excluded.basis, config_version = excluded.config_version,
                   classified_at = excluded.classified_at""",
                (case.id, basis, cfg_version, now_iso()),
            )
            conn.execute(  # a decision on a row that no longer exists has nothing to apply to
                "DELETE FROM txn_class_overrides WHERE case_id = ? AND txn_id NOT IN (SELECT txn_id FROM txn_class WHERE case_id = ?)",
                (case.id, case.id),
            )
    unsettled = _raise_reviews(conn, case.id)
    return {"rows": len(rows), "unsettled": sum(unsettled.values()), "rewritten": rewritten}


def ensure_current(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> None:
    """Before a read: make sure the labels match the case as it now stands. `refresh` compares a hash of the rows,
    the names they may mention and the configuration version, and rewrites only when it moved."""
    refresh(conn, root, case)


def _unsettled_by_document(conn: sqlite3.Connection, case_id: str) -> dict[str, tuple[str, int]]:
    """Per statement: its account and how many rows nothing has settled."""
    out: dict[str, tuple[str, int]] = {}
    for r in conn.execute(
        """SELECT t.document_id, t.account, SUM(t.needs_model = 1 AND o.txn_id IS NULL) AS open
           FROM txn_class t LEFT JOIN txn_class_overrides o ON o.case_id = t.case_id AND o.txn_id = t.txn_id
           WHERE t.case_id = ? GROUP BY t.document_id, t.account""",
        (case_id,),
    ):
        out[r["document_id"]] = (r["account"], int(r["open"] or 0))
    return out


def _raise_reviews(conn: sqlite3.Connection, case_id: str) -> dict[str, int]:
    counts = {}
    with transaction(conn):
        for doc_id, (account, n) in _unsettled_by_document(conn, case_id).items():
            ref = f"txns:{doc_id}"
            summary = f"{n} transaction{'s' if n != 1 else ''} on {account} could not be classified"
            existing = conn.execute(
                "SELECT id, status FROM review_items WHERE case_id = ? AND kind = ? AND ref = ?",
                (case_id, REVIEW_KIND, ref),
            ).fetchone()
            counts[doc_id] = n
            if n:
                detail = dumps({"document_id": doc_id, "account": account, "open": n})
                if existing is None:
                    raise_item(conn, case_id=case_id, kind=REVIEW_KIND, ref=ref, summary=summary,
                               detail=json.loads(detail))
                else:
                    conn.execute(
                        """UPDATE review_items SET summary = ?, detail = ?, status = 'open', decision = NULL, reason = NULL,
                           decided_by = NULL, decided_at = NULL WHERE id = ?""",
                        (summary, detail, existing["id"]),
                    )
            elif existing is not None and existing["status"] == "open":
                close_item(conn, item_id=existing["id"], decision="confirm", reason="All transactions classified",
                           decided_by=SYSTEM)
    return counts


# ---- Reads ----------------------------------------------------------------------------------------------------

def _categories(cfg: TxnClassificationSection) -> dict:
    return {c.id: c for c in cfg.categories}


def _row(r: sqlite3.Row, cats: dict, override: sqlite3.Row | None) -> TxnRow:
    category = override["category"] if override else r["category"]
    cat = cats.get(category)
    method = "manual" if override else r["method"]
    settled = override is not None or r["status"] == "matched" and not r["needs_model"]
    return TxnRow(
        txn_id=r["txn_id"], document_id=r["document_id"], account=r["account"], seq=r["seq"], date=r["date"],
        narration=r["narration"], debit=r["debit"], credit=r["credit"], category=category,
        category_label=cat.label if cat else category,
        direction=cat.direction if cat else ("credit" if r["credit"] else "debit"),
        status="matched" if override else r["status"], method=method,
        rule_id=None if override else r["rule_id"], confidence=1.0 if override else r["confidence"],
        channel=r["channel"], counterparty=r["counterparty"],
        candidates=json.loads(r["candidates"]), flags=json.loads(r["flags"]), paired_with=r["paired_with"],
        needs_review=not settled, evidence=[Evidence.model_validate(e) for e in json.loads(r["evidence"])],
    )


def _all(conn: sqlite3.Connection, root: Path, case_id: str) -> list[TxnRow]:
    cats = _categories(reader.load_txn_classification(root))
    overrides = {o["txn_id"]: o for o in conn.execute("SELECT * FROM txn_class_overrides WHERE case_id = ?", (case_id,))}
    return [_row(r, cats, overrides.get(r["txn_id"]))
            for r in conn.execute("SELECT * FROM txn_class WHERE case_id = ? ORDER BY document_id, seq", (case_id,))]


def list_rows(conn: sqlite3.Connection, root: Path, case_id: str, *, category: str | None = None,
              account: str | None = None, status: str | None = None, month: str | None = None,
              counterparty: str | None = None, flag: str | None = None, q: str | None = None,
              needs_review: bool | None = None, limit: int = 200, offset: int = 0) -> TxnPage:
    rows = _all(conn, root, case_id)
    needle = (q or "").lower()
    party = (counterparty or "").lower()

    def keep(r: TxnRow) -> bool:
        return ((category is None or r.category == category) and (account is None or r.account == account)
                and (status is None or r.status == status or (status == "manual" and r.method == "manual"))
                and (month is None or (r.date or "").startswith(month))
                and (not party or party in (r.counterparty or "").lower())
                and (flag is None or flag in r.flags) and (needs_review is None or r.needs_review == needs_review)
                and (not needle or needle in r.narration.lower() or needle in (r.counterparty or "").lower()))

    kept = [r for r in rows if keep(r)]
    return TxnPage(items=kept[offset: offset + limit], total=len(kept), limit=limit, offset=offset)


def summary(conn: sqlite3.Connection, root: Path, case_id: str) -> TxnSummary:
    cfg = reader.load_txn_classification(root)
    cats = _categories(cfg)
    rows = _all(conn, root, case_id)
    totals: dict[str, list] = {}
    months: dict[str, dict] = defaultdict(lambda: {"credits": 0.0, "debits": 0.0, "by": defaultdict(float)})
    for r in rows:
        t = totals.setdefault(r.category, [0, 0.0])
        amount = r.credit or r.debit
        t[0] += 1
        t[1] += amount
        if r.date:
            m = months[r.date[:7]]
            m["credits" if r.credit else "debits"] += amount
            m["by"][r.category] += amount
    basis = conn.execute("SELECT config_version FROM txn_class_basis WHERE case_id = ?", (case_id,)).fetchone()
    order = {c.id: i for i, c in enumerate(cfg.categories)}
    return TxnSummary(
        case_id=case_id, config_version=basis["config_version"] if basis else None, total=len(rows),
        by_rule=sum(1 for r in rows if r.method == "rule" and not r.needs_review),
        by_person=sum(1 for r in rows if r.method == "manual"),
        unsettled=sum(1 for r in rows if r.needs_review),
        categories=[TxnCategoryTotal(category=c, label=cats[c].label if c in cats else c,
                                     direction=cats[c].direction if c in cats else "debit", count=n, amount=a)
                    for c, (n, a) in sorted(totals.items(), key=lambda kv: order.get(kv[0], 999))],
        months=[TxnMonthTotal(month=m, credits=v["credits"], debits=v["debits"], by_category=dict(v["by"]))
                for m, v in sorted(months.items())],
        accounts=sorted({r.account for r in rows}),
    )


# ---- A person's decision --------------------------------------------------------------------------------------

def set_category(conn: sqlite3.Connection, root: Path, case: CaseDetail, txn_id: str, category: str, reason: str,
                 *, actor: str) -> TxnRow:
    cats = _categories(reader.load_txn_classification(root))
    with transaction(conn):
        row = conn.execute("SELECT * FROM txn_class WHERE case_id = ? AND txn_id = ?", (case.id, txn_id)).fetchone()
        if row is None:
            raise TxnError(404, f"no transaction {txn_id!r} in this case")
        cat = cats.get(category)
        if cat is None:
            raise TxnError(422, f"unknown category {category!r}")
        direction = "credit" if row["credit"] else "debit"
        if cat.direction != direction:
            raise TxnError(422, f"a {direction} cannot be filed under {cat.label.lower()}")
        conn.execute(
            """INSERT INTO txn_class_overrides (case_id, txn_id, category, reason, decided_by, decided_at)
               VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(case_id, txn_id) DO UPDATE SET category = excluded.category,
               reason = excluded.reason, decided_by = excluded.decided_by, decided_at = excluded.decided_at""",
            (case.id, txn_id, category, reason, actor, now_iso()),
        )
        log_decision(conn, at=now_iso(), actor=actor, case_id=case.id, action="transaction.categorised",
                     detail=dumps({"txn_id": txn_id, "from": row["category"], "to": category, "reason": reason}))
    _raise_reviews(conn, case.id)
    return one(conn, root, case.id, txn_id)


def clear_category(conn: sqlite3.Connection, root: Path, case: CaseDetail, txn_id: str, *, actor: str) -> TxnRow:
    with transaction(conn):
        gone = conn.execute("DELETE FROM txn_class_overrides WHERE case_id = ? AND txn_id = ?", (case.id, txn_id)).rowcount
        if not gone:
            raise TxnError(404, "that transaction has no decision to remove")
        log_decision(conn, at=now_iso(), actor=actor, case_id=case.id, action="transaction.category_cleared",
                     detail=dumps({"txn_id": txn_id}))
    _raise_reviews(conn, case.id)
    return one(conn, root, case.id, txn_id)


def one(conn: sqlite3.Connection, root: Path, case_id: str, txn_id: str) -> TxnRow:
    for r in _all(conn, root, case_id):
        if r.txn_id == txn_id:
            return r
    raise TxnError(404, f"no transaction {txn_id!r} in this case")
