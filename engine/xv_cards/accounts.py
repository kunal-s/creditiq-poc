"""Cards for BA-01 and BA-02 (bank accounts).

Presentation only: built after the rule has decided its outcome (see engine/xv_cards/__init__.py).

The columns are the rule's sides: the accounts declared (in the declaration of existing facilities
or the sourcing message), the statements on file and, for BA-02, the accounts seen only in a
transfer. Each row is one account and where it appears, linked to the page it was read from. The
difference in words comes from the finding's own line-by-line rows.

The key figures: a line per account the rule flagged ("Account ·5678: declared, no statement"),
or on a pass what the rule confirmed ("2 declared accounts: each with a statement").

The helpers for pages and reviews serve the obligation and board-resolution cards too. A check
short of documents asks for them in the words every card uses (engine/xv_cards/__init__.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts import AccountFact, Evidence, Finding, FindingSide, SourceColumn, XvHighlight
from ..crosschecks import DECLARATION, YES
from . import builds, column, column_from_side, highlight, plural, row, sentence, wanted

if TYPE_CHECKING:
    from ..configstore.schema import CrossCheckRule
    from ..crosschecks import Context

# Where the account set says an account appears (engine/facts.py _accounts).
MESSAGE = "Sourcing message"
TRANSFER = "Transfer in "
# The rule's sides (engine/crosschecks.py _declared_accounts_side, _statements_side, _evidenced_accounts).
SIDES = {"Declared accounts": "declared", "Declared in the sourcing message": "declared",
         "Statements on file": "statements", "Seen in transfers": "transfers"}
ROW_COLUMNS = ["Account", "Where it appears"]
BA_01 = "declared_accounts_with_statements"


# --- Shared with the obligation and board-resolution cards ---


def waits_for_review(finding: Finding) -> bool:
    return any(s.awaiting_review for s in finding.sides)


def page_line(evidence: list[Evidence]) -> str | None:
    return f"Page {evidence[0].page}" if evidence else None


def traced(rows: list, fallback: list[Evidence]) -> list[Evidence]:
    """A column's evidence: the first page of each row, else the side's own; each page once."""
    found: dict[tuple, Evidence] = {}
    for e in [r.evidence[0] for r in rows if r.evidence] or fallback:
        found.setdefault((e.document_id, e.page, e.bbox), e)
    return list(found.values())


# --- BA-01, BA-02 ---


def _declaration_documents(ctx: Context) -> set[str]:
    """The declarations of existing facilities on file, by the facts read from them."""
    f = ctx.facts
    found: list = [f.declaration] if f.declaration else []
    found += [x for x in f.facilities if x.source == DECLARATION]
    found += [v for v in f.identities.entity_pan + f.identities.gstin + f.identities.legal_name + f.identities.cin
              if v.source == DECLARATION]
    return {e.document_id for x in found for e in x.evidence}


def _in_declaration(ctx: Context, where: str) -> bool:
    return ctx.type_names.get(DECLARATION, DECLARATION) in where.split(" + ")


def _pages(ctx: Context, a: AccountFact, declarations: set[str]) -> dict[str, list[Evidence]]:
    """The pages one account was read from, by where it appears.

    The account set reads the statements first, then the declaration's accounts, then the
    sourcing message, and takes an account from a transfer narration only when nothing else names
    it; each adds the first page it read (engine/facts.py _accounts). So an account with a
    statement starts with its statement's page, the sourcing message's page is the message's own,
    and an account seen only in a transfer has only transfer pages."""
    pages: dict[str, list[Evidence]] = {"statements": [], "declaration": [], "message": [], "transfers": []}
    rest = list(a.evidence)
    if not (a.has_statement or a.declared):
        pages["transfers"] = rest
        return pages
    if a.has_statement and rest:
        pages["statements"].append(rest.pop(0))
    banking = ctx.facts.declared_banking
    message = banking.evidence[:1] if banking and MESSAGE in a.sources else []
    in_declaration = any(_in_declaration(ctx, s) for s in a.sources)
    for e in rest:
        if in_declaration and e.document_id in declarations:
            pages["declaration"].append(e)
        elif e in message:
            pages["message"].append(e)
        else:
            pages["statements" if a.has_statement else "declaration"].append(e)
    if in_declaration and not pages["declaration"] and len(pages["statements"]) > 1:
        # A declaration not recognised by its facts: its page came after every statement's.
        pages["declaration"].append(pages["statements"].pop())
    return pages


def _where(ctx: Context, a: AccountFact, kind: str) -> str:
    """Where the account appears, for the column it is shown in."""
    def declares(s: str) -> bool:
        return s == MESSAGE or _in_declaration(ctx, s)

    if kind == "declared":
        found = [s for s in a.sources if declares(s)]
    elif kind == "transfers":
        found = [s for s in a.sources if s.startswith(TRANSFER)]
    else:
        found = [s for s in a.sources if not (declares(s) or s.startswith(TRANSFER))]
    return "; ".join(found or a.sources)


def _accounts_column(ctx: Context, side: FindingSide, kind: str, declarations: set[str]) -> SourceColumn:
    accounts = {
        "declared": [a for a in ctx.facts.accounts if a.declared],
        "statements": [a for a in ctx.facts.accounts if a.has_statement],
        "transfers": [a for a in ctx.facts.accounts if not (a.has_statement or a.declared)],
    }[kind]
    rows = []
    for a in accounts:
        pages = _pages(ctx, a, declarations)
        shown = pages["declaration"] + pages["message"] if kind == "declared" else pages[kind]
        rows.append(row([a.label, _where(ctx, a, kind)], shown))
    n = len(accounts)
    coverage = {
        "declared": f"{plural(n, 'account')} declared",
        "statements": f"Statements for {plural(n, 'account')}" if n else "No statement on file",
        "transfers": f"{plural(n, 'account')} named in transfer narrations",
    }[kind]
    return column(ctx, kind, side.label, sources=side.sources, value=side.value, coverage=coverage,
                  differs=side.differs, manual=side.relies_on_manual, awaiting=side.awaiting_review,
                  field_ids=side.field_ids, evidence=traced(rows, side.evidence), row_columns=ROW_COLUMNS, rows=rows)


def _flagged(rule: CrossCheckRule, finding: Finding) -> list[tuple[str, str]]:
    """Each account the rule flagged, from its own table, and what is wrong with it. BA-02's rows
    read declared, statement on file, where it appears: a flagged row with a statement was not
    declared; one without was seen only in a transfer."""
    flagged = [r for r in finding.detail.rows if r.flagged] if finding.detail else []
    if rule.variable == BA_01:
        return [(r.label, "declared") for r in flagged]
    return [(r.label, "undeclared" if r.cells[1:2] == [YES] else "transfer") for r in flagged]


# What is wrong with a flagged account: in the card's words, and on its line of the overview card.
MISMATCH = {"declared": "{} was declared but has no statement", "undeclared": "{} has a statement but was not declared",
            "transfer": "{} appears only in a transfer, with no statement and no declaration"}
NOTE = {"declared": "declared, no statement", "undeclared": "statement, not declared",
        "transfer": "seen only in transfers"}


def _accounts_mismatch(rule: CrossCheckRule, finding: Finding) -> str | None:
    """The flagged rows of the rule's own table, in words."""
    found = [MISMATCH[kind].format(account) for account, kind in _flagged(rule, finding)]
    return sentence("; ".join(found)) if found else None


