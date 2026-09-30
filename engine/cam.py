"""The draft Credit Approval Memo (FRD F-23).

Sections in the configured order (config/cam.yaml; an interim list until
RBL's template arrives, F-23.1). Each section is drafted from the facts
only, in a neutral register, and every figure carries the pages it rests
on (F-23.2). The memo ends with a structured summary of findings (F-19),
deviations (F-20) and open queries (F-14) (F-23.3), then an empty
recommendation for credit to complete (F-23.4).

The text is composed from the facts, not written by a model, so the same
case always gives the same memo (F-23.6, principle 6).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from . import completeness, facts as facts_module, policy as policy_module, reads, spread as spread_module
from .config import load_app_config
from .configstore import reader
from .contracts import (
    Cam,
    CamSection,
    CamSummaryItem,
    CamTable,
    CamText,
    CaseDetail,
    CaseFacts,
    Evidence,
    PolicyAssessment,
    Spread,
)

inr = facts_module.inr

# How the memo names each constitution in a sentence.
ENTITY = {
    "private_limited": "a private limited company",
    "partnership": "a partnership firm",
    "proprietorship": "a proprietorship concern",
}


def _join(items: list[str]) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return items[0] if items else ""
    return ", ".join(items[:-1]) + " and " + items[-1]


def _pct(a: float, b: float) -> str:
    return f"{(a - b) / b * 100:+.1f}%" if b else "—"


class Draft:
    def __init__(self, conn: sqlite3.Connection, root: Path, case: CaseDetail) -> None:
        self.conn, self.root, self.case = conn, root, case
        app = load_app_config()
        self.facility_names = {f["id"]: f["label"] for f in app["facilities"]}
        self.facts: CaseFacts = facts_module.compute(conn, root, case)
        self.policy: PolicyAssessment = policy_module.assess(conn, root, case)
        self.spread: Spread = spread_module.build(conn, root, case)
        self.findings = reads.findings(conn, case.id)
        self.readiness, _ = completeness.evaluate(conn, root, case)
        self.waived = {
            r["ref"]
            for r in conn.execute(
                "SELECT ref FROM review_items WHERE case_id = ? AND kind = 'finding' AND decision = 'waive'",
                (case.id,),
            )
        }

    # --- Sections ---

    def borrower_profile(self) -> list[CamText]:
        c = self.case
        entity = ENTITY.get(c.constitution)
        out = [CamText(text=f"{c.borrower} is {entity}." if entity else
                       f"{c.borrower}; its constitution is not yet confirmed.")]
        ids = []
        cites: list[Evidence] = []
        for label, values in (("PAN", self.facts.identities.entity_pan), ("GSTIN", self.facts.identities.gstin)):
            if values:
                ids.append(f"{label} {values[0].value}")
                cites += values[0].evidence[:1]
        if ids:
            out.append(CamText(text=f"Its {_join(ids)} are as read from its registration documents.", citations=cites))
        vintage = self.policy_input("vintage_years")
        if vintage:
            out.append(CamText(text=f"It has been in business for {vintage.value:g} years.", citations=vintage.evidence))
        return out

    def proposal(self) -> list[CamText]:
        c = self.case
        facilities = _join([self.facility_names.get(f, f).lower() for f in c.facilities]) or "facilities"
        out = [CamText(text=f"The proposal is for {facilities} of {inr(c.amount_inr)} in total"
                            f"{', with collateral offered' if c.collateral_present else ''}.")]
        declared = next((f for y in self.facts.turnover for f in y.figures if f.source == "declared"), None)
        if declared and declared.value:
            out.append(CamText(text=f"The sourcing message states annual turnover of {inr(declared.value)}.",
                               citations=declared.evidence))
        return out

    def promoters(self) -> list[CamText]:
        out = []
        for p in self.facts.persons:
            out.append(CamText(text=f"{p.label} names {_join(p.names)}.", citations=p.evidence[:1]))
        return out

    def financial_performance(self) -> tuple[list[CamText], CamTable | None]:
        cols = [i for i, c in enumerate(self.spread.columns) if c.basis in ("audited", "provisional")][-3:]
        if not cols:
            return [], None
        rows = {r.key: r for r in self.spread.rows}
        keys = [("revenue_from_operations", "inr"), ("ebitda", "inr"), ("profit_after_tax", "inr"),
                ("net_worth", "inr"), ("total_borrowings", "inr"), ("current-ratio", "x"), ("debt-equity", "x")]
        table_rows = []
        for key, unit in keys:
            row = rows.get(key)
            if row is None or all(row.cells[i].value is None for i in cols):
                continue
            cells = [CamText(text=row.label)]
            for i in cols:
                cell = row.cells[i]
                text = "—" if cell.value is None else (inr(cell.value) if unit == "inr" else f"{cell.value:.2f}x")
                cells.append(CamText(text=text, citations=cell.evidence[:2]))
            table_rows.append(cells)
        columns = ["", *[f"{self.spread.columns[i].fy} ({self.spread.columns[i].basis})" for i in cols]]
        paragraphs = []
        revenue = rows.get("revenue_from_operations")
        audited = [i for i in cols if self.spread.columns[i].basis == "audited" and revenue and revenue.cells[i].value]
        if revenue and len(audited) >= 2:
            a, b = audited[-1], audited[-2]
            now, before = revenue.cells[a].value, revenue.cells[b].value
            paragraphs.append(CamText(
                text=f"Revenue from operations was {inr(now)} in {self.spread.columns[a].fy}, against {inr(before)} "
                     f"in {self.spread.columns[b].fy} ({_pct(now, before)}).",
                citations=revenue.cells[a].evidence[:1] + revenue.cells[b].evidence[:1]))
        elif revenue and audited:
            a = audited[-1]
            paragraphs.append(CamText(
                text=f"Revenue from operations was {inr(revenue.cells[a].value)} in {self.spread.columns[a].fy}.",
                citations=revenue.cells[a].evidence[:1]))
        return paragraphs, CamTable(columns=columns, rows=table_rows) if table_rows else None

    def working_capital(self) -> tuple[list[CamText], CamTable | None]:
        wc = self.spread.working_capital
        if wc.method == "not_applicable":
            return [CamText(text=wc.reason)], None
        if wc.missing:
            return [CamText(text=f"{wc.reason} It cannot be computed: {_join(wc.missing)} not on file.")], None
        table = CamTable(columns=["Step", "Amount", "Basis"], rows=[
            [CamText(text=s.label), CamText(text=inr(s.value), citations=s.evidence[:2]), CamText(text=s.basis or "")]
            for s in wc.steps
        ])
        verdict = ("within" if wc.eligible is not None and wc.requested <= wc.eligible else "above")
        return [CamText(text=wc.reason),
                CamText(text=f"On the figures for {wc.column}, eligible bank finance is {inr(wc.eligible)}; the "
                             f"request of {inr(wc.requested)} is {verdict} it.",
                        citations=[e for s in wc.steps for e in s.evidence[:1]])], table

    def banking(self) -> list[CamText]:
        out = []
        for c in self.facts.credits:
            excluded = sorted({e.label.lower() for e in c.exclusions})
            text = (f"Credits in {c.account} total {inr(c.gross)}; after excluding {inr(c.excluded)}"
                    f"{' (' + _join(excluded) + ')' if excluded else ''}, business inflow is {inr(c.net)}"
                    f" over {len(c.months)} month(s).")
            out.append(CamText(text=text, citations=[e for x in c.exclusions[:3] for e in x.evidence[:1]]))
        for a in self.facts.accounts:
            if not a.has_statement:
                out.append(CamText(text=f"No statements have been received for {a.label} "
                                        f"({'declared' if a.declared else 'not declared'}; seen in {_join(a.sources)}).",
                                   citations=a.evidence[:1]))
        return out

    def existing_facilities(self) -> list[CamText]:
        out = []
        declared = [f for f in self.facts.facilities if f.source == "existing_facilities_declaration"]
        if self.facts.declaration_received and not declared:
            out.append(CamText(text="The declaration of existing facilities declares none."))
        for f in self.facts.facilities:
            detail = _join([f.facility or "", inr(f.amount) if f.amount else "", f"EMI {inr(f.emi)}" if f.emi else ""])
            out.append(CamText(text=f"{f.label}: {f.lender}{' — ' + detail if detail else ''}.", citations=f.evidence[:1]))
        for o in self.facts.obligations:
            out.append(CamText(text=f"The bank statements show regular debits of about {inr(o.typical_amount)} a month to "
                                    f"{o.lender} in {len(o.months)} month(s), from {o.account}.",
                               citations=o.evidence[:2]))
        return out

    def cross_verification(self) -> list[CamText]:
        counted = [f for f in self.findings if f.outcome != "not_applicable"]
        fails = [f for f in counted if f.outcome == "fail"]
        incomplete = [f for f in counted if f.outcome == "incomplete"]
        out = [CamText(text=f"{len(counted)} cross-checks were run: {len(fails)} found a discrepancy, "
                            f"{len(incomplete)} could not be completed and "
                            f"{len(counted) - len(fails) - len(incomplete)} agreed.")]
        for f in fails:
            status = " A reviewer has found this flag not valid." if f"finding:{f.id}" in self.waived else ""
            out.append(CamText(text=f"{f.explanation}{status}",
                               citations=[e for s in f.sides for e in s.evidence[:1]]))
        return out

    def policy_section(self) -> list[CamText]:
        norms = [n for n in self.policy.norms if n.outcome != "not_applicable"]
        deviations = [n for n in norms if n.outcome == "deviation"]
        unknown = [n for n in norms if n.outcome == "cannot_evaluate"]
        out = [CamText(text=f"{len(norms)} norms were assessed"
                            f"{' on the ' + self.policy.period + ' statements' if self.policy.period else ''}: "
                            f"{len(deviations)} deviation(s), {len(unknown)} could not be assessed.")]
        for n in deviations:
            joiner = ":" if n.unit == "count" else " is"
            out.append(CamText(text=f"{n.label}{joiner} {policy_module.unit_text(n.actual, n.unit)} against a norm of "
                                    f"{n.required} ({n.category_label}).",
                               citations=[e for i in n.inputs for e in i.evidence[:1]]))
        for n in unknown:
            out.append(CamText(text=f"{n.label} could not be assessed: {_join(n.missing)} not on file."))
        return out

    def documentation(self) -> list[CamText]:
        r = self.readiness
        open_items = [i for i in r.items if i.status in ("missing", "insufficient")]
        out = [CamText(text=f"Readiness is {r.score_pct:.0f}% against a review gate of {r.gate_pct}%; "
                            f"{r.blocking_open} blocking item(s) remain open.")]
        for i in open_items[:10]:
            deficiency = i.deficiency or i.status
            if i.status == "missing" and deficiency.lower().startswith("not received"):
                deficiency = "not received"
            out.append(CamText(text=f"{i.name}: {deficiency.rstrip('.')}."))
        return out

    # --- Helpers and summary ---

    def policy_input(self, name: str):
        for n in self.policy.norms:
            for i in n.inputs:
                if i.name == name:
                    return i
        return None

    def summary(self) -> list[CamSummaryItem]:
        items: list[CamSummaryItem] = []
        for f in self.findings:
            if f.outcome == "fail" and f"finding:{f.id}" not in self.waived:
                items.append(CamSummaryItem(kind="finding", severity=f.severity, ref=f.id,
                                            text=f.explanation,
                                            citations=[e for s in f.sides for e in s.evidence[:1]]))
        for n in self.policy.norms:
            if n.outcome == "deviation":
                items.append(CamSummaryItem(kind="deviation", ref=n.id,
                                            text=f"{n.category_label}: {n.label} {policy_module.unit_text(n.actual, n.unit)}"
                                                 f" against {n.required}.",
                                            citations=[e for i in n.inputs for e in i.evidence[:1]]))
        for q in reads.query_items(self.conn, self.case.id):
            if not q.resolved:
                items.append(CamSummaryItem(kind="query", ref=q.id, text=q.text, citations=q.evidence[:1]))
        return items


def build(conn: sqlite3.Connection, root: Path, case: CaseDetail) -> Cam:
    config = reader.load_cam(root)
    d = Draft(conn, root, case)
    sections = []
    for s in config.sections:
        table = None
        if s.kind == "financial_performance":
            paragraphs, table = d.financial_performance()
        elif s.kind == "working_capital":
            paragraphs, table = d.working_capital()
        elif s.kind == "policy":
            paragraphs = d.policy_section()
        else:
            paragraphs = getattr(d, s.kind)()
        sections.append(CamSection(id=s.id, title=s.title, paragraphs=paragraphs, table=table,
                                   empty=None if paragraphs or table else "Nothing on file yet."))
    return Cam(case_id=case.id, interim_template=config.interim_template, sections=sections,
               summary_title=config.summary_title, summary=d.summary(),
               recommendation_title=config.recommendation_title)

