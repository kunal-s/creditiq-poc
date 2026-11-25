"""The six-stage pipeline (quality gate, read and route, classify, extract, validate, score).

Each stage reads only the configuration version pinned on the run, records its output in SQLite
with an input and output hash, and hands a plain value to the next. Nothing here reads the clock."""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field

from . import CONTRACT_VERSION, ENGINE_VERSION
from .config.models import IngestionConfig
from . import fill as fill_stage
from .contracts import CaseType, FileResult, FileSpec, FillRequest, FillResult, IngestRequest, IngestResult
from .llm.calllog import call_context
from .llm.recorder import ModelClient
from .pageindex import Page
from .readers.ocr import OcrEngine
from .stages import identity as identity_stage
from .stages import pages as pages_stage
from .stages import route as route_stage
from .stages.extract.run import extract_case_type, extract_instance
from .integrity.locate import locate as locate_on_pages
from .integrity.locate import place_objects
from .stages.integrity_file import run_integrity_file
from .stages.integrity_page import run_integrity_arithmetic, run_integrity_page
from .stages.quality import run_gate
from .stages.read import document_grade, read_document
from .stages.score import decide, score_field, score_table
from .stages.validate import validate_instance
from .store import Store
from .util import hash_of, sha256_hex

RANK = {"reject": 2, "human_review": 1, "auto_accept": 0}


#: Integrity recommendations that send a document to a person. A single
#: low-impact observation (`needs_review`) is recorded as a reason so a reader
#: sees it, but it does not hold up a document on its own: a bank's own system
#: saves a file again, and a portal writes to it on download.
INTEGRITY_ESCALATES = ("needs_review_priority", "high_risk_indicators")


def _integrity_reason(integrity, reasons: list[dict]) -> str:
    """Record what integrity found, whatever it was, and give back its code.

    Every recommendation with a signal behind it is written down. Nothing the
    stage found is dropped because it was not severe enough to escalate.
    """
    code = integrity.recommendation["code"]
    if code not in ("no_notable_issue", "not_applicable"):
        reasons.append({"kind": "integrity", "code": code, "detail": integrity.recommendation["why"]})
    return code


def _unit_classification(cfg: IngestionConfig, typing, doc_type: str, pages: list[Page]) -> dict:
    """How a document typed page by page was placed: its strongest page's score and words, the ways its pages were
    placed, and the model's tier when the model placed any of them."""
    secs = [x for p in pages for x in typing.pages.get(p.no, []) if doc_type in x.types]
    scored = [x for x in secs if x.placed_by in ("keywords", "all_types")]
    best = max(scored, key=lambda x: x.score) if scored else (secs[0] if secs else None)
    how: dict[str, int] = {}
    for x in secs:
        how[x.placed_by or "?"] = how.get(x.placed_by or "?", 0) + 1
    by_model = how.get("model", 0) > 0
    conf = best.score if best and best.placed_by in ("keywords", "all_types") else cfg.keywords.settings.scoring.model_confidence
    return {"type": doc_type, "confidence": round(conf, 4), "tier": "model" if by_model else "signals",
            "signals": best.signals if best else {}, "needs_review": False,
            # The document's own type first, then the other guesses its strongest page had.
            "candidates": ([{"type": doc_type, "score": round(conf, 4)}]
                           + [{"type": t, "score": sc} for t, sc in (best.candidates if best else []) if t != doc_type])[:3],
            "reason": "pages placed by " + ", ".join(f"{k} ({v})" for k, v in sorted(how.items())), "mixed_content": []}


def _file_classification(cfg: IngestionConfig, typing, runs: list, unplaced: list[list[int]]) -> dict:
    """The file's classification, for what reads one type per file: the type of the first document; none when no page
    was placed."""
    if runs:
        t, run_pages = runs[0]
        return _unit_classification(cfg, typing, t, run_pages)
    secs = [x for v in typing.pages.values() for x in v]
    top = max(secs, key=lambda x: x.score) if secs else None
    asked = [e for e in typing.trace if e["step"] == "model"]
    error = next((e.get("model_error") for e in asked if e.get("model_error")), None)
    if error:
        why, extra = f"no page placed by the keyword lists; model unavailable ({error})", {"model_error": error}
    elif asked:
        why, extra = "the model found none of the listed types: " + "; ".join(sorted({e.get("reason") or "" for e in asked}))[:300], {}
    else:
        why, extra = "no page placed by the keyword lists; no model configured", {}
    return {"type": None, "confidence": 0.0, "tier": "none", "signals": {}, "needs_review": True, "mixed_content": [],
            "candidates": [{"type": t, "score": sc} for t, sc in (top.candidates if top else [])][:3], "reason": why, **extra}


