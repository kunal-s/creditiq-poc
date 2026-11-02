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
from .forensics import Forensics, examine
from .meta import FileMeta, read_meta

__all__ = ["file_checks"]

#: Producers that append a revision as a matter of course. Their presence makes
#: an incremental update unremarkable, so the finding says so rather than
#: leaving a reader to read significance into routine behaviour.
_APPENDING_PRODUCERS = ("acrobat", "pdftk", "itext", "hanko", "sign", "foxit")


def _result(cfg: dict, code: str, status: str, finding: str,
            evidence: list[IntegrityEvidence] | None = None,
            skipped_for_type: str | None = None) -> IntegrityFinding:
    """One check's result, with its definition read from configuration."""
    spec = cfg["checks"][code]
    return IntegrityFinding(
        code=code, family=spec["family"], status=status, finding=finding,
        evidence=evidence or [], tier=spec["tier"], impact=spec["impact"],
        context=bool(spec.get("context", False)),
        method={"engine": "parser", "library": spec.get("library", ""),
                "rule": spec.get("rule", ""), "policy_version": cfg["version"]},
        skipped_for_type=skipped_for_type)


def _ev(observed: str, threshold: str, page: int = 1) -> list[IntegrityEvidence]:
    return [IntegrityEvidence(page=page, rect=None, observed=observed, threshold=threshold)]


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
    if routine or reprint:
        how = f"{meta.producer} does that as a matter of course" if routine else f"the file was printed again by {reprint}"
        return _result(cfg, code, "pass",
                       f"The file holds {f.revision_count} revisions: {how}.", _ev(measured, limit))
    return _result(cfg, code, "warning",
                   f"The file holds {f.revision_count} revisions: it was saved again after it was first written, "
                   f"and nothing in the file accounts for it.",
                   _ev(f"{measured}, {f.unexplained_revisions} unaccounted for", limit))


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
                                      threshold="an earlier definition printing a different figure")
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
    return _result(cfg, code, "warning",
                   f"A later revision replaced {many} object{'s' if many > 1 else ''} the pages draw "
                   f"— their content, a font, an image or an annotation.",
                   _ev(f"objects {', '.join(str(n) for n in f.content_revised[:8])}"
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
    if not said:
        return _result(cfg, code, "pass", "The file's two records of itself agree.",
                       _ev("producer, creating program and both dates agree", f"within {int(_slack().total_seconds() // 60)} minutes"))
    return _result(cfg, code, "warning",
                   "The file's two records of itself disagree — " + "; ".join(said) + ".",
                   _ev("; ".join(said), f"within {int(_slack().total_seconds() // 60)} minutes"))


def _maker_named(cfg: dict, meta: FileMeta) -> IntegrityFinding:
    code = "PDF_MAKER_NAMED"
    named = meta.producer or meta.creator
    if not named:
        return _result(cfg, code, "warning", "The file does not name the program that wrote it.",
                       _ev("no producer and no creator", "the file names its maker"))
    return _result(cfg, code, "pass", f"The file names its maker as {named}.",
                   _ev(f"producer “{meta.producer or 'none'}”, creator “{meta.creator or 'none'}”",
                       "the file names its maker"))


def _named_tools(cfg: dict, meta: FileMeta) -> tuple[str | None, str | None]:
    """The design or editing tool that last wrote the file, and the tool that
    printed or exported it again, if either is named in its own records."""
    tools = cfg.get("editing_tools", {})
    said = " | ".join(n for n in (meta.producer, meta.creator) if n).lower()
    editor = next((t["name"] for t in tools.get("editors", []) if t["match"] in said), None)
    again = next((t["name"] for t in tools.get("re_renderers", []) if t["match"] in said), None)
    return editor, again


def _editing_tool(cfg: dict, meta: FileMeta, editor: str | None, again: str | None) -> IntegrityFinding:
    code = "PDF_WRITTEN_BY_EDITING_TOOL"
    version = cfg.get("editing_tools", {}).get("version", "editing_tools_v1")
    if editor:
        return _result(cfg, code, "warning",
                       f"The file was last written by {editor}, a design or editing tool rather than a "
                       f"system a document of this kind is issued from.",
                       _ev(f"producer “{meta.producer}”, creator “{meta.creator}”", f"not on {version} editors"))
    if again:
        return _result(cfg, code, "pass",
                       f"The file was printed or exported again by {again}. That is not an edit, but the "
                       f"original file's own record is lost.",
                       _ev(f"producer “{meta.producer}”", f"not on {version} editors"))
    return _result(cfg, code, "pass",
                   f"The file names its maker as {meta.producer or meta.creator or 'nothing'}, "
                   f"which is not a design or editing tool.",
                   _ev(f"producer “{meta.producer or 'none'}”", f"not on {version} editors"))


def _producer_expected(cfg: dict, meta: FileMeta, doc_type: str | None) -> IntegrityFinding:
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

def file_checks(data: bytes, cfg: dict[str, Any], doc_type: str | None = None) -> list[IntegrityFinding]:
    """Every use-case-1 check a file answers from its bytes, in configuration order.

    `doc_type` is CreditIQ's own classification where it is already known; the
    two checks that need it say so when it is not.
    """
    meta = read_meta(data)
    if meta.unreadable:
        return [_result(cfg, code, "unable_to_determine", f"The file could not be opened: {meta.unreadable}")
                for code in cfg["checks"] if code != "METADATA_VS_PERIOD"]
    f = examine(data)
    editor, reprint = _named_tools(cfg, meta)

    found = [
        _incremental_update(cfg, f, meta, reprint),
        _prior_value(cfg, f),
        _revisions_touch_content(cfg, f),
        _id_pair(cfg, f),
        _date_order(cfg, meta),
        _info_xmp(cfg, meta),
        _maker_named(cfg, meta),
        _editing_tool(cfg, meta, editor, reprint),
        _producer_expected(cfg, meta, doc_type),
    ]
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
