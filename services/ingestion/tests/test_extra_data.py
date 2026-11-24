"""Story 6.4: what a document prints that no field and no table claimed is kept, each item with its page (scenario 20)."""

from ingestion.config.models import ExtraDataConfig, NumberForms
from ingestion.pageindex import Line, Page, Word
from ingestion.stages.extract import extra
from ingestion.stages.extract.normalise import number_forms


def page(no: int, rows: list[list[tuple[float, str]]]) -> Page:
    lines = []
    for i, cells in enumerate(rows):
        words, spans, text = [], [], ""
        for x, chunk in cells:
            x0 = x
            for w in chunk.split():
                if text:
                    text += " "
                spans.append((len(text), len(text) + len(w)))
                text += w
                words.append(Word(w, x0, 100 + i * 14, x0 + 6 * len(w), 110 + i * 14))
                x0 += 6 * len(w) + 4
        lines.append(Line(no, i, text, words, spans))
    return Page(no, "text_layer", 600, 800, [w for l in lines for w in l.words], lines)


P = page(7, [
    [(40, "Notes to the financial statements")],
    [(40, "Goodwill"), (400, "12,34,567")],
    [(40, "Earnings per equity share")],
    [(40, "Profit for the year"), (400, "8,00,000")],
    [(40, "Weighted average shares"), (400, "1,00,000")],
    [(40, "Basic EPS"), (400, "8.00")],
    [(40, "Diluted EPS"), (400, "8.00")],
    [(40, "The company has no contingent liabilities at the year end and nothing else to state here.")],
])


def collect(claimed=()):
    with number_forms(NumberForms()):
        return extra.collect([P], set(claimed), 20.0, ExtraDataConfig())[0]


def test_scenario_20_a_line_and_a_table_that_match_no_field_are_kept():
    got = collect()
    assert got["pairs"] == [{"label": "Goodwill", "values": ["12,34,567"], "page": 7, "line_id": P.lines[1].id}]
    (table,) = got["tables"]
    assert table["description"] == "Earnings per equity share" and table["described_by"] == "heading"
    assert table["page"] == 7 and table["rows"][0] == ["Profit for the year", "8,00,000"] and len(table["rows"]) == 4


def test_a_line_a_field_or_table_claimed_is_not_extra():
    got = collect(claimed=[P.lines[1].id] + [l.id for l in P.lines[3:7]])
    assert got == {"pairs": [], "tables": []}


def test_a_sentence_is_not_a_pair():
    assert all(p["line_id"] != P.lines[7].id for p in collect()["pairs"])


def test_a_line_of_dates_heads_the_columns_and_a_blank_is_not_a_value():
    p = page(3, [[(40, "6. Borrowings")], [(40, "Particulars"), (300, "31 March 2024"), (450, "31 March 2023")],
                 [(40, "Term loans"), (300, "40,00,000"), (450, "45,00,000")], [(40, "Vehicle loans"), (300, "2,00,000"), (450, "3,00,000")],
                 [(40, "Total"), (300, "42,00,000"), (450, "48,00,000")], [(40, "Verified by: _______________")]])
    with number_forms(NumberForms()):
        got = extra.collect([p], set(), 20.0, ExtraDataConfig())[0]
    (table,) = got["tables"]
    assert table["columns"] == ["Particulars", "31 March 2024", "31 March 2023"] and table["description"] == "6. Borrowings"
    assert table["rows"][0][0] == "Term loans" and len(table["rows"]) == 3
    assert got["pairs"] == []
