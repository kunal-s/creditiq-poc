"""Page typing (Epic 3 of the classification restructure; FRD F-08.1, F-09): scenarios 5 to 11 and 32 of the plan."""

from ingestion.contracts import FileSpec
from ingestion.llm.openai import FixtureProvider
from ingestion.llm.recorder import ModelClient
from ingestion.pipeline import Ingestor
from ingestion.stages import pages as P
from ingestion.store import Store
from ingestion.util import sha256_hex

from . import model_answers
from .test_keywords import page

B = 14.0   # a title's size; body text is 10 pt


def title(text):
    return (text, B, True)


COI = [title("Certificate of Incorporation"), "Registrar of Companies, Mumbai", "Corporate Identity Number U28999MH2015PTC123456",
       "is incorporated under the Companies Act, 2013 and the company is limited by shares"]
PAN = [title("Intimation of Allotment of Permanent Account Number"), "Income Tax Department", "PAN AAACK1234F",
       "Assessing Officer Ward 1(1)"]
KYC = [title("Director KYC"), "Director Identification Number 01234567", "Date of birth 01 January 1970", "Residential address Mumbai"]
BS = [title("Balance Sheet as at 31 March 2026"), "Equity and liabilities", "Share capital 50,00,000", "Reserves and surplus 4,12,00,000",
      "Trade payables 1,48,00,000", "Inventories 2,16,00,000"]
PL = [title("Statement of Profit and Loss for the year ended 31 March 2026"), "Revenue from operations 23,60,00,000",
      "Other income 12,00,000", "Finance costs 32,00,000", "Profit before tax 1,54,00,000"]
BANK = [title("Statement of Account"), "Account Number 602010345567", "IFSC HCBL0004417", "Opening balance 2,50,00,000",
        "03 Apr 2025 NEFT CR PRAGATI TOOLING 64,40,000 3,14,40,000"]
ROWS = ["11 Apr 2025 NEFT CR BHARAT PUMPS 73,60,000 2,72,67,000", "14 Apr 2025 RTGS DR VENDOR 18,40,000 2,54,27,000"]


def typed(cfg, *pages, model=None):
    return P.type_pages(cfg, list(pages), model)


def test_scenario_5_financial_pages_after_the_first_n_are_still_found(cfg):
    pages = [page(1, *COI), page(2, *PAN), page(3, *KYC), page(4, *KYC), page(5, *BS), page(6, *PL)]
    t = typed(cfg, *pages)
    assert t.categories[0] == "identity" and "financials" in t.categories
    assert [t.types_of(n) for n in range(1, 7)] == [["certificate_of_incorporation"], ["company_pan"], ["director_kyc"],
                                                      ["director_kyc"], ["audited_financial_statements"], ["audited_financial_statements"]]
    assert t.pages[5][0].placed_by == "all_types"       # outside the categories the first pages chose


def test_scenario_6_an_index_page_naming_every_document_is_not_each_of_them(cfg):
    index = page(1, title("Documents enclosed"), title("Certificate of Incorporation"), title("Balance Sheet"),
                 title("Statement of Account"), title("Sanction Letter"))
    t = typed(cfg, index, page(2, *COI))
    assert t.types_of(1) == [] and t.pages[1][0].placed_by == "index"
    assert t.types_of(2) == ["certificate_of_incorporation"]


def test_scenario_7_an_untitled_middle_page_takes_its_neighbours_type(cfg):
    t = typed(cfg, page(1, *BS), page(2, "Item A 1,00,000", "Item B 2,00,000"), page(3, *PL))
    assert t.types_of(2) == ["audited_financial_statements"] and t.pages[2][0].placed_by == "continued"


def test_scenario_8_a_table_running_onto_a_page_with_no_title_keeps_its_type(cfg):
    t = typed(cfg, page(1, *BANK), page(2, *ROWS))
    assert t.types_of(2) == ["bank_statement"]


def test_scenario_9_the_end_of_one_statement_and_the_start_of_the_next_on_one_page(cfg):
    p = page(1, *BS[1:], *PL)                          # the balance sheet's last rows, then the profit and loss opens
    t = typed(cfg, page(0, *BS), p)
    info = t.page_info(1)
    assert [s["part"] for s in info["sections"]] == ["balance_sheet", "profit_and_loss"]
    assert info["types"] == ["audited_financial_statements"]


