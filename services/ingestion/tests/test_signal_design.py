"""The deterministic rules, tested on wording they were not written from.

Each case is a page of text in a layout a real document might use. Nothing here needs the sample
documents or a model: the rules must carry the classification, and the model is only the fallback."""

import copy

import pytest

from ingestion.config.models import IngestionConfig, SignalsConfig
from ingestion.pageindex import Page, Word, build_lines
from ingestion.stages.classify import classify
from ingestion.stages.extract.fields import extract_scalar
from ingestion.stages.extract.normalise import to_date, to_number
from ingestion.stages.instances import split_instances

from .conftest import CONFIG  # noqa: F401  (the session `cfg` fixture is used below)


def page(no: int, *lines: str) -> Page:
    words, y = [], 40.0
    for text in lines:
        x = 40.0
        for tok in text.split():
            words.append(Word(tok, x, y, x + 6 * len(tok), y + 10))
            x += 6 * len(tok) + 4
        y += 16
    return Page(no, "text_layer", 600, 800, words, build_lines(no, words, y_tol=3, column_gap=12, boilerplate=[]))


def kind(cfg, *pages: Page):
    return classify(cfg, list(pages), None)["type"]


# --- a document names itself in many ways --------------------------------------------------------

TITLES = [
    ("income_tax_return", ["INCOME TAX RETURN DOCUMENT SET", "ITR + Computation of Income + Acknowledgement", "Assessment Year 2025-26"]),
    ("income_tax_return", ["ITR-V Acknowledgement", "Assessment Year 2024-25", "PAN AAHCS6612M"]),
    ("income_tax_return", ["Indian Income Tax Return Acknowledgement", "Assessment Year: 2023-24"]),
    ("income_tax_return", ["FORM ITR-6", "Assessment Year 2025-26", "Computation of Total Income"]),
    ("audited_financial_statements", ["Independent Auditor's Report", "To the Members of Southgate Textiles Private Limited", "Balance Sheet", "Statement of Profit and Loss"]),
    ("audited_financial_statements", ["Audited Financial Statements", "for the year ended 31 March 2025", "Balance-Sheet"]),
    ("audited_financial_statements", ["Balance Sheet as at 31 March 2025", "Independent Auditor", "Statement of Profit and Loss"]),
    ("bank_statement", ["Account Statement", "Account No 1234567890", "IFSC ABCD0123456", "Date Narration Withdrawal Deposit Balance"]),
    ("bank_statement", ["Statement of Transactions", "Opening Balance 1,00,000", "Closing Balance 2,00,000"]),
    ("bank_statement", ["Statement of Account", "Opening Balance 1,00,000", "Branch Coimbatore"]),
    ("gstr_3b", ["FORM GSTR-3B", "[See rule 61(5)]", "Return Period March 2025", "GSTIN 33AAHCS6612M1Z5", "ARN AA3303250000001"]),
    ("gstr_3b", ["Monthly Return (GSTR-3B)", "Return Period: Apr 2025", "Outward taxable supplies"]),
    ("board_resolution_borrowing", ["Extract of the Minutes of the Meeting of the Board of Directors", "RESOLVED THAT the company borrow", "Section 179"]),
    ("board_resolution_borrowing", ["Board Resolution", "RESOLVED FURTHER THAT the Directors are authorised to execute", "borrowing"]),
    ("company_pan", ["Permanent Account Number Card", "Income Tax Department", "AAHCS6612M"]),
    ("company_pan", ["Intimation of Allotment of Permanent Account Number", "Income Tax Department", "Assessing Officer"]),
    ("director_kyc", ["DIR-3 KYC", "Director Identification Number 01234567", "Residential Address"]),
    ("certificate_of_incorporation", ["Certificate of Incorporation", "Registrar of Companies, Coimbatore", "Corporate Identity Number U17291TZ2016PTC027431"]),
    ("memorandum_articles_of_association", ["Memorandum and Articles of Association", "Name Clause", "Objects Clause", "Liability Clause"]),
]


@pytest.mark.parametrize("expected,lines", TITLES, ids=[f"{t}-{i}" for i, (t, _) in enumerate(TITLES)])
def test_a_document_is_recognised_by_what_it_is_not_by_one_fixed_phrase(cfg, expected, lines):
    assert kind(cfg, page(1, *lines)) == expected


def test_the_acknowledgement_on_a_late_page_still_counts(cfg):
    cover = page(1, "INCOME TAX RETURN DOCUMENT SET", "Assessment Year 2025-26")
    filler = [page(n, "Particulars", "Amount", "Profit before tax 15,490,378") for n in (2, 3, 4)]
    assert kind(cfg, cover, *filler, page(5, "ITR ACKNOWLEDGEMENT", "Assessment Year 2025-26")) == "income_tax_return"


