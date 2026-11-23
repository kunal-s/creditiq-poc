"""Page typing by keywords (Epic 2 of the classification restructure, FRD F-09, decision 14; keywords.yaml).

Scenarios 1 to 4 of the plan, the matching and zone rules, the configuration check, and the switch back to signals."""

import pytest

from ingestion.config.models import KwEntry, KwPart
from ingestion.pageindex import Page, Word, build_lines
from ingestion.stages import keywords as K
from ingestion.stages.classify import classify


def page(no: int, *lines, height: float = 800) -> Page:
    """A digital page: each line is text, or (text, size, bold). Body text is 10 pt; lines start 120 pt down, below the
    header band, unless `top` is given as the first line ("@top")."""
    words, y = [], 120.0
    for line in lines:
        text, size, bold = (line, 10.0, False) if isinstance(line, str) else line
        if text == "@top":
            y = 30.0
            continue
        x = 40.0
        for tok in text.split():
            words.append(Word(tok, x, y, x + 0.6 * size * len(tok), y + size, size=size, bold=bold))
            x += 0.6 * size * len(tok) + 4
        y += size * 1.6
    return Page(no, "text_layer", 600, height, words, build_lines(no, words, y_tol=3, column_gap=12, boilerplate=[]))


def kind(cfg, *pages):
    return classify(cfg, list(pages), None)["type"]


@pytest.fixture(scope="module")
def kcfg(cfg):
    assert cfg.uses_keywords(), "the published lists type documents (keywords.yaml settings.classifier)"
    return cfg


# --- normalising (Story 2.2) ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw, folded", [
    ("STATEMENT OF ACCOUNT", "statement of account"),
    ("Bal-\nance Sheet", "balance sheet"),                     # a word broken by a hyphen at a line end
    ("S T A T E M E N T of account", "statement of account"),  # spaced-out letters
    ("Audited ﬁnancial statements", "audited financial statements"),   # a ligature
    ("B0ARD RES0LUTION", "board resolution"),                  # a scan's 0 for O inside a word
    ("Auditor’s Report", "auditors report"),
    ("FORM GSTR‑3B", "form gstr 3b"),                         # a non-breaking hyphen; a code keeps its digit
])
def test_text_is_folded_before_it_is_matched(raw, folded):
    assert K.fold(raw) == folded


# --- matching (Story 2.3) ---------------------------------------------------------------------------------------------

def _hit(kcfg, phrase, text, *, exact=False):
    z = K.Zones(text, "", "")
    return K._found(kcfg.keywords, KwEntry(phrase=phrase), z, "title", exact=exact)


def test_a_long_phrase_matches_a_near_spelling_word_by_word(kcfg):
    assert _hit(kcfg, "statement of account", "Statemcnt of Account")
    assert _hit(kcfg, "statement of account", "State ment of Account")          # a word split by a scan
    assert not _hit(kcfg, "unaudited financial statements", "Audited Financial Statements")   # an opposite, not a misspelling
    assert not _hit(kcfg, "udyam registration certificate", "Registration Certificate of Establishment")


def test_a_short_word_matches_only_exactly(kcfg):
    assert _hit(kcfg, "pan card", "PAN Card")
    assert not _hit(kcfg, "pan card", "PAD Card")
    assert not _hit(kcfg, "neft", "NEXT")


def test_a_warning_matches_only_exactly(kcfg):
    assert _hit(kcfg, "unaudited", "Unaudited", exact=True)
    assert not _hit(kcfg, "unaudited", "Unaudlted", exact=True)


# --- zones (Story 2.1) ------------------------------------------------------------------------------------------------

def test_a_title_is_found_by_its_print_wherever_it_sits(kcfg):
    p = page(1, "Particulars as follows", ("Balance Sheet as at 31 March 2026", 14.0, True), "Share capital 50,00,000")
    z = K.zones(kcfg.keywords, p)
    assert "Balance Sheet" in z.title and "Share capital" not in z.title


def test_a_table_row_is_never_a_title(kcfg):
    p = page(1, "@top", "20 Jan 2026 GST PMT GSTR-3B JAN 55 22,46,000 66,91,650", "21 Jan 2026 NEFT CR 13,43,000 80,34,650")
    assert K.zones(kcfg.keywords, p).title == ""


# --- scenarios 1 to 4 (Stories 2.4, 2.5) ------------------------------------------------------------------------------

def test_scenario_1_a_reworded_title_is_still_a_balance_sheet(kcfg):
    p = page(1, ("Statement of Financial Position as at 31 March 2026", 14.0, True), "Equity and liabilities",
             "Share capital 50,00,000", "Other equity 4,12,00,000", "Trade payables 1,48,00,000", "Inventories 2,16,00,000")
    assert K._best_part(K.part_scores(kcfg.keywords, p)) == "balance_sheet"
    assert kind(kcfg, p) == "audited_financial_statements"     # statements that do not say provisional are audited


def test_scenario_2_a_title_only_in_the_footer_counts(kcfg):
    # Three lines from 120 pt down a 160 pt page: the last one sits in the footer band.
    p = page(1, "Account Number 602010345567", "IFSC HCBL0004417", "Statement of Account - page 2", height=160)
    z = K.zones(kcfg.keywords, p)
    assert "Statement of Account" in z.footer and not z.title
    assert kind(kcfg, p) == "bank_statement"


