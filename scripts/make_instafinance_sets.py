"""Document sets for one company whose figures come from an InstaFinance (BRisk-FIN) company report, drawn on the
real-document templates (the GigsTech sample folder; scripts/tpl_*.py and realistic_docs.py):

  1_clean_pass_everything/        a complete, consistent file: every figure agrees, every document present and current
  2_TC-21_turnover_fail/          the same file with TC-21's turnover gaps planted
  3_TC-22_accounts_differ/        the clean file with a second declared account (Orchid Cooperative Bank) that has no
                                  statement, and a statement for an account not declared (Meridian Trust Bank)
  4_TC-24_request_over_20pct/     Rs 4.95 Cr asked on Rs 24.16 Cr turnover (20.5%): every amount of the report scaled by
                                  one factor so that FY2025-26 revenue is Rs 24.16 Cr; ratios and proportions unchanged

From the report: the three latest audited years (profit and loss, balance sheet, the schedules of borrowings, loans
and advances, expenses and revenue mix), the comparative year before them, the paid-up and authorised capital, the
incorporation date, the number and roles of the directors, the state and the line of business. The report's latest
years are placed one year later (its FY2022-23, FY2023-24 and FY2024-25 become FY2023-24, FY2024-25 and FY2025-26)
so that the file is current for a case opened in November 2026.

Fictional, never the report's (CLAUDE.md rule 8; a generated government document must not carry a real company's
identity): the company's name, PAN, CIN number, GSTIN, TAN, address, directors' names, DINs and addresses, and the bank
account. The auditor, the bank and the lender are the pack's fictional ones.

Derived, because the report does not carry them: the monthly GST returns (each year's revenue from operations spread
over its months; the months after March 2026 continue at FY2025-26's level), the bank statement (credits equal to the
month's outward supplies), the split of current liabilities and provisions (70% trade payables, 8% provisions, the
rest other current liabilities), the gross block (net block x 1.38), the shareholding among the directors, and the
existing term loan (sanctioned Rs 20 Cr over 72 months, outstanding the year's long-term borrowings).

    cd services/ingestion && PYTHONPATH=.:../../scripts:<dir holding reportlab> \\
        .venv/bin/python ../../scripts/make_instafinance_sets.py REPORT.json OUT_DIR [SET_ID ...]
"""

from __future__ import annotations

import calendar
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path

_args = sys.argv[1:]
sys.argv = sys.argv[:1]
import make_test_pack as M          # noqa: E402  (moves the dates to the November 2026 case and installs the builders)
import realistic_docs as R          # noqa: E402
import tpl_annual_report as AR      # noqa: E402
import tpl_memorandum as MOA        # noqa: E402
from tests import docsets as D      # noqa: E402

SHIFT = {"2021-2022": 2023, "2022-2023": 2024, "2023-2024": 2025, "2024-2025": 2026}   # report year -> FY end used


def load(path: Path) -> dict:
    rd = json.loads(path.read_text())["ReportData"]
    fin = rd["ComparativeFinancialsStandalone"]
    sch = rd["SchedulesAndDisclosuresFinancialsInfo"]

    def series(lst) -> dict[str, float]:
        return {x["FinancialYear"]: float(x.get("Amount") or 0) for x in lst or []}

    pl = {k: series(v) for k, v in fin["ProfitAndLossStatement"].items()}
    bs = {k: series(v) for k, v in fin["BalanceSheetStandalone"].items() if isinstance(v, list)}
    exp = {k: series(v) for k, v in sch["ExpenseBreakup"].items() if isinstance(v, list)}
    lna = {k: series(v) for k, v in sch["LoansAndAdvancesSchedulesAndDisclosures"].items() if isinstance(v, list)}
    dom = {k: series(v) for k, v in sch["RevenueFromOperations"]["DomesticTurnover"].items()}
    brw = sch["Borrowings"]
    borrow = {"secured": series(brw["SecuredBorrowings"]["TotalSecuredBorrowings"]),
              "secured_st_banks": series(brw["SecuredBorrowings"]["SecuredBorrowingsShortTerm"]["LoansRepayableOnDemandFromBanks"]),
              "unsecured": series(brw["UnsecuredBorrowings"]["TotalUnsecuredBorrowings"])}
    other_exp = {k: series(v) for k, v in sch["OtherExpense"].items() if isinstance(v, list)}
    ageing = {"over6": series(sch["TradeReceivablesAgeing"]["DueExceedingSixMonths"]["NetTradeReceivables"]),
              "upto6": series(sch["TradeReceivablesAgeing"]["DueUptoSixMonths"]["NetTradeReceivables"])}
    interest = series(sch["FinanceCost"]["InterestOnBorrowings"])
    master = rd["CorporateDirectory"]["CompanyMaster"]
    directors = rd["DirectorKYCAndNetworks"].get("CurrentDirectors") or []
    return {"pl": pl, "bs": bs, "exp": exp, "lna": lna, "dom": dom, "borrow": borrow, "other_exp": other_exp,
            "ageing": ageing, "interest": interest,
            "paid_up": float(master["PaidupCapital"]), "authorised": float(master["AuthorizedCapital"]),
            "incorporated": str(master["DateOfIncorporation"])[:10],
            "designations": [d.get("Designation") or "Director" for d in directors],
            "address": str(master.get("Address") or "")}