def _account_lines(rule: CrossCheckRule, finding: Finding) -> list[XvHighlight]:
    """A line per account flagged, as the rule found it; on a pass, what the rule confirmed (BA-01:
    each declared account has a statement; BA-02: each account on file was declared, or, with
    nothing declared, that no other account appears in the documents)."""
    if finding.outcome == "fail":
        return [highlight(finding, account, note=NOTE[kind]) for account, kind in _flagged(rule, finding)]
    if finding.outcome == "incomplete":
        return [highlight(finding, "Declared accounts" if rule.variable == BA_01 else "Accounts on file",
                          note=wanted(finding))]
    if finding.outcome != "pass":
        return []
    rows = finding.detail.rows if finding.detail else []
    if rule.variable == BA_01:
        # A row per declared account, each with its statement.
        return [highlight(finding, plural(len(rows), "declared account"),
                          note="each with a statement" if len(rows) > 1 else "with a statement")]
    # A row per account seen anywhere; those with a statement are the accounts on file.
    n = sum(1 for r in rows if r.cells[1:2] == [YES])
    if not n:
        return [highlight(finding, "Accounts on file", note="none named in the documents")]
    if any(SIDES.get(s.label) == "declared" for s in finding.sides):
        note = "each declared" if n > 1 else "declared"
    else:
        note = "no other account in the documents"
    return [highlight(finding, f"{plural(n, 'account')} on file", note=note)]


@builds(BA_01, "evidenced_accounts_declared")
def accounts_card(ctx: Context, rule: CrossCheckRule, finding: Finding) -> None:
    declarations = _declaration_documents(ctx)
    finding.columns = [
        _accounts_column(ctx, side, SIDES[side.label], declarations) if side.label in SIDES
        else column_from_side(ctx, side, f"side-{i}")
        for i, side in enumerate(finding.sides)
    ]
    if finding.outcome == "fail":
        finding.mismatch = _accounts_mismatch(rule, finding)
    finding.highlights = _account_lines(rule, finding)