def _unplaced(typing, unplaced: list[list[int]]) -> list[dict]:
    """Each run of unplaced pages with its three best guesses (F-09.5): kept for a person and for the leftover sweep."""
    out = []
    for run in unplaced:
        secs = [x for no in run for x in typing.pages.get(no, [])]
        best: dict[str, float] = {}
        for x in secs:
            for t, sc in x.candidates:
                best[t] = max(best.get(t, 0.0), sc)
        notes = sorted({x.note for x in secs if x.note})
        out.append({"pages": run, "candidates": [{"type": t, "score": round(sc, 4)} for t, sc in sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))[:3]],
                    **({"note": "; ".join(notes)} if notes else {})})
    return out


def run_id_for(case_ref: str, sha256: str, cfg: IngestionConfig, pages: list[int] | None = None) -> str:
    part = f"|pages:{','.join(map(str, sorted(pages)))}" if pages else ""
    return "RUN-" + sha256_hex(f"{case_ref}|{sha256}|{cfg.hash}|{ENGINE_VERSION}{part}")[:12].upper()


@dataclass
class _Trace:
    store: Store
    run_id: str
    prev: str
    seq: int = 0
    entries: list[dict] = field(default_factory=list)

    def record(self, stage: str, payload, ms: int) -> None:
        out = hash_of(payload)
        self.seq += 1
        self.store.save_stage(self.run_id, self.seq, stage, payload, self.prev, out, ms)
        self.entries.append({"stage": stage, "input_hash": self.prev, "output_hash": out})
        self.prev = out


_RUN_LOCKS: dict[str, list] = {}          # run id -> [lock, readings holding or waiting for it]
_RUN_LOCKS_GUARD = threading.Lock()


@contextmanager
def _run_lock(run_id: str):
    with _RUN_LOCKS_GUARD:
        entry = _RUN_LOCKS.setdefault(run_id, [threading.Lock(), 0])
        entry[1] += 1
    try:
        with entry[0]:
            yield
    finally:
        with _RUN_LOCKS_GUARD:   # forgotten once no reading of the run holds it or waits for it
            entry[1] -= 1
            if entry[1] == 0:
                del _RUN_LOCKS[run_id]


