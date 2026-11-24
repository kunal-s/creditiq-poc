"""Story 6.6: a model's value is matched to its line by what it is, and the printed text is kept (scenario 30)."""

import pytest

from ingestion.config.models import NumberForms
from ingestion.stages.extract import printed
from ingestion.stages.extract.normalise import number_forms


@pytest.fixture(autouse=True)
def forms():
    with number_forms(NumberForms()):
        yield


def shown(raw, text, ratio=90):
    hit = printed.find(raw, text, ratio)
    return None if hit is None else text[hit[0]:hit[1]]


def test_scenario_30_a_figure_written_without_its_separators_is_the_figure_printed():
    assert shown("123456", "Revenue from operations   1,23,456   98,765") == "1,23,456"


def test_the_sign_must_agree():
    assert shown("-123456", "Profit for the year  (1,23,456)") == "(1,23,456)"
    assert shown("123456", "Profit for the year  (1,23,456)") is None


def test_another_figure_on_the_line_is_not_taken():
    assert shown("123457", "Revenue from operations   1,23,456") is None


def test_a_date_written_in_another_form_is_the_date_printed():
    assert shown("2024-03-31", "Balance Sheet as at 31st March, 2024") == "31st March, 2024"
    assert shown("2024-03-30", "Balance Sheet as at 31st March, 2024") is None


def test_text_within_the_ratio_is_the_text_printed():
    line = "Name of the Company: SOUTHGATE ENGINEERING PVT. LTD."
    assert shown("Southgate Engineering Pvt Ltd", line).upper().startswith("SOUTHGATE ENGINEERING PVT")
    assert shown("Northgate Trading Co", line) is None


def test_an_exact_match_is_kept_as_printed():
    assert shown("aaacb1234c", "PAN: AAACB1234C") == "AAACB1234C"
