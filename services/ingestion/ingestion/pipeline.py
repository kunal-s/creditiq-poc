"""The six-stage pipeline (quality gate, read and route, classify, extract, validate, score).

Each stage reads only the configuration version pinned on the run, records its output in SQLite
with an input and output hash, and hands a plain value to the next. Nothing here reads the clock."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import CONTRACT_VERSION, ENGINE_VERSION
from .config.models import IngestionConfig
from .contracts import FileResult, FileSpec, IngestRequest, IngestResult
from .llm.recorder import ModelClient
from .pageindex import Page
from .readers.ocr import OcrEngine
from .stages import classify as classify_stage
from .stages import instances as instances_stage
from .stages import route as route_stage
from .stages.extract.run import extract_instance
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


def run_id_for(case_ref: str, sha256: str, cfg: IngestionConfig) -> str:
    return "RUN-" + sha256_hex(f"{case_ref}|{sha256}|{cfg.hash}|{ENGINE_VERSION}")[:12].upper()


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
    def process_file(self, case_ref: str, spec: FileSpec, data: bytes | None) -> FileResult:
        base = {"file_id": spec.file_id, "sha256": spec.sha256, "name": spec.original_name}
        if data is None:
            return FileResult(**base, status="rejected", reject={"code": "missing_part", "message": "no file part was sent for this file_id"})
        actual = sha256_hex(data)
        if actual != spec.sha256:
            return FileResult(**base, status="rejected", reject={"code": "sha_mismatch", "message": f"the bytes hash to {actual[:12]}, not {spec.sha256[:12]}"})
        run_id = run_id_for(case_ref, spec.sha256, self.cfg)
        self.store.add_document(spec.sha256, spec.original_name, spec.content_type, len(data), None)
        self.store.begin_run(run_id, case_ref, spec.sha256, spec.original_name, self.cfg.version, self.cfg.hash, ENGINE_VERSION)
        tr = _Trace(self.store, run_id, spec.sha256)
        stage = "quality"
        # What a stage has already established, so a later crash does not throw
        # it away: integrity reads the bytes before the file is read at all, and
        # a file that cannot be read is exactly one worth saying that about.
        carry: dict = {}
        try:
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
            return pages, [{**p.summary(), "text_sha": sha256_hex(p.text())} for p in pages]

        pages: list[Page] = self._timed(tr, "read", read)
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

        if spec.assigned_type:
            if spec.assigned_type not in cfg.document_types.by_id():
                return FileResult(**base, status="rejected", run_id=run_id, reject={"code": "bad_assignment", "message": f"{spec.assigned_type} is not a document type in configuration {cfg.version}"},
                                  decision="reject", trace=tr.entries)
            person = {"type": spec.assigned_type, "confidence": 1.0, "tier": "person", "signals": {}, "needs_review": False, "mixed_content": [],
                      "candidates": [{"type": spec.assigned_type, "score": 1.0}], "reason": "assigned by a person"}
            cls = self._timed(tr, "classify", lambda: (person, person))
        else:
            cls = self._timed(tr, "classify", lambda: ((c := classify_stage.classify(cfg, pages, self.model)), c))
        self.store.save_classification(run_id, cls)
        # F-07A phase 2: what each page draws, now that the pages are read (a
        # page read by OCR has no text of its own) and the type is known.
        scanned = {p.no for p in pages if p.source == "ocr"}
        integrity = self._timed(tr, "integrity_page", lambda: (
            (i := run_integrity_page(data, gate.kind, integrity, cfg.integrity, cls["type"], scanned,
                                     pages, self.ocr, self.store)), i.to_json()))
        carry["integrity"] = integrity.findings
        carry["integrity_recommendation"] = integrity.recommendation["code"]
        carry["integrity_figures"] = integrity.figures
        page_infos = [p.summary() for p in pages]
        common = dict(**base, status="processed", run_id=run_id, source={"kind": gate.kind, "pages": gate.pages}, grade=grade, route=route,
                      pages=page_infos, classification=cls,
                      integrity=integrity.findings, integrity_recommendation=integrity.recommendation["code"],
                      integrity_facts=integrity.facts, integrity_figures=integrity.figures)
        if cls["type"] is None:
            reasons = [{"kind": "type_unassigned", "detail": cls.get("reason")}]
            _integrity_reason(integrity, reasons)
            return FileResult(**common, decision="reject" if grade == "U" else "human_review", review_reasons=reasons, trace=tr.entries)

        front, groups = self._timed(tr, "instances", lambda: ((r := instances_stage.split_instances(cfg, cls["type"], pages)), {"front_matter": r[0], "instances": [[p.no for p in g] for g in r[1]]}))
        by_no = {p.no: p for p in pages}
        extracted = []
        for n, ipages in enumerate(groups, start=1):
            extracted.append(extract_instance(cfg, cls["type"], ipages, self.model))
        self._timed(tr, "extract", lambda: (None, [{"fields": e["fields"], "tables": {k: {**t, "rows": len(t["rows"])} for k, t in e["tables"].items()}, "trace": e["trace"]} for e in extracted]))

        checks_all = [validate_instance(cfg, cls["type"], g, e["fields"], e["tables"]) for g, e in zip(groups, extracted)]
        self._timed(tr, "validate", lambda: (None, checks_all))
        # F-07A: whether the printed figures add up, now that they are read.
        integrity = self._timed(tr, "integrity_arithmetic", lambda: (
            (i := run_integrity_arithmetic(integrity, cfg.integrity, cls["type"], pages, extracted)), i.to_json()))
        common.update(integrity=integrity.findings, integrity_recommendation=integrity.recommendation["code"])
        carry["integrity"] = integrity.findings
        carry["integrity_recommendation"] = integrity.recommendation["code"]

        docs, decisions, reasons = [], [], []
        rule = cfg.signals.types[cls["type"]].instances
        for n, (ipages, e, checks) in enumerate(zip(groups, extracted, checks_all), start=1):
            ipg = {p.no: p for p in ipages}
            fields = {k: score_field(cfg, k, f, cls["confidence"], by_no, checks) for k, f in e["fields"].items()}
            tables = {k: score_table(cfg, k, t, by_no, checks) for k, t in e["tables"].items()}
            igrade = document_grade(ipages)
            conf = decide(cfg, igrade, cls, fields, checks, tables)
            key = None
            if rule and rule.keys:
                key = " | ".join(str(fields[k]["value"] or fields[k]["raw_text"]) for k in rule.keys if fields[k]["status"] == "found") or None
            tf = cfg.fields.types.get(cls["type"])
            identity = {}
            for ikey, fname in (tf.identity if tf else {}).items():
                f = fields.get(fname)
                if f and f["status"] == "found" and f["value"] not in (None, ""):
                    identity[ikey] = str(f["value"])
            codes = {r.id: r.defect for r in cfg.validators.rules if r.defect}
            defects = [{"code": codes[c["id"]], "detail": c["detail"], "pages": [p.no for p in ipages]} for c in checks if c["id"] in codes and c["outcome"] != "pass"]
            docs.append({"instance_no": n, "instance_key": key, "page_from": ipages[0].no, "page_to": ipages[-1].no, "document_type": cls["type"],
                         "fields": fields, "tables": tables, "validation": checks, "confidence": conf, "identity": identity, "defects": defects})
            decisions.append(conf["decision"])
            reasons += [{**r, "instance": n} for r in conf["reasons"]]
            self.store.save_instance(run_id, n, key, ipages[0].no, ipages[-1].no, fields, tables, checks)
        self._timed(tr, "score", lambda: (None, [d["confidence"] for d in docs]))
        decision = max(decisions, key=RANK.get) if decisions else "human_review"
        if not docs:
            reasons.append({"kind": "no_pages", "detail": "no readable page"})
        # F-07A: integrity never rejects, and the extraction above has already
        # run. A file whose own structure contradicts itself goes to a person.
        if _integrity_reason(integrity, reasons) in INTEGRITY_ESCALATES:
            decision = max(decision, "human_review", key=RANK.get)
        return FileResult(**common, front_matter_pages=front, documents=docs, decision=decision, review_reasons=reasons, trace=tr.entries)