# --- a mention is not a title --------------------------------------------------------------------


def test_a_passing_mention_in_the_body_does_not_make_a_type(cfg):
    ret = page(1, "INCOME TAX RETURN DOCUMENT SET", "Assessment Year 2025-26", "Taxpayer Southgate", "PAN AAHCS6612M",
               "Status Company", "Registered office Coimbatore", "Figures are taken from the audited financial statements and the Balance Sheet.")
    c = classify(cfg, [ret], None)
    assert c["type"] == "income_tax_return"
    afs = next(x for x in c["candidates"] if x["type"] == "audited_financial_statements") if any(
        x["type"] == "audited_financial_statements" for x in c["candidates"]) else {"score": 0}
    assert afs["score"] < 0.5


def test_a_bank_narration_about_gst_is_not_a_gst_return(cfg):
    stmt = page(1, "Account Statement", "Opening Balance 1,00,000", "Date Narration Withdrawal Deposit Balance",
                "01/04/2025 GSTR-3B PAYMENT 12,000 88,000")
    assert kind(cfg, stmt) == "bank_statement"


def test_a_covering_letter_that_lists_documents_is_not_any_of_them(cfg):
    letter = page(1, "Covering letter", "Enclosed: Certificate of Incorporation, Audited Financial Statements,",
                  "Income Tax Return Acknowledgement, GSTR-3B returns and Statement of Account.")
    assert kind(cfg, letter) is None


def test_a_page_titled_provisional_is_not_audited(cfg):
    assert kind(cfg, page(1, "Provisional Financial Statements", "Balance Sheet as at 30 June 2026", "Unaudited")) is None


# --- the text is normalised before it is matched ---------------------------------------------------


@pytest.mark.parametrize("title", ["Independent Auditor’s Report", "Independent Auditor's​ Report", "INDEPENDENT AUDITOR'S REPORT"])
def test_spacing_case_and_invisible_characters_do_not_matter(cfg, title):
    assert kind(cfg, page(1, title, "Balance Sheet", "Statement of Profit and Loss")) == "audited_financial_statements"


def test_dash_and_ligature_variants_are_folded(cfg):
    assert kind(cfg, page(1, "FORM GSTR‑3B", "Return Period March 2025", "ARN AA3303250000001")) == "gstr_3b"
    assert kind(cfg, page(1, "Audited ﬁnancial statements", "Balance‑Sheet", "Independent Auditor")) == "audited_financial_statements"


# --- instances follow a key, not a phrase ----------------------------------------------------------


def _itr_page(no, ay=None, head="ITR Acknowledgement"):
    return page(no, head, *( [f"Assessment Year {ay}"] if ay else [] ), "Particulars Amount")


def test_one_return_spread_over_pages_is_one_instance(cfg):
    pages = [_itr_page(1, "2025-26", "INCOME TAX RETURN DOCUMENT SET"), _itr_page(2, "2025-26", "FORM ITR-6"),
             _itr_page(3, None, "Computation"), _itr_page(4, "2025-26", "ITR ACKNOWLEDGEMENT")]
    front, groups = split_instances(cfg, "income_tax_return", pages)
    assert front == [] and [[p.no for p in g] for g in groups] == [[1, 2, 3, 4]]


def test_two_years_in_one_file_are_two_instances(cfg):
    pages = [_itr_page(1, "2024-25"), _itr_page(2, None, "Computation"), _itr_page(3, "2025-26"), _itr_page(4, "2025-26")]
    _, groups = split_instances(cfg, "income_tax_return", pages)
    assert [[p.no for p in g] for g in groups] == [[1, 2], [3, 4]]


def test_a_file_with_no_year_is_one_instance_not_front_matter(cfg):
    front, groups = split_instances(cfg, "income_tax_return", [_itr_page(1), _itr_page(2)])
    assert front == [] and len(groups) == 1 and len(groups[0]) == 2


def test_the_year_is_the_same_year_however_it_is_written(cfg):
    pages = [_itr_page(1, "2025-26"), _itr_page(2, "2025 - 2026")]
    assert len(split_instances(cfg, "income_tax_return", pages)[1]) == 1


# --- evidence is weighed, and a wrong type needs a margin ---------------------------------------------


def test_title_without_supporting_evidence_is_below_the_exit_threshold_or_marked_weak(cfg):
    c = classify(cfg, [page(1, "Account Statement")], None)
    top = c["candidates"][0]
    assert top["type"] == "bank_statement"
    assert c["confidence"] <= 0.7  # the title alone is not a confident exit


