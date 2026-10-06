"""Small helpers shared by every stage. Nothing here reads the clock."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def canonical_json(value: Any) -> str:
    """Keys sorted at every level, no whitespace: the same value always serialises the same way."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=_default)


def _default(o: Any) -> Any:
    if hasattr(o, "model_dump"):
        return o.model_dump(mode="json")
    raise TypeError(f"not serialisable: {type(o)}")


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def hash_of(value: Any) -> str:
    return sha256_hex(canonical_json(value))


_WS = re.compile(r"\s+")


def collapse_ws(s: str) -> str:
    return _WS.sub(" ", s).strip()


def fold(s: str) -> str:
    """Comparison form: case-folded, whitespace collapsed, punctuation spacing removed."""
    return re.sub(r"[\s]+", " ", s).strip().casefold()