def scaled(r: dict, revenue: float) -> dict:
    """The report with every amount multiplied by one factor, so that its latest revenue from operations is `revenue`
    (each amount rounded to the thousand, as the statements print). The company's facts (paid-up and authorised
    capital, incorporation, directors) are not amounts of the business and stay as reported; reserves take the
    difference, so net worth scales with the rest."""
    k = revenue / r["pl"]["OperatingRevenues"]["2024-2025"]
    amount = lambda v: round(v * k / 1000) * 1000  # noqa: E731

    def walk(o):
        if isinstance(o, dict):
            return {key: walk(v) for key, v in o.items()}
        return amount(o) if isinstance(o, float) else o

    out = dict(r)
    for key in ("pl", "bs", "exp", "lna", "dom", "borrow", "other_exp", "ageing", "interest"):
        out[key] = walk(r[key])
    out["factor"] = k
    return out


def year_figures(r: dict, y: str) -> tuple[dict, dict]:
    """The report's year y as the annual report builder takes it (rupees)."""
    pl, bs, exp, lna = r["pl"], r["bs"], r["exp"], r["lna"]
    pnl = {"rev": pl["OperatingRevenues"][y], "oi": pl["OtherIncomes"][y], "mat": exp["CostOfMaterialsConsumed"][y],
           "emp": exp["EmployeeBenefitExpenses"][y], "fin": pl["Interests"][y], "dep": pl["Depreciations"][y],
           "pbt": pl["PBT"][y], "tax": pl["Taxes"][y], "adj": pl.get("OtherAdjustments", {}).get(y, 0.0)}
    stb = bs["CurrentLiabilities"][y] - bs["CurrentLiabilitiesAndProvisions"][y]
    clp = bs["CurrentLiabilitiesAndProvisions"][y]
    deferred = bs["DeferredTaxLiabilityOfAssets"][y]
    sheet = {"sc": r["paid_up"], "res": bs["NetWorth"][y] - r["paid_up"], "ltb": bs["Borrowings"][y] - stb, "stb": stb,
             "dtl": max(0.0, deferred), "oltl": bs["OtherNonCurrentLiabilities"][y], "tp": clp * 0.70, "stp": clp * 0.08,
             "ppe": bs["TangibleAssets"][y] + bs["IntangibleAssets"][y], "cwip": bs["CapitalWIPAndOthers"][y],
             "ncinv": bs["Investments"][y], "dta": max(0.0, -deferred), "onca": lna["LongTermLoansAndAdvances"][y],
             "inv": bs["Inventories"][y], "tr": bs["TradeReceivables"][y], "cash": bs["CashAndBankBalances"][y],
             "stla": lna["ShortTermLoansAndAdvances"][y], "oca": bs["OtherAssets"][y]}
    return policy_ready(r, y, sheet, pnl)


