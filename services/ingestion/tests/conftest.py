import json
import os
from pathlib import Path

import pytest

from ingestion.config.loader import load_dir
from ingestion.contracts import FileSpec
from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.store import Store
from ingestion.util import sha256_hex

HERE = Path(__file__).parent
CONFIG = HERE.parent.parent.parent / "config" / "ingestion"
OVERLAY = HERE / "fixtures" / "southgate_config"
FIXTURE_DOCS = Path(os.environ.get("INGEST_FIXTURE_DOCS", HERE.parent.parent.parent / "workflow" / "docs" / "reference" / "fixtures" / "southgate"))

pytestmark = pytest.mark.skipif(not FIXTURE_DOCS.exists(), reason="fixture documents not present")

IN_SCOPE = {
    "Southgate_Certificate_of_Incorporation.pdf": "certificate_of_incorporation",
    "Southgate_MOA_AOA.pdf": "memorandum_articles_of_association",
    "Southgate_Entity_PAN.pdf": "company_pan",
    "Southgate_Director_KYC_Iyer_x2.pdf": "director_kyc",
    "Southgate_Board_Resolution_draft.pdf": "board_resolution_borrowing",
    "Southgate_Audited_FS_FY2024.pdf": "audited_financial_statements",
    "Southgate_Audited_FS_FY2025.pdf": "audited_financial_statements",
    "Southgate_ITR_FY2024_FY2025.pdf": "income_tax_return",
    "Southgate_GSTR3B_Dec2025_Jul2026.pdf": "gstr_3b",
    "Southgate_CCB_CA_Statements_12m.pdf": "bank_statement",
    # A declaration of nil facilities is a declaration of existing facilities that declares none.
    "Southgate_Nil_Facilities_Declaration.pdf": "existing_facilities_declaration",
}
OUT_OF_SCOPE = ["Southgate_Provisional_FY2026.pdf", "Southgate_Stock_BookDebt_30Jun2026.pdf",
                "Southgate_Title_Deed_Coimbatore_Unit.pdf"]


@pytest.fixture(scope="session")
def cfg():
    return load_dir(CONFIG, version="test", overlay=OVERLAY)


def fixture_doc(name: str) -> bytes:
    return (FIXTURE_DOCS / name).read_bytes()


def spec(name: str, data: bytes, ctype: str = "application/pdf", fid: str = "f1") -> FileSpec:
    return FileSpec(file_id=fid, sha256=sha256_hex(data), original_name=name, content_type=ctype)


@pytest.fixture()
def ingestor(cfg):
    return Ingestor(cfg, Store(), None, None)


@pytest.fixture(scope="session")
def results(cfg):
    """Every in-scope sample processed once with signals only (no model, no OCR)."""
    ing = Ingestor(cfg, Store(), None, None)
    return {n: ing.process_file("CASE", spec(n, fixture_doc(n)), fixture_doc(n)) for n in [*IN_SCOPE, *OUT_OF_SCOPE]}


def values(doc) -> dict:
    return {k: f.value for k, f in doc.fields.items() if f.status == "found"}