def test_scenario_32_two_documents_on_one_page_are_both_read(cfg):
    sanction = [title("Sanction Letter"), "We are pleased to sanction the following credit facility",
                "Sanctioned amount Rs 2,50,00,000", "Rate of interest 10.5% per annum", "Tenure 60 months"]
    bureau = [title("Commercial Credit Information Report"), "Credit rank 4", "Days past due 0", "Related parties", "Report date 10 October 2026"]
    t = typed(cfg, page(1, *sanction, *bureau))
    assert t.types_of(1) == ["sanction_letter", "commercial_bureau_report"]
    runs, _ = P.documents(t, [page(1, *sanction, *bureau)])
    assert [(ty, [p.no for p in ps]) for ty, ps in runs] == [("commercial_bureau_report", [1]), ("sanction_letter", [1])]


def test_scenario_10_a_document_of_no_known_type_is_kept_with_its_best_guesses(cfg):
    data = _pdf(cfg, ["DEED OF LEASE", "This deed of lease is made between the lessor and the lessee", "Monthly rent Rs 3,55,000"])
    r = Ingestor(cfg, Store(), None, None).process_file("C", FileSpec(file_id="f", sha256=sha256_hex(data), original_name="x.pdf",
                                                                      content_type="application/pdf"), data)
    assert r.documents == [] and r.decision == "human_review"
    assert r.unplaced and r.unplaced[0]["pages"] == [1] and len(r.unplaced[0]["candidates"]) <= 3
    assert r.review_reasons[0]["kind"] == "type_unassigned"


def test_scenario_11_a_page_only_the_model_can_place_is_placed_and_replayed(cfg):
    def answer(req):
        if req.task == "classify_page":
            return {"type": "sanction_letter", "reason": "a lender's offer of a facility"}
        return model_answers.answerer(req)
    store = Store()
    odd = page(1, "Dear Sir, with reference to your request", "Facility amount Rs 2,50,00,000", "Yours faithfully")
    rec = ModelClient(FixtureProvider(cfg.llm, answer), "record", store)
    assert typed(cfg, odd, model=rec).types_of(1) == ["sanction_letter"]
    rep = ModelClient(FixtureProvider(cfg.llm, lambda req: {}), "replay", store)
    again = typed(cfg, page(1, "Dear Sir, with reference to your request", "Facility amount Rs 2,50,00,000", "Yours faithfully"), model=rep)
    assert again.types_of(1) == ["sanction_letter"] and again.pages[1][0].placed_by == "model" and rep.calls == 0


def test_the_model_is_overruled_by_a_title_warning_on_the_page(cfg):
    def answer(req):
        return {"type": "bank_statement", "reason": "rows of amounts"}
    store = Store()
    p = page(1, title("Balance Sheet"), "Item 1,00,000")       # a bank statement is ruled out by a balance sheet title
    cfg2 = cfg.model_copy(deep=True)
    for d in cfg2.document_types.documents:
        if d.document_type in ("audited_financial_statements", "provisional_financial_statements", "projected_financial_statements"):
            d.enabled = False
    t = typed(cfg2, p, model=ModelClient(FixtureProvider(cfg2.llm, answer), "record", store))
    assert t.types_of(1) == [] and "balance sheet" in (t.pages[1][0].note or "")


def test_gap_fill_takes_an_unplaced_page_between_two_of_one_type(cfg):
    off = cfg.model_copy(deep=True)
    for d in off.document_types.documents:
        if d.document_type == "projected_financial_statements":
            d.enabled = False
    gap = page(2, title("Key assumptions"), "Growth rate as assumed")      # a titled page of a switched-off type
    t = typed(off, page(1, *BANK), gap, page(3, *BANK))
    assert t.types_of(2) == ["bank_statement"] and t.pages[2][0].placed_by == "gap"


def test_an_acknowledgement_filed_with_its_computation_carries_both_types_and_is_read_once(cfg):
    ack = page(1, title("Indian Income Tax Return Acknowledgement"), "Assessment Year 2025-26", "Acknowledgement Number 123456789012",
               "PAN AAACK1234F")
    comp = page(2, title("Computation of Total Income"), "Gross total income 1,54,90,378", "Deductions under Chapter VI-A 0",
                "Total tax payable 40,27,498", "Assessment Year 2025-26")
    t = typed(cfg, ack, comp)
    assert set(t.types_of(1)) == {"itr_acknowledgement", "income_tax_return"}
    runs, _ = P.documents(t, [ack, comp])
    assert [(ty, [p.no for p in ps]) for ty, ps in runs] == [("income_tax_return", [1, 2])]
    alone = typed(cfg, page(1, title("Indian Income Tax Return Acknowledgement"), "Assessment Year 2025-26",
                            "Acknowledgement Number 123456789012", "PAN AAACK1234F"))
    assert alone.types_of(1) == ["itr_acknowledgement"]


def _pdf(cfg, lines: list[str]) -> bytes:
    from .docsets import one_page
    return one_page([[(40, t)] for t in lines])
