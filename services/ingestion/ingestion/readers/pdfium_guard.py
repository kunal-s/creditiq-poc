"""pdfium is not thread-safe: two threads in it at once abort the process. The service reads several files at
once, so every call into pypdfium2, in any module, holds this one lock."""

from __future__ import annotations

import threading

PDFIUM = threading.RLock()
