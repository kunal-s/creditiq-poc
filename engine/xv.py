"""The cross-verification board (F-19; the Cross-checks tab).

Ranks the discrepancies by credit impact, gives each finding a reference that stays the same
across runs (XV-<case number>-<sequence>), records each run, assembles the board by area (the
areas of the rules switched on, each with its overview counts and its discrepancies ranked within
it), and takes the reviewer's decisions:

- accept: a valid finding. It stays on the query list (F-19.5) and is recorded as decided.
- dismiss: not a valid finding, with the reason. It leaves the query list.
- escalate: handed to the Credit Manager. The finding stays open and keeps blocking until it is
  accepted or dismissed, and only a holder of `finding.escalation` may then decide it. It is
  escalated once, and the escalation is kept with the discrepancy's identity as well as on its
  review item (engine/review_items.py), so a run that withdraws the item does not lose it.

A comment is required for every decision, and each is kept with the appraisal (the review item,
and the decision log). Accept and dismiss close the finding's review item through
engine/review.py, so the query list, the stage progress, the CAM and the PD note follow them.

A check that could not run can put its request on the query list. The query list asks for what
the check needs now: the wording follows the check's current request as documents arrive, and
the query is resolved once the check completes or only waits for a person's review.

Nothing here decides an outcome: the rules do (engine/crosschecks.py).
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable, Iterable
from pathlib import Path

from .config import find_user_by_id
from .configstore import reader
from .configstore.schema import CrossCheckRule
from .contracts import (
    CaseDetail,
    CrossVerificationView,
    Finding,
    ReviewDecisionRequest,
    XvCounts,
    XvDecision,
    XvArea,
    XvDecisionRequest,
    XvItem,
    XvRun,
)
from .db import log_decision, transaction
from .review_items import keep_escalation
from .util import now_iso

SEVERITY_ORDER = {"serious": 0, "moderate": 1, "mild": 2}
OUTCOME_ORDER = {"fail": 0, "incomplete": 1, "pass": 2, "not_applicable": 3}
ESCALATION_PERMISSION = "finding.escalation"
DECIDED = "this discrepancy has already been decided"
ESCALATED = "this discrepancy has already been escalated to the Credit Manager"
HIGHLIGHTS = 3
"""Key-figure lines on an area's overview card."""


class XvError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def case_number(case_id: str) -> str:
    """The case's number as its reference prints it: BBG-2026-000004 -> 000004."""
    found = re.findall(r"\d+", case_id)
    return found[-1] if found else case_id


def rank_key(rules: Iterable[CrossCheckRule]) -> Callable[[Finding], tuple]:
    """Credit impact: severity, then the size of the gap in rupees (findings with no amount after
    those with one), then the rules' configured order."""
    order = {r.id: i for i, r in enumerate(rules)}
    return lambda f: (SEVERITY_ORDER.get(f.severity, 9), f.amount is None, -(f.amount or 0.0),
                      order.get(f.rule_id, 999), f.scope or "")


def assign_refs(conn: sqlite3.Connection, case_id: str, findings: list[Finding], rules: Iterable[CrossCheckRule]) -> None:
    """Give each failed finding its reference the first time it fails, in ranked order; a
    finding keeps its reference on every later run, whatever its outcome."""
    rules = list(rules)
    held = {(r["rule_id"], r["scope"]): r["seq"]
            for r in conn.execute("SELECT rule_id, scope, seq FROM finding_refs WHERE case_id = ?", (case_id,))}
    seq = max(held.values(), default=0)
    at = now_iso()
    for f in sorted((f for f in findings if f.outcome == "fail"), key=rank_key(rules)):
        key = (f.rule_id, f.scope or "")
        if key not in held:
            seq += 1
            conn.execute("INSERT INTO finding_refs (case_id, rule_id, scope, seq, assigned_at) VALUES (?, ?, ?, ?, ?)",
                         (case_id, f.rule_id, f.scope or "", seq, at))
            held[key] = seq
    number = case_number(case_id)
    for f in findings:
        n = held.get((f.rule_id, f.scope or ""))
        f.ref = f"XV-{number}-{n:02d}" if n else None


