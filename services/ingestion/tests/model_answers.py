"""A stand-in for the model that answers like a careful reader. It authors the test recordings
(marked origin='fixture'); it says nothing about how a real model performs."""

import re

from ingestion.llm.provider import ModelRequest

PATTERNS = {"accounting_standard": r"applicable accounting standards"}
NAMES = ["Lakshmi Iyer", "Venkat Iyer"]
HALLUCINATE: dict[str, str] = {}   # field -> a value that is not on the page (set by a test)


def answerer(req: ModelRequest) -> dict:
    if req.task == "classify":
        return {"type": "none_of_these", "reason": "the text is not any of the listed kinds"}
    fields = re.findall(r"^- (\w+) \(", req.user, re.M)
    lines = dict(re.findall(r"^(p\d+\.l\d+): (.*)$", req.user, re.M))
    out = {}
    for f in fields:
        value, ids = None, []
        if f in HALLUCINATE:
            value, ids = HALLUCINATE[f], [next(iter(lines))]
        elif f in PATTERNS:
            for i, t in lines.items():
                m = re.search(PATTERNS[f], t, re.I)
                if m:
                    value, ids = m.group(0), [i]
                    break
        elif f == "authorized_signatories":
            ids = [i for i, t in lines.items() if any(n in t for n in NAMES)]
            value = NAMES if ids else None
        out[f] = {"value": value, "line_ids": ids}
    return {"fields": out}
