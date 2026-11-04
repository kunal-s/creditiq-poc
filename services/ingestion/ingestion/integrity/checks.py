"""The use-case-1 checks a file can answer from its bytes alone.

Ten checks, each deterministic code plus a threshold from
`config/ingestion/integrity.yaml`. They run before the file is read, before it
is classified and long before a field is extracted, so an obviously re-saved
file is flagged before any page is rendered or read optically.

Every finding says what was measured, what it was compared with and the limit
it crossed. None of them is a verdict: a document system of the bank's own
saves a file again, a portal writes to it on download, and a producer string is
trivially edited. They are reasons for a person to look.

Ported from RBL/fault_detection (PROVENANCE.md): `pdfforensics.py` and
`metadata_analysis.py`, in the shape of `ingestion.contracts.IntegrityFinding`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from ..contracts import IntegrityEvidence, IntegrityFinding
from .forensics import DRAWN, Forensics, examine
from .meta import FileMeta, read_meta
from .pagechecks import PAGE_CHECKS
from .signatures import signature_checks
from .spec import method

__all__ = ["file_checks", "producer_expected", "apply_skip", "named_tools"]

#: Producers that append a revision as a matter of course. Their presence makes
#: an incremental update unremarkable, so the finding says so rather than
#: leaving a reader to read significance into routine behaviour.
_APPENDING_PRODUCERS = ("acrobat", "pdftk", "itext", "hanko", "sign", "foxit")


#: Which of the file's facts (IntegrityFacts) each check reads. It is a property of
#: the code below, not a setting, so it lives beside it: a reader is shown exactly
#: the records an answer came from.
READS: dict[str, list[str]] = {
    "PDF_INCREMENTAL_UPDATE": ["revisions", "signatures", "info.Producer"],
    "PDF_PRIOR_VALUE_RECOVERABLE": ["revisions", "recovered"],
    "REVISIONS_TOUCH_CONTENT": ["revisions", "signatures"],
    "PDF_ID_PAIR_DIFFERS": ["id"],
    "METADATA_DATE_ORDER": ["info.CreationDate", "info.ModDate", "xmp.create_date", "xmp.modify_date"],
    "METADATA_INFO_XMP": ["info.Producer", "xmp.producer", "info.Creator", "xmp.creator_tool",
                          "info.CreationDate", "xmp.create_date", "info.ModDate", "xmp.modify_date"],
    "PDF_MAKER_NAMED": ["info.Producer", "info.Creator"],
    "PDF_WRITTEN_BY_EDITING_TOOL": ["info.Producer", "info.Creator", "revisions"],
    "METADATA_PRODUCER_EXPECTED": ["info.Producer"],
}


def _result(cfg: dict, code: str, status: str, finding: str,
            evidence: list[IntegrityEvidence] | None = None,
            skipped_for_type: str | None = None, failed: bool = False) -> IntegrityFinding:
    """One check's result, with its definition read from configuration."""
    spec = cfg["checks"][code]
    return IntegrityFinding(
        code=code, family=spec["family"], status=status, finding=finding,
        evidence=evidence or [], tier=spec["tier"], impact=spec["impact"],
        context=bool(spec.get("context", False)),
        method=method(spec, cfg["version"], failed=failed),
        skipped_for_type=skipped_for_type, reads=READS.get(code, []))


def _ev(observed: str, threshold: str, page: int = 1) -> list[IntegrityEvidence]:
    return [IntegrityEvidence(page=page, rect=None, observed=observed, threshold=threshold)]


#: The most objects a finding points at. A save that drew more rewrote the page.
MAX_OBJECT_EVIDENCE = 8

_A = {"image": "an image", "form": "a drawing", "font": "a font", "annotation": "an annotation", "page": "a page"}


def _saves(f: Forensics) -> list[IntegrityEvidence]:
    """One line per later save: where it sits in the bytes and what it wrote."""
    return [IntegrityEvidence(page=1, rect=None,
                              observed=f"save {r.index + 1}: bytes {r.start:,} to {r.end:,}, "
                                       f"{r.replaced_count} object{'s' if r.replaced_count != 1 else ''} replaced, "
                                       f"{r.added_count} added",
                              threshold="written by the first save only")
            for r in f.revisions[1:]]


def _drawn_by_later_saves(f: Forensics) -> list[IntegrityEvidence]:
    """What the later saves put on the pages: each page they replaced, then each
    image, drawing, font or annotation they replaced or added. Each names its
    object, so it can be shown where the page draws it once the pages are read."""
    out: list[IntegrityEvidence] = []
    for r in f.revisions[1:]:
        for verb, objs in (("replaced", r.replaced), ("added", r.added)):
            for o in objs:
                if o.kind in DRAWN and len(out) < MAX_OBJECT_EVIDENCE:
                    out.append(IntegrityEvidence(
                        page=1, rect=None, object=o.number,
                        observed=f"save {r.index + 1} {verb} {_A[o.kind]} (object {o.number})",
                        threshold="a page draws only what the first save wrote"))
    # Pages first: they say which page changed; then what was drawn on it.
    return sorted(out, key=lambda e: "a page" not in e.observed)