# --- the two of the bank's norms the report's own figures breach ------------------------------------------------
# The report's receivables are close to a year's revenue (a working-capital cycle of 202 days against the norm of at
# most 75) and its interest cover in its latest year is 2.36x (norm at least 2.50x). A clean file must meet every
# norm, so two figures are moved within the statements, each by one rule for every year, leaving every total, the
# turnover, the profit and the current ratio as the report has them:
#   - receivables above a 70-day cycle are shown as unbilled revenue, in other current assets;
#   - finance costs above what gives 2.8x interest cover are shown in other expenses.
CYCLE_DAYS, COVER = 70, 2.8


def policy_ready(r: dict, y: str, sheet: dict, pnl: dict) -> tuple[dict, dict]:
    adjusted = r.setdefault("adjusted", {})
    days = (sheet["inv"] + sheet["tr"] - sheet["tp"]) / pnl["rev"] * 365 if pnl["rev"] else 0
    if days > CYCLE_DAYS:
        tr = int(CYCLE_DAYS / 365 * pnl["rev"] + sheet["tp"] - sheet["inv"]) // 1000 * 1000
        moved = sheet["tr"] - tr
        adjusted[(y, "TradeReceivables")] = (sheet["tr"], tr, f"working-capital cycle {days:.0f} days; {moved / 1e7:,.2f} Cr "
                                                              f"shown as unbilled revenue in other current assets")
        adjusted[(y, "OtherAssets")] = (sheet["oca"], sheet["oca"] + moved, "takes the unbilled revenue moved out of "
                                                                            "trade receivables")
        sheet = {**sheet, "tr": tr, "oca": sheet["oca"] + moved}
    if pnl["fin"] and (pnl["pbt"] + pnl["fin"]) / pnl["fin"] < COVER:
        fin = int(pnl["pbt"] / (COVER - 1)) // 1000 * 1000
        adjusted[(y, "Interests")] = (pnl["fin"], fin, f"interest cover {(pnl['pbt'] + pnl['fin']) / pnl['fin']:.2f}x; "
                                                       f"{(pnl['fin'] - fin) / 1e7:,.2f} Cr shown in other expenses")
        pnl = {**pnl, "fin": fin}
    return sheet, pnl


OTHER_EXPENSE_LINES = (("Rents", "Rent"), ("TravellingConveyances", "Travelling and conveyance"),
                       ("RatesAndTaxes", "Rates and taxes"), ("LegalProfessionalCharges", "Legal and professional charges"),
                       ("AdvertisingPromotionals", "Advertising and promotion"), ("PowerAndFuels", "Power and fuel"),
                       ("RepairsToBuildingAndMachineries", "Repairs to buildings and machinery"),
                       ("PaymentsToAuditors", "Payments to auditors"), ("MiscellaneousExpenses", "Miscellaneous expenses"))


