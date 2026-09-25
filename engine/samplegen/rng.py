"""Deterministic, independent random streams (reference/05 section A):
adding a new document or event generator must not perturb any other value.
Each stream is seeded from a hash of (case seed, case id, stream name), not
from a shared global generator."""

from __future__ import annotations

import hashlib
import random


def named_rng(seed: int, case_id: str, stream_name: str) -> random.Random:
    digest = hashlib.sha256(f"{seed}|{case_id}|{stream_name}".encode("utf-8")).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))