# --- history: what the bytes say was done to the file -----------------------

def _incremental_update(cfg: dict, f: Forensics, meta: FileMeta, reprint: str | None) -> IntegrityFinding:
    code = "PDF_INCREMENTAL_UPDATE"
    limit = "no revision beyond the ones signing and re-printing account for"
    measured = (f"{f.revision_count} revision{'s' if f.revision_count != 1 else ''}, "
                f"{f.signature_count} signature{'s' if f.signature_count != 1 else ''}")
    if f.revision_count <= 1:
        return _result(cfg, code, "pass", "The file holds one revision: it has not been saved again since it was written.",
                       _ev(measured, limit))
    # Applying a signature appends a revision — that is how a PDF is signed
    # without disturbing the bytes already signed. Counting it would call every
    # properly signed document into question.
    if f.unexplained_revisions == 0:
        return _result(cfg, code, "pass",
                       f"The file holds {f.revision_count} revisions, which its "
                       f"{f.signature_count} signature{'s' if f.signature_count != 1 else ''} account for.",
                       _ev(measured, limit))
    # A producer that appends as a matter of course, or that printed the file
    # again, explains the revision as well: listed, never counted as a signal.
    routine = next((p for p in _APPENDING_PRODUCERS if p in meta.producer.lower()), None)
    # A printer writes a whole file in one save and never appends. Where the
    # later save left the pages alone (a viewer stamping its own record), the
    # printer still explains the file; where it changed what a page draws,
    # something other than the printer wrote it, and the printer's name explains
    # nothing about that save.
    if reprint and f.content_revised:
        return _result(cfg, code, "warning",
                       f"The file holds {f.revision_count} revisions. It names {reprint} as its maker, which "
                       f"writes a file in one save; a later save by a program that does not name itself "
                       f"changed what the pages draw.",
                       [*_ev(f"{measured}, {f.unexplained_revisions} unaccounted for", limit), *_saves(f)])
    if routine or reprint:
        how = f"{meta.producer} does that as a matter of course" if routine else f"the file was printed again by {reprint}"
        return _result(cfg, code, "pass",
                       f"The file holds {f.revision_count} revisions: {how}.", _ev(measured, limit))
    return _result(cfg, code, "warning",
                   f"The file holds {f.revision_count} revisions: it was saved again after it was first written, "
                   f"and nothing in the file accounts for it.",
                   [*_ev(f"{measured}, {f.unexplained_revisions} unaccounted for", limit), *_saves(f)])


def _prior_value(cfg: dict, f: Forensics) -> IntegrityFinding:
    code = "PDF_PRIOR_VALUE_RECOVERABLE"
    if f.revision_count <= 1:
        return _result(cfg, code, "not_applicable",
                       "The file holds one revision, so it keeps no earlier version of any figure.")
    if not f.recovered:
        return _result(cfg, code, "pass",
                       "No earlier figure differing from the current one is left in the file.",
                       _ev(f"{len(f.superseded_objects)} objects redefined, none printing a different figure",
                           "an earlier definition printing a different figure"))
    first = f.recovered[0]
    rest = f" and {len(f.recovered) - 1} more" if len(f.recovered) > 1 else ""
    return _result(cfg, code, "review_required",
                   f"An earlier version of this file printed “{first.was}” where it now prints "
                   f"“{first.now}”{rest}. Both values are still in the bytes.",
                   [IntegrityEvidence(page=1, rect=None,
                                      observed=f"object {r.object_number}: “{r.was}” became “{r.now}”",
                                      threshold="an earlier definition printing a different figure",
                                      locate=r.now)
                    for r in f.recovered[:10]])


