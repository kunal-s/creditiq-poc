"""The settings an Administrator edits on the Administration screen (F-00.6).

Tolerances, the policy norms' thresholds, the cross-check rules (on or off, severity, whether they
block) and the approval matrix's bands and deviation steps. An edit is checked as a publish from
the configuration files is, then published as a new immutable version (origin "app") with the
editor's name and note, recorded in the audit trail, and every case's checks re-run.

This module and the command line are the only ways to the configuration writer (CLAUDE.md rule 4,
.importlinter): the API calls it for the Administrator; nothing that runs on a case may import it.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ValidationError

from . import db, pipeline
from .config import option_ids
from .configstore import reader, writer
from .configstore.schema import (
    ApprovalMatrixSection,
    CrossChecksSection,
    PolicySection,
    TolerancesSection,
    cross_check,
)
from .contracts.admin import (
    EditableAuthority,
    EditableBand,
    EditableDeviation,
    EditableMatrix,
    EditableNorm,
    EditableProduct,
    EditableRatio,
    EditableRule,
    EditableSettings,
    EditableTolerance,
    SettingChange,
    SettingsChanges,
    SettingsPreview,
    SettingsPublished,
)
from .util import now_iso

NOTE_MIN = 3
# Tolerances that are a whole count, and the name similarity, which is a share of 1.
COUNTS = {"emi_min_occurrences", "turnover_window_min_months", "itr_due_days"}
SIMILARITY = {"name_match"}


class SettingsInvalid(ValueError):
    """The changes cannot be published; each problem in words."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def editable(root: Path) -> EditableSettings:
    """The editable settings as the version now published has them."""
    record = reader.published_version(root)
    tolerances = reader.load_tolerances(root)
    policy = reader.load_policy(root)
    checks = reader.load_crosschecks(root)
    matrix = reader.load_approval_matrix(root)
    used_by: dict[str, list[str]] = {}
    for rule in checks.rules:
        if rule.tolerance:
            used_by.setdefault(rule.tolerance, []).append(rule.id)
    ratio_norms: dict[str, list[str]] = {}
    for norm in policy.norms:
        if norm.ratio:
            ratio_norms.setdefault(norm.ratio, []).append(norm.id)
    categories = {c.key: c.label for c in policy.deviation_categories}
    return EditableSettings(
        version=record["version"],
        published_at=record["published_at"],
        author=record["author"],
        origin=record.get("origin", "cli"),
        tolerances=[EditableTolerance(key=t.key, label=t.label, value=t.value, unit=t.unit, source=t.source,
                                      rules=used_by.get(t.key, [])) for t in tolerances.tolerances],
        ratios=[EditableRatio(key=r.key, label=r.label, unit=r.unit, kind=r.kind, acceptable=r.acceptable,
                              marginal=r.marginal, norms=ratio_norms.get(r.key, [])) for r in policy.ratios],
        norms=[EditableNorm(id=n.id, family=n.family, label=n.label or n.id, unit=n.unit, kind=n.kind,
                            threshold=n.threshold)
               for n in policy.norms if n.ratio is None and n.threshold is not None and n.kind is not None],
        rules=[EditableRule(id=r.id, title=r.title, area=r.area, severity=r.severity, blocking=r.blocking,
                            enabled=r.enabled) for r in checks.rules],
        matrix=EditableMatrix(
            status=matrix.status,
            authorities=[EditableAuthority(key=a.key, level=a.level, label=a.label) for a in matrix.authorities],
            products=[EditableProduct(key=p.key, label=p.label,
                                      bands=[EditableBand(up_to_inr=b.up_to_inr, authority=b.authority)
                                             for b in matrix.bands.get(p.key, [])]) for p in matrix.products],
            deviations=[EditableDeviation(category=d.category, label=categories.get(d.category, d.category),
                                          levels_above=d.levels_above, at_least=d.at_least)
                        for d in matrix.deviations],
        ),
    )


def preview(root: Path, changes: SettingsChanges) -> SettingsPreview:
    """What the changes would change, and why they could not be published, without publishing."""
    _, out, problems = _apply(root, changes)
    return SettingsPreview(changes=out, problems=problems)


def publish(conn: sqlite3.Connection, root: Path, user: dict, note: str, changes: SettingsChanges) -> SettingsPublished:
    """Publish the changes as a new version and re-run every case. Raises SettingsInvalid."""
    note = note.strip()
    sections, out, problems = _apply(root, changes)
    if len(note) < NOTE_MIN:
        problems = [f"A note of at least {NOTE_MIN} characters is required.", *problems]
    if problems:
        raise SettingsInvalid(problems)
    record = writer.publish_edited(data_root=root, author=user["name"], note=note, sections=sections,
                                   changes=[c.model_dump(mode="json") for c in out])
    db.log_decision(conn, at=now_iso(), actor=user["id"], action="config.published", case_id=None,
                    detail=json.dumps({"version": record["version"], "note": note,
                                       "changes": [c.model_dump(mode="json") for c in out]}))
    conn.commit()
    ran, failed = pipeline.refresh_all_cases(conn, root)
    return SettingsPublished(version=record["version"], published_at=record["published_at"], changes=out,
                             cases_rerun=len(ran), cases_failed=sorted(failed))