def notes(r: dict, e: D.Entity, y: str, yp: str, pnl: dict, pnl_prev: dict, bs: dict, bs_prev: dict) -> dict:
    """The notes to the statements for report year y (comparative yp), from the report's schedules. Where the report
    gives only a total, the note has that one line."""
    b, ag, ox, dom = r["borrow"], r["ageing"], r["other_exp"], r["dom"]
    sec_lt = lambda yy: b["secured"].get(yy, 0) - b["secured_st_banks"].get(yy, 0)  # noqa: E731
    traded, services = dom.get("DomesticSalesOfTradedGoods", {}), dom.get("DomesticSalesOfServices", {})

    def split(total_cur, total_prev, parts):          # scale the report's parts to the line printed (a planted revenue)
        rows = []
        for lab, cur, prev in parts:
            fc = cur / sum(p[1] for p in parts) if sum(p[1] for p in parts) else 0
            fp = prev / sum(p[2] for p in parts) if sum(p[2] for p in parts) else 0
            rows.append((lab, total_cur * fc, total_prev * fp, ""))
        return rows

    oth = lambda f: f["rev"] + f["oi"] - f["pbt"] - f["mat"] - f["emp"] - f["fin"] - f["dep"]  # noqa: E731
    listed = [(lab, ox.get(key, {}).get(y, 0), ox.get(key, {}).get(yp, 0)) for key, lab in OTHER_EXPENSE_LINES]
    listed = [x for x in listed if x[1] or x[2]]
    return {
        "3": [("Secured", None, None, "b"), (f"Term Loan from {e.lender}", sec_lt(y), sec_lt(yp), ""),
              ("Unsecured", None, None, "b"), ("Loans from others", b["unsecured"].get(y, 0), b["unsecured"].get(yp, 0), "")],
        "4": [("Secured", None, None, "b"), (f"Loans repayable on demand from banks (cash credit from {e.bank})",
                                             bs["stb"], bs_prev["stb"], "")],
        "5": [("Trade Payables", bs["tp"], bs_prev["tp"], "")],
        "6": [("Other Current Liabilities", bs["ocl"] if "ocl" in bs else 0, bs_prev.get("ocl", 0), "")],
        "7": [("Short-Term Provisions", bs["stp"], bs_prev["stp"], "")],
        "9": [("Stock-in-Trade (IT and communication equipment)", bs["inv"], bs_prev["inv"], "")],
        "10": [("Outstanding for more than six months", None, None, "b"),
               ("Unsecured, considered good", ag["over6"].get(y, 0), ag["over6"].get(yp, 0), ""),
               ("Others", None, None, "b"),
               ("Unsecured, considered good", ag["upto6"].get(y, 0), ag["upto6"].get(yp, 0), "")],
        "11": [("Cash and Bank Balances", bs["cash"], bs_prev["cash"], "")],
        "12": [("Unsecured, considered good", bs["stla"], bs_prev["stla"], "")],
        "13": split(pnl["rev"], pnl_prev["rev"],
                    [("Sale of Traded Goods (IT and communication equipment)", traded.get(y, 0), traded.get(yp, 0)),
                     ("Sale of Services (installation, integration and support)", services.get(y, 0), services.get(yp, 0))]),
        "14": [("Other Income", pnl["oi"], pnl_prev["oi"], "")],
        "15": [("Cost of Materials Consumed", pnl["mat"], pnl_prev["mat"], "")],
        "16": [("Salaries, wages and other employee benefits", pnl["emp"], pnl_prev["emp"], "")],
        "17": [("Interest on borrowings", pnl["fin"], pnl_prev["fin"], "")],
        "18": [(lab, cur, prev, "") for lab, cur, prev in listed]
              + [("Other administrative expenses", oth(pnl) - sum(x[1] for x in listed),
                  oth(pnl_prev) - sum(x[2] for x in listed), "")],
    }


# --- the company: the report's facts, a fictional identity ------------------------------------------------------

def person(name, din, designation, dob, pan, aadhaar, address) -> D.Person:
    return D.Person(name, din, designation, dob, pan, aadhaar, address)


def entity(r: dict) -> D.Entity:
    y, m, d = (int(x) for x in r["incorporated"].split("-"))
    names = [("Arvind Rao Pendyala", "07714208", "12 June 1974", "AXXXX7731P", "XXXX XXXX 4418",
              "Flat 502, Sai Krupa Towers, Kondapur, Hyderabad 500084, Telangana"),
             ("Lakshmi Prasanna Pendyala", "07714215", "03 September 1978", "BXXXX2164Q", "XXXX XXXX 9025",
              "Flat 502, Sai Krupa Towers, Kondapur, Hyderabad 500084, Telangana"),
             ("Kiran Kumar Veluri", "08350172", "21 January 1980", "CXXXX5590R", "XXXX XXXX 3367",
              "H.No. 8-2-114, Road No. 7, Banjara Hills, Hyderabad 500034, Telangana"),
             ("Sunitha Rani Gadde", "08350189", "17 April 1983", "DXXXX8842S", "XXXX XXXX 6610",
              "Villa 21, Green Meadows, Gachibowli, Hyderabad 500032, Telangana"),
             ("Mahesh Chandra Bollam", "09126645", "08 November 1976", "EXXXX1109T", "XXXX XXXX 2785",
              "Flat 304, Lake View Residency, Kukatpally, Hyderabad 500072, Telangana")]
    roles = (r["designations"] + ["Director"] * 5)[:5] if r["designations"] else ["Managing Director"] + ["Director"] * 4
    persons = tuple(person(n, din, role, dob, pan, aad, addr) for (n, din, dob, pan, aad, addr), role
                    in zip(names[:max(2, len(r["designations"]) or 2)], roles))
    pan = "AAGCC4417M"
    return replace(D.BASE, name="Corvane Infocomm Services Private Limited", pan=pan,
                   cin=f"U63990TG{y}PTC115842", gstin=D.gstin_with_check(f"36{pan}1Z"),
                   incorporated=f"{d:02d} {D.FULLMON[m - 1]} {y}",
                   office="Flat 302, H.No. 2-48/7/12, Sri Sai Enclave, Road No. 3, Madhapur, Hyderabad 500081, Telangana", state="Telangana",
                   roc="Registrar of Companies, Hyderabad", branch="Madhapur", ifsc="HCBL0006120",
                   account="602010781234", persons=persons)


