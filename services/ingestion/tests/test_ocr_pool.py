"""Files are read side by side: OCR runs in at most the configured number of processes at once, each
with its own engine, and every pdfium call holds the one lock."""

from __future__ import annotations

import functools
import os
import time
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from ingestion.integrity import pagedoc
from ingestion.pageindex import Word
from ingestion.readers import pdf_text
from ingestion.readers.ocr import OcrProcessPool, OcrResult
from ingestion.readers.pdfium_guard import PDFIUM
from ingestion.settings import Settings


class FakeEngine:
    """Says which process read the page and when, and what it was given."""

    name = "fake"

    def __init__(self, pause: float) -> None:
        self.pause = pause

    def recognise(self, img, dpi):
        start = time.monotonic()
        time.sleep(self.pause)
        return OcrResult([Word(f"{os.getpid()}|{start}|{time.monotonic()}|{img.size[0]}x{img.size[1]}|{dpi}",
                               0.0, 0.0, 1.0, 1.0, 0.9)], 90.0)


def _read(pool, n: int, threads: int) -> list[tuple[int, float, float, str, str]]:
    img = Image.new("RGB", (40, 30), "white")
    with ThreadPoolExecutor(threads) as ex:
        results = list(ex.map(lambda _: pool.recognise(img, 200), range(n)))
    out = []
    for r in results:
        pid, start, end, size, dpi = r.words[0].text.split("|")
        out.append((int(pid), float(start), float(end), size, dpi))
    return out


def test_at_most_the_configured_processes_read_at_once():
    pool = OcrProcessPool(functools.partial(FakeEngine, 0.3), workers=2, name="fake")
    try:
        reads = _read(pool, 6, threads=6)
    finally:
        pool.close()
    assert {(size, dpi) for _, _, _, size, dpi in reads} == {("40x30", "200")}
    assert len({pid for pid, *_ in reads}) == 2 and os.getpid() not in {pid for pid, *_ in reads}
    peak = max(sum(1 for _, s, e, *_ in reads if s <= t < e) for _, t, *_ in reads)
    assert peak == 2
    assert pool.name == "fake"


def test_a_second_process_starts_only_when_two_pages_wait():
    pool = OcrProcessPool(functools.partial(FakeEngine, 0.0), workers=2, name="fake")
    try:
        reads = _read(pool, 3, threads=1)
    finally:
        pool.close()
    assert len({pid for pid, *_ in reads}) == 1


def test_ocr_workers_default_to_two(monkeypatch):
    monkeypatch.delenv("INGEST_OCR_WORKERS", raising=False)
    assert Settings.from_env().ocr_workers == 2
    monkeypatch.setenv("INGEST_OCR_WORKERS", "3")
    assert Settings.from_env().ocr_workers == 3


def test_every_pdfium_call_holds_the_one_lock():
    assert pagedoc._PDFIUM is PDFIUM
    assert pdf_text.PDFIUM is PDFIUM


def test_files_read_side_by_side_read_as_they_do_one_at_a_time(ingestor):
    """Several files read at once on threads (as the service does for the engine's parallel requests): every pdfium
    call is serialised, so nothing crashes, and each file reads exactly as it does alone. The same file for the same
    case (one run) is read once at a time, so a retry sent while its first attempt runs does not collide with it."""
    from tests import docsets as D
    from tests.conftest import spec

    docs = {"pan.pdf": D.company_pan(), "resolution.pdf": D.board_resolution(),
            "gstr3b.pdf": D.gstr_3b(month=(2026, 4), taxable=12_500_000)}
    alone = {n: ingestor.process_file("CASE", spec(n, b, fid=n), b) for n, b in docs.items()}
    with ThreadPoolExecutor(6) as ex:
        together = list(ex.map(lambda nb: (nb[0], ingestor.process_file("CASE", spec(nb[0], nb[1], fid=nb[0]), nb[1])),
                               list(docs.items()) * 4))
    for name, res in together:
        assert res.status == alone[name].status == "processed", (name, res.error, alone[name].error)
        assert res.model_dump(exclude={"timings", "run_id"}) == alone[name].model_dump(exclude={"timings", "run_id"})