# --- Applying the changes ---


def _apply(root: Path, changes: SettingsChanges) -> tuple[dict[str, BaseModel], list[SettingChange], list[str]]:
    """The edited sections (only those that change), each change, and the problems."""
    tolerances = reader.load_tolerances(root).model_copy(deep=True)
    policy = reader.load_policy(root).model_copy(deep=True)
    checks = reader.load_crosschecks(root).model_copy(deep=True)
    matrix = reader.load_approval_matrix(root).model_copy(deep=True)
    out: list[SettingChange] = []
    problems: list[str] = []
    _tolerances(tolerances, changes, out, problems)
    _ratios(policy, changes, out, problems)
    _norms(policy, changes, out, problems)
    _rules(checks, changes, out, problems)
    _bands(matrix, changes, out, problems)
    _deviations(matrix, policy, changes, out, problems)
    if problems:
        return {}, out, problems
    if not out:
        return {}, out, ["Nothing has changed."]
    edited: dict[str, BaseModel] = {}
    try:
        for name, section, model in (("tolerances", tolerances, TolerancesSection), ("policy", policy, PolicySection),
                                     ("crosschecks", checks, CrossChecksSection),
                                     ("approval_matrix", matrix, ApprovalMatrixSection)):
            if any(c.section == name for c in out):
                edited[name] = model.model_validate(section.model_dump(mode="json"))
    except ValidationError as e:
        return {}, out, [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]
    sections = {**reader.published_sections(root), **edited}
    problems = cross_check(sections, reader.published_ingestion_sections(root), facilities=option_ids("facilities"))
    return edited, out, problems


def _change(out: list[SettingChange], section: str, item: str, label: str, field: str, before, after,
            unit: str | None = None) -> None:
    out.append(SettingChange(section=section, item=item, label=label, field=field, unit=unit, before=before,
                             after=after))


def _whole(value: float) -> bool:
    return float(value).is_integer()


def _tolerances(section: TolerancesSection, changes: SettingsChanges, out: list, problems: list) -> None:
    by_key = {t.key: t for t in section.tolerances}
    for key, value in changes.tolerances.items():
        t = by_key.get(key)
        if t is None:
            problems.append(f"There is no tolerance {key!r}.")
            continue
        if key in SIMILARITY and not 0.5 <= value <= 1:
            problems.append(f"{t.label}: give a similarity between 0.5 and 1.")
        elif key in COUNTS and (value < 0 or not _whole(value)):
            problems.append(f"{t.label}: give a whole number, 0 or more.")
        elif t.unit == "%" and not 0 <= value <= 100:
            problems.append(f"{t.label}: give a percentage between 0 and 100.")
        elif value < 0:
            problems.append(f"{t.label}: give a value of 0 or more.")
        elif value != t.value:
            _change(out, "tolerances", key, t.label, "value", t.value, value, t.unit)
            t.value = value


def _ratios(policy: PolicySection, changes: SettingsChanges, out: list, problems: list) -> None:
    by_key = {r.key: r for r in policy.ratios}
    for key, change in changes.ratios.items():
        r = by_key.get(key)
        if r is None:
            problems.append(f"There is no financial ratio {key!r}.")
            continue
        acceptable = r.acceptable if change.acceptable is None else change.acceptable
        marginal = r.marginal if change.marginal is None else change.marginal
        if acceptable <= 0 or marginal <= 0:
            problems.append(f"{r.label}: give values above 0.")
            continue
        if r.kind == "min" and marginal > acceptable:
            problems.append(f"{r.label}: the marginal value cannot be above the acceptable one for a minimum.")
            continue
        if r.kind == "max" and marginal < acceptable:
            problems.append(f"{r.label}: the marginal value cannot be below the acceptable one for a maximum.")
            continue
        for field, after in (("acceptable", acceptable), ("marginal", marginal)):
            before = getattr(r, field)
            if after != before:
                _change(out, "policy", key, r.label, field, before, after, r.unit)
                setattr(r, field, after)