def profile(r: dict, e: D.Entity) -> None:
    """What the annual report and the memorandum say of the business, from the report's revenue mix."""
    goods = r["dom"].get("DomesticSalesOfTradedGoods", {}).get("2024-2025", 0.0)
    services = r["dom"].get("DomesticSalesOfServices", {}).get("2024-2025", 0.0)
    share = goods / (goods + services) if goods + services else 0.5
    shares = round(r["paid_up"] / 10)
    split = [0.45, 0.25, 0.12, 0.10, 0.08][:len(e.persons)]
    held = [round(shares * f / sum(split)) for f in split]
    held[0] += shares - sum(held)
    AR.PROFILE.update({
        "business": "trading in information technology and communication equipment and providing installation, "
                    "integration, support and other information and communication services to enterprise customers",
        "energy": "The company's operations are not energy-intensive; it takes measures to conserve energy at its "
                  "offices wherever possible.",
        "revenue_lines": [("Sale of Traded Goods (IT and communication equipment)", share),
                          ("Sale of Services (installation, integration and support)", 1 - share)],
        "inventory_lines": [("Stock-in-Trade (IT and communication equipment)", 1.0)],
        "inventory_policy": "Stock-in-trade is valued at the lower of cost and net realisable value; cost is determined "
                            "on the first-in, first-out basis and includes freight and other costs of purchase.",
        "authorised_shares": round(r["authorised"] / 10), "shares": shares,
        "holders": list(enumerate(held)),
    })
    MOA.CAPITAL = int(r["authorised"])
    MOA.OBJECTS_A = (
        "1. To carry on the business of trading in, supplying, installing, integrating and maintaining information "
        "technology and communication equipment, networks and systems for enterprise and government customers in India "
        "and abroad.",
        "",
        "2. To carry on the business of providers of information and communication services of every kind, including "
        "network design and integration, data centre and cloud services, managed services, software implementation, "
        "technical support, annual maintenance and facility management, and to buy, sell, import, export, lease, hire, "
        "repair and deal in computers, servers, storage, networking and telecommunication equipment, peripherals, "
        "software licences, spares and accessories, either on its own account or on commission, sub-contract or turnkey "
        "basis, and to set up and run offices, warehouses, service centres and training facilities for any of the said "
        "purposes. It may also design, supply, install and commission structured cabling, wireless, surveillance, "
        "audio-visual and access control systems, provide software development, systems integration and technology "
        "consulting services, and act as authorised distributor or reseller of such products.",
    )
    R.SUBSCRIBERS[e.persons[0].name] = ("son of Venkata Subbarayudu Narasimha Rao Pendyala", "business", 10_000)
    R.SUBSCRIBERS[e.persons[1].name] = ("daughter of Suryanarayana Murthy Kameswara Rao Vadlamani", "business", 10_000)
    R.TAN = "HYDC04417F"
    import tpl_income_tax_return as ITR
    ITR.TDS_PAYERS = [("Nirmala Technology Solutions Private Limited", "HYDN", "A"),
                      ("Vistara Digital Networks Private Limited", "HYDV", "C")]       # fictional customers
    ITR.TDS_SECTION = "194J(a)"


# --- the monthly figures --------------------------------------------------------------------------------------

WEIGHTS = [x / sum(D.OUTWARD[:12]) for x in D.OUTWARD[:12]]          # April to March: the pack's seasonal pattern


def months_of(fy_end: int) -> list[tuple[int, int]]:
    return [(fy_end - 1, m) for m in range(4, 13)] + [(fy_end, m) for m in range(1, 4)]


def monthly(revenue: float, fy_end: int) -> dict[tuple[int, int], int]:
    ms = months_of(fy_end)
    out = {m: int(round(revenue * w)) for m, w in zip(ms, WEIGHTS)}
    out[ms[-1]] += int(round(revenue)) - sum(out.values())             # the year adds up to the audited revenue
    return out


