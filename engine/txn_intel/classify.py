"""The deterministic pass (config/txn_classification.yaml)."""

from __future__ import annotations

import re
from collections import defaultdict

from ..configstore.schema import TxnClassificationSection, TxnRule
from ..names import normalise_name
from .models import Context, Label, Txn


class _Compiled:
    """The configuration's patterns, compiled once."""

    def __init__(self, cfg: TxnClassificationSection) -> None:
        self.cfg = cfg
        self.channels = [(c.id, re.compile(c.pattern, re.I)) for c in cfg.channels]
        self.strip = [re.compile(p, re.I) for p in cfg.counterparty.strip]
        self.noise = {w.lower() for w in cfg.counterparty.noise_words}
        self.lender_cues = {w.lower() for w in cfg.counterparty.lender_cues}
        self.rules = [
            (r, [re.compile(p, re.I) for p in r.any], [re.compile(p, re.I) for p in r.none],
             re.compile(r.counterparty, re.I) if r.counterparty not in ("none", "auto") else None)
            for r in cfg.rules
        ]


def cluster_key(narration: str) -> str:
    """Narrations that differ only in their digits and spacing are one question for the model."""
    return re.sub(r"\s+", " ", re.sub(r"\d+", "#", (narration or "").lower())).strip()


def _tokens(name: str, noise: set[str]) -> list[str]:
    return [w for w in normalise_name(name).split() if w not in noise and len(w) > 1]


def _contains_name(narration_tokens: set[str], name: str, noise: set[str]) -> bool:
    """Every telling word of the name is in the narration (a narration abbreviates, never adds)."""
    words = _tokens(name, noise)
    return bool(words) and all(w in narration_tokens or any(t.startswith(w[:4]) for t in narration_tokens if len(w) >= 4)
                               for w in words)


def _channel(c: _Compiled, text: str) -> str | None:
    return next((cid for cid, rx in c.channels if rx.search(text)), None)


def _auto_counterparty(c: _Compiled, text: str) -> str | None:
    out = text
    for rx in c.strip:
        out = rx.sub(" ", out)
    out = re.sub(r"[^A-Za-z0-9&.' -]+", " ", out)
    out = re.sub(r"\s+", " ", out).strip(" -.")
    return out.upper() or None


def _counterparty(c: _Compiled, rule: TxnRule, rx: re.Pattern | None, text: str) -> str | None:
    if rule.counterparty == "none":
        return None
    if rx is not None:
        m = rx.search(text)
        return re.sub(r"\s+", " ", m[1]).strip(" -.").upper() or None if m else None
    return _auto_counterparty(c, text)


def _key(c: _Compiled, name: str | None) -> str | None:
    if not name:
        return None
    words = _tokens(name, c.noise)
    return " ".join(words) or None


def _lookup_hit(rule: TxnRule, t: Txn, ctx: Context, c: _Compiled, tokens: set[str]) -> bool:
    if rule.lookup == "own_account_number":
        digits = {d[-4:] for d in re.findall(r"\d{4,}", t.narration)}
        return bool(digits & (ctx.own_account_last4 - ({t.account_last4} if t.account_last4 else set())))
    if rule.lookup == "borrower_name":
        return _contains_name(tokens, ctx.borrower_name, c.noise) if ctx.borrower_name else False
    names = ctx.lender_names if rule.lookup == "lender_name" else ctx.director_names
    return any(_contains_name(tokens, n, c.noise) for n in names)