def _norms(policy: PolicySection, changes: SettingsChanges, out: list, problems: list) -> None:
    by_id = {n.id: n for n in policy.norms}
    ratios = {r.key: r.label for r in policy.ratios}
    for norm_id, value in changes.norms.items():
        n = by_id.get(norm_id)
        if n is None:
            problems.append(f"There is no policy norm {norm_id!r}.")
            continue
        label = f"{n.id} {n.label or ''}".strip()
        if n.ratio:
            problems.append(f"{label} takes its threshold from {ratios.get(n.ratio, n.ratio)}: change it there.")
        elif n.threshold is None:
            problems.append(f"{label} has no threshold to change.")
        elif n.unit in ("count", "rank") and (value < 0 or not _whole(value)):
            problems.append(f"{label}: give a whole number, 0 or more.")
        elif n.unit == "%" and not 0 <= value <= 100:
            problems.append(f"{label}: give a percentage between 0 and 100.")
        elif value < 0:
            problems.append(f"{label}: give a value of 0 or more.")
        elif value != n.threshold:
            _change(out, "policy", norm_id, label, "threshold", n.threshold, value, n.unit)
            n.threshold = value
            if n.applies_when == "turnover_method":
                # The turnover method finances the requirement less the borrower's margin (F-22.2): the
                # norm and the working-capital assessment move together, the margin staying as it is.
                wc = policy.working_capital
                requirement = value + wc.turnover_margin_pct
                _change(out, "policy", "working_capital", "Turnover method: working-capital requirement",
                        "turnover_requirement_pct", wc.turnover_requirement_pct, requirement, "%")
                wc.turnover_requirement_pct = requirement


def _rules(checks: CrossChecksSection, changes: SettingsChanges, out: list, problems: list) -> None:
    by_id = {r.id: r for r in checks.rules}
    for rule_id, change in changes.rules.items():
        r = by_id.get(rule_id)
        if r is None:
            problems.append(f"There is no cross-check {rule_id!r}.")
            continue
        for field in ("enabled", "severity", "blocking"):
            after = getattr(change, field)
            before = getattr(r, field)
            if after is not None and after != before:
                _change(out, "crosschecks", rule_id, f"{r.id} {r.title}", field, before, after)
                setattr(r, field, after)


def _bands(matrix: ApprovalMatrixSection, changes: SettingsChanges, out: list, problems: list) -> None:
    products = {p.key: p for p in matrix.products}
    authorities = {a.key: a.label for a in matrix.authorities}
    for key, bands in changes.bands.items():
        product = products.get(key)
        if product is None:
            problems.append(f"There is no product {key!r} in the approval matrix.")
            continue
        current = matrix.bands.get(key, [])
        if len(bands) != len(current):
            problems.append(f"{product.label}: give all {len(current)} amount bands.")
            continue
        unknown = [b.authority for b in bands if b.authority not in authorities]
        if unknown:
            problems.append(f"{product.label}: there is no authority {unknown[0]!r}.")
            continue
        limits = [b.up_to_inr for b in bands]
        if limits[-1] is not None or any(v is None for v in limits[:-1]):
            problems.append(f"{product.label}: every band but the last needs an upper amount; the last is open.")
            continue
        if any(a >= b for a, b in zip(limits[:-1], limits[1:-1])):
            problems.append(f"{product.label}: the amount bands must rise from one to the next.")
            continue
        for i, (old, new) in enumerate(zip(current, bands), start=1):
            label = f"{product.label}, band {i}"
            if new.up_to_inr != old.up_to_inr:
                _change(out, "approval_matrix", key, label, "up_to_inr", old.up_to_inr, new.up_to_inr, "inr")
                old.up_to_inr = new.up_to_inr
            if new.authority != old.authority:
                _change(out, "approval_matrix", key, label, "authority", authorities[old.authority],
                        authorities[new.authority])
                old.authority = new.authority


def _deviations(matrix: ApprovalMatrixSection, policy: PolicySection, changes: SettingsChanges, out: list,
                problems: list) -> None:
    by_category = {d.category: d for d in matrix.deviations}
    labels = {c.key: c.label for c in policy.deviation_categories}
    authorities = {a.key: a.label for a in matrix.authorities}
    for category, change in changes.deviations.items():
        d = by_category.get(category)
        if d is None:
            problems.append(f"There is no deviation step for {category!r}.")
            continue
        label = labels.get(category, category)
        if change.levels_above is not None and change.levels_above != d.levels_above:
            _change(out, "approval_matrix", category, label, "levels_above", d.levels_above, change.levels_above)
            d.levels_above = change.levels_above
        if "at_least" in change.model_fields_set:
            after = change.at_least or None
            if after is not None and after not in authorities:
                problems.append(f"{label}: there is no authority {after!r}.")
                continue
            if after != d.at_least:
                _change(out, "approval_matrix", category, label, "at_least",
                        authorities.get(d.at_least) if d.at_least else None, authorities.get(after) if after else None)
                d.at_least = after
