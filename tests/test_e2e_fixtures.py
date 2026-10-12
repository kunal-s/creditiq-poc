"""The screen tests' fixtures name only what the configuration defines, so a renamed norm,
category or authority fails here rather than leaving the screens tested against ids the
engine never sends."""

import re
from pathlib import Path

from engine.configstore import writer

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = (ROOT / "e2e" / "fixtures" / "data.ts").read_text(encoding="utf-8")
SPECS = "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "e2e").glob("*.spec.ts"))


def test_fixture_norm_ids_are_configured_norms():
    configured = {n.id for n in writer.load_authored_sections()["policy"].norms}
    used = set(re.findall(r'id: "((?:EL|FR|DOC|SC)-\d+)"', FIXTURES))
    assert used and used <= configured, used - configured


def test_fixture_authorities_are_matrix_authorities():
    keys = {a.key for a in writer.load_authored_sections()["approval_matrix"].authorities}
    text = FIXTURES + SPECS
    used = set(re.findall(r'authority\("([a-z_]+)"', text))
    used |= set(re.findall(r'(?:authority_key|authority|at_least): "([a-z_]+)"', text))
    used |= set(re.findall(r'key: "([a-z_]+_(?:officer|head|committee))"', text))
    assert used and used <= keys, used - keys


def test_fixture_categories_are_configured_categories():
    categories = {c.key for c in writer.load_authored_sections()["policy"].deviation_categories}
    used = set(re.findall(r'category: "([a-z_]+)"', FIXTURES))
    assert used and used <= categories, used - categories
