from ingestion.stages.extract import identifiers
from ingestion.stages.extract.tables import TableResult, repair_running_balance
from ingestion.stages.validate import validate_instance


def F(v, raw=None):
    return {"status": "found", "value": v, "raw_text": raw if raw is not None else str(v), "method": "pattern", "source": {}, "required": False, "key_field": False}


def M(required=False):
    return {"status": "missing", "reason": "not_found", "value": None, "raw_text": None, "method": None, "source": None, "required": required, "key_field": required}


def outcome(checks, cid):
    return next(c for c in checks if c.id == cid).outcome if any(c.id == cid for c in checks) else None


def get(checks, cid):
    return next((c for c in checks if c["id"] == cid), None)


def test_cin_year_must_match_incorporation_year(cfg):
    ok = validate_instance(cfg, "certificate_of_incorporation", [], {"cin": F("U17291TZ2016PTC027431"), "date_of_incorporation": F("2016-03-18")}, {})
    bad = validate_instance(cfg, "certificate_of_incorporation", [], {"cin": F("U17291TZ2016PTC027431"), "date_of_incorporation": F("2019-03-18")}, {})
    assert get(ok, "cin_year_matches_incorporation")["outcome"] == "pass"
    assert get(bad, "cin_year_matches_incorporation")["outcome"] == "warn"


def test_required_fields_missing_is_a_fail(cfg):
    fields = {f.name: (M(f.required)) for f in cfg.document_types.by_id()["company_pan"].schema_.fields}
    fields["pan"] = F("AAHCS6612M")
    c = get(validate_instance(cfg, "company_pan", [], fields, {}), "required_present")
    assert c["outcome"] == "fail" and "company_name" in c["detail"]


def test_pan_of_a_company_has_c_as_fourth_character(cfg):
    f = {"company_name": F("X"), "pan": F("AAHPS6612M"), "date_of_issue": M()}
    assert get(validate_instance(cfg, "company_pan", [], f, {}), "pan_is_company")["outcome"] == "warn"


def test_statement_period_must_be_in_order(cfg):
    f = {"statement_period_start": F("2026-07-31"), "statement_period_end": F("2025-08-01")}
    assert get(validate_instance(cfg, "bank_statement", [], {**{k.name: M() for k in cfg.document_types.by_id()["bank_statement"].schema_.fields}, **f}, {}), "period_in_order")["outcome"] == "fail"


def table(rows, **kw):
    return {"status": "found", "rows": [{"cells": r, "raw": {}, "source": {}} for r in rows], "repairs": kw.get("repairs", [])}


def test_running_balance_break_is_found(cfg):
    base = {k.name: M() for k in cfg.document_types.by_id()["bank_statement"].schema_.fields}
    rows = [{"debit": None, "credit": None, "balance": 100}, {"debit": None, "credit": 50, "balance": 150}, {"debit": 20, "credit": None, "balance": 999}]
    c = get(validate_instance(cfg, "bank_statement", [], {**base, "closing_balance": F(999)}, {"transactions": table(rows)}), "running_balance")
    assert c["outcome"] == "fail" and "1 of 2 rows break" in c["detail"]
    good = [rows[0], rows[1], {"debit": 20, "credit": None, "balance": 130}]
    c = get(validate_instance(cfg, "bank_statement", [], {**base, "closing_balance": F(130), "opening_balance": F(100)}, {"transactions": table(good)}), "running_balance")
    assert c["outcome"] == "pass"
    c = get(validate_instance(cfg, "bank_statement", [], {**base, "closing_balance": F(131)}, {"transactions": table(good)}), "running_balance")
    assert c["outcome"] == "fail" and "does not agree with the closing balance" in c["detail"]


def test_balance_sheet_totals_must_agree(cfg):
    base = {k.name: M() for k in cfg.document_types.by_id()["audited_financial_statements"].schema_.fields}
    rows = [{"particulars": "TOTAL", "current_period": 100, "previous_period": 90}, {"particulars": "TOTAL", "current_period": 101, "previous_period": 90}]
    checks = validate_instance(cfg, "audited_financial_statements", [], base, {"balance_sheet": table(rows)})
    assert get(checks, "balance_sheet_balances")["outcome"] == "fail" and get(checks, "balance_sheet_balances_previous")["outcome"] == "pass"


def test_identifier_formats_and_checksum():
    assert identifiers.check("pan", "AAHCS6612M")[0] and not identifiers.check("pan", "AAHCS6612")[0]
    assert identifiers.check("masked_pan", "AXXXX1683M")[0] and not identifiers.check("masked_pan", "AAHCS6612M")[0]
    assert identifiers.check("masked_aadhaar", "XXXX XXXX 4471")[0]
    assert identifiers.check("ifsc", "CCBL0004821")[0] and not identifiers.check("ifsc", "CCBL1004821")[0]
    g = "27AAPFU0939F1ZV"  # a published valid GSTIN
    assert identifiers.gstin_checksum_ok(g) and not identifiers.gstin_checksum_ok(g[:-1] + "A")
    ok, detail = identifiers.check("gstin", g[:-1] + "A")
    assert not ok and "check digit" in detail


def _t(rows):
    return TableResult(["debit", "credit", "balance"], [{"cells": r, "raw": {}, "source": {"page": 1}} for r in rows], 1, 1, None)


CFG = {"kind": "running_balance", "debit": "debit", "credit": "credit", "balance": "balance"}


def test_a_single_wrong_balance_cell_is_repaired_arithmetically_and_recorded():
    t = _t([{"debit": None, "credit": None, "balance": 1000}, {"debit": None, "credit": 500, "balance": 1999},
            {"debit": 200, "credit": None, "balance": 1300}])
    repair_running_balance(t, CFG, {})
    assert t.rows[1]["cells"]["balance"] == 1500
    assert t.repairs == [{"row": 1, "column": "balance", "from": 1999, "to": 1500, "page": 1}]


def test_a_single_wrong_amount_cell_is_repaired():
    t = _t([{"debit": None, "credit": None, "balance": 1000}, {"debit": None, "credit": 590, "balance": 1500},
            {"debit": 200, "credit": None, "balance": 1300}])
    repair_running_balance(t, CFG, {})
    assert t.rows[1]["cells"]["credit"] == 500 and t.repairs[0]["column"] == "credit"


def test_a_break_with_no_single_cell_explanation_is_left_alone():
    t = _t([{"debit": None, "credit": None, "balance": 1000}, {"debit": None, "credit": 500, "balance": 1999},
            {"debit": 200, "credit": None, "balance": 1234}])
    repair_running_balance(t, CFG, {})
    assert t.repairs == [] and t.rows[1]["cells"]["balance"] == 1999 and t.rows[1]["cells"]["credit"] == 500


def test_a_break_with_one_explanation_names_it():
    t = _t([{"debit": None, "credit": None, "balance": 1000}, {"debit": None, "credit": 500, "balance": 1999},
            {"debit": 200, "credit": None, "balance": 1799}])
    repair_running_balance(t, CFG, {})
    assert t.repairs[0]["column"] == "credit" and t.repairs[0]["to"] == 999  # the later row continues from 1999