def _revisions_touch_content(cfg: dict, f: Forensics) -> IntegrityFinding:
    code = "REVISIONS_TOUCH_CONTENT"
    if f.revision_count <= 1:
        return _result(cfg, code, "not_applicable", "The file holds one revision, so none replaced anything.")
    if not f.content_revised:
        return _result(cfg, code, "pass",
                       "The later revisions left the pages' content alone.",
                       _ev(f"{len(f.superseded_objects)} objects redefined, none of them page content",
                           "a replaced object a page draws"))
    many = len(f.content_revised)
    # Signing appends a revision that replaces the page's annotations, to carry
    # the signature widget. Where every revision is a signature's, so is this.
    if f.unexplained_revisions == 0:
        return _result(cfg, code, "pass",
                       f"A later revision replaced {many} object{'s' if many > 1 else ''} the pages draw, "
                       f"which the file's {f.signature_count} signature"
                       f"{'s' if f.signature_count != 1 else ''} account for.",
                       _ev(f"{many} replaced, {f.revision_count} revisions, {f.signature_count} signatures",
                           "a replaced object a page draws, beyond what signing accounts for"))
    drawn = _drawn_by_later_saves(f)
    return _result(cfg, code, "warning",
                   f"A later revision replaced {many} object{'s' if many > 1 else ''} the pages draw "
                   f"— their content, a font, an image or an annotation.",
                   drawn or _ev(f"objects {', '.join(str(n) for n in f.content_revised[:8])}"
                                f"{' and more' if many > 8 else ''}", "a replaced object a page draws"))


def _id_pair(cfg: dict, f: Forensics) -> IntegrityFinding:
    code = "PDF_ID_PAIR_DIFFERS"
    if f.id_changed is None:
        return _result(cfg, code, "unable_to_determine", "The file carries no identifier pair to compare.")
    if not f.id_changed:
        return _result(cfg, code, "pass", "The file's two identifiers match: it has not been saved since it was made.",
                       _ev("both halves equal", "the two halves of /ID are equal"))
    return _result(cfg, code, "warning",
                   "The file's two identifiers differ: it has been saved at least once since it was made.",
                   _ev(f"{f.id_original} became {f.id_current}", "the two halves of /ID are equal"))


# --- metadata: what the file says about itself ------------------------------

def _date_order(cfg: dict, meta: FileMeta) -> IntegrityFinding:
    code = "METADATA_DATE_ORDER"
    made, changed = meta.created_at(), meta.modified_at()
    if made is None or changed is None:
        missing = "created date" if made is None else "modified date"
        return _result(cfg, code, "unable_to_determine", f"The file states no {missing}, so the order cannot be checked.")
    if changed >= made:
        return _result(cfg, code, "pass", "The file was modified after it was created, as it must be.",
                       _ev(f"created {made.isoformat()}, modified {changed.isoformat()}", "modified is not before created"))
    gap = made - changed
    return _result(cfg, code, "warning",
                   f"The file states it was modified {_span(gap)} before it was created.",
                   _ev(f"created {made.isoformat()}, modified {changed.isoformat()}", "modified is not before created"))


def _info_xmp(cfg: dict, meta: FileMeta) -> IntegrityFinding:
    code = "METADATA_INFO_XMP"
    if not meta.has_xmp:
        return _result(cfg, code, "not_applicable", "The file carries no XMP packet, so there is no second record to compare.")
    if not meta.info:
        return _result(cfg, code, "not_applicable", "The file carries no information dictionary to compare with its XMP.")
    said = meta.disagreements()
    within = f"within {int(_slack().total_seconds() // 60)} minutes"
    if not said:
        return _result(cfg, code, "pass", "The file's two records of itself agree.",
                       _ev("producer, creating program and both dates agree", within))
    if meta.xmp_is_template() and all(s.startswith("the created date") for s in said):
        # Listed, not counted: only the created date differs, and the XMP is a
        # template's record that the program filling it in left untouched.
        hit = _result(cfg, code, "warning",
                      "The file's XMP record is older than the file and names no program or change of its own: "
                      "a template's record, left as it was when the file was filled in — " + "; ".join(said) + ".",
                      _ev("; ".join(said), within))
        return hit.model_copy(update={"context": True})
    return _result(cfg, code, "warning",
                   "The file's two records of itself disagree — " + "; ".join(said) + ".",
                   _ev("; ".join(said), within))


def _maker_named(cfg: dict, meta: FileMeta) -> IntegrityFinding:
    code = "PDF_MAKER_NAMED"
    named = meta.producer or meta.creator
    if not named:
        return _result(cfg, code, "warning", "The file does not name the program that wrote it.",
                       _ev("no producer and no creator", "the file names its maker"))
    return _result(cfg, code, "pass", f"The file names its maker as {named}.",
                   _ev(f"producer “{meta.producer or 'none'}”, creator “{meta.creator or 'none'}”",
                       "the file names its maker"))


def named_tools(cfg: dict, meta: FileMeta) -> tuple[str | None, str | None]:
    """The design or editing tool that last wrote the file, and the tool that
    printed or exported it again, if either is named in its own records."""
    tools = cfg.get("editing_tools", {})
    said = " | ".join(n for n in (meta.producer, meta.creator) if n).lower()
    editor = next((t["name"] for t in tools.get("editors", []) if t["match"] in said), None)
    again = next((t["name"] for t in tools.get("re_renderers", []) if t["match"] in said), None)
    return editor, again