class Ingestor:
    def __init__(self, cfg: IngestionConfig, store: Store, model: ModelClient | None, ocr: OcrEngine | None):
        self.cfg, self.store, self.model, self.ocr = cfg, store, model, ocr
        self.on_stage = None  # optional callback(stage_name) for progress streaming

    def engine_ref(self) -> dict:
        return {"version": ENGINE_VERSION, "ocr": self.ocr.name if self.ocr else "none", "model": self.model.name if self.model else "none"}

    def process_request(self, req: IngestRequest, payloads: dict[str, bytes]) -> IngestResult:
        files = [self.process_file(req.case_ref, f, payloads.get(f.file_id)) for f in req.files]
        return IngestResult(contract_version=CONTRACT_VERSION, case_ref=req.case_ref,
                            config={"version": self.cfg.version, "hash": self.cfg.hash}, engine=self.engine_ref(), files=files)

    # ------------------------------------------------------------------------------------
    def fill(self, req: FillRequest, data: bytes | None) -> FillResult:
        """Epic 6: read a case's pending fields from the pages of one file the engine names (fill.py)."""
        if data is None or sha256_hex(data) != req.file.sha256:
            return FillResult(trace=[{"call": "fill", "error": "missing_or_changed_file"}])
        gate = run_gate(data, req.file.original_name, req.file.content_type, self.cfg.quality, self.cfg.routing)
        if gate.status == "rejected":
            return FillResult(trace=[{"call": "fill", "error": gate.reason or "unsupported"}])
        pages = read_document(data, gate.kind, self.cfg.quality, self.cfg.routing, self.ocr, self.store)
        return fill_stage.fill(self.cfg, req, pages, self.model)

    def process_file(self, case_ref: str, spec: FileSpec, data: bytes | None) -> FileResult:
        base = {"file_id": spec.file_id, "sha256": spec.sha256, "name": spec.original_name}
        if data is None:
            return FileResult(**base, status="rejected", reject={"code": "missing_part", "message": "no file part was sent for this file_id"})
        actual = sha256_hex(data)
        if actual != spec.sha256:
            return FileResult(**base, status="rejected", reject={"code": "sha_mismatch", "message": f"the bytes hash to {actual[:12]}, not {spec.sha256[:12]}"})
        run_id = run_id_for(case_ref, spec.sha256, self.cfg, spec.pages)
        # Files are read side by side; one run (the same file for the same case under the same configuration, say a
        # job's retry while its first attempt is still being read) is read once at a time, as its rows are one set.
        with _run_lock(run_id):
            return self._process_run(case_ref, spec, data, run_id, base)

    def _process_run(self, case_ref: str, spec: FileSpec, data: bytes, run_id: str, base: dict) -> FileResult:
        self.store.add_document(spec.sha256, spec.original_name, spec.content_type, len(data), None)
        self.store.begin_run(run_id, case_ref, spec.sha256, spec.original_name, self.cfg.version, self.cfg.hash, ENGINE_VERSION)
        tr = _Trace(self.store, run_id, spec.sha256)
        stage = "quality"
        # What a stage has already established, so a later crash does not throw
        # it away: integrity reads the bytes before the file is read at all, and
        # a file that cannot be read is exactly one worth saying that about.
        carry: dict = {}
        try:
            # Every model call of this file's run is logged against its case and run (llm/calllog.py).
            with call_context(case_ref=case_ref, run_id=run_id):
                res = self._run(case_ref, spec, data, run_id, tr, base, carry)
        except Exception as e:  # a stage crashed: say which, never return a half answer as if it were whole
            res = FileResult(**base, status="failed", run_id=run_id, error={"stage": stage if tr.seq == 0 else tr.entries[-1]["stage"] + "+1", "type": type(e).__name__, "message": str(e)[:300]},
                             trace=tr.entries, **carry)
        self.store.finish_run(run_id, res.status, res.decision, res.model_dump(mode="json"))
        return res

    def _timed(self, tr: _Trace, name: str, fn):
        t = time.perf_counter()
        out, payload = fn()
        tr.record(name, payload, round((time.perf_counter() - t) * 1000))
        if self.on_stage:
            self.on_stage(name)
        return out

    def _case_type_file(self, cfg: IngestionConfig, ct: CaseType, pages: list[Page], common: dict, tr: _Trace) -> FileResult:
        """A file read as a case document type (F-09.8, F-15.8): the whole file is the one document, read by
        the model only. A discovered field always goes to a person (F-17.7)."""
        e = self._timed(tr, "extract", lambda: ((x := extract_case_type(cfg, ct, pages, self.model)), {"fields": x["fields"], "trace": x["trace"]}))
        by_no = {p.no: p for p in pages}
        cls = common["classification"]
        fields = {}
        for k, f in e["fields"].items():
            scored = score_field(cfg, k, f, cls["confidence"], by_no, [])
            if f.get("origin") in ("discovered", "gap") and scored["status"] == "found":
                scored["needs_review"] = True
            fields[k] = scored
        grade = document_grade(pages)
        conf = decide(cfg, grade, cls, fields, [], {})
        reasons = conf["reasons"] + [{"kind": f"{f['origin']}_field", "field": k} for k, f in fields.items()
                                     if f.get("origin") in ("discovered", "gap")]
        # Only an unreadable document is rejected: a person chose this type, so a weak reading goes back to them.
        if grade in cfg.decision.reject_grades:
            decision = "reject"
        else:
            decision = "human_review" if reasons or not fields or conf["decision"] != "auto_accept" else "auto_accept"
        nos = [p.no for p in pages]
        doc = {"instance_no": 1, "instance_key": None, "page_from": nos[0], "page_to": nos[-1], "document_type": ct.id,
               "fields": fields, "tables": {}, "validation": [], "confidence": {**conf, "decision": decision, "reasons": reasons},
               "identity": {}, "defects": [], "origin": "classified", "pages": nos}
        self.store.save_instance(common["run_id"], 1, None, nos[0], nos[-1], fields, {}, [])
        self._timed(tr, "score", lambda: (None, [doc["confidence"]]))
        return FileResult(**common, front_matter_pages=[], documents=[doc], decision=decision,
                          review_reasons=[{**r, "instance": 1} for r in reasons], trace=tr.entries)

    def _run(self, case_ref: str, spec: FileSpec, data: bytes, run_id: str, tr: _Trace, base: dict, carry: dict) -> FileResult:
        cfg = self.cfg
        gate = self._timed(tr, "quality_gate", lambda: ((g := run_gate(data, spec.original_name, spec.content_type, cfg.quality, cfg.routing)), g.to_json()))
        if gate.status == "rejected":
            return FileResult(**base, status="rejected", run_id=run_id, source={"kind": gate.kind, "pages": gate.pages},
                              reject={"code": gate.reason or "unsupported", "message": gate.message or "", "rescan_request": gate.rescan_request},
                              decision="reject", trace=tr.entries)

        # F-07A: what the file says about its own history, before it is read.
        # Deterministic, bytes only, and it never rejects: its findings are
        # indicators for a person and at most move the decision to review.
        stage = "integrity_file"
        integrity = self._timed(tr, "integrity_file",
                                lambda: ((i := run_integrity_file(data, gate.kind, cfg.integrity)), i.to_json()))
        carry["integrity"] = integrity.findings
        carry["integrity_recommendation"] = integrity.recommendation["code"]
        carry["integrity_facts"] = integrity.facts

        def read():
            pages = read_document(data, gate.kind, cfg.quality, cfg.routing, self.ocr, self.store)
            if spec.pages:
                pages = [p for p in pages if p.no in set(spec.pages)]
            return pages, [{**p.summary(), "text_sha": sha256_hex(p.text())} for p in pages]

        pages: list[Page] = self._timed(tr, "read", read)
        if spec.pages and not pages:
            return FileResult(**base, status="rejected", run_id=run_id, reject={"code": "no_such_pages", "message": f"the file has none of pages {spec.pages}"},
                              decision="reject", trace=tr.entries)
        self.store.save_pages(run_id, pages)
        # F-07A: now that the pages are read, place on them what the integrity
        # checks found in the bytes (a recovered figure is printed somewhere; an
        # image a later save added is drawn somewhere).
        if any(e.locate or e.object is not None for f in integrity.findings for e in f.evidence):
            integrity.findings = self._timed(tr, "integrity_locate", lambda: (
                (located := place_objects(locate_on_pages(integrity.findings, pages), data)),
                [e.model_dump(mode="json") for f in located for e in f.evidence if e.locate or e.object is not None]))
            carry["integrity"] = integrity.findings
        grade = document_grade(pages)
        route = self._timed(tr, "route", lambda: ((r := route_stage.profile(pages)), r))

        typing = None
        runs, unplaced = [], []
        if spec.assigned_type:
            if spec.assigned_type not in cfg.document_types.by_id():
                return FileResult(**base, status="rejected", run_id=run_id, reject={"code": "bad_assignment", "message": f"{spec.assigned_type} is not a document type in configuration {cfg.version}"},
                                  decision="reject", trace=tr.entries)
            person = {"type": spec.assigned_type, "confidence": 1.0, "tier": "person", "signals": {}, "needs_review": False, "mixed_content": [],
                      "candidates": [{"type": spec.assigned_type, "score": 1.0}], "reason": "assigned by a person"}
            cls = self._timed(tr, "classify", lambda: (person, person))
            typing = pages_stage.assigned(cfg, pages, spec.assigned_type)
            runs, unplaced = pages_stage.documents(typing, pages)
        elif spec.case_type:
            ct = spec.case_type
            person = {"type": ct.id, "confidence": 1.0, "tier": "person", "signals": {}, "needs_review": False, "mixed_content": [],
                      "candidates": [{"type": ct.id, "score": 1.0}], "reason": "a case document type assigned by a person"}
            cls = self._timed(tr, "classify", lambda: (person, person))
        else:
            # Each page, and each section a title opens, typed by the keyword lists (F-09, decision 14).
            typing = self._timed(tr, "classify", lambda: ((t := pages_stage.type_pages(cfg, pages, self.model)), {
                "categories": t.categories, "pages": {no: t.page_info(no) for no in t.pages}, "trace": t.trace}))
            runs, unplaced = pages_stage.documents(typing, pages)
            cls = _file_classification(cfg, typing, runs, unplaced)
        self.store.save_classification(run_id, cls)
        # F-07A phase 2: what each page draws, now that the pages are read (a
        # page read by OCR has no text of its own) and the type is known.
        scanned = {p.no for p in pages if p.source == "ocr"}
        integrity = self._timed(tr, "integrity_page", lambda: (
            (i := run_integrity_page(data, gate.kind, integrity, cfg.integrity, None if spec.case_type else cls["type"], scanned,
                                     pages, self.ocr, self.store)), i.to_json()))
        carry["integrity"] = integrity.findings
        carry["integrity_recommendation"] = integrity.recommendation["code"]
        carry["integrity_figures"] = integrity.figures
        page_infos = [{**p.summary(), **(typing.page_info(p.no) if typing and p.no in typing.pages else {})} for p in pages]
        common = dict(**base, status="processed", run_id=run_id, source={"kind": gate.kind, "pages": gate.pages}, grade=grade, route=route,
                      pages=page_infos, classification=cls,
                      integrity=integrity.findings, integrity_recommendation=integrity.recommendation["code"],
                      integrity_facts=integrity.facts, integrity_figures=integrity.figures)
        if spec.case_type:
            return self._case_type_file(cfg, spec.case_type, pages, common, tr)
        if cls["type"] is None:
            reasons = [{"kind": "type_unassigned", "detail": cls.get("reason")}]
            _integrity_reason(integrity, reasons)
            return FileResult(**common, decision="reject" if grade == "U" else "human_review", review_reasons=reasons,
                              unplaced=_unplaced(typing, unplaced) if typing else [], trace=tr.entries)
        return self._typed_pages(cfg, run_id, pages, typing, runs, unplaced, integrity, common, carry, tr)

    def _assemble(self, cfg: IngestionConfig, run_id: str, by_no: dict, units: list, front: list[int], integrity, common: dict,
                  tr: _Trace, extra_reasons: list[dict] | None = None, unplaced: list[dict] | None = None) -> FileResult:
        """Each document scored and decided, and the file's result: its documents, its decision and why."""
        docs, decisions, reasons = [], [], []
        codes = {r.id: r.defect for r in cfg.validators.rules if r.defect}
        for n, (ipages, e, checks, ucls, origin, *rest) in enumerate(units, start=1):
            ident = rest[0] if rest else None
            utype = ucls["type"]
            fields = {k: score_field(cfg, k, f, ucls["confidence"], by_no, checks) for k, f in e["fields"].items()}
            tables = {k: score_table(cfg, k, t, by_no, checks) for k, t in e["tables"].items()}
            igrade = document_grade(ipages)
            conf = decide(cfg, igrade, ucls, fields, checks, tables)
            key = None
            unit = fields.get("amount_unit")
            if unit and unit["status"] == "missing" and unit.get("reason") == "unit_not_stated":
                conf = {**conf, "decision": max(conf["decision"], "human_review", key=RANK.get),
                        "reasons": [*conf["reasons"], {"kind": "unit_not_stated",
                                                       "detail": "no page states the unit its amounts are in; a person sets it"}]}
            if ident is not None:
                # The document's own period, account or person (Epic 4); a period not found or in conflict goes to a person.
                key = ident.key
                if ident.status in ("not_found", "conflict"):
                    conf = {**conf, "decision": max(conf["decision"], "human_review", key=RANK.get),
                            "reasons": [*conf["reasons"], {"kind": f"period_{ident.status}", "detail": ident.note}]}
            tf = cfg.fields.types.get(utype)
            identity = {}
            for ikey, fname in (tf.identity if tf else {}).items():
                f = fields.get(fname)
                if f and f["status"] == "found" and f["value"] not in (None, ""):
                    identity[ikey] = str(f["value"])
            defects = [{"code": codes[c["id"]], "detail": c["detail"], "pages": [p.no for p in ipages]} for c in checks if c["id"] in codes and c["outcome"] != "pass"]
            doc = {"instance_no": n, "instance_key": key, "page_from": ipages[0].no, "page_to": ipages[-1].no, "document_type": utype,
                   "fields": fields, "tables": tables, "validation": checks, "confidence": conf, "identity": identity, "defects": defects,
                   "origin": origin, "pages": [p.no for p in ipages]}
            if e.get("extra") and (e["extra"]["pairs"] or e["extra"]["tables"]):
                doc["extra"] = e["extra"]
            if ident is not None:
                doc["period"] = ident.period.to_json() if ident.period else None
                doc["period_status"] = ident.status
                doc["period_source"] = {"source": ident.source, "page": ident.page, "note": ident.note}
            if origin == "sibling":
                doc["classification"] = ucls
            docs.append(doc)
            decisions.append(conf["decision"])
            reasons += [{**r, "instance": n} for r in conf["reasons"]]
            self.store.save_instance(run_id, n, key, ipages[0].no, ipages[-1].no, fields, tables, checks)
        self._timed(tr, "score", lambda: (None, [d["confidence"] for d in docs]))
        decision = max(decisions, key=RANK.get) if decisions else "human_review"
        reasons += extra_reasons or []
        if extra_reasons:
            decision = max(decision, "human_review", key=RANK.get)
        if not docs:
            reasons.append({"kind": "no_pages", "detail": "no readable page"})
        # F-07A: integrity never rejects, and the extraction above has already
        # run. A file whose own structure contradicts itself goes to a person.
        if _integrity_reason(integrity, reasons) in INTEGRITY_ESCALATES:
            decision = max(decision, "human_review", key=RANK.get)
        return FileResult(**common, front_matter_pages=front, documents=docs, decision=decision, review_reasons=reasons,
                          unplaced=unplaced or [], trace=tr.entries)

    def _typed_pages(self, cfg: IngestionConfig, run_id: str, pages: list[Page], typing, runs: list, unplaced: list[list[int]],
                     integrity, common: dict, carry: dict, tr: _Trace) -> FileResult:
        """The documents of a file typed page by page: each run of pages carrying one type is split into its instances
        and read on its own pages (principle 7); pages left unplaced go to a person with their best guesses."""
        front: list[int] = []
        plan: list[tuple[str, list[Page]]] = []
        for t, run_pages in runs:
            f, groups = identity_stage.split(cfg, t, run_pages)
            front += [n for n in f if n not in front]
            plan += [(t, g) for g in groups]
        idents = [identity_stage.identify(cfg, t, g, self.model) for t, g in plan]
        self._timed(tr, "instances", lambda: (None, {"instances": [{"type": t, "pages": [p.no for p in g], **i.to_json()}
                                                                   for (t, g), i in zip(plan, idents)]}))
        extracted = [extract_instance(cfg, t, g, self.model) for t, g in plan]
        self._timed(tr, "extract", lambda: (None, [{"type": t, "fields": e["fields"], "tables": {k: {**x, "rows": len(x["rows"])} for k, x in e["tables"].items()},
                                                     "trace": e["trace"]} for (t, _), e in zip(plan, extracted)]))
        checks_all = [validate_instance(cfg, t, g, e["fields"], e["tables"]) for (t, g), e in zip(plan, extracted)]
        self._timed(tr, "validate", lambda: (None, checks_all))
        primary = common["classification"]["type"]
        mine = [e for (t, _), e in zip(plan, extracted) if t == primary]
        integrity = self._timed(tr, "integrity_arithmetic", lambda: (
            (i := run_integrity_arithmetic(integrity, cfg.integrity, primary, pages, mine)), i.to_json()))
        common.update(integrity=integrity.findings, integrity_recommendation=integrity.recommendation["code"])
        carry["integrity"] = integrity.findings
        carry["integrity_recommendation"] = integrity.recommendation["code"]
        units = [(g, e, checks, _unit_classification(cfg, typing, t, g), "classified", i)
                 for (t, g), e, checks, i in zip(plan, extracted, checks_all, idents)]
        left = _unplaced(typing, unplaced)
        extra = [{"kind": "pages_unplaced", "pages": u["pages"], "candidates": u["candidates"]} for u in left]
        return self._assemble(cfg, run_id, {p.no: p for p in pages}, units, front, integrity, common, tr, extra, left)