def record_run(conn: sqlite3.Connection, case_id: str, findings: list[Finding], rules: Iterable[CrossCheckRule],
               types: Iterable[str]) -> None:
    """Record this run: its number, when, how many rules, and how many source documents it compared:
    the configured document types (`types`, by id) among its findings' sides and columns. A source
    that is not a document type (the case's appraisal date, its constitution) is not counted."""
    rules = list(rules)
    prev = conn.execute("SELECT run_no FROM crosscheck_runs WHERE case_id = ?", (case_id,)).fetchone()
    run_no = (prev["run_no"] if prev else 0) + 1
    compared = {s for f in findings for c in f.columns for s in c.sources}
    compared |= {s for f in findings for side in f.sides for s in side.sources}
    sources = compared & set(types)
    conn.execute(
        """INSERT INTO crosscheck_runs (case_id, run_no, run_at, rules, sources) VALUES (?, ?, ?, ?, ?)
           ON CONFLICT (case_id) DO UPDATE SET run_no = excluded.run_no, run_at = excluded.run_at,
           rules = excluded.rules, sources = excluded.sources""",
        (case_id, run_no, now_iso(), len(rules), len(sources)),
    )
    run_id = run_label(case_id, run_no)
    for f in findings:
        f.run_id = run_id


def run_label(case_id: str, run_no: int) -> str:
    return f"XR-{case_number(case_id)}-{run_no:03d}"


def _name(user_id: str | None) -> str:
    if not user_id:
        return ""
    user = find_user_by_id(user_id)
    return user["name"] if user else user_id


def _review_rows(conn: sqlite3.Connection, case_id: str) -> dict[str, sqlite3.Row]:
    return {r["ref"]: r for r in conn.execute(
        "SELECT * FROM review_items WHERE case_id = ? AND kind = 'finding'", (case_id,))}


def _additions(conn: sqlite3.Connection, case_id: str) -> dict[tuple[str, str], sqlite3.Row]:
    return {(r["rule_id"], r["scope"]): r for r in conn.execute(
        "SELECT * FROM query_additions WHERE case_id = ?", (case_id,))}


def _item(f: Finding, review: sqlite3.Row | None, added: bool) -> XvItem:
    decision = escalation = None
    if review is not None:
        if review["status"] == "decided" and review["decision"] in ("confirm", "waive"):
            decision = XvDecision(decision="accept" if review["decision"] == "confirm" else "dismiss",
                                  comment=review["reason"] or "", by=review["decided_by"] or "",
                                  by_name=_name(review["decided_by"]), at=review["decided_at"] or "")
        raised = json.loads(review["detail"] or "{}").get("escalation")
        if raised:
            escalation = XvDecision(decision="escalate", comment=raised["comment"], by=raised["by"],
                                    by_name=_name(raised["by"]), at=raised["at"])
    return XvItem(finding=f, review_item_id=review["id"] if review is not None else None, decision=decision,
                  escalation=escalation, adjudicated=decision is not None, in_query_list=added)


