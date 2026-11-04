"""F-07A phase 2: a statement's printed figures add up, and a PDF's signatures hold.

The statements are built here as what extraction hands on (rows with their
printed text, the opening and closing balances, the page lines), so the checks
are tested, not the reading. The signed files are signed here with a test
certificate authority made for the test.
"""

from __future__ import annotations

import datetime as dt
import io

import pytest

from ingestion.integrity.arithmetic import ARITHMETIC_CHECKS, arithmetic_checks, paise, rupees
from ingestion.pageindex import Line, Page, Word


def _policy(cfg) -> dict:
    return cfg.integrity.model_dump(mode="python")


def _by_code(found) -> dict:
    out = {f.code: f for f in found}
    assert len(out) == len(found), "a check answered twice"
    return out


def _line(page: int, idx: int, words: list[tuple[str, float]], y: float = 100.0) -> Line:
    ws = [Word(t, x, y, x + 6.0 * len(t), y + 10.0, 1.0) for t, x in words]
    text, spans, at = "", [], 0
    for w in ws:
        if text:
            text += " "
            at += 1
        spans.append((at, at + len(w.text)))
        text += w.text
        at += len(w.text)
    return Line(page, idx, text, ws, spans)


ROWS = [  # date, debit, credit, balance (as printed)
    ("01/04/2026", "", "50,000.00", "1,50,000.00"),
    ("03/04/2026", "12,500.00", "", "1,37,500.00"),
    ("05/04/2026", "", "8,250.50", "1,45,750.50"),
    ("09/04/2026", "40,000.00", "", "1,05,750.50"),
    ("12/04/2026", "", "1,20,000.00", "2,25,750.50"),
]


def _statement(rows=ROWS, *, source: str = "text_layer", repaired: dict | None = None,
               opening: str = "1,00,000.00", closing: str = "2,25,750.50", extra_lines=()):
    """One page, one statement: the extracted table, its fields, and the page lines."""
    repaired = repaired or {}
    table_rows, repairs = [], []
    for i, (date, debit, credit, balance) in enumerate(rows):
        raw = {"date": date, "debit": debit, "credit": credit, "balance": balance}
        cells = {k: (paise(v) / 100 if v and k != "date" else (v or None)) for k, v in raw.items()}
        if i in repaired:
            col, value = repaired[i]
            repairs.append({"row": i, "column": col, "from": cells[col], "to": value, "page": 1})
            cells[col] = value
        table_rows.append({"cells": cells, "raw": raw, "source": {"page": 1, "bbox": [40, 200 + 20 * i, 560, 212 + 20 * i]}})
    table = {"status": "found", "rows": table_rows, "repairs": repairs}
    fields = {"opening_balance": {"status": "found", "value": paise(opening) / 100, "raw_text": opening, "source": None},
              "closing_balance": {"status": "found", "value": paise(closing) / 100, "raw_text": closing, "source": None}}
    lines = [_line(1, n, words, y=600 + 15 * n) for n, words in enumerate(extra_lines)]
    page = Page(1, source, 595.0, 842.0, [w for l in lines for w in l.words], lines)
    return [page], [{"fields": fields, "tables": {"transactions": table}}]


def _checks(cfg, doc_type="bank_statement", **kw):
    pages, extracted = _statement(**kw)
    return _by_code(arithmetic_checks(_policy(cfg), doc_type, pages, extracted))


def test_money_is_whole_paise_with_indian_grouping():
    assert paise("1,23,456.78") == 12345678 and paise("(500.00)") == -50000 and paise("2,000.00 Dr") == -200000
    assert rupees(12345678) == "1,23,456.78" and rupees(-50) == "-0.50" and paise("n/a") is None


def test_a_statement_whose_figures_add_up_passes_every_check(cfg):
    found = _checks(cfg, extra_lines=[[("Total", 40), ("Credits", 80), ("1,78,250.50", 300)],
                                      [("Total", 40), ("Debits", 80), ("52,500.00", 300)]])
    assert set(found) == set(ARITHMETIC_CHECKS)
    for code in ("BALANCE_CHAIN", "OPENING_BALANCE", "CLOSING_BALANCE", "SUMMARY_TOTALS", "HEADER_ARITHMETIC"):
        assert found[code].status == "pass", (code, found[code].finding)
    assert found["PAGE_CARRY"].status == "not_applicable" and found["BS_BALANCES"].status == "not_applicable"


def test_a_credit_edited_on_a_page_of_text_breaks_the_chain_even_after_repair(cfg):
    # The page prints 58,250.50 where the balances say 8,250.50; extraction repaired
    # the cell back, which would hide the edit: the check reads what is printed.
    rows = list(ROWS)
    rows[2] = ("05/04/2026", "", "58,250.50", "1,45,750.50")
    hit = _checks(cfg, rows=rows, repaired={2: ("credit", 8250.5)})["BALANCE_CHAIN"]
    assert hit.status == "review_required" and not hit.context
    assert "row 3" in hit.evidence[0].observed and hit.evidence[0].rect is not None


