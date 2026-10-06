"""HTTP surface. One call does the work (POST /v1/ingest); the rest are read-only views of what a
run stored, so the evidence viewer and a reviewer can see exactly what was read."""

from __future__ import annotations

import hmac
import json
import queue
import threading
from functools import lru_cache

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.datastructures import UploadFile as FormFile

from . import CONTRACT_VERSION, ENGINE_VERSION
from .config.loader import ConfigError, ConfigStore, load_dir
from .config.models import IngestionConfig
from .contracts import IngestRequest
from .llm.openai import OpenAIProvider
from .llm.recorder import ModelClient
from .pipeline import Ingestor
from .readers.ocr import get_engine
from .settings import Settings
from .stages.quality import run_gate
from .stages.read import document_grade, read_document
from .store import Store
from .util import sha256_hex

LOOPBACK = {"127.0.0.1", "::1", "localhost", "testclient"}


def create_app(settings: Settings | None = None, store: Store | None = None) -> FastAPI:
    st = settings or Settings.from_env()
    db = store or Store(st.db_path)
    app = FastAPI(title="CreditIQ ingestion", version=ENGINE_VERSION)
    ocr_cache: dict = {}

    def auth(request: Request) -> None:
        if st.api_key:
            given = request.headers.get("x-api-key") or request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not given or not hmac.compare_digest(given.encode(), st.api_key.encode()):
                raise HTTPException(401, "unauthorised")
        elif (request.client.host if request.client else "") not in LOOPBACK:
            raise HTTPException(401, "no API key is configured, so only local callers are served")

    def config_for(version: str) -> IngestionConfig:
        try:
            if st.config_dir and version == "dev":
                return _dev(str(st.config_dir))
            return ConfigStore(st.data_root).load(version)
        except ConfigError as e:
            raise HTTPException(409, str(e)) from e

    @lru_cache(maxsize=2)
    def _dev(path: str) -> IngestionConfig:
        return load_dir(path, version="dev")

    def ingestor(cfg: IngestionConfig) -> Ingestor:
        import os

        if "ocr" not in ocr_cache:
            ocr_cache["ocr"] = get_engine(cfg.routing.ocr)
        provider = OpenAIProvider(cfg.llm, os.environ.get(cfg.llm.api_key_env))
        model = ModelClient(provider, st.model_mode, db) if cfg.llm.provider == "openai" else None
        return Ingestor(cfg, db, model, ocr_cache["ocr"])

    @app.get("/v1/health")
    def health():
        return {"ok": True, "service": "ingestion", "engine_version": ENGINE_VERSION, "contract_version": CONTRACT_VERSION,
                "model_mode": st.model_mode, "ocr": ocr_cache["ocr"].name if ocr_cache.get("ocr") else "not loaded",
                "versions": ConfigStore(st.data_root).versions() + (["dev"] if st.config_dir else [])}

    @app.post("/v1/ingest", dependencies=[Depends(auth)])
    async def ingest(request: Request):
        form = await request.form()
        try:
            req = IngestRequest.model_validate_json(str(form.get("request")))
        except Exception as e:
            raise HTTPException(400, f"bad request: {e}") from e
        payloads = {k: await v.read() for k, v in form.items() if isinstance(v, FormFile)}
        cfg = config_for(req.config_version)
        return JSONResponse(ingestor(cfg).process_request(req, payloads).model_dump(mode="json"))

    @app.post("/v1/ingest/stream", dependencies=[Depends(auth)])
    async def ingest_stream(request: Request):
        """Server-Sent Events: one `stage` event per completed stage, then `result`."""
        form = await request.form()
        req = IngestRequest.model_validate_json(str(form.get("request")))
        payloads = {k: await v.read() for k, v in form.items() if isinstance(v, FormFile)}
        cfg = config_for(req.config_version)
        q: "queue.Queue[tuple[str, dict] | None]" = queue.Queue()

        def work():
            try:
                ing = ingestor(cfg)
                ing.on_stage = lambda name: q.put(("stage", {"stage": name}))
                q.put(("result", ing.process_request(req, payloads).model_dump(mode="json")))
            except Exception as e:  # noqa: BLE001
                q.put(("error", {"message": str(e)}))
            q.put(None)

        threading.Thread(target=work, daemon=True).start()

        def gen():
            while (item := q.get()) is not None:
                yield f"event: {item[0]}\ndata: {json.dumps(item[1])}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post("/v1/parse", dependencies=[Depends(auth)])
    async def parse(file: UploadFile = File(...), config_version: str = Form("dev")):
        """Stages 1 and 2 only: what the extractor will read. No model is called."""
        cfg = config_for(config_version)
        data = await file.read()
        gate = run_gate(data, file.filename or "", file.content_type or "", cfg.quality, cfg.routing)
        if gate.status == "rejected":
            return {"sha256": sha256_hex(data), "gate": gate.to_json(), "pages": []}
        ing = ingestor(cfg)
        pages = read_document(data, gate.kind, cfg.quality, cfg.routing, ing.ocr, db)
        return {"sha256": sha256_hex(data), "gate": gate.to_json(), "grade": document_grade(pages),
                "pages": [{**p.summary(), "text": p.text()} for p in pages]}

    @app.get("/v1/types", dependencies=[Depends(auth)])
    def types(config_version: str = "dev"):
        cfg = config_for(config_version)
        return {"config": {"version": cfg.version, "hash": cfg.hash}, "types": [d.model_dump(by_alias=True, mode="json") for d in cfg.document_types.documents]}

    @app.get("/v1/runs", dependencies=[Depends(auth)])
    def runs(case_ref: str):
        return db.list_runs(case_ref)

    @app.get("/v1/runs/{run_id}", dependencies=[Depends(auth)])
    def run(run_id: str):
        r = db.get_run(run_id)
        if not r:
            raise HTTPException(404, "no such run")
        return r

    @app.get("/v1/runs/{run_id}/stages", dependencies=[Depends(auth)])
    def stages(run_id: str):
        return db.get_stages(run_id)

    @app.get("/v1/runs/{run_id}/pages/{page_no}", dependencies=[Depends(auth)])
    def page(run_id: str, page_no: int):
        p = db.get_page(run_id, page_no)
        if not p:
            raise HTTPException(404, "no such page")
        return p

    return app