def gst_by_month(r: dict) -> dict[tuple[int, int], int]:
    latest = r["pl"]["OperatingRevenues"]["2024-2025"]
    gst = monthly(latest, 2026)
    nxt = monthly(latest, 2027)                                         # April to October 2026, at FY2025-26's level
    gst.update({m: v for m, v in nxt.items() if m <= M.STATEMENT_THROUGH})
    return {m: gst[m] for m in D.MONTHS}


# --- the sets -------------------------------------------------------------------------------------------------

def emi(principal: int, rate_pa: float = 0.1025, months: int = 72) -> int:
    r = rate_pa / 12
    return int(round(principal * r * (1 + r) ** months / ((1 + r) ** months - 1), -2))


TL_TENURE = 72                                                     # months, at 10.25% p.a.
TL_SANCTIONED, TL_EMI = "20,00,00,000", emi(200_000_000, months=TL_TENURE)
ORCHID = ("Orchid Cooperative Bank", "118820045511", "Current Account")       # TC-22: declared, no statement
MERIDIAN = ("Meridian Trust Bank", "740030091256")                            # TC-22: a statement, not declared


def build(r: dict, e: D.Entity, *, plant: bool = False, accounts_differ: bool = False,
          request: tuple[str, str] = ("15,00,00,000", "Fifteen Crore"),
          term_loan: tuple[str, int] = (TL_SANCTIONED, TL_EMI)) -> dict[str, bytes]:
    gst = gst_by_month(r)
    credits = {m: gst[m] for m in D.STATEMENT_MONTHS}
    years = {fy: year_figures(r, y) for y, fy in SHIFT.items()}         # fy end -> (balance sheet, profit and loss)
    itr_turn = {fy: years[fy][1]["rev"] for fy in years}
    if plant:   # TC-21: the four turnover gaps of the pack's TC-21 fail set, on this company's figures
        for m in ((2026, 1), (2026, 2), (2026, 3)):
            credits[m] = int(credits[m] * 0.62)                         # bank credits well below the returns
        for m in ((2026, 7), (2026, 8), (2026, 9)):
            gst[m] = int(gst[m] * 1.35)                                 # returns well above the bank
        bs, pnl = years[2026]
        extra = pnl["rev"] * 0.22                                       # audited revenue 22% above the returns,
        years[2026] = (bs, {**pnl, "rev": pnl["rev"] + extra, "mat": pnl["mat"] + extra})   # its profit unchanged
        itr_turn[2026] = pnl["rev"] * 0.80                              # the return's turnover 20% below
    tl_sanctioned, tl_emi = term_loan
    outstanding = D.inr(round(years[2026][0]["ltb"]))
    facility = [(e.lender, "Term Loan", tl_sanctioned, outstanding, D.inr(tl_emi))]
    opening = int(r["bs"]["CashAndBankBalances"]["2023-2024"])         # the bank balance at 1 April 2025
    # TC-22: part of each month's receipts goes to the undeclared account instead, so the two accounts together still
    # receive exactly the month's outward supplies (the turnover checks see the same total).
    elsewhere = {m: int(credits[m] * 0.08) for m in D.STATEMENT_MONTHS} if accounts_differ else {}
    txns = D.statement_transactions(D.STATEMENT_MONTHS, {m: credits[m] - elsewhere.get(m, 0) for m in credits},
                                    opening=opening, emi=tl_emi, emi_party="LOTUSCREST FIN")
    first, last = D.STATEMENT_MONTHS[0], D.STATEMENT_MONTHS[-1]
    last_day = {1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}[last[1]]

    year_of = {fy: y for y, fy in SHIFT.items()}

    def annual(fy_end: int, signed: str) -> bytes:
        bs, pnl = years[fy_end]
        bs_prev, pnl_prev = years[fy_end - 1] if fy_end - 1 in years else year_figures(r, "2021-2022")
        n = notes(r, e, year_of[fy_end], year_of[fy_end - 1], pnl, pnl_prev, bs, bs_prev)
        return R.annual_report(e, revenue=int(pnl["rev"]), profit_before_tax=int(pnl["pbt"]), fy_end=fy_end, signed_on=signed,
                               figures={"bs": bs, "bs_prev": bs_prev, "pl": pnl, "pl_prev": pnl_prev, "notes": n})

    def itr(fy_end: int, filed: str) -> bytes:
        return R.income_tax_return(e, turnover=int(itr_turn[fy_end]), profit=int(years[fy_end][1]["pbt"]),
                                   ay=f"{fy_end}-{(fy_end + 1) % 100:02d}", fy=f"{fy_end - 1}-{fy_end % 100:02d}",
                                   filed=filed)

    docs = {
        "01_Certificate_of_Incorporation.pdf": R.certificate_of_incorporation(e),
        "02_Company_PAN.pdf": R.company_pan(e),
        "03_Memorandum_and_Articles_of_Association.pdf": R.memorandum(e, directors=tuple(p.name for p in e.persons[:2])),
        "04_Director_KYC.pdf": R.director_kyc(e),
        "05_Board_Resolution.pdf": R.board_resolution(e, amount=request[0], amount_words=request[1],
                                                      lender=f"{e.bank}, {e.branch} Branch"),
        "06_Existing_Facilities_Declaration.pdf": R.facilities_declaration(
            e, facilities=facility,
            accounts=[(e.bank, e.account, "Current Account")] + ([ORCHID] if accounts_differ else [])),
        "07_Sanction_Letter_Lotuscrest.pdf": R.sanction_letter(e, amount=tl_sanctioned, rate="10.25% p.a.",
                                                               tenure=f"{TL_TENURE} months", emi=D.inr(tl_emi)),
        "08_Commercial_Bureau_Report.pdf": R.bureau_report(
            e, facilities=[(e.lender, "Term Loan", tl_sanctioned, outstanding, "0", "Standard")], rank="3"),
        "09_Bank_Statement_Harbour_CA.pdf": R.bank_statement(
            e, txns=txns, opening=opening, start=f"01 {D.MON[first[1] - 1]} {first[0]}",
            end=f"{last_day} {D.MON[last[1] - 1]} {last[0]}"),
        "10_ITR_AY2026-27.pdf": itr(2026, "28 September 2026"),
        "11_Audited_Financial_Statements_FY2025-26.pdf": annual(2026, "27 August 2026"),
        "12_Audited_Financial_Statements_FY2024-25.pdf": annual(2025, "29 August 2025"),
        "13_ITR_AY2025-26.pdf": itr(2025, "30 September 2025"),
        "14_Audited_Financial_Statements_FY2023-24.pdf": annual(2024, "30 August 2024"),
        "15_ITR_AY2024-25.pdf": itr(2024, "30 September 2024"),
    }
    for m in D.MONTHS:
        docs[f"GSTR3B_{D._label(m)}.pdf"] = D.gstr_3b(e, month=m, taxable=gst[m])
    for m in D.MONTHS[-12:]:
        docs[f"GSTR1_{D._label(m)}.pdf"] = R.gstr_1(e, month=m, taxable=gst[m])
    if accounts_differ:   # TC-22: the undeclared account's statement, over the same months as the declared one
        months = D.STATEMENT_MONTHS
        other = D.statement_transactions(months, elsewhere, opening=4_500_000, emi_months=set())
        (y0, m0), (y1, m1) = months[0], months[-1]
        docs["16_Bank_Statement_Meridian_CA.pdf"] = R.bank_statement(
            e, txns=other, opening=4_500_000, start=f"01 {D.MON[m0 - 1]} {y0}",
            end=f"{calendar.monthrange(y1, m1)[1]} {D.MON[m1 - 1]} {y1}",
            account=MERIDIAN[1], bank=MERIDIAN[0])
    return docs


