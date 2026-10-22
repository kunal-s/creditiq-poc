#!/usr/bin/env python3
"""Create a case and upload a folder of PDFs to it through the engine API, as the RM and the analyst would.

    .venv/bin/python scripts/run_test_set.py <folder> [--borrower NAME --pan PAN --gstin GSTIN --cin CIN --amount INR]

Defaults are the fictional borrower of the generated test sets (services/ingestion/tests/docsets.py). The sign-in
password is auth.demoPassword in config/roles.yaml. Prints the case id; the service then reads the files in the
background (watch the ingestion log, or the case's progress)."""

from __future__ import annotations

import argparse
import glob
import json
import os
import urllib.request
import uuid
from collections import Counter
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def call(base: str, path: str, data: bytes | None = None, token: str | None = None, headers: dict | None = None) -> dict:
    req = urllib.request.Request(base + path, data=data, method="POST" if data is not None else "GET")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    return json.load(urllib.request.urlopen(req))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--base", default="http://localhost:8010")
    ap.add_argument("--borrower", default="Kestrel Fabricators Private Limited")
    ap.add_argument("--pan", default="AAACK1234F")
    ap.add_argument("--gstin", default="27AAACK1234F1Z0")
    ap.add_argument("--cin", default="U28999MH2015PTC123456")
    ap.add_argument("--amount", type=int, default=42_500_000)
    a = ap.parse_args()
    roles = yaml.safe_load((ROOT / "config" / "roles.yaml").read_text())
    password = roles["auth"]["demoPassword"]
    users = {u["role"]: u["email"] for u in roles["users"]}

    def login(role: str) -> str:
        body = json.dumps({"email": users[role], "password": password}).encode()
        return call(a.base, "/api/auth/login", body, headers={"content-type": "application/json"})["token"]

    case = call(a.base, "/api/cases", json.dumps({
        "borrower": a.borrower, "constitution": "private_limited", "facilities": ["cash_credit", "term_loan"], "amount_inr": a.amount,
        "channel": "email", "pan": a.pan, "gstin": a.gstin, "cin": a.cin,
        "duplicate_override_reason": f"Test document set {Path(a.folder).name}"}).encode(),
        token=login("rm"), headers={"content-type": "application/json"})["id"]
    files = sorted(glob.glob(os.path.join(a.folder, "*.pdf")))
    boundary = uuid.uuid4().hex
    body = b""
    for f in files:
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="{os.path.basename(f)}"\r\n'
                 "Content-Type: application/pdf\r\n\r\n").encode() + Path(f).read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    r = call(a.base, f"/api/cases/{case}/files", body, token=login("analyst"),
             headers={"content-type": f"multipart/form-data; boundary={boundary}"})
    print(case, Path(a.folder).name, len(files), "files", dict(Counter(x["status"] for x in r["files"])))


if __name__ == "__main__":
    main()
