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
    """Canned results by file hash. Every file in a request must have a fixture."""

    def __init__(self, fixtures: Path = FIXTURES) -> None:
        self.fixtures = fixtures

    def process(self, request: IngestRequest, payloads: dict[str, bytes]) -> IngestResult:
        documents, outcomes = [], []
        for f in request.files:
            path = self.fixtures / f"{f.sha256}.json"
            if not path.is_file():
                raise IngestError(f"no stub fixture for {f.original_name} ({f.sha256}) in {self.fixtures}")
            canned = IngestResult.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for doc in canned.documents:
                documents.append(doc.model_copy(update={"file_id": f.file_id}))
            outcomes.extend(o.model_copy(update={"file_id": f.file_id}) for o in canned.files)
        return IngestResult(
            case_ref=request.case_ref,
            config_version=request.config_version,
            engine_version="stub",
            model_provider="stub",
            files=outcomes,
            documents=documents,
        )