HONORIFIC = ("Mr.", "Mrs.", "Mr.", "Mrs.", "Mr.")                    # of the five fictional directors, in order


def message(e: D.Entity, r: dict, amount: int) -> str:
    p = e.persons
    cr = lambda n: f"Rs {n / 10_000_000:.2f} Cr"  # noqa: E731
    return "\n".join([
        f"Subject: New proposal - {e.name}", "", "Dear Credit Team,", "",
        f"Please find below a new proposal sourced at {e.branch} branch.", "",
        f"Borrower: {e.name} (private limited company)",
        f"PAN: {e.pan} | GSTIN: {e.gstin} | CIN: {e.cin}",
        "Promoters and directors: " + ", ".join(f"{h} {x.name}" + (" (MD)" if i == 0 else "")
                                                for i, (h, x) in enumerate(zip(HONORIFIC, p[:-1])))
        + f" and {HONORIFIC[len(p) - 1]} {p[-1].name}",
        f"Business: IT and communication equipment trading and services, Hyderabad, in business since {e.incorporated[-4:]}",
        f"Turnover FY 2025-26: {cr(r['pl']['OperatingRevenues']['2024-2025'])} (audited)",
        f"Requirement: cash credit {cr(amount)}",
        f"Existing: current account with {e.bank} a/c {e.account} and TL with {e.lender.replace(' Limited', '')}",
        "Collateral: none; primary security by hypothecation of stock and book debts",
        "", "The customer's documents are attached. Request you to initiate the appraisal.", "",
        "Regards,", "Relationship Manager, Business Banking", f"{e.branch} branch", ""])