def _editing_tool(cfg: dict, meta: FileMeta, editor: str | None, again: str | None,
                  f: Forensics) -> IntegrityFinding:
    code = "PDF_WRITTEN_BY_EDITING_TOOL"
    version = cfg.get("editing_tools", {}).get("version", "editing_tools_v1")
    if editor:
        return _result(cfg, code, "warning",
                       f"The file was last written by {editor}, a design or editing tool rather than a "
                       f"system a document of this kind is issued from.",
                       _ev(f"producer “{meta.producer}”, creator “{meta.creator}”", f"not on {version} editors"))
    if again and f.content_revised and f.unexplained_revisions:
        return _result(cfg, code, "pass",
                       f"The file names {again} as the program that printed it. Printing is not an edit, "
                       f"but the file was saved again afterwards by a program that does not name itself.",
                       _ev(f"producer “{meta.producer}”", f"not on {version} editors"))
    if again:
        return _result(cfg, code, "pass",
                       f"The file was printed or exported again by {again}. That is not an edit, but the "
                       f"original file's own record is lost.",
                       _ev(f"producer “{meta.producer}”", f"not on {version} editors"))
    return _result(cfg, code, "pass",
                   f"The file names its maker as {meta.producer or meta.creator or 'nothing'}, "
                   f"which is not a design or editing tool.",
                   _ev(f"producer “{meta.producer or 'none'}”", f"not on {version} editors"))


def producer_expected(cfg: dict, meta: FileMeta, doc_type: str | None) -> IntegrityFinding:
    code = "METADATA_PRODUCER_EXPECTED"
    expected = (cfg.get("expected_producers") or {}).get(doc_type or "")
    if not expected:
        return _result(cfg, code, "not_applicable",
                       "No producing program is recorded for this kind of document.")
    if not meta.producer:
        return _result(cfg, code, "unable_to_determine", "The file does not name the program that wrote it.")
    low = meta.producer.lower()
    if any(e.lower() in low for e in expected):
        return _result(cfg, code, "pass",
                       f"The file was made by {meta.producer}, which is what a document of this kind comes from.",
                       _ev(meta.producer, " or ".join(expected)))
    return _result(cfg, code, "warning",
                   f"The file was made by {meta.producer}; a document of this kind is issued from "
                   f"{' or '.join(expected)}.",
                   _ev(meta.producer, " or ".join(expected)))


def _span(gap: timedelta) -> str:
    minutes = int(gap.total_seconds() // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 48:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours // 24} days"


def _slack() -> timedelta:
    from .meta import DATE_SLACK  # noqa: PLC0415 - one constant, kept beside what it measures

    return DATE_SLACK


# --- the stage's entry point ------------------------------------------------

def file_checks(data: bytes, cfg: dict[str, Any], doc_type: str | None = None,
                meta: FileMeta | None = None, f: Forensics | None = None) -> list[IntegrityFinding]:
    """Every use-case-1 check a file answers from its bytes, in configuration order.

    `doc_type` is CreditIQ's own classification where it is already known; the
    two checks that need it say so when it is not. `meta` and `f` are the file's
    records already read, so the stage reads them once for checks and facts both.
    """
    meta = meta or read_meta(data)
    if meta.unreadable:
        return [_result(cfg, code, "unable_to_determine", f"The file could not be opened: {meta.unreadable}",
                        failed=True)
                for code in cfg["checks"] if code != "METADATA_VS_PERIOD" and code not in PAGE_CHECKS]
    f = f or examine(data)
    editor, reprint = named_tools(cfg, meta)

    found = [
        _incremental_update(cfg, f, meta, reprint),
        _prior_value(cfg, f),
        _revisions_touch_content(cfg, f),
        _id_pair(cfg, f),
        _date_order(cfg, meta),
        _info_xmp(cfg, meta),
        _maker_named(cfg, meta),
        _editing_tool(cfg, meta, editor, reprint, f),
        producer_expected(cfg, meta, doc_type),
        *signature_checks(cfg, data),
    ]
    return apply_skip(found, cfg, doc_type)


def apply_skip(found: list[IntegrityFinding], cfg: dict[str, Any], doc_type: str | None) -> list[IntegrityFinding]:
    """Each check configured not to run for this kind of document, said so with why."""
    skip = (cfg.get("skip_for_type") or {})
    out = []
    for r in found:
        why = (skip.get(r.code) or {}).get(doc_type or "")
        if why:
            out.append(_result(cfg, r.code, "not_applicable", f"Not run for this kind of document: {why}.",
                               skipped_for_type=doc_type))
        else:
            out.append(r)
    return out
