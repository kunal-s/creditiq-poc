"""Stage 3b: document integrity from what each page draws (FRD F-07A, phase 2).

Runs after the file is read and classified. The pages say which were read from
their own text and which by OCR, and the type says which checks apply, so this
is the first point where both are known. It adds the page checks to what the
bytes already said, answers the one file check that needs the type (the
producing program), and recomputes the recommendation over all of them.

Deterministic; no OCR and no model. It never rejects.
"""

from __future__ import annotations

from ..config.models import IntegrityConfig
from ..integrity import recommend
from ..integrity.arithmetic import ARITHMETIC_CHECKS, arithmetic_checks, not_added_up
from ..integrity.capture import made_as
from ..integrity.checks import apply_skip, named_tools, producer_expected
from ..contracts import IntegrityFacts, IntegrityFinding, IntegrityMadeAs
from ..integrity.pagechecks import PAGE_CHECKS, PageReading, read_pages
from ..integrity.scanchecks import SCAN_CHECKS, scan_reading
from ..integrity.spec import method
from .integrity_file import IntegrityResult

__all__ = ["run_integrity_page"]


def _unable(policy: dict, code: str, e: Exception) -> IntegrityFinding:
    spec = policy["checks"][code]
    return IntegrityFinding(code=code, family=spec["family"], status="unable_to_determine",
                            finding=f"The pages could not be checked: {type(e).__name__}.",
                            tier=spec["tier"], impact=spec["impact"], context=bool(spec.get("context", False)),
                            method=method(spec, policy["version"], failed=True),
                            reads=["pages"])


#: Image uploads the scan checks read (use case 2): a picture is all they are.
IMAGE_KINDS = ("png", "jpg", "tiff", "bmp", "webp")


def _scans(data: bytes, kind: str, pages, policy: dict, ocr, cache) -> tuple[list, dict[int, str], list[str]]:
    """The scan checks (use case 2), never failing the file, with the pages' kinds and captures."""
    try:
        return scan_reading(data, kind, pages or [], policy, ocr, cache)
    except Exception as e:  # noqa: BLE001 - said on each check, never dropped
        return [_unable(policy, code, e) for code in SCAN_CHECKS if code in policy["checks"]], {}, []


def run_integrity_page(data: bytes, kind: str | None, integrity: IntegrityResult, cfg: IntegrityConfig,
                       doc_type: str | None, scanned: set[int], pages=None, ocr=None, cache=None) -> IntegrityResult:
    """The file's integrity result with the page checks added, under its type: what
    pages of text draw (use case 1) and what pictures of pages show (use case 2)."""
    policy = cfg.model_dump(mode="python")
    if kind in IMAGE_KINDS:
        # An image upload: a scan or a photo, judged by its pixels alone.
        scans, kinds, captures = _scans(data, kind, pages, policy, ocr, cache)
        found = apply_skip(scans + not_added_up(policy, NOT_READ), policy, doc_type)
        facts = IntegrityFacts(size_bytes=len(data), made_as=_made_as(kinds, captures, None))
        return IntegrityResult(found, recommend(found, policy), facts, None, [])
    if kind != "pdf" or integrity.meta is None or integrity.meta.unreadable:
        return integrity
    found = [producer_expected(policy, integrity.meta, doc_type)
             if f.code == "METADATA_PRODUCER_EXPECTED" else f for f in integrity.findings]
    pages_read = pages
    try:
        pages = read_pages(data, policy, scanned)
    except Exception as e:  # noqa: BLE001 - the page checks failing must not fail the file
        # Said on each check, never dropped: the file's other checks and its
        # extraction stand, and a reader sees the page checks could not run.
        pages = PageReading([_unable(policy, code, e) for code in PAGE_CHECKS if code in policy["checks"]])
    scans, kinds, captures = _scans(data, "pdf", pages_read, policy, ocr, cache)
    found = apply_skip(found + pages.findings + scans + not_added_up(policy, NOT_READ), policy, doc_type)
    editor, _again = named_tools(policy, integrity.meta)
    facts = integrity.facts.model_copy(update={"made_as": _made_as(kinds, captures, editor)}) \
        if integrity.facts else None
    return IntegrityResult(found, recommend(found, policy), facts, integrity.meta, pages.figures)


#: The arithmetic checks answer here until the figures are read, and keep this
#: answer when they never are (a file whose type is not known is not extracted).
NOT_READ = "Not added up: the file's figures were not read."


def run_integrity_arithmetic(integrity: IntegrityResult, cfg: IntegrityConfig, doc_type: str | None,
                             pages, extracted: list[dict]) -> IntegrityResult:
    """The file's integrity result with its printed figures added up (F-07A, T0),
    once extraction has read them. Never fails the file."""
    policy = cfg.model_dump(mode="python")
    try:
        added = arithmetic_checks(policy, doc_type, pages or [], extracted)
    except Exception as e:  # noqa: BLE001 - said on each check, never dropped
        added = [_unable(policy, code, e) for code in ARITHMETIC_CHECKS if code in policy["checks"]]
    codes = {f.code for f in added}
    found = apply_skip([f for f in integrity.findings if f.code not in codes] + added, policy, doc_type)
    return IntegrityResult(found, recommend(found, policy), integrity.facts, integrity.meta, integrity.figures)


def _made_as(kinds: dict[int, str], captures: list[str], editor: str | None) -> IntegrityMadeAs | None:
    said = made_as(kinds, captures, editor)
    if said is None:
        return None
    pictures = sum(1 for k in kinds.values() if k == "picture") if kinds else len(captures)
    return IntegrityMadeAs(kind=said, text_pages=sum(1 for k in kinds.values() if k == "text"),
                           picture_pages=pictures, writer=editor if said == "design_tool" else None)