def write(report: Path, out: Path, only: set[str] | None = None) -> None:
    r = load(report)
    e = entity(r)
    profile(r, e)
    M.ENTITIES[e.name] = e
    small = scaled(r, 241_600_000)                  # TC-24: Rs 24.16 Cr turnover
    # id, folder, report figures, amount asked, the board resolution's amount, build options
    sets = [("ALL", "1_clean_pass_everything", r, 150_000_000, ("15,00,00,000", "Fifteen Crore"), {}),
            ("TC-21", "2_TC-21_turnover_fail", r, 150_000_000, ("15,00,00,000", "Fifteen Crore"), {"plant": True}),
            ("TC-22", "3_TC-22_accounts_differ", r, 150_000_000, ("15,00,00,000", "Fifteen Crore"),
             {"accounts_differ": True}),
            ("TC-24", "4_TC-24_request_over_20pct", small, 49_500_000, ("4,95,00,000", "Four Crore Ninety-Five Lakh"),
             {"term_loan": ("2,75,00,000", emi(27_500_000, months=TL_TENURE))})]
    old = json.loads((out / "index.json").read_text())["sets"] if (out / "index.json").exists() else []
    index = {s["folder"]: s for s in old}
    for id_, name, figures, amount, request, opts in sets:
        if only and id_ not in only:
            continue
        folder = out / name
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        for fname, data in sorted(build(figures, e, request=request, **opts).items()):
            (folder / fname).write_bytes(data)
        text = message(e, figures, amount)
        case = {"borrower": e.name, "constitution": "private_limited", "facilities": ["cash_credit"],
                "amount_inr": amount, "channel": "email", "collateral_present": False}
        (folder / "00_Sourcing_Message.txt").write_text(text)
        (folder / "case.json").write_text(json.dumps({**case, "message_text": text}, indent=1) + "\n")
        index[name] = {"id": id_, "set": name, "folder": name, "files": len(list(folder.glob("*.pdf")))}
        print(f"{name}: {index[name]['files']} documents")
    index = [index[n] for _, n, *_ in sets if n in index]
    (out / "index.json").write_text(json.dumps({"case_date": M.CASE_DATE, "sets": index}, indent=1))
    fy = {y: f"FY{e - 1}-{e % 100:02d}" for y, e in SHIFT.items()}
    listed = lambda figs: [{"report_year": y, "printed_as": fy[y], "item": item, "report_value": round(a),  # noqa: E731
                            "printed_value": round(b), "why": why}
                           for (y, item), (a, b, why) in sorted(figs.get("adjusted", {}).items())]
    (out / "adjustments.json").write_text(json.dumps({
        "rule": f"receivables above a {CYCLE_DAYS}-day working-capital cycle shown as unbilled revenue (other current "
                f"assets); finance costs above {COVER}x interest cover shown in other expenses; every total, the "
                f"turnover and the profit unchanged",
        "sets_1_to_3": listed(r), "set_4_scaled": listed(small)}, indent=1) + "\n")


if __name__ == "__main__":
    write(Path(_args[0]), Path(_args[1]).resolve(), set(_args[2:]) or None)
