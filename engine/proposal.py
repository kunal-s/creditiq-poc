"""A new application from a pasted message (F-04): rule-based, no model.

1. Normalise: WhatsApp timestamps and sender prefixes, email headers,
   quoted replies and signatures are set aside (kept as provenance in
   `stripped`). They are blanked in a same-length copy of the text, so every
   span found afterwards is an offset into the message as pasted.
2. Extract, every value with its span (F-04.3; a value without a span is
   never proposed): identifiers (validated, never corrected, F-04.4),
   amounts in Indian units, facilities by alias, constitution cues, the
   borrower's name, promoters, declared turnover, existing banking, contact.
3. Duplicate-case check on PAN, GSTIN and normalised name (F-04.5), and the
   configured minimum fields still missing (F-04.6).

Nothing is stored (F-04.7).
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from . import identifiers
from .cases import find_duplicates
from .config import load_app_config
from .contracts import CaseProposal, ProposedCandidate, ProposedField, Span, StrippedSpan
from .names import normalise_name, similarity
from .parties import name_tolerance
from .util import format_inr

# --- Normalisation ---

_WA = re.compile(
    r"^[ \t]*\[?(?P<ts>\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4},?[ \t]+\d{1,2}[:.]\d{2}(?:[:.]\d{2})?"
    r"(?:[ \t]?[APap]\.?[ \t]?[Mm]\.?)?)\]?[ \t]*(?:[-–][ \t]*)?(?P<sender>[^:\n]{1,40}?):[ \t]"
)
_HEADER = re.compile(r"^[ \t]*(?:from|to|cc|bcc|sent|date|reply-to)[ \t]*:", re.I)
_SUBJECT = re.compile(r"^[ \t]*subject[ \t]*:[ \t]*(?:(?:re|fw|fwd)[ \t]*:[ \t]*)*", re.I)
_QUOTE_START = re.compile(r"^[ \t]*(?:on\s.{3,200}\bwrote:[ \t]*$|-{2,}[ \t]*original message[ \t]*-{2,})", re.I)
_FORWARD = re.compile(r"^[ \t]*-{3,}[ \t]*forwarded message[ \t]*-{3,}[ \t]*$", re.I)
_SIGNATURE = re.compile(
    r"^[ \t]*(?:--[ \t]*|(?:thanks|thank you|regards|best regards|kind regards|warm regards|"
    r"thanks[ \t]*(?:&|and)[ \t]*regards|cheers)[,.!]?[ \t]*|sent from my .*)$",
    re.I,
)


@dataclass
class Normalised:
    text: str
    masked: str
    stripped: list[StrippedSpan]


def normalise(text: str) -> Normalised:
    chars = list(text)
    stripped: list[tuple[str, int, int]] = []

    def mask(kind: str, start: int, end: int) -> None:
        if end <= start:
            return
        for i in range(start, end):
            if chars[i] != "\n":
                chars[i] = " "
        if stripped and stripped[-1][0] == kind and text[stripped[-1][2]:start].strip() == "":
            stripped[-1] = (kind, stripped[-1][1], end)
        else:
            stripped.append((kind, start, end))

    mode: str | None = None
    for m in re.finditer(r"[^\n]*\n?", text):
        if not m.group(0):
            continue
        start = m.start()
        line = m.group(0).rstrip("\n")
        end = start + len(line)
        wa = _WA.match(line)
        if wa:
            mode = None
            mask("timestamp", start + wa.start("ts"), start + wa.end("ts"))
            mask("sender", start + wa.start("sender"), start + wa.end())
            # The bracket and dash around the timestamp are provenance too.
            for i in range(start, start + wa.start("sender")):
                if chars[i] != "\n":
                    chars[i] = " "
            continue
        if _FORWARD.match(line):
            mode = None
            mask("header", start, end)
            continue
        if mode is not None:
            mask(mode, start, end)
            continue
        if _QUOTE_START.match(line):
            mode = "quoted"
            mask("quoted", start, end)
        elif line.lstrip().startswith(">"):
            mask("quoted", start, end)
        elif _HEADER.match(line):
            mask("header", start, end)
        elif (sm := _SUBJECT.match(line)) is not None:
            mask("header", start, start + sm.end())
        elif line.strip() and _SIGNATURE.match(line):
            mode = "signature"
            mask("signature", start, end)
    return Normalised(
        text=text,
        masked="".join(chars),
        stripped=[StrippedSpan(kind=k, span=Span(start=s, end=e)) for k, s, e in stripped],
    )


# --- Hits ---


@dataclass
class Hit:
    value: str
    start: int
    end: int
    note: str | None = None
    status: str = "found"
    kind: str = ""
    extra: dict = field(default_factory=dict)

    def span(self) -> Span:
        return Span(start=self.start, end=self.end)

    def candidate(self, value: str | None = None) -> ProposedCandidate:
        return ProposedCandidate(value=value if value is not None else self.value, span=self.span())


def _not_found() -> ProposedField:
    return ProposedField(value=None, status="not_found")


def _found(hit: Hit, value: str | None = None, note: str | None = None) -> ProposedField:
    return ProposedField(
        value=value if value is not None else hit.value, status=hit.status if hit.status == "invalid" else "found",
        span=hit.span(), note=note if note is not None else hit.note,
    )


def _dedupe_overlaps(hits: list[Hit]) -> list[Hit]:
    """Keep the longest of overlapping hits."""
    kept: list[Hit] = []
    for h in sorted(hits, key=lambda h: (-(h.end - h.start), h.start)):
        if all(h.end <= k.start or h.start >= k.end for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda h: h.start)


def _words(words: list[str], *, case_sensitive: bool = False) -> re.Pattern:
    alts = "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))
    return re.compile(rf"(?<![A-Za-z0-9])(?:{alts})(?![A-Za-z0-9])", 0 if case_sensitive else re.I)


# --- Identifiers (F-04.4: flagged, never corrected) ---

_LABELLED = {
    "pan": r"\bPAN\b(?:[ \t]*(?:no\.?|number|#|card))?[ \t]*[:\-–=]?[ \t]*((?=[A-Za-z0-9]*\d)[A-Za-z0-9]{6,14})(?![A-Za-z0-9])",
    "gstin": r"\bGST(?:IN)?(?:[ \t]*(?:no\.?|number|#|reg(?:istration)?(?:[ \t]*no\.?)?))?[ \t]*[:\-–=]?[ \t]*"
    r"((?=[A-Za-z0-9]*\d)[A-Za-z0-9]{12,18})(?![A-Za-z0-9])",
    "cin": r"\bCIN\b(?:[ \t]*(?:no\.?|number))?[ \t]*[:\-–=]?[ \t]*((?=[A-Za-z0-9]*\d)[A-Za-z0-9]{15,25})(?![A-Za-z0-9])",
    "udyam": r"\budyam\b(?:[ \t]*(?:reg(?:istration)?\.?))?(?:[ \t]*(?:no\.?|number))?[ \t]*[:\-–=][ \t]*"
    r"((?=[A-Za-z0-9-]*\d)[A-Za-z0-9-]{8,25})(?![A-Za-z0-9])",
}
_BARE = {
    "pan": (r"(?<![A-Za-z0-9])([A-Z]{5}\d{4}[A-Z])(?![A-Za-z0-9])", 0),
    "gstin": (r"(?<![A-Za-z0-9])(\d{2}[A-Z]{5}\d{4}[A-Z][A-Z0-9]{3})(?![A-Za-z0-9])", 0),
    "cin": (r"(?<![A-Za-z0-9])([LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6})(?![A-Za-z0-9])", 0),
    "udyam": (r"(?<![A-Za-z0-9])(UDYAM[- \t]?[A-Za-z]{2}[- \t]?\d{2}[- \t]?\d{5,9})(?![A-Za-z0-9])", re.I),
}


def _validate_identifier(kind: str, value: str) -> tuple[bool, str | None]:
    if kind == "pan":
        if not re.fullmatch(r"[A-Z]{5}\d{4}[A-Z]", value):
            return False, "Not a valid PAN format (five letters, four digits, one letter); not corrected."
        if not identifiers.validate_pan_format(value):
            return False, f"The fourth character {value[3]!r} is not a valid PAN holder type; not corrected."
        return True, None
    if kind == "gstin":
        if identifiers.validate_gstin(value):
            return True, None
        if re.fullmatch(r"[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]", value):
            return False, "The GSTIN check character does not match; not corrected."
        return False, "Not a valid GSTIN format; not corrected."
    if kind == "cin":
        return (True, None) if identifiers.validate_cin(value) else (False, "Not a valid CIN format; not corrected.")
    if kind == "udyam":
        if identifiers.validate_udyam(value):
            return True, None
        return False, "Not a valid Udyam number (UDYAM-XX-00-0000000); not corrected."
    return False, None


def _identifier_hits(masked: str, kind: str) -> list[Hit]:
    hits: list[Hit] = []
    for m in re.finditer(_LABELLED[kind], masked, re.I):
        hits.append(Hit(m.group(1).upper(), m.start(1), m.end(1), kind=kind))
    pattern, flags = _BARE[kind]
    for m in re.finditer(pattern, masked, flags):
        hits.append(Hit(m.group(1).upper(), m.start(1), m.end(1), kind=kind))
    hits = _dedupe_overlaps(hits)
    for h in hits:
        ok, note = _validate_identifier(kind, h.value)
        h.status = "found" if ok else "invalid"
        h.note = note
    return hits


def _identifier_field(hits: list[Hit], label: str) -> ProposedField:
    if not hits:
        return _not_found()
    distinct: dict[str, Hit] = {}
    for h in hits:
        distinct.setdefault(h.value, h)
    if len(distinct) == 1:
        return _found(hits[0])
    return ProposedField(
        value=None,
        status="unclear",
        candidates=[h.candidate() for h in distinct.values()],
        note=f"The message has more than one {label}.",
    )


def _pan_field(hits: list[Hit]) -> tuple[ProposedField, Hit | None]:
    """The entity's PAN. Individual PANs (fourth character P) are promoters'
    unless nothing else is given (a proprietor's own PAN)."""
    entity = [h for h in hits if not (h.status == "found" and h.value[3] == "P")]
    personal = [h for h in hits if h.status == "found" and h.value[3] == "P"]
    chosen = entity or personal
    field_ = _identifier_field(chosen, "PAN")
    if field_.status in ("found", "invalid") and not entity and personal:
        field_.note = "An individual's PAN: the borrower's own PAN only if it is a proprietorship."
    single = chosen[0] if field_.status in ("found", "invalid") else None
    return field_, single


# --- Amounts ---

_NUM = r"(?:\d{1,3}(?:,\d{2})+,\d{3}|\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_UNIT = r"(?:lakhs|lakh|lacs|lac|lkh|lk|crores|crore|crs|cr|mn|million|l|k)"
_AMOUNT = re.compile(
    rf"(?<![\w.,/])(?:(?P<cur>₹|rs\.?|inr)[ \t]?)?(?P<n1>{_NUM})[ \t]?(?P<u1>{_UNIT})?(?![a-z0-9])\.?"
    rf"(?:[ \t]?(?:-|–|to)[ \t]?(?:(?:₹|rs\.?)[ \t]?)?(?P<n2>{_NUM})[ \t]?(?P<u2>{_UNIT})?(?![a-z0-9]))?",
    re.I,
)
_MULT = {"l": 1e5, "lk": 1e5, "lkh": 1e5, "lac": 1e5, "lacs": 1e5, "lakh": 1e5, "lakhs": 1e5,
         "cr": 1e7, "crs": 1e7, "crore": 1e7, "crores": 1e7, "k": 1e3, "mn": 1e6, "million": 1e6}


@dataclass
class Amount:
    hit: Hit
    values: list[int]
    """One value, or two for a range."""
    kind: str = ""
    """turnover | facility | request | existing | ''"""
    facility: str | None = None
    approximate: bool = False


def _amounts(masked: str) -> list[Amount]:
    out = []
    for m in _AMOUNT.finditer(masked):
        u1, u2 = (m["u1"] or "").lower(), (m["u2"] or "").lower()
        if m["n2"] is not None and not (u1 or u2 or m["cur"]):
            continue
        n1 = m["n1"]
        if not (u1 or u2 or m["cur"] or ("," in n1 and float(n1.replace(",", "")) >= 10000)):
            continue
        v1 = float(n1.replace(",", "")) * _MULT.get(u1 or (u2 if m["n2"] else ""), 1)
        values = [int(round(v1))]
        end = m.end("u1") if m["u1"] else m.end("n1")
        if m["n2"] is not None:
            v2 = float(m["n2"].replace(",", "")) * _MULT.get(u2 or u1, 1)
            values.append(int(round(v2)))
            end = m.end("u2") if m["u2"] else m.end("n2")
        start = m.start("cur") if m["cur"] else m.start("n1")
        out.append(Amount(Hit(str(values[0]), start, end, kind="amount"), values))
    return out


# --- Lexicon ---


@dataclass
class Lexicon:
    facilities: list[tuple[str, re.Pattern]]
    turnover: list[re.Pattern]
    request: re.Pattern
    existing: re.Pattern
    approximate: re.Pattern
    company_suffixes: list[str]
    firm_suffixes: list[str]
    suffix_re: re.Pattern
    stopwords: set[str]
    honorifics: set[str]
    roles: dict[str, list[str]]

    @classmethod
    def load(cls) -> "Lexicon":
        cfg = load_app_config()
        p = cfg["proposal"]
        facilities = []
        for f in cfg["facilities"]:
            for alias in f.get("aliases", []):
                capitals = alias == alias.upper() and any(c.isalpha() for c in alias)
                facilities.append((f["id"], _words([alias], case_sensitive=capitals)))
        suffixes = p["company_suffixes"] + p["firm_suffixes"]
        suffix_alts = "|".join(re.escape(s) for s in sorted(suffixes, key=len, reverse=True))
        return cls(
            facilities=facilities,
            turnover=[_words(p["turnover_words"]), _words(p["turnover_capitals"], case_sensitive=True)],
            request=_words(p["request_words"]),
            existing=_words(p["existing_words"]),
            approximate=re.compile(
                r"(?:(?<![A-Za-z])(?:" + "|".join(re.escape(w) for w in p["approximate_words"] if w != "~") + r")"
                r"(?![A-Za-z])|~)",
                re.I,
            ),
            company_suffixes=[s.lower() for s in p["company_suffixes"]],
            firm_suffixes=[s.lower() for s in p["firm_suffixes"]],
            suffix_re=re.compile(rf"(?<![A-Za-z])(?:{suffix_alts})(?![A-Za-z])", re.I),
            stopwords={w.lower() for w in p["name_stopwords"]},
            honorifics={w.lower() for w in p["honorifics"]},
            roles=p["role_words"],
        )


def _facility_hits(masked: str, lex: Lexicon) -> list[Hit]:
    hits = [
        Hit(fid, m.start(), m.end(), kind="facility") for fid, pattern in lex.facilities for m in pattern.finditer(masked)
    ]
    return _dedupe_overlaps(hits)


def _line_bounds(masked: str, pos: int) -> tuple[int, int]:
    start = masked.rfind("\n", 0, pos) + 1
    end = masked.find("\n", pos)
    return start, len(masked) if end < 0 else end


def _existing_zones(masked: str, lex: Lexicon) -> list[tuple[int, int]]:
    """Stretches that describe existing banking: from an existing-banking
    word to the next request word, or the end of the sentence or line."""
    zones = []
    for m in lex.existing.finditer(masked):
        _, line_end = _line_bounds(masked, m.start())
        stop = line_end
        req = lex.request.search(masked, m.end(), line_end)
        if req:
            stop = req.start()
        sentence = re.search(r"[.;](?:\s|$)", masked[m.end():stop])
        if sentence:
            stop = m.end() + sentence.start()
        zones.append((m.start(), stop))
    return zones


def _in(zones: list[tuple[int, int]], pos: int) -> bool:
    return any(a <= pos < b for a, b in zones)


def _classify_amounts(masked: str, amounts: list[Amount], facilities: list[Hit], lex: Lexicon,
                      zones: list[tuple[int, int]]) -> None:
    turnover_hits = sorted(
        (m.start(), m.end()) for pattern in lex.turnover for m in pattern.finditer(masked)
    )
    request_hits = [(m.start(), m.end()) for m in lex.request.finditer(masked)]
    prev_end = 0
    for i, a in enumerate(amounts):
        line_start, line_end = _line_bounds(masked, a.hit.start)
        lo = max(line_start, prev_end, a.hit.start - 45)
        next_start = amounts[i + 1].hit.start if i + 1 < len(amounts) else line_end
        hi = min(line_end, a.hit.end + 15, next_start)
        before = masked[lo:a.hit.start]
        a.approximate = bool(lex.approximate.search(before))
        if _in(zones, a.hit.start):
            a.kind = "existing"
            prev_end = a.hit.end
            continue
        # A facility or turnover word before the amount says what it is; a
        # request word ("limit", "need") only says that it is asked for.
        cues: list[tuple[int, str, str | None]] = []
        cues += [(e, "turnover", None) for s, e in turnover_hits if lo <= s and e <= a.hit.start]
        cues += [(f.end, "facility", f.value) for f in facilities if lo <= f.start and f.end <= a.hit.start]
        requests = [(e, "request", None) for s, e in request_hits if lo <= s and e <= a.hit.start]
        if cues or requests:
            _, a.kind, a.facility = max(cues or requests, key=lambda c: c[0])
        else:
            after = [(f.start, "facility", f.value) for f in facilities if a.hit.end <= f.start < hi]
            after += [(s, "turnover", None) for s, e in turnover_hits if a.hit.end <= s < hi]
            if after:
                _, a.kind, a.facility = min(after, key=lambda c: c[0])
            elif i > 0 and re.fullmatch(r"\s*(?:or|/|,)\s*", masked[amounts[i - 1].hit.end:a.hit.start], re.I):
                # "3 cr or 30 cr": the second reading of the same figure.
                a.kind, a.facility = amounts[i - 1].kind, amounts[i - 1].facility
        prev_end = a.hit.end


def _amount_text(a: Amount) -> str:
    return " to ".join(format_inr(v) for v in a.values)


def _figure_field(amounts: list[Amount], label: str) -> ProposedField:
    if not amounts:
        return _not_found()
    distinct: dict[tuple[int, ...], Amount] = {}
    for a in amounts:
        distinct.setdefault(tuple(a.values), a)
    if len(distinct) == 1:
        a = amounts[0]
        if len(a.values) == 2:
            return ProposedField(
                value=None,
                status="unclear",
                candidates=[a.hit.candidate(str(v)) for v in a.values],
                note=f"A range ({_amount_text(a)}); confirm the {label}.",
            )
        return ProposedField(
            value=str(a.values[0]),
            status="found",
            span=a.hit.span(),
            note="Stated as approximate." if a.approximate else None,
        )
    return ProposedField(
        value=None,
        status="unclear",
        candidates=[a.hit.candidate(str(v)) for a in distinct.values() for v in a.values],
        note=f"The message gives more than one figure for the {label}: "
        + ", ".join(_amount_text(a) for a in distinct.values())
        + ".",
    )


def _amount_field(amounts: list[Amount]) -> ProposedField:
    requested = [a for a in amounts if a.kind in ("facility", "request")]
    if not requested:
        loose = [a for a in amounts if a.kind == ""]
        if loose:
            return ProposedField(
                value=None,
                status="unclear",
                candidates=[a.hit.candidate(str(v)) for a in loose for v in a.values],
                note="An amount is given but not what it is for; confirm the amount requested.",
            )
        return _not_found()
    per_facility: dict[str, list[Amount]] = {}
    general = []
    for a in requested:
        if a.kind == "facility" and a.facility:
            per_facility.setdefault(a.facility, []).append(a)
        else:
            general.append(a)
    if len(per_facility) > 1 and all(len(v) == 1 and len(v[0].values) == 1 for v in per_facility.values()):
        parts = [v[0] for v in per_facility.values()]
        total = sum(a.values[0] for a in parts)
        if general and any(g.values == [total] for g in general):
            g = next(g for g in general if g.values == [total])
            return ProposedField(value=str(total), status="found", span=g.hit.span())
        return ProposedField(
            value=str(total),
            status="unclear",
            span=Span(start=min(a.hit.start for a in parts), end=max(a.hit.end for a in parts)),
            candidates=[a.hit.candidate() for a in parts],
            note="Total of the amounts per facility: " + " + ".join(format_inr(a.values[0]) for a in parts)
            + f" = {format_inr(total)}; confirm.",
        )
    return _figure_field(requested, "amount requested")


# --- Names ---

_TOKEN = r"[A-Za-z0-9&][A-Za-z0-9&'.\-]*"


def _is_stop(token: str, lex: Lexicon) -> bool:
    t = token.lower().rstrip(".,")
    return t in lex.stopwords or bool(re.match(r"\d", t))


def _company_hits(masked: str, lex: Lexicon) -> list[Hit]:
    hits: list[Hit] = []
    for m in lex.suffix_re.finditer(masked):
        suffix = m.group(0).lower()
        tokens: list[int] = []
        pos = m.start()
        while len(tokens) < 6:
            tm = re.search(rf"(?:^|(?<=[\s(\[\"']))({_TOKEN})([ \t]+)$", masked[max(0, pos - 80):pos])
            if not tm:
                break
            offset = max(0, pos - 80)
            token = tm.group(1)
            if _is_stop(token, lex) or any(p.search(token) for _, p in lex.facilities):
                break
            tokens.insert(0, offset + tm.start(1))
            pos = offset + tm.start(1)
        if not tokens:
            continue
        start, end = tokens[0], m.end()
        name = masked[start:end].strip()
        if re.search(r"\bbank\b", name, re.I):
            continue
        constitution = None
        if suffix in ("llp",):
            constitution = "llp"
        elif suffix in lex.company_suffixes:
            constitution = "private_limited" if re.search(r"pvt|private|\(p\)", suffix) else "limited"
        hits.append(Hit(name, start, end, kind="company", extra={"constitution": constitution}))
    for m in re.finditer(r"\bM/s\.?[ \t]+", masked, re.I):
        pos = m.end()
        end = pos
        count = 0
        for tm in re.finditer(rf"({_TOKEN})([ \t]*)", masked[pos:]):
            if tm.start() != end - pos:
                break
            token = tm.group(1)
            if count and _is_stop(token, lex) and not lex.suffix_re.fullmatch(token):
                break
            end = pos + tm.start(1) + len(token)
            count += 1
            if count >= 7 or not tm.group(2) or token.endswith(","):
                break
        name = masked[pos:end].rstrip(".,")
        if name:
            hits.append(Hit(name, pos, pos + len(name), kind="company", extra={"constitution": None}))
    label = re.compile(
        r"\b(?:borrower|client|customer|company|firm|entity|applicant)(?:'s)?[ \t]*(?:name)?[ \t]*[:\-–][ \t]*"
        r"(?P<v>[^\n,;()]{3,80})",
        re.I,
    )
    for m in label.finditer(masked):
        value = re.split(r"\s+[-–]\s+|\s{2,}", m["v"])[0].rstrip(" .")
        if value and not re.match(r"\d", value):
            hits.append(Hit(value, m.start("v"), m.start("v") + len(value), kind="company", extra={"constitution": None}))
    return _dedupe_overlaps(hits)


def _core(name: str) -> str:
    return re.sub(r"\b(?:pvt|ltd|llp|private|limited)\b", " ", normalise_name(name)).strip()


def _borrower_field(hits: list[Hit]) -> ProposedField:
    groups: list[list[Hit]] = []
    for h in hits:
        for g in groups:
            a, b = _core(h.value), _core(g[0].value)
            if a and b and (a.startswith(b) or b.startswith(a) or similarity(a, b) >= 0.9):
                g.append(h)
                break
        else:
            groups.append([h])
    if not groups:
        return _not_found()
    best = [max(g, key=lambda h: (len(h.value), -h.start)) for g in groups]
    if len(best) == 1:
        return _found(best[0])
    return ProposedField(
        value=None,
        status="unclear",
        candidates=[h.candidate() for h in best],
        note="The message names more than one business; confirm which is the borrower.",
    )


_PERSON = r"[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){0,3}"


def _promoter_hits(masked: str, lex: Lexicon, companies: list[Hit]) -> list[Hit]:
    hits: list[Hit] = []
    hon = "|".join(re.escape(h) for h in sorted(lex.honorifics, key=len, reverse=True))
    for m in re.finditer(rf"\b(?:{hon})\b\.?[ \t]+(?P<n>{_PERSON})", masked, re.I):
        name = m["n"]
        if name[0].isupper():
            hits.append(Hit(name, m.start("n"), m.end("n"), kind="person"))
    role_words = sorted({w for words in lex.roles.values() for w in words}, key=len, reverse=True)
    roles = "|".join(re.escape(w) for w in role_words)
    for m in re.finditer(
        rf"\b(?:{roles})\b[ \t]*(?:is|are|:|-|–|=|names?(?:[ \t]+(?:is|are))?)[ \t]*(?P<list>[^\n.;]{{3,120}})",
        masked,
        re.I,
    ):
        base = m.start("list")
        for part in re.finditer(r"[^,&/]+", m["list"]):
            for piece in re.split(r"\band\b", part.group(0)):
                offset = part.group(0).find(piece)
                text = piece.strip()
                text = re.sub(rf"^(?:{hon})\b\.?[ \t]*", "", text, flags=re.I)
                if not re.fullmatch(r"[A-Z][a-zA-Z.']+(?:[ \t]+[A-Z][a-zA-Z.']+){0,3}", text):
                    continue
                if all(_is_stop(t, lex) for t in text.split()):
                    continue
                start = base + part.start() + offset + piece.find(text)
                hits.append(Hit(text, start, start + len(text), kind="person"))
    for m in re.finditer(rf"(?P<n>[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){{1,3}})[ \t]*(?:\(|,|-|–)[ \t]*(?:{roles})\b",
                         masked):
        hits.append(Hit(m["n"], m.start("n"), m.end("n"), kind="person"))
    hits = [h for h in hits if not any(c.start <= h.start < c.end for c in companies)]
    hits = [h for h in hits if not all(_is_stop(t, lex) for t in h.value.split())]
    return _dedupe_overlaps(hits)


def _people_field(hits: list[Hit]) -> ProposedField:
    if not hits:
        return _not_found()
    distinct: dict[str, Hit] = {}
    for h in hits:
        key = normalise_name(h.value)
        if not any(similarity(key, k) >= 0.9 for k in distinct):
            distinct[key] = h
    people = list(distinct.values())
    return ProposedField(
        value="; ".join(h.value for h in people),
        status="found",
        span=people[0].span(),
        candidates=[h.candidate() for h in people],
    )


# --- Constitution ---

_CONSTITUTION_WORDS = [
    (r"\bprivate\s+limited\s+company\b|\bpvt\.?\s*ltd\.?\s+company\b", "private_limited"),
    (r"\bLLP\b|\blimited\s+liability\s+partnership\b", "llp"),
    (r"\bpartnership(?:\s+firm)?\b", "partnership"),
    (r"\b(?:sole\s+)?proprietor(?:ship)?\b|\bprop\.?\s+(?:firm|concern)\b", "proprietorship"),
]
_PAN_CONSTITUTION = {"C": "private_limited", "F": "partnership", "P": "proprietorship"}


def _constitution_field(masked: str, companies: list[Hit], pan: Hit | None, borrower: ProposedField) -> ProposedField:
    cues: list[Hit] = []
    chosen = [c for c in companies if borrower.span and c.start == borrower.span.start] or companies
    for c in chosen:
        cons = c.extra.get("constitution")
        if cons in ("private_limited", "llp"):
            cues.append(Hit(cons, c.start, c.end, kind="constitution"))
    for pattern, value in _CONSTITUTION_WORDS:
        for m in re.finditer(pattern, masked, re.I if value != "llp" else 0):
            if not any(h.start <= m.start() < h.end for h in cues):
                cues.append(Hit(value, m.start(), m.end(), kind="constitution"))
    if pan is not None and pan.status == "found" and pan.value[3] in _PAN_CONSTITUTION:
        cues.append(Hit(_PAN_CONSTITUTION[pan.value[3]], pan.start, pan.end, kind="constitution",
                        note="From the PAN's fourth character."))
    if not cues:
        return _not_found()
    distinct: dict[str, Hit] = {}
    for h in sorted(cues, key=lambda h: h.start):
        distinct.setdefault(h.value, h)
    if len(distinct) == 1 and "llp" not in distinct:
        return _found(next(iter(distinct.values())))
    note = "The message suggests more than one constitution; confirm."
    if "llp" in distinct:
        note = "The message calls the borrower an LLP, which is not a constitution on the checklist; confirm."
    return ProposedField(
        value=None,
        status="unclear",
        candidates=[h.candidate("unknown" if v == "llp" else v) for v, h in distinct.items()],
        note=note,
    )


# --- Contact and existing banking ---

_PHONE = re.compile(r"(?<![\d+])(?:\+?91[ \t-]?)?[6-9]\d{4}[ \t-]?\d{5}(?!\d)")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_CONTACT_LABEL = re.compile(
    r"\bcontact(?:[ \t]*(?:person|no\.?|number|details|name))?[ \t]*[:\-–][ \t]*(?P<v>[^\n]{3,80})", re.I
)


def _contact_field(masked: str) -> ProposedField:
    hits = [Hit(m["v"].rstrip(" .,"), m.start("v"), m.start("v") + len(m["v"].rstrip(" .,")), kind="contact")
            for m in _CONTACT_LABEL.finditer(masked)]
    hits += [Hit(m.group(0), m.start(), m.end(), kind="contact") for m in _PHONE.finditer(masked)]
    hits += [Hit(m.group(0), m.start(), m.end(), kind="contact") for m in _EMAIL.finditer(masked)]
    hits = _dedupe_overlaps(hits)
    if not hits:
        return _not_found()
    first = hits[0]
    return ProposedField(
        value=first.value, status="found", span=first.span(),
        candidates=[h.candidate() for h in hits] if len(hits) > 1 else [],
    )


def _existing_field(masked: str, zones: list[tuple[int, int]]) -> ProposedField:
    hits = []
    for a, b in zones:
        text = masked[a:b]
        stripped = text.strip(" \t,.-–")
        if len(stripped) < 4:
            continue
        start = a + text.find(stripped)
        hits.append(Hit(stripped, start, start + len(stripped), kind="existing"))
    hits = _dedupe_overlaps(hits)
    if not hits:
        return _not_found()
    return ProposedField(
        value=hits[0].value, status="found", span=hits[0].span(),
        candidates=[h.candidate() for h in hits] if len(hits) > 1 else [],
    )


# --- The proposal ---


def _facilities_field(hits: list[Hit], zones: list[tuple[int, int]]) -> ProposedField:
    requested = [h for h in hits if not _in(zones, h.start)]
    if not requested:
        return _not_found()
    ids = list(dict.fromkeys(h.value for h in requested))
    firsts = [next(h for h in requested if h.value == fid) for fid in ids]
    return ProposedField(
        value=",".join(ids), status="found", span=firsts[0].span(), candidates=[h.candidate() for h in firsts]
    )


FIELD_ALIASES = {"borrower": "borrower", "facilities": "facilities", "amount_inr": "amount_inr"}


def parse(text: str) -> tuple[dict[str, ProposedField], list[StrippedSpan]]:
    lex = Lexicon.load()
    norm = normalise(text)
    masked = norm.masked
    zones = _existing_zones(masked, lex)
    facilities = _facility_hits(masked, lex)
    amounts = _amounts(masked)
    # An amount inside an identifier or phone number is not an amount.
    ids = {kind: _identifier_hits(masked, kind) for kind in ("pan", "gstin", "cin", "udyam")}
    blocked = [(h.start, h.end) for hits in ids.values() for h in hits]
    blocked += [(m.start(), m.end()) for m in _PHONE.finditer(masked)]
    amounts = [a for a in amounts if not any(s <= a.hit.start < e for s, e in blocked)]
    _classify_amounts(masked, amounts, facilities, lex, zones)

    companies = _company_hits(masked, lex)
    borrower = _borrower_field(companies)
    pan_field, pan_hit = _pan_field(ids["pan"])
    fields = {
        "borrower": borrower,
        "constitution": _constitution_field(masked, companies, pan_hit, borrower),
        "facilities": _facilities_field(facilities, zones),
        "amount_inr": _amount_field(amounts),
        "pan": pan_field,
        "gstin": _identifier_field(ids["gstin"], "GSTIN"),
        "cin": _identifier_field(ids["cin"], "CIN"),
        "udyam": _identifier_field(ids["udyam"], "Udyam number"),
        "promoters": _people_field(_promoter_hits(masked, lex, companies)),
        "declared_turnover_inr": _figure_field([a for a in amounts if a.kind == "turnover"], "turnover"),
        "existing_banking": _existing_field(masked, zones),
        "contact": _contact_field(masked),
    }
    return fields, norm.stripped


def propose(conn: sqlite3.Connection, root: Path, text: str) -> CaseProposal:
    fields, stripped = parse(text)
    threshold = name_tolerance(root)
    names = []
    if fields["borrower"].value:
        names.append(fields["borrower"].value)
    names += [c.value for c in fields["borrower"].candidates]
    seen: dict[str, object] = {}
    pan = fields["pan"].value if fields["pan"].status == "found" else None
    gstin = fields["gstin"].value if fields["gstin"].status == "found" else None
    for name in names or [None]:
        for dup in find_duplicates(conn, pan=pan, gstin=gstin, borrower=name, name_threshold=threshold):
            seen.setdefault(dup.id, dup)
    minimum = load_app_config()["case_create_minimum"]
    missing = [
        name for name in minimum
        if name not in fields or fields[name].value is None or fields[name].status in ("not_found", "invalid")
    ]
    return CaseProposal(
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        fields=fields,
        duplicates=list(seen.values()),
        missing_minimum=missing,
        stripped=stripped,
    )
