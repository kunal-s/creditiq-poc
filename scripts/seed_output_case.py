#!/usr/bin/env python3
"""Seed one case through to the outputs, so the credit appraisal memo can be looked at.

    .venv/bin/python scripts/seed_output_case.py [--root workflow/data]

The case is the fictional Kestrel borrower of the test fixtures: its fifteen documents
(tests/fixtures/cases.json "complete") are uploaded as the RM would, read with their recorded
service output (the stub client, so no model is called and the result is the same every run),
and the case is created by the analyst once the review gate is met. Nothing is written past
what the screens would write, except the case's as_of, which is pinned to the date the fixture
documents were drawn up against (as the tests do).

Safe beside a running engine: each job this script queues is marked running under its own lease
before it is committed, so the engine's worker never claims it, and the script runs it in process.
Prints the case id, the gate and the memo's sections.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
RM = "arjun.deshpande@rblbank.com"
ANALYST = "ananya.krishnan@rblbank.com"
AS_OF = "2026-09-29"
CASE = {
    "borrower": "Kestrel Fabricators Pvt Ltd",
    "constitution": "private_limited",
    "facilities": ["cash_credit"],
    "amount_inr": 30_000_000,
    "channel": "email",
    "collateral_present": False,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT / "workflow" / "data"))
    a = ap.parse_args()
    root = Path(a.root).resolve()
    os.environ.update(CREDITIQ_DATA_ROOT=str(root), CREDITIQ_INGEST="stub", CREDITIQ_WORKER="0")
    sys.path.insert(0, str(ROOT))

    from fastapi.testclient import TestClient

    from engine import auth, db, deps, jobs
    from engine.api import app
    from engine.config import find_user
    from engine.ingest_client import StubIngestClient

    # Act as the RM, then the analyst, without a sign-in.
    acting = {"email": RM}
    app.dependency_overrides[deps.current_user] = lambda: auth.user_payload(find_user(acting["email"]))

    # Every job queued here is leased to this script inside the transaction that queues it.
    ours: list[str] = []
    enqueue = jobs.enqueue

    def leased(conn, *, case_id, kind, payload):
        job_id = enqueue(conn, case_id=case_id, kind=kind, payload=payload)
        now = datetime.now(timezone.utc)
        conn.execute(
            "UPDATE jobs SET status = 'running', attempts = 1, started_at = ?, lease_until = ? WHERE id = ?",
            (now.isoformat(), (now + timedelta(days=1)).isoformat(), job_id),
        )
        ours.append(job_id)
        return job_id

    jobs.enqueue = leased
    api = TestClient(app)

    def call(method: str, path: str, **kw):
        r = api.request(method, path, **kw)
        if r.status_code >= 400:
            raise SystemExit(f"{method} {path}: {r.status_code} {r.text}")
        return r.json()

    created = api.post("/api/cases", json=CASE)
    if created.status_code == 409:
        created = api.post(
            "/api/cases", json={**CASE, "duplicate_override_reason": "Sample case to the outputs"}
        )
    if created.status_code != 201:
        raise SystemExit(f"create: {created.status_code} {created.text}")
    case_id = created.json()["id"]
    conn = db.connect(root)
    try:
        conn.execute("UPDATE cases SET as_of = ? WHERE id = ?", (AS_OF, case_id))
        conn.commit()
    finally:
        conn.close()

    names = json.loads((FIXTURES / "cases.json").read_text())["complete"]
    files = [("files", (n, (FIXTURES / "files" / n).read_bytes(), "application/pdf")) for n in names]
    call("POST", f"/api/cases/{case_id}/files", files=files)

    client = StubIngestClient()
    done: set[str] = set()
    while pending := [j for j in ours if j not in done]:
        conn = db.connect(root)
        try:
            for job_id in pending:
                row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
                jobs.run_job(conn, root, row, client)
                status = conn.execute("SELECT status, error FROM jobs WHERE id = ?", (job_id,)).fetchone()
                if status["status"] != "done":
                    raise SystemExit(f"job {job_id}: {status['status']} {status['error']}")
                done.add(job_id)
        finally:
            conn.close()

    acting["email"] = ANALYST
    gate = call("GET", f"/api/cases/{case_id}/progress")["gate"]
    print(case_id, "gate:", json.dumps({k: gate.get(k) for k in ("score_pct", "gate_pct", "can_open", "blockers")}))
    if not gate["can_open"]:
        return 1
    call("POST", f"/api/cases/{case_id}/assessment")
    cam = call("GET", f"/api/cases/{case_id}/cam")
    for s in cam["sections"]:
        print(f"  {s['id']}: {len(s['blocks'])} blocks")
    stages = call("GET", f"/api/cases/{case_id}/progress")["stages"]
    print("stages:", {s["key"]: s["status"] for s in stages})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
