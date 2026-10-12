"""Approving authority (docs/functional-requirements.md F-21; decision C.4-9).

Who must approve a case: for each product requested, the published matrix's amount band,
then each category of the case's policy deviations (F-20) raising that by its rule. Rules
never stack: each counts from the amount authority, and the case takes the highest any one
step needs. Norms that could not be assessed make the answer a lower bound.

Reads configuration only, through the reader. Never reads RBL's reference record
(.importlinter contract 2): the analyst works blind to the recorded approval.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

from . import policy
from .configstore import reader
from .configstore.schema import ApprovalMatrixSection, MatrixAuthority, PolicySection
from .contracts import ApprovingAuthority, AuthorityRef, AuthorityStep, CaseDetail, PolicyAssessment


def _ref(authority: MatrixAuthority) -> AuthorityRef:
    return AuthorityRef(key=authority.key, label=authority.label, level=authority.level)


def lookup(
    matrix: ApprovalMatrixSection,
    category_order: Sequence[str],
    category_labels: Mapping[str, str],
    facilities: Iterable[str],
    amount_inr: int,
    deviations: Mapping[str, list[tuple[str, str]]],
    unevaluated: Sequence[tuple[str, str, str]] = (),
    *,
    case_id: str = "",
    config_version: str = "",
) -> ApprovingAuthority:
    """The required authority. deviations: category -> [(norm id, label)];
    unevaluated: [(norm id, label, category)] for norms that could not be assessed."""
    facilities = list(facilities)
    ladder = sorted(matrix.authorities, key=lambda a: a.level)
    by_key = {a.key: a for a in ladder}
    products = [p for p in matrix.products if set(p.facilities) & set(facilities)]
    mapped = {f for p in matrix.products for f in p.facilities}
    common = dict(
        case_id=case_id,
        amount_inr=amount_inr,
        amount_basis=matrix.amount_basis,
        products=[p.key for p in products],
        product_labels=[p.label for p in products],
        unmapped_facilities=[f for f in facilities if f not in mapped],
        source=matrix.source,
        config_version=config_version,
    )
    provisional = matrix.status == "provisional"
    if not products:
        return ApprovingAuthority(
            outcome="cannot_determine", required=None, reason="no_product", steps=[], lower_bound=False,
            unevaluated=[], unevaluated_labels=[], could_rise_to=None, provisional=provisional, **common,
        )

    steps: list[AuthorityStep] = []
    for product in products:
        lower = None
        for i, band in enumerate(matrix.bands[product.key]):
            if band.up_to_inr is None or amount_inr <= band.up_to_inr:
                authority = by_key[band.authority]
                provisional = provisional or "provisional" in (band.status, authority.status)
                steps.append(AuthorityStep(
                    kind="amount", rule=f"bands.{product.key}[{i}]", product=product.key, product_label=product.label,
                    band_from_inr=lower, band_to_inr=band.up_to_inr, authority=_ref(authority),
                ))
                break
            lower = band.up_to_inr
    # Positions on the ladder are levels: the publish check makes levels consecutive from 1.
    base = max(ladder.index(by_key[s.authority.key]) for s in steps)

    rules = {r.category: r for r in matrix.deviations}
    for category in category_order:
        found = deviations.get(category)
        rule = rules.get(category)
        if not found or rule is None:  # the publish cross-check gives every category a rule
            continue
        position = base + rule.levels_above
        at_least = by_key[rule.at_least] if rule.at_least else None
        if at_least is not None:
            position = max(position, ladder.index(at_least))
        capped = position > len(ladder) - 1
        authority = ladder[min(position, len(ladder) - 1)]
        provisional = provisional or "provisional" in (rule.status, authority.status)
        steps.append(AuthorityStep(
            kind="deviation", rule=f"deviations.{category}", category=category,
            category_label=category_labels.get(category, category),
            norms=[n for n, _ in found], norm_labels=[label for _, label in found],
            levels_above=rule.levels_above, at_least=_ref(at_least) if at_least else None, capped=capped,
            authority=_ref(authority),
        ))

    top = max(s.authority.level for s in steps)
    governing = next(s for s in steps if s.authority.level == top)
    governing.governs = True
    required = governing.authority

    could_rise_to = None
    if unevaluated:
        widened = {c: list(v) for c, v in deviations.items()}
        for norm_id, label, category in unevaluated:
            widened.setdefault(category, []).append((norm_id, label))
        could_rise_to = lookup(matrix, category_order, category_labels, facilities, amount_inr, widened).required

    return ApprovingAuthority(
        outcome="determined", required=required, steps=steps, lower_bound=bool(unevaluated),
        unevaluated=[n for n, _, _ in unevaluated], unevaluated_labels=[label for _, label, _ in unevaluated],
        could_rise_to=could_rise_to, provisional=provisional, **common,
    )


def required(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> ApprovingAuthority:
    """The authority the case needs on its current policy assessment (F-20)."""
    matrix = reader.load_approval_matrix(root)
    return from_assessment(matrix, reader.load_policy(root), case, policy.assess(conn, root, case))


def from_assessment(matrix: ApprovalMatrixSection, policy_config: PolicySection, case: CaseDetail,
                    assessment: PolicyAssessment) -> ApprovingAuthority:
    deviations: dict[str, list[tuple[str, str]]] = {}
    unevaluated: list[tuple[str, str, str]] = []
    for norm in assessment.norms:
        if norm.outcome == "deviation":
            deviations.setdefault(norm.category, []).append((norm.id, norm.label))
        elif norm.outcome == "cannot_evaluate":
            unevaluated.append((norm.id, norm.label, norm.category))
    return lookup(
        matrix,
        [c.key for c in policy_config.deviation_categories],
        {c.key: c.label for c in policy_config.deviation_categories},
        case.facilities,
        case.amount_inr,
        deviations,
        unevaluated,
        case_id=case.id,
        config_version=assessment.config_version or "",
    )