@pytest.mark.parametrize("title", ["B0ARD RES0LUTION", "Certified true c0py of the res0lution", "B O A R D  R E S O L U T I O N"])
def test_scenario_3_scan_errors_do_not_hide_the_type(kcfg, title):
    p = page(1, (title, 14.0, True), "RESOLVED THAT the consent of the Board be and is hereby accorded to borrow",
             "RESOLVED FURTHER THAT the Directors are authorised to execute")
    assert kind(kcfg, p) == "board_resolution_borrowing"


def test_scenario_4_look_alikes_are_told_apart(kcfg):
    prov = page(1, ("Provisional Financial Statements", 14.0, True), ("Balance Sheet as at 30 September 2026", 12.0, True),
                "Unaudited", "Share capital 50,00,000", "Trade payables 1,48,00,000")
    assert kind(kcfg, prov) == "provisional_financial_statements"
    pad = page(1, ("PAD PRINTING ORDER", 14.0, True), "Permanent address", "Account of the order")
    assert kind(kcfg, pad) is None


# --- configuration (Story 1.9) and the switch -------------------------------------------------------------------------

def test_the_configuration_check_names_what_is_wrong(kcfg):
    bad = kcfg.model_copy(deep=True)
    bad.keywords.parts["transactions"].warning.append(KwEntry(phrase="opening balance"))
    bad.keywords.types["bank_statement"].parts.append("no_such_part")
    del bad.keywords.types["gstr_1"]
    problems = bad.check_consistency()
    assert any("'opening balance' is both a keyword and a warning word" in p for p in problems)
    assert any("unknown part no_such_part" in p for p in problems)
    assert any("no entry for document type gstr_1" in p for p in problems)


def test_adding_a_keyword_places_a_missed_page_with_no_code_change(kcfg):
    p = page(1, ("Inventory and Receivables Position", 14.0, True), "Item A 1,86,42,300", "Item B 1,80,69,000")
    assert kind(kcfg, p) is None
    fixed = kcfg.model_copy(deep=True)
    fixed.keywords.parts["stock_statement"].title.append(KwEntry(phrase="inventory and receivables position"))
    q = page(1, ("Inventory and Receivables Position", 14.0, True), "Item A 1,86,42,300", "Item B 1,80,69,000")
    assert kind(fixed, q) == "stock_statement"


def test_the_signals_still_type_documents_when_the_switch_says_so(kcfg):
    from .conftest import fixture_doc
    from ingestion.stages.read import read_document
    old = kcfg.model_copy(deep=True)
    old.keywords.settings.classifier = "signals"
    assert not old.uses_keywords()
    pages = read_document(fixture_doc("Southgate_Audited_FS_FY2025.pdf"), "pdf", old.quality, old.routing, None)
    a, b = classify(old, pages, None), classify(kcfg, pages, None)
    assert a["type"] == b["type"] == "audited_financial_statements"
    assert "part" not in a["signals"] and b["signals"]["part"]


def test_a_part_that_needs_its_title_scores_nothing_without_it(kcfg):
    p = page(1, "Registered Office: Plot 47", "Corporate Identity Number U17291TZ2016PTC027431", "Companies Act, 2013")
    assert K.part_scores(kcfg.keywords, p)["incorporation_certificate"].score == 0
    assert isinstance(kcfg.keywords.parts["incorporation_certificate"], KwPart)


# --- Story 2.6: identifiers read through a scan's confusion, confirmed by a check -----------------------------------

def _scan(cfg, kind, *lines):
    from ingestion.config.models import FieldRule
    from ingestion.stages.extract.fields import extract_scalar
    return extract_scalar(FieldRule(identifier=kind), [page(1, *lines)], None, cfg.fields.identifier_reading)


def test_scenario_22_a_gstin_with_o_for_zero_is_read_on_its_check_digit(cfg):
    from .docsets import gstin_with_check
    good = gstin_with_check("27AAACK1234F1Z")
    printed = good[:7] + "I" + good[8:]            # the 1 of 1234 read as an I
    f = _scan(cfg, "gstin", f"GSTIN {printed}")
    assert f is not None and f.raw == printed and f.corrected == good


def test_a_reading_the_check_digit_refuses_is_not_taken(cfg):
    from .docsets import gstin_with_check
    good = gstin_with_check("27AAACK1234F1Z")
    wrong = good[:14] + ("A" if good[14] != "A" else "B")
    assert _scan(cfg, "gstin", f"GSTIN {wrong[:7]}I{wrong[8:]}") is None


def test_a_pan_is_read_only_when_a_gstin_of_the_same_document_carries_it(cfg):
    from .docsets import gstin_with_check
    gstin = gstin_with_check("27AAACK1234F1Z")
    f = _scan(cfg, "pan", "PAN AAACKI234F", f"GSTIN {gstin}")
    assert f is not None and (f.raw, f.corrected) == ("AAACKI234F", "AAACK1234F")
    assert _scan(cfg, "pan", "PAN AAACKI234F") is None     # nothing on the document confirms it


def test_a_value_printed_in_the_format_is_read_as_printed(cfg):
    f = _scan(cfg, "pan", "PAN AAACK1234F")
    assert f is not None and f.corrected is None and f.raw == "AAACK1234F"
