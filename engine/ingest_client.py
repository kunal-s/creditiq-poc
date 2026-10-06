"""Client for the document-processing service (docs/functional-requirements.md AD-2a).

The engine never parses documents itself. It sends files to the service and
stores what comes back. Two implementations share one interface:

- HttpIngestClient: the real service at config/app.yaml services.ingest_url.
- StubIngestClient: a canned IngestFileResult per file SHA-256, from
  tests/fixtures/ingest/<sha256>.json (or <sha256>@<type_id>.json for a file a
  person assigned a type). The fixtures are the service's own output
  (`python -m tests.fixtures.build_fixtures`). A missing fixture is an error,
  never a guess (AD-5a).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Protocol

from .contracts import IngestRequest, IngestResult
from .contracts.ingest import IngestFileResult

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "ingest"


class IngestError(RuntimeError):
    pass


class IngestClient(Protocol):
    def process(self, request: IngestRequest, payloads: dict[str, bytes]) -> IngestResult:
        """`payloads` maps each request file's file_id to its bytes."""
        ...


class HttpIngestClient:
    def __init__(self, base_url: str, timeout_s: float = 600, api_key: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.api_key = api_key

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

        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        req = urllib.request.Request(f"{self.base_url}/v1/ingest", data=body, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return IngestResult.model_validate_json(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            raise IngestError(f"ingest service answered {e.code}: {detail}") from e
        except OSError as e:
            raise IngestError(f"ingest service unavailable at {self.base_url}: {e}") from e


class StubIngestClient:
    """Canned results by file hash. Every file in a request must have a fixture; a file with a
    person's type assignment needs the `<sha256>@<type_id>.json` fixture."""

    def __init__(self, fixtures: Path | None = None) -> None:
        self.fixtures = fixtures or Path(os.environ.get("CREDITIQ_INGEST_FIXTURES", str(FIXTURES)))

    def _load(self, name: str) -> IngestFileResult | None:
        path = self.fixtures / name
        if not path.is_file():
            return None
        return IngestFileResult.model_validate(json.loads(path.read_text(encoding="utf-8")))

    def process(self, request: IngestRequest, payloads: dict[str, bytes]) -> IngestResult:
        files = []
        for f in request.files:
            name = f"{f.sha256}@{f.assigned_type}.json" if f.assigned_type else f"{f.sha256}.json"
            canned = self._load(name)
            if canned is None:
                raise IngestError(f"no stub fixture {name} for {f.original_name} in {self.fixtures}")
            files.append(canned.model_copy(update={"file_id": f.file_id, "name": f.original_name}))
        return IngestResult.model_validate(
            {"contract_version": "2", "case_ref": request.case_ref, "config": {"version": request.config_version, "hash": "stub"},
             "engine": {"version": "stub", "ocr": "stub", "model": "stub"}, "files": [x.model_dump(mode="json") for x in files]}
        )


def get_client() -> IngestClient:
    """CREDITIQ_INGEST selects the client: "http" (the service at services.ingest_url, the
    default) or "stub" (canned fixtures; tests). CREDITIQ_INGEST_API_KEY is sent as x-api-key."""
    kind = os.environ.get("CREDITIQ_INGEST", "http").strip().lower()
    if kind == "stub":
        return StubIngestClient()
    if kind == "http":
        from .config import load_app_config

        return HttpIngestClient(
            os.environ.get("CREDITIQ_INGEST_URL") or load_app_config()["services"]["ingest_url"],
            api_key=os.environ.get("CREDITIQ_INGEST_API_KEY") or None,
        )
    raise IngestError(f"CREDITIQ_INGEST must be 'stub' or 'http', not {kind!r}")