def test_a_break_one_misread_explains_on_an_ocr_page_is_listed_not_counted(cfg):
    rows = list(ROWS)
    rows[2] = ("05/04/2026", "", "8,256.50", "1,45,750.50")
    hit = _checks(cfg, rows=rows, source="ocr", repaired={2: ("credit", 8250.5)})["BALANCE_CHAIN"]
    assert hit.status == "warning" and hit.context and "misread" in hit.evidence[0].observed


def test_a_closing_balance_that_does_not_follow_is_found(cfg):
    hit = _checks(cfg, closing="2,52,750.50")["CLOSING_BALANCE"]
    assert hit.status == "review_required" and "2,52,750.50" in hit.evidence[0].observed


def test_a_printed_total_that_disagrees_with_the_rows_is_found(cfg):
    # Printed as a summary row of headings over a row of figures.
    found = _checks(cfg, extra_lines=[[("Opening", 40), ("Total", 140), ("Credits", 180), ("Total", 300),
                                       ("Debits", 340), ("Closing", 450)],
                                      [("1,00,000.00", 40), ("1,98,250.50", 150), ("52,500.00", 310),
                                       ("2,25,750.50", 450)]])
    assert found["SUMMARY_TOTALS"].status == "review_required"
    assert "1,98,250.50" in found["SUMMARY_TOTALS"].evidence[0].observed
    assert found["HEADER_ARITHMETIC"].status == "review_required"


def test_a_carried_forward_figure_that_is_not_the_balance_is_found(cfg):
    hit = _checks(cfg, extra_lines=[[("Balance", 40), ("carried", 90), ("forward", 140), ("2,35,750.50", 300)]])
    assert hit["PAGE_CARRY"].status == "review_required"


def test_a_statement_printed_newest_first_adds_up(cfg):
    found = _checks(cfg, rows=ROWS[::-1])
    assert found["BALANCE_CHAIN"].status == "pass" and "newest first" in found["BALANCE_CHAIN"].finding


def test_columns_read_out_of_place_are_not_called_edits(cfg):
    rows = [(d, c, b, a) for d, a, b, c in ROWS]  # every column shifted
    hit = _checks(cfg, rows=rows * 3)["BALANCE_CHAIN"]
    assert hit.status in ("unable_to_determine", "not_applicable")


def test_other_kinds_of_document_are_not_added_up(cfg):
    found = _checks(cfg, doc_type="company_pan")
    assert all(f.status == "not_applicable" for f in found.values())


def _sheet(total_assets: str, total_liabilities: str):
    rows = [{"cells": {"particulars": p, "current_period": v, "previous_period": "9,10,000"},
             "raw": {"particulars": p, "current_period": v, "previous_period": "9,10,000"},
             "source": {"page": 1, "bbox": [40, 300 + 20 * i, 560, 312 + 20 * i]}}
            for i, (p, v) in enumerate([("Total current assets", "4,00,000"), ("Total Assets", total_assets),
                                        ("Total Equity and Liabilities", total_liabilities)])]
    return [{"fields": {}, "tables": {"balance_sheet": {"status": "found", "rows": rows}}}]


def test_a_balance_sheet_whose_totals_differ_is_found(cfg):
    page = Page(1, "text_layer", 595.0, 842.0)
    ok = _by_code(arithmetic_checks(_policy(cfg), "audited_financial_statements", [page], _sheet("12,40,500", "12,40,500")))
    assert ok["BS_BALANCES"].status == "pass"
    off = _by_code(arithmetic_checks(_policy(cfg), "audited_financial_statements", [page], _sheet("12,40,500", "12,45,500")))
    assert off["BS_BALANCES"].status == "review_required" and "5,000" in off["BS_BALANCES"].evidence[0].observed


def test_every_arithmetic_check_answers_before_the_figures_are_read(cfg):
    from ingestion.stages.integrity_file import run_integrity_file
    from ingestion.stages.integrity_page import NOT_READ, run_integrity_arithmetic, run_integrity_page
    from tests.test_integrity_file import _pdf

    data = _pdf()
    page = run_integrity_page(data, "pdf", run_integrity_file(data, "pdf", cfg.integrity), cfg.integrity, None, set())
    before = _by_code(page.findings)
    assert all(before[c].status == "not_applicable" and before[c].finding == NOT_READ for c in ARITHMETIC_CHECKS)
    pages, extracted = _statement(closing="2,52,750.50")
    after = _by_code(run_integrity_arithmetic(page, cfg.integrity, "bank_statement", pages, extracted).findings)
    assert after["CLOSING_BALANCE"].status == "review_required"
    assert set(after) == set(before)


