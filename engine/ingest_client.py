"""Client for the document-processing sidecar (docs/functional-requirements.md AD-2).

The engine never parses documents itself. It sends files to the sidecar and
stores what comes back. Two implementations share one interface:

- HttpIngestClient: the real sidecar at config/app.yaml services.ingest_url.
- StubIngestClient: canned IngestResult JSON per file SHA-256, from
  tests/fixtures/ingest/<sha256>.json. Used by tests and by Wave 1 streams
  that must not wait for the sidecar. A missing fixture is an error, never a
  guess (AD-5).
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid
from pathlib import Path
from typing import Protocol

from .contracts import IngestRequest, IngestResult

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ingest"


class IngestError(RuntimeError):
    pass


class IngestClient(Protocol):
    def process(self, request: IngestRequest, payloads: dict[str, bytes]) -> IngestResult:
        """`payloads` maps each request file's file_id to its bytes."""
        ...


class HttpIngestClient:
    def __init__(self, base_url: str, timeout_s: float = 600) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def process(self, request: IngestRequest, payloads: dict[str, bytes]) -> IngestResult:
        boundary = uuid.uuid4().hex
        parts: list[bytes] = []

        def part(name: str, content: bytes, content_type: str, filename: str | None = None) -> None:
            disposition = f'form-data; name="{name}"' + (f'; filename="{filename}"' if filename else "")
            parts.append(
                f"--{boundary}\r\nContent-Disposition: {disposition}\r\nContent-Type: {content_type}\r\n\r\n".encode()
                + content
                + b"\r\n"
            )

        part("request", request.model_dump_json().encode(), "application/json")
        for f in request.files:
            part(f.file_id, payloads[f.file_id], f.content_type, filename=f.file_id)
        body = b"".join(parts) + f"--{boundary}--\r\n".encode()

        req = urllib.request.Request(
            f"{self.base_url}/v1/process",
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return IngestResult.model_validate_json(resp.read())
        except OSError as e:
            raise IngestError(f"ingest sidecar unavailable at {self.base_url}: {e}") from e


class StubIngestClient:
    """Canned results by file hash. Every file in a request must have a fixture.

    A type assignment (IngestRequest.assignments) is honoured the way the
    sidecar honours it: the document for that page range takes the assigned
    type at exit tier "person". Its fields come from `<sha256>@<type_id>.json`
    when that fixture exists; otherwise the canned fields are kept.
    """

    def __init__(self, fixtures: Path | None = None) -> None:
        self.fixtures = fixtures or Path(os.environ.get("CREDITIQ_INGEST_FIXTURES", str(FIXTURES)))

    def _load(self, name: str) -> IngestResult | None:
        path = self.fixtures / name
        if not path.is_file():
            return None
        return IngestResult.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def process(self, request: IngestRequest, payloads: dict[str, bytes]) -> IngestResult:
        documents, outcomes, timings = [], [], []
        for f in request.files:
            canned = self._load(f"{f.sha256}.json")
            if canned is None:
                raise IngestError(f"no stub fixture for {f.original_name} ({f.sha256}) in {self.fixtures}")
            assigned = {
                (a.page_from, a.page_to): a.type_id for a in request.assignments if a.file_id == f.file_id
            }
            for doc in canned.documents:
                type_id = assigned.get((doc.page_from, doc.page_to))
                if type_id is not None:
                    override = self._load(f"{f.sha256}@{type_id}.json")
                    source = next(
                        (d for d in (override.documents if override else []) if d.page_from == doc.page_from),
                        doc,
                    )
                    classification = doc.classification.model_copy(
                        update={"types": [type_id], "exit_tier": "person", "confidence": 1.0}
                    )
                    doc = source.model_copy(update={"classification": classification, "doc_key": doc.doc_key})
                documents.append(doc.model_copy(update={"file_id": f.file_id}))
            outcomes.extend(o.model_copy(update={"file_id": f.file_id}) for o in canned.files)
            timings.extend(t.model_copy(update={"file_id": f.file_id}) for t in canned.timings)
        return IngestResult(
            case_ref=request.case_ref,
            config_version=request.config_version,
            engine_version="stub",
            model_provider="stub",
            files=outcomes,
            documents=documents,
            timings=timings,
        )


def get_client() -> IngestClient:
    """CREDITIQ_INGEST selects the client: "http" (the sidecar at
    services.ingest_url, the default) or "stub" (canned fixtures; tests)."""
    kind = os.environ.get("CREDITIQ_INGEST", "http").strip().lower()
    if kind == "stub":
        return StubIngestClient()
    if kind == "http":
        from .config import load_app_config

        return HttpIngestClient(os.environ.get("CREDITIQ_INGEST_URL") or load_app_config()["services"]["ingest_url"])
    raise IngestError(f"CREDITIQ_INGEST must be 'stub' or 'http', not {kind!r}")