def _classify_one(c: _Compiled, t: Txn, ctx: Context) -> Label:
    direction = "credit" if t.credit and not t.debit else "debit"
    text = t.narration or ""
    tokens = set(normalise_name(text).split())
    hits: list[tuple[TxnRule, str | None]] = []
    for rule, any_rx, none_rx, cp_rx in c.rules:
        if rule.direction != direction:
            continue
        if any_rx and not any(rx.search(text) for rx in any_rx):
            continue
        if any(rx.search(text) for rx in none_rx):
            continue
        if rule.lookup and not _lookup_hit(rule, t, ctx, c, tokens):
            continue
        hits.append((rule, _counterparty(c, rule, cp_rx, text)))
    channel = _channel(c, text)
    fallback = "other_credit" if direction == "credit" else "other_debit"
    if not hits:
        cp = _auto_counterparty(c, text)
        return Label(t.id, fallback, "unmatched", None, 0.0, channel, cp, _key(c, cp), needs_model=True)
    best_tier = min(r.tier for r, _ in hits)
    top = [(r, cp) for r, cp in hits if r.tier == best_tier]
    categories = list(dict.fromkeys(r.category for r, _ in top))
    if len(categories) > 1:
        cp = _auto_counterparty(c, text)
        return Label(t.id, fallback, "ambiguous", None, 0.0, channel, cp, _key(c, cp), candidates=categories,
                     needs_model=True)
    rule, cp = max(top, key=lambda h: h[0].confidence)
    cp = cp or next((p for _, p in top if p), None)
    return Label(t.id, rule.category, "matched", rule.id, rule.confidence, channel, cp, _key(c, cp),
                 needs_model=rule.confidence < c.cfg.model_threshold)


def _flag_round(c: _Compiled, t: Txn, label: Label) -> None:
    amount = t.credit or t.debit
    m = c.cfg.round_amount_multiple
    if amount >= m and round(amount) % m == 0:
        label.flags.append("round_amount")


def _month(t: Txn) -> tuple[int, int] | None:
    return (t.date.year, t.date.month) if t.date else None


def _recurring(c: _Compiled, txns: list[Txn], labels: dict[str, Label], ctx: Context) -> None:
    """A debit to the same party in enough months, at about the same amount, is recurring (F-18.4). When the
    party reads as a lender and nothing more specific was said, it is a loan instalment."""
    groups: dict[str, list[Txn]] = defaultdict(list)
    for t in txns:
        lab = labels[t.id]
        if t.debit and lab.counterparty_key:
            groups[lab.counterparty_key].append(t)
    for key, rows in groups.items():
        by_month: dict[tuple[int, int], float] = {}
        for t in rows:
            if (ym := _month(t)) and ym not in by_month:
                by_month[ym] = t.debit
        if len(by_month) < ctx.emi_min_months:
            continue
        amounts = sorted(by_month.values())
        median = amounts[len(amounts) // 2]
        steady = [t for t in rows if median and abs(t.debit - median) / median * 100 <= ctx.emi_tolerance_pct]
        if len({_month(t) for t in steady}) < ctx.emi_min_months:
            continue
        lender_like = bool(set(key.split()) & c.lender_cues)
        for t in steady:
            lab = labels[t.id]
            lab.flags.append("recurring")
            if lender_like and lab.category in ("other_debit", "supplier_payment") and (lab.status != "matched" or lab.confidence < 0.8):
                lab.category, lab.status, lab.rule_id, lab.confidence, lab.needs_model = "loan_emi", "matched", "recurring_lender_debit", 0.8, False
                lab.candidates = []


def _pair(c: _Compiled, txns: list[Txn], labels: dict[str, Label]) -> None:
    """Equal amounts out of one account and into another within a few days, with nothing more said of either."""
    generic = {"other_debit", "other_credit"}
    outs = [t for t in txns if t.debit and t.date and labels[t.id].category in generic]
    ins = [t for t in txns if t.credit and t.date and labels[t.id].category in generic]
    used: set[str] = set()
    for o in outs:
        for i in ins:
            if i.id in used or i.account == o.account or abs(i.credit - o.debit) > 0.005:
                continue
            if abs((i.date - o.date).days) > c.cfg.pairing.days:
                continue
            for a, b, cat in ((o, i, "own_transfer_out"), (i, o, "own_transfer_in")):
                lab = labels[a.id]
                lab.category, lab.status, lab.rule_id, lab.confidence = cat, "matched", "paired_transfer", 0.75
                lab.needs_model, lab.paired_with, lab.candidates = False, b.id, []
            used.add(i.id)
            break


def classify(cfg: TxnClassificationSection, txns: list[Txn], ctx: Context | None = None) -> list[Label]:
    """Label every transaction, in the order given."""
    ctx = ctx or Context()
    c = _Compiled(cfg)
    labels = {t.id: _classify_one(c, t, ctx) for t in txns}
    for t in txns:
        _flag_round(c, t, labels[t.id])
    _recurring(c, txns, labels, ctx)
    _pair(c, txns, labels)
    return [labels[t.id] for t in txns]