# --- digital signatures ------------------------------------------------------------------

pyhanko = pytest.importorskip("pyhanko")


def _identity():
    from asn1crypto import keys as akeys
    from asn1crypto import x509 as ax509
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    start = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    name = lambda cn: x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])  # noqa: E731
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca = (x509.CertificateBuilder().subject_name(name("Test Root CA")).issuer_name(name("Test Root CA"))
          .public_key(ca_key.public_key()).serial_number(1).not_valid_before(start)
          .not_valid_after(start + dt.timedelta(days=3650))
          .add_extension(x509.BasicConstraints(True, None), True).sign(ca_key, hashes.SHA256()))
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    cert = (x509.CertificateBuilder().subject_name(name("Test Issuer")).issuer_name(ca.subject)
            .public_key(key.public_key()).serial_number(2).not_valid_before(start)
            .not_valid_after(start + dt.timedelta(days=3650))
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), True)
            .sign(ca_key, hashes.SHA256()))
    asn = lambda c: ax509.Certificate.load(c.public_bytes(serialization.Encoding.DER))  # noqa: E731
    private = akeys.PrivateKeyInfo.load(key.private_bytes(serialization.Encoding.DER,
                                                          serialization.PrivateFormat.PKCS8,
                                                          serialization.NoEncryption()))
    return asn(cert), private, asn(ca)


def _signed(data: bytes) -> bytes:
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import signers
    from pyhanko_certvalidator.registry import SimpleCertificateStore

    cert, key, root = _identity()
    signer = signers.SimpleSigner(signing_cert=cert, signing_key=key,
                                  cert_registry=SimpleCertificateStore.from_certs([root]))
    out = io.BytesIO()
    signers.sign_pdf(IncrementalPdfFileWriter(io.BytesIO(data), strict=False),
                     signers.PdfSignatureMetadata(field_name="Signature1"), signer=signer, output=out)
    return out.getvalue()


def _well_formed() -> bytes:
    """A small PDF as a writer would make it (the signing library reads strictly)."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument.new()
    doc.new_page(595, 842)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _signature_checks(cfg, data):
    from ingestion.integrity.signatures import signature_checks

    return _by_code(signature_checks(_policy(cfg), data))


def test_an_unsigned_file_says_so_and_a_picture_of_a_signature_is_not_one(cfg):
    from tests.test_integrity_file import _pdf

    found = _signature_checks(cfg, _pdf())
    assert found["SIGNATURE_PRESENT"].status == "not_applicable" == found["SIGNATURE_VALID"].status
    assert "picture of a signature" in found["SIGNATURE_VALID"].finding


def test_an_untouched_signed_file_holds_and_names_its_signer(cfg):
    found = _signature_checks(cfg, _signed(_well_formed()))
    assert found["SIGNATURE_PRESENT"].status == "pass" and "Test Issuer" in found["SIGNATURE_PRESENT"].finding
    assert found["SIGNATURE_PRESENT"].context
    assert found["SIGNATURE_VALID"].status == "pass" and "no trust list" in found["SIGNATURE_VALID"].finding


def test_content_replaced_after_signing_does_not_hold(cfg):
    from pyhanko.pdf_utils import generic
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

    writer = IncrementalPdfFileWriter(io.BytesIO(_signed(_well_formed())), strict=False)
    page_ref, _ = writer.find_page_for_modification(0)
    page = page_ref.get_object()
    page["/Contents"] = writer.add_object(generic.StreamObject(stream_data=b"BT /F1 12 Tf 72 700 Td (9,99,999.00) Tj ET"))
    writer.update_container(page)
    out = io.BytesIO()
    writer.write(out)
    hit = _signature_checks(cfg, out.getvalue())["SIGNATURE_VALID"]
    assert hit.status == "review_required" and not hit.context and "not permitted" in hit.evidence[0].observed


def test_bytes_changed_inside_the_signed_range_break_it(cfg):
    signed = bytearray(_signed(_well_formed()))
    at = signed.index(b"842")              # the page's height, in the signed first revision
    signed[at:at + 3] = b"843"
    hit = _signature_checks(cfg, bytes(signed))["SIGNATURE_VALID"]
    assert hit.status == "review_required"


def test_a_signature_is_checked_inside_a_running_event_loop_as_the_service_runs_it(cfg):
    import asyncio

    signed = _signed(_well_formed())

    async def in_the_service():
        return _signature_checks(cfg, signed)

    found = asyncio.run(in_the_service())
    assert found["SIGNATURE_VALID"].status == "pass"
