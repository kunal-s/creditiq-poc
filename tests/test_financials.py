import yaml

from engine.samplegen.financials import build
from engine.samplegen.schema import CaseDescriptor


def _load(case_id: str) -> CaseDescriptor:
    data = yaml.safe_load(open(f"sample-data/cases/{case_id}/case.yaml"))
    return CaseDescriptor.model_validate(data)


def _existing_term_debt(d: CaseDescriptor) -> int:
    return sum(
        f.amount for f in d.facilities_existing if f.type in ("term_loan", "vehicle_loan")
    )


def test_case_a_balance_sheet_foots_every_year():
    d = _load("case-a")
    fin = build(d.financial_model, existing_term_debt_opening=_existing_term_debt(d))
    for fy, year in fin.years.items():
        assets = year.bs.ppe + year.bs.inventories + year.bs.receivables + year.bs.cash
        assert assets == year.bs.total, f"FY{fy} does not foot"


def test_case_b_balance_sheet_foots_every_year():
    d = _load("case-b")
    fin = build(d.financial_model, existing_term_debt_opening=_existing_term_debt(d))
    for fy, year in fin.years.items():
        assets = year.bs.ppe + year.bs.inventories + year.bs.receivables + year.bs.cash
        assert assets == year.bs.total, f"FY{fy} does not foot"


def test_net_worth_rolls_forward_exactly():
    for case_id in ["case-a", "case-b"]:
        d = _load(case_id)
        fin = build(d.financial_model, existing_term_debt_opening=_existing_term_debt(d))
        years = sorted(fin.years)
        prior_nw = d.financial_model.net_worth_opening
        for fy in years:
            y = fin.years[fy]
            assert y.bs.net_worth == prior_nw + y.pl.pat, f"{case_id} FY{fy} net worth does not roll forward"
            prior_nw = y.bs.net_worth


def test_pl_waterfall_reconciles():
    for case_id in ["case-a", "case-b"]:
        d = _load(case_id)
        fin = build(d.financial_model, existing_term_debt_opening=_existing_term_debt(d))
        for fy, y in fin.years.items():
            pl = y.pl
            assert pl.pbt == pl.ebitda - pl.depreciation - pl.finance_costs
            assert pl.pat == pl.pbt - pl.tax


def test_no_negative_borrowings_or_cash():
    for case_id in ["case-a", "case-b"]:
        d = _load(case_id)
        fin = build(d.financial_model, existing_term_debt_opening=_existing_term_debt(d))
        for fy, y in fin.years.items():
            assert y.bs.borrowings_st >= 0, f"{case_id} FY{fy} negative CC utilisation"
            assert y.bs.borrowings_lt >= 0, f"{case_id} FY{fy} negative term debt"
            assert y.bs.cash >= 0, f"{case_id} FY{fy} negative cash"


def test_case_a_ratios_sit_within_policy_bands_on_latest_year():
    """Case A's rating is meant to be pulled down by the planted findings'
    evidence-quality overlay, not by weak fundamentals — the latest year's
    ratios should clear the acceptable band on their own."""
    d = _load("case-a")
    fin = build(d.financial_model, existing_term_debt_opening=_existing_term_debt(d))
    latest = max(fin.years)
    ratios = fin.ratios(latest)
    assert ratios["current-ratio"] >= 1.2
    assert ratios["tol-tnw"] <= 3.0
    assert ratios["dscr"] >= 1.5


def test_case_b_current_ratio_is_acceptable_on_latest_year():
    d = _load("case-b")
    fin = build(d.financial_model, existing_term_debt_opening=_existing_term_debt(d))
    latest = max(fin.years)
    assert fin.ratios(latest)["current-ratio"] >= 1.2