def view(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> CrossVerificationView:
    """The board: the latest run's findings of the enabled rules, by area (in the order the areas
    first appear in configuration); within an area, discrepancies by credit impact, then the
    checks that could not run, the passed ones and those that did not apply."""
    from . import reads

    rules = reader.load_crosschecks(root).enabled_rules
    order = {r.id: i for i, r in enumerate(rules)}
    area_of = {r.id: r.area for r in rules}
    # A switched-off rule's last findings stay until the next run; the board leaves them out.
    findings = [f for f in reads.findings(conn, case.id) if f.rule_id in order]
    reviews = _review_rows(conn, case.id)
    additions = _additions(conn, case.id)
    failed = [_item(f, reviews.get(f"finding:{f.id}"), False)
              for f in sorted((f for f in findings if f.outcome == "fail"), key=rank_key(rules))]
    others: list[XvItem] = []
    for f in sorted((f for f in findings if f.outcome != "fail"),
                    key=lambda f: (OUTCOME_ORDER.get(f.outcome, 9), order.get(f.rule_id, 999), f.scope or "")):
        # A request stays recorded after its check completes (it returns if the check cannot run
        # again), but the check is on the query list only while it is incomplete and has something
        # to ask for (requests_for_queries): not while it only waits for a person's review.
        asked = f.outcome == "incomplete" and bool(f.request) and (f.rule_id, f.scope or "") in additions
        others.append(_item(f, reviews.get(f"finding:{f.id}"), asked))
    items: list[XvItem] = []
    areas: list[XvArea] = []
    for area in dict.fromkeys(r.area for r in rules):
        ranked = [i for i in failed if area_of[i.finding.rule_id] == area]
        for rank, it in enumerate(ranked, start=1):
            it.rank = rank
        rest = [i for i in others if area_of[i.finding.rule_id] == area]
        for it in ranked + rest:
            # Its area as configured now, should the area have changed since the case last ran.
            it.finding.area = area  # type: ignore[assignment]
        items += ranked + rest
        areas.append(_area(area, sum(1 for r in rules if r.area == area), ranked, rest))
    # The banner's blocking discrepancy is the greatest across the board; the card opened first is
    # the first card on the board: the top of the first area with an open discrepancy (else with any).
    open_ = [i for i in failed if not i.adjudicated]
    first_blocking = next((i.finding.id for i in open_ if i.finding.blocking), None)
    top = next((a.top_finding_id for a in areas if a.open), None) or next(
        (a.top_finding_id for a in areas if a.top_finding_id), None)
    counts = XvCounts(
        serious=sum(1 for i in open_ if i.finding.severity == "serious"),
        moderate=sum(1 for i in open_ if i.finding.severity == "moderate"),
        mild=sum(1 for i in open_ if i.finding.severity == "mild"),
        adjudicated=len(failed) - len(open_),
        total=len(failed),
        blocking_open=sum(1 for i in open_ if i.finding.blocking),
    )
    run_row = conn.execute("SELECT * FROM crosscheck_runs WHERE case_id = ?", (case.id,)).fetchone()
    run = XvRun(id=run_label(case.id, run_row["run_no"]), at=run_row["run_at"], rules=run_row["rules"],
                sources=run_row["sources"]) if run_row else None
    return CrossVerificationView(case_id=case.id, run=run, areas=areas, items=items, counts=counts,
                                 blocked=counts.blocking_open > 0, first_blocking=first_blocking, top_finding_id=top)


def _area(area: str, rules: int, ranked: list[XvItem], rest: list[XvItem]) -> XvArea:
    """An area's overview card: its discrepancies (ranked) and the rest of its findings."""
    open_ = [i for i in ranked if not i.adjudicated]
    outcomes = [i.finding.outcome for i in rest]
    top = (open_ or ranked)[0].finding.id if ranked else None
    status = "open" if open_ else "decided" if ranked else "incomplete" if "incomplete" in outcomes else "clear"
    # Key figures: open discrepancies by rank, then decided ones, then the checks that could not run
    # and the passed ones (rest is in that order), at most three lines.
    sources = open_ + [i for i in ranked if i.adjudicated] + [i for i in rest if i.finding.outcome != "not_applicable"]
    highlights = [h for i in sources for h in i.finding.highlights][:HIGHLIGHTS]
    return XvArea(
        area=area, rules=rules, discrepancies=len(ranked), open=len(open_),  # type: ignore[arg-type]
        serious=sum(1 for i in open_ if i.finding.severity == "serious"),
        moderate=sum(1 for i in open_ if i.finding.severity == "moderate"),
        mild=sum(1 for i in open_ if i.finding.severity == "mild"),
        blocking_open=sum(1 for i in open_ if i.finding.blocking), adjudicated=len(ranked) - len(open_),
        incomplete=outcomes.count("incomplete"), passed=outcomes.count("pass"),
        not_applicable=outcomes.count("not_applicable"), top_finding_id=top, highlights=highlights,
        status=status,  # type: ignore[arg-type]
    )


def _finding(conn: sqlite3.Connection, root: Path, case: CaseDetail, finding_id: str) -> XvItem:
    for it in view(conn, root, case).items:
        if it.finding.id == finding_id:
            return it
    raise XvError(404, f"no finding {finding_id!r} on this case")


def decide(conn: sqlite3.Connection, root: Path, case: CaseDetail, finding_id: str, body: XvDecisionRequest,
           user: dict) -> XvItem:
    """Accept, dismiss or escalate a discrepancy, with the comment every decision needs."""
    from . import review

    comment = body.comment.strip()
    if len(comment) < 3:
        raise XvError(422, "a comment is required for every decision")
    item = _finding(conn, root, case, finding_id)
    if item.finding.outcome != "fail":
        raise XvError(409, "only a discrepancy is adjudicated")
    if item.adjudicated:
        raise XvError(409, DECIDED)
    if item.review_item_id is None:
        raise XvError(409, "this discrepancy has no review item")
    if item.escalation is not None and ESCALATION_PERMISSION not in user["permissions"]:
        raise XvError(403, "an escalated discrepancy is decided by the Credit Manager")

    if body.decision == "escalate":
        if item.escalation is not None:
            raise XvError(409, ESCALATED)
        at = now_iso()
        escalation = {"by": user["id"], "at": at, "comment": comment}
        with transaction(conn):
            # Read again under the write lock: another reviewer may have decided or escalated it
            # since the board was read, and neither is overwritten.
            row = conn.execute("SELECT status, detail FROM review_items WHERE id = ?",
                               (item.review_item_id,)).fetchone()
            if row is None:
                raise XvError(409, "this discrepancy has no review item")
            if row["status"] != "open":
                raise XvError(409, DECIDED)
            detail = json.loads(row["detail"] or "{}")
            if detail.get("escalation"):
                raise XvError(409, ESCALATED)
            detail["escalation"] = escalation
            conn.execute("UPDATE review_items SET detail = ? WHERE id = ?", (json.dumps(detail), item.review_item_id))
            keep_escalation(conn, case_id=case.id, rule_id=item.finding.rule_id, scope=item.finding.scope,
                            escalation=escalation)
            log_decision(conn, at=at, actor=user["id"], case_id=case.id, action="finding.escalated",
                         detail=json.dumps({"finding_id": finding_id, "rule_id": item.finding.rule_id,
                                            "ref": item.finding.ref, "comment": comment}))
    else:
        try:
            review.decide(conn, root, item.review_item_id,
                          ReviewDecisionRequest(decision="confirm" if body.decision == "accept" else "waive",
                                                reason=comment), user)
        except review.ReviewError as e:
            raise XvError(e.status, str(e)) from e
    return _finding(conn, root, case, finding_id)


def add_query(conn: sqlite3.Connection, root: Path, case: CaseDetail, finding_id: str, user: dict) -> XvItem:
    """Put an incomplete check's request on the query list (F-14), until the check completes. The
    decision log records the addition once: adding it again changes nothing."""
    from . import queries

    item = _finding(conn, root, case, finding_id)
    f = item.finding
    if f.outcome != "incomplete" or not f.request:
        raise XvError(409, "only a check that could not run, with something to ask for, goes on the query list")
    at = now_iso()
    with transaction(conn):
        added = conn.execute(
            """INSERT INTO query_additions (case_id, rule_id, scope, text, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT (case_id, rule_id, scope) DO NOTHING""",
            (case.id, f.rule_id, f.scope or "", query_text(f), user["id"], at),
        ).rowcount
        if added:
            log_decision(conn, at=at, actor=user["id"], case_id=case.id, action="finding.query_added",
                         detail=json.dumps({"finding_id": finding_id, "rule_id": f.rule_id, "request": f.request}))
    queries.refresh(conn, root, case.id)
    return _finding(conn, root, case, finding_id)


def query_text(f: Finding) -> str:
    return f"Please provide {f.request}, so that the check “{f.compares or f.title}” can be completed."


def requests_for_queries(conn: sqlite3.Connection, case_id: str) -> list[tuple[str, str]]:
    """(source ref, text) for each request put on the query list whose check is still incomplete and
    has something to ask for, worded as the check asks now: the request narrows as documents arrive,
    and a check that only waits for a person's review asks the customer for nothing. (What was first
    asked stays in query_additions.text, as the record of the addition.)"""
    from . import reads

    added = [(r["rule_id"], r["scope"]) for r in conn.execute(
        "SELECT rule_id, scope FROM query_additions WHERE case_id = ? ORDER BY added_at", (case_id,))]
    if not added:
        return []
    asking = {(f.rule_id, f.scope or ""): f for f in reads.findings(conn, case_id)
              if f.outcome == "incomplete" and f.request}
    return [(f"{rule_id}:{scope}:request", query_text(asking[(rule_id, scope)]))
            for rule_id, scope in added if (rule_id, scope) in asking]
