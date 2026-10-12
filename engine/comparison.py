"""CreditIQ against RBL's reference record (docs/functional-requirements.md F-25.2 to F-25.5):
the deviations and approving-authority areas.

Computed on read from the policy assessment (F-20), the approving authority (F-21), the
confirmed reference rows and the reviewer's adjudications. Adjudications never feed back:
no processing module imports this one (.importlinter contract 2), so the policy, authority,
memo and PD note are the same before and after any decision (F-25.5).
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from . import approval, db, policy, reference
from .config import find_user_by_id
from .configstore import reader
from .contracts import (
    Adjudication,
    AdjudicationRequest,
    ApprovingAuthority,
    AreaScore,
    CaseComparison,
    CaseDetail,
    ComparisonCounts,
    ComparisonItem,
    NormResult,
    ReferenceDeviation,
    ReferenceRecord,
)
from .util import now_iso

# A minus sign only when it is not part of a code: "CMR-7" is rank 7, "-40 lakh" is negative.
_NUMBER = re.compile(r"(?:(?<![A-Za-z0-9])[-−])?\d[\d,]*(?:\.\d+)?")
_SCALE = {"cr": 1e7, "crs": 1e7, "crore": 1e7, "crores": 1e7,
          "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5, "lk": 1e5, "lkh": 1e5, "lks": 1e5}
# A negative written without a leading minus: "(-) 40" for any figure; for an amount also
# accounting brackets, "(40.00) lakh", or words, "net loss of Rs 40 lakh", "negative net worth of 1.5 cr".
_CURRENCY = r"(?:rs\.?|inr|₹)?\s*"
_MINUS_SIGN = re.compile(r"\(\s*[-−]\s*\)\s*" + _CURRENCY + "$", re.IGNORECASE)
_OPEN_BRACKET = re.compile(r"\(\s*" + _CURRENCY + "$", re.IGNORECASE)
_LOSS_WORDS = re.compile(r"\b(?:loss|negative|deficit)\b", re.IGNORECASE)
AUTHORITY_KEY = "approval"


class ComparisonError(Exception):
    pass


class NotFound(ComparisonError):
    pass


class Conflict(ComparisonError):
    pass


class Invalid(ComparisonError):
    pass


def parse_recorded(text: str | None, unit: str | None) -> tuple[float, int, float] | None:
    """The first number in a recorded value, signed as the record writes it, its decimals, and
    its scale (crore or lakh for rupee norms); None when the text holds no number."""
    if not text:
        return None
    match = _NUMBER.search(text)
    if match is None:
        return None
    digits = match.group(0).replace(",", "").replace("−", "-")
    decimals = len(digits.split(".")[1]) if "." in digits else 0
    before, after = text[:match.start()], text[match.end():]
    negative = bool(_MINUS_SIGN.search(before))
    scale = 1.0
    if unit == "inr":
        word = re.match(r"\s*\)?\s*([A-Za-z]+)", after)
        scale = _SCALE.get(word.group(1).lower(), 1.0) if word else 1.0
        negative = (negative or bool(_OPEN_BRACKET.search(before) and re.match(r"\s*\)", after))
                    or bool(_LOSS_WORDS.search(before)))
    value = float(digits)
    return (-value if negative and value > 0 else value), decimals, scale


def values_agree(actual: float | None, recorded: str | None, unit: str | None) -> bool:
    """Agree when the record's value is unparseable, when CreditIQ's is unbounded, or when
    CreditIQ's lies within half a unit of the record's last decimal (2.25 agrees with a
    recorded 2.3 and with 2.2: either way of rounding a tie)."""
    parsed = parse_recorded(recorded, unit)
    if parsed is None or actual is None:
        return True
    value, decimals, scale = parsed
    return abs(actual / scale - value) <= 0.5 * 10 ** -decimals + 1e-9


def _record_category(d: ReferenceDeviation, norms: dict[str, NormResult]) -> str | None:
    return d.category or (norms[d.norm_id].category if d.norm_id in norms else None)


def _snapshot(item: ComparisonItem, config_version: str | None) -> dict:
    return {
        "status": item.status,
        "creditiq_text": item.creditiq_text,
        "record_text": item.record_text,
        "required": item.required.required.key if item.required and item.required.required else None,
        "config_version": config_version,
    }


def _adjudications(conn: sqlite3.Connection, case_id: str) -> dict[tuple[str, str], dict]:
    rows = conn.execute("SELECT * FROM comparison_adjudications WHERE case_id = ?", (case_id,)).fetchall()
    return {(r["area"], r["item_key"]): dict(r) for r in rows}


def _name(user_id: str) -> str:
    user = find_user_by_id(user_id)
    return user["name"] if user else user_id


def _deviation_items(record: ReferenceRecord, norms: list[NormResult], scored: bool) -> tuple[list[ComparisonItem], int]:
    by_id = {n.id: n for n in norms}
    rows = {d.norm_id: d for d in record.deviations if d.norm_id}
    items: list[ComparisonItem] = []
    neither = 0
    for norm in norms:
        row = rows.get(norm.id)
        deviation = norm.outcome == "deviation"
        if not deviation and row is None:
            neither += 1
            continue
        notes: list = []
        if deviation and row is not None:
            status = "agree" if values_agree(norm.actual, row.recorded_value, norm.unit) else "differ"
            if status == "differ":
                notes.append("value_differs")
            if row.category and row.category != norm.category:
                notes.append("category_differs")
        elif deviation:
            status = "new"
        else:
            status = "missed"
            notes.append(norm.outcome)
        items.append(ComparisonItem(
            area="deviations", key=norm.id, label=norm.label, status=status,
            creditiq_text=norm.actual_text if norm.outcome in ("deviation", "pass") else None,
            record_text=(row.recorded_value or row.description) if row else None,
            norm=norm, record_deviation=row, notes=notes, adjudicable=False, scored=scored,
        ))
    for d in record.deviations:
        if d.norm_id is None or d.norm_id not in by_id:
            items.append(ComparisonItem(
                area="deviations", key=reference.item_key(d), label=d.description, status="missed",
                creditiq_text=None, record_text=d.recorded_value or d.description, record_deviation=d,
                notes=["no_norm"], adjudicable=False, scored=scored,
            ))
    return items, neither


def _authority_item(record: ReferenceRecord, required: ApprovingAuthority, on_record: ApprovingAuthority,
                    levels: dict[str, int], scored: bool) -> ComparisonItem | None:
    recorded = record.approval
    if recorded is None:
        return None
    notes: list = []
    if required.outcome != "determined" or required.required is None:
        status, notes = "differ", ["cannot_determine"]
    elif recorded.authority_key == required.required.key:
        status = "agree"
    else:
        status = "differ"
        if recorded.authority_key is None or recorded.authority_key not in levels:
            # Also a key the published matrix no longer has (RBL's matrix replaced the interim one).
            notes = ["not_in_matrix"]
        else:
            notes = ["lower" if levels[recorded.authority_key] < required.required.level else "higher"]
    return ComparisonItem(
        area="approving_authority", key=AUTHORITY_KEY, label="Approving authority", status=status,
        creditiq_text=required.required.label if required.required else None, record_text=recorded.authority_text,
        required=required, record_approval=recorded, authority_on_record_deviations=on_record.required,
        notes=notes, adjudicable=False, scored=scored,
    )


def compare(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> CaseComparison:
    """The comparison as it stands now."""
    matrix = reader.load_approval_matrix(root)
    policy_config = reader.load_policy(root)
    record = reference.load(conn, case.id)
    provisional_matrix = matrix.status == "provisional"
    if record is None:
        return CaseComparison(
            case_id=case.id, config_version=reader.published_version(root)["version"], record=None,
            provisional_norms=any(n.status == "provisional" for n in policy_config.norms),
            provisional_matrix=provisional_matrix,
            counts=ComparisonCounts(agree=0, differ=0, new=0, missed=0, to_adjudicate=0, no_deviation_either_side=0),
            items=[], scores=[],
        )

    assessment = policy.assess(conn, root, case)
    required = approval.from_assessment(matrix, policy_config, case, assessment)
    norms_by_id = {n.id: n for n in assessment.norms}
    order = [c.key for c in policy_config.deviation_categories]
    labels = {c.key: c.label for c in policy_config.deviation_categories}
    record_deviations: dict[str, list[tuple[str, str]]] = {}
    for d in record.deviations:
        category = _record_category(d, norms_by_id)
        if category:
            record_deviations.setdefault(category, []).append((reference.item_key(d), d.description))
    on_record = approval.lookup(matrix, order, labels, case.facilities, case.amount_inr, record_deviations,
                                case_id=case.id, config_version=assessment.config_version or "")

    authority_scored = matrix.status == "active"
    items, neither = _deviation_items(record, assessment.norms, scored=True)
    authority = _authority_item(record, required, on_record, {a.key: a.level for a in matrix.authorities},
                                authority_scored)
    if authority is not None:
        items.append(authority)

    confirmed = record.confirmed_by is not None
    decisions = _adjudications(conn, case.id)
    for item in items:
        item.adjudicable = confirmed and item.status in ("differ", "new")
        decision = decisions.get((item.area, item.key))
        if decision is not None:
            item.adjudication = Adjudication(
                verdict=decision["verdict"], reason=decision["reason"], decided_by=decision["decided_by"],
                decided_by_name=_name(decision["decided_by"]), decided_at=decision["decided_at"],
                stale=json.loads(decision["snapshot"]) != _snapshot(item, assessment.config_version),
            )

    def current(item: ComparisonItem) -> bool:
        return item.adjudication is not None and not item.adjudication.stale

    deviation_items = [i for i in items if i.area == "deviations"]
    count = {s: sum(1 for i in deviation_items if i.status == s) for s in ("agree", "differ", "new", "missed")}
    counts = ComparisonCounts(
        **count,
        to_adjudicate=sum(1 for i in items if i.adjudicable and not current(i)),
        no_deviation_either_side=neither,
    )
    upheld = sum(1 for i in deviation_items
                 if i.status in ("differ", "new") and current(i) and i.adjudication.verdict == "valid")
    scores = [AreaScore(
        area="deviations", scored=True,
        found_in_record=count["agree"] + count["differ"],
        recorded_total=count["agree"] + count["differ"] + count["missed"],
        flagged_total=count["agree"] + count["differ"] + count["new"],
        valid=count["agree"] + upheld,
        pending=sum(1 for i in deviation_items if i.status in ("differ", "new") and not current(i)),
    )]
    if authority is not None and authority_scored:
        found = int(authority.status == "agree"
                    or (current(authority) and authority.adjudication.verdict == "valid"))
        scores.append(AreaScore(
            area="approving_authority", scored=True, found_in_record=found, recorded_total=1, valid=found,
            flagged_total=1, pending=int(authority.status == "differ" and not current(authority)),
        ))
    return CaseComparison(
        case_id=case.id, config_version=assessment.config_version, record=record,
        provisional_norms=any(n.provisional for n in assessment.norms), provisional_matrix=provisional_matrix,
        counts=counts, items=items, scores=scores,
    )


def adjudicate(conn: sqlite3.Connection, root: Path, case: CaseDetail, area: str, key: str,
               request: AdjudicationRequest, user: dict) -> ComparisonItem:
    """The reviewer's verdict on a differ or new item (F-25.4). A new decision replaces the
    last; each is logged with a snapshot of what was decided on."""
    reason = request.reason.strip()
    if len(reason) < 3:
        raise Invalid("a reason of at least 3 characters is required")
    request = request.model_copy(update={"reason": reason})
    comparison = compare(conn, root, case)
    if comparison.record is None or comparison.record.confirmed_by is None:
        raise Conflict("the reference record must be confirmed before items are adjudicated")
    item = next((i for i in comparison.items if i.area == area and i.key == key), None)
    if item is None:
        raise NotFound(f"no comparison item {area}/{key}")
    if item.status not in ("differ", "new"):
        raise Conflict(f"a {item.status} item is not adjudicated")
    snapshot = _snapshot(item, comparison.config_version)
    now = now_iso()
    with db.transaction(conn):
        conn.execute(
            """INSERT INTO comparison_adjudications (case_id, area, item_key, verdict, reason, snapshot, decided_by,
               decided_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT (case_id, area, item_key) DO UPDATE SET verdict = excluded.verdict,
               reason = excluded.reason, snapshot = excluded.snapshot, decided_by = excluded.decided_by,
               decided_at = excluded.decided_at""",
            (case.id, area, key, request.verdict, request.reason, json.dumps(snapshot), user["id"], now),
        )
        db.log_decision(conn, at=now, actor=user["id"], case_id=case.id, action="comparison.adjudicated",
                        detail=json.dumps({"area": area, "key": key, "verdict": request.verdict,
                                           "reason": request.reason, "snapshot": snapshot}))
    return next(i for i in compare(conn, root, case).items if i.area == area and i.key == key)