def test_more_supporting_evidence_means_more_confidence(cfg):
    thin = classify(cfg, [page(1, "Account Statement", "Branch Coimbatore")], None)
    rich = classify(cfg, [page(1, "Account Statement", "Opening Balance 1", "Closing Balance 2", "IFSC ABCD0123456", "Account No 123",
                               "Date Narration Withdrawal Deposit Balance")], None)
    assert rich["confidence"] > thin["confidence"]


# --- the configuration refuses a rule that cannot work ---------------------------------------------------


def _signals(cfg: IngestionConfig, edit) -> dict:
    raw = copy.deepcopy(cfg.signals.model_dump(mode="json"))
    edit(raw)
    return raw


def test_a_named_fragment_must_exist(cfg):
    def edit(raw):
        raw["types"]["gstr_3b"]["supporting"].append({"rx": "{NO_SUCH_THING}", "weight": 1.0})
    with pytest.raises(ValueError, match="unknown pattern"):
        SignalsConfig.model_validate(_signals(cfg, edit))


def test_an_instance_rule_needs_exactly_one_way_of_splitting(cfg):
    def edit(raw):
        raw["types"]["income_tax_return"]["instances"] = {"start": "x", "key_pattern": "(y)", "keys": []}
    with pytest.raises(ValueError, match="exactly one"):
        SignalsConfig.model_validate(_signals(cfg, edit))


def test_a_key_pattern_needs_one_capture_group(cfg):
    raw = _signals(cfg, lambda r: r["types"]["income_tax_return"]["instances"].update(key_pattern="assessment year \\d+"))
    bad = cfg.model_copy(update={"signals": SignalsConfig.model_validate(raw)})
    assert any("one capture group" in p for p in bad.check_consistency())


# --- values: the first candidate that parses wins, and nothing is guessed --------------------------------


@pytest.mark.parametrize("raw,expected", [
    ("15 September 2025 (illustrative)", "2025-09-15"),
    ("15-Sep-2025 10:32:11", "2025-09-15"),
    ("Filed on 15/09/2025", "2025-09-15"),
    ("from 01/04/2024 to 31/03/2025", None),     # a range is not a date
    ("31-02-2025", None),                        # not a calendar date
])
def test_dates_tolerate_a_trailing_note_and_refuse_a_range(raw, expected):
    assert to_date(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    ("4,027,498 (illustrative)", 4027498),
    ("4,027,498 (FY 2025)", 4027498),
    ("(1,234)", -1234),
    ("1,23,456 Dr", -123456),
    ("Rs. 1,000/-", 1000),
    ("4,027,498 as on 31 March 2025", None),     # two quantities: joining the digits would invent a number
])
def test_numbers_never_join_digits_from_a_note(raw, expected):
    assert to_number(raw) == expected


def test_a_label_followed_by_something_that_is_not_a_value_does_not_hide_the_real_one(cfg):
    from ingestion.stages.extract.normalise import normalise

    rule = cfg.fields.types["income_tax_return"].fields["filing_date"]
    pg = page(1, "Date of Filing as shown on the portal", "Date of Filing 15 September 2025")
    found = extract_scalar(rule, [pg], lambda c: normalise(str(c.raw), "date")[1] is None)
    assert found is not None and to_date(str(found.raw)) == "2025-09-15"


def test_label_variants_are_all_understood(cfg):
    rule = cfg.fields.types["income_tax_return"].fields["acknowledgement_number"]
    for label in ("Acknowledgement No.", "Acknowledgement Number", "e-Filing Acknowledgement Number", "Ack No."):
        got = extract_scalar(rule, [page(1, f"{label} 123456789012345")])
        assert got is not None and got.raw == "123456789012345", label


# --- OCR boxes a few points apart still make one row ------------------------------------------------------


def test_words_whose_boxes_overlap_share_a_line_even_when_their_centres_differ():
    words = [Word("Amount", 400, 114, 450, 124), Word("Particulars", 40, 118, 100, 130),
             Word("15,490,378", 400, 137, 470, 147), Word("Profit", 40, 140, 80, 152)]
    tight = build_lines(1, words, y_tol=3, column_gap=12, boilerplate=[])
    scaled = build_lines(1, words, y_tol=3, column_gap=12, boilerplate=[], min_overlap=0.5)
    assert len(tight) == 4
    assert [l.text for l in scaled] == ["Particulars  Amount", "Profit  15,490,378"]


def test_two_lines_of_ordinary_spacing_are_never_merged():
    words = [Word("one", 40, 100, 70, 110), Word("two", 40, 114, 70, 124)]
    assert len(build_lines(1, words, y_tol=3, column_gap=12, boilerplate=[], min_overlap=0.5)) == 2
