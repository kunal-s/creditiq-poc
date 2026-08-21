"""Adversarial validation of the generated set against the brief's hard constraints."""
import json
import os
import re

import pymupdf

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                   "docready-southgate-documents"))

fails = []
oks = []


def texts(fn):
    doc = pymupdf.open(os.path.join(OUT, fn))
    return [doc[i].get_text() for i in range(doc.page_count)], doc.page_count


def norm(s):
    return re.sub(r"\s+", " ", s)


def check(cond, msg):
    (oks if cond else fails).append(msg)


def has(fn, s, page=None):
    pages, n = texts(fn)
    body = norm(pages[page - 1]) if page else norm("".join(pages))
    check(s in body, "%s: contains %r%s" % (fn, s, (" on p%d" % page) if page else ""))


def absent(fn, s):
    pages, n = texts(fn)
    check(s not in norm("".join(pages)), "%s: does NOT contain %r" % (fn, s))


# 1. Title deed
has("Southgate_Title_Deed_Coimbatore_Unit.pdf", "MORTGAGE BY DEPOSIT OF TITLE DEEDS", 3)
has("Southgate_Title_Deed_Coimbatore_Unit.pdf", "MERIDIAN BANK, Coimbatore Branch", 3)
has("Southgate_Title_Deed_Coimbatore_Unit.pdf", "1,75,00,000", 3)
has("Southgate_Title_Deed_Coimbatore_Unit.pdf", "14 March 2024", 3)
pages, n = texts("Southgate_Title_Deed_Coimbatore_Unit.pdf")
check(n == 4, "Title deed is 4 pages (got %d)" % n)

# 2. Nil declaration
has("Southgate_Nil_Facilities_Declaration.pdf", "does not have any existing credit facilities")
has("Southgate_Nil_Facilities_Declaration.pdf", "06 August 2026")
has("Southgate_Nil_Facilities_Declaration.pdf", "Lakshmi Iyer")

# 3. CA statement: exactly 12 Meridian EMI of 2,18,750; single account
pages, n = texts("Southgate_CCB_CA_Statements_12m.pdf")
alltext = "".join(pages)
emi = alltext.count("ACH/MERIDIAN/EMI")  # ledger reference token (summary line excluded)
check(emi == 12, "CA statement has 12 MERIDIAN EMI ledger rows (got %d)" % emi)
check(10 <= n <= 14, "CA statement 10-14 pages (got %d)" % n)
has("Southgate_CCB_CA_Statements_12m.pdf", "914020055831447")
has("Southgate_CCB_CA_Statements_12m.pdf", "2,18,750")
check("8830" not in alltext and "Meridian Bank, account" not in alltext,
      "CA statement covers only the one CCB account")

# 4. Stock & book-debt exact figures + ageing + staleness
sb = "Southgate_Stock_BookDebt_30Jun2026.pdf"
has(sb, "AS AT 30 JUNE 2026", 1)
has(sb, "4,38,92,150")
has(sb, "3,12,47,880")
has(sb, "41,83,200")
has(sb, "04 July 2026")
# RM+WIP+FG sum
check(18642300 + 7180850 + 18069000 == 43892150, "stock components sum to closing stock")

# 5. GSTR: 8 periods, Aug-Nov absent, sum consistent
gp, gn = texts("Southgate_GSTR3B_Dec2025_Jul2026.pdf")
gall = norm("".join(gp))
for present in ["December 2025", "January 2026", "February 2026", "March 2026",
                "April 2026", "May 2026", "June 2026", "July 2026"]:
    check(("Tax Period " + present) in gall or present in gall,
          "GSTR includes %s" % present)
# The four missing periods must not appear as their own return period pages.
for miss in ["Return Period 08/2025", "Return Period 09/2025", "Return Period 10/2025",
             "Return Period 11/2025"]:
    check(miss not in gall, "GSTR omits %s" % miss)
has("Southgate_GSTR3B_Dec2025_Jul2026.pdf",
    "August 2025, September 2025, October 2025 and November 2025 are not enclosed", 1)
gsum = sum([24120500, 23864000, 22705500, 27418300, 24980400, 26142600, 25873100, 23890900])
check(abs(gsum - 198642300) / 198642300 < 0.03,
      "GSTR outward supplies sum %s within 3%% of part-year revenue 19,86,42,300" % gsum)

# 6. Provisional page numbering 1,2,6,7
pp, pn = texts("Southgate_Provisional_FY2026.pdf")
check(pn == 4, "Provisional is 4 physical pages (got %d)" % pn)
labels = [("Page 1 of 7" in pp[0]), ("Page 2 of 7" in pp[1]),
          ("Page 6 of 7" in pp[2]), ("Page 7 of 7" in pp[3])]
check(all(labels), "Provisional numbering runs 1,2,6,7 (got %s)" % labels)
check("Page 3 of 7" not in norm("".join(pp)) and "Page 4 of 7" not in norm("".join(pp))
      and "Page 5 of 7" not in norm("".join(pp)), "Provisional pages 3,4,5 absent")
has("Southgate_Provisional_FY2026.pdf", "19,86,42,300")
has("Southgate_Provisional_FY2026.pdf", "96,18,470")

# 7. Board resolution: amount, section, empty signature, plain paper
br = "Southgate_Board_Resolution_draft.pdf"
has(br, "4,25,00,000")
has(br, "Section 179(3)(d)")
has(br, "Signature:")
brtext = norm("".join(texts(br)[0]))
# plain paper: no CIN/GSTIN letterhead line that the other Southgate docs carry
check("GSTIN: 33AAHCS6612M1ZQ" not in brtext, "Board resolution has no letterhead block")

# 8-14 anchors
import financials as F
from common import indian_group as ig
for fn, cur, prev in [("Southgate_Audited_FS_FY2024.pdf", F.FY2024, F.FY2023),
                      ("Southgate_Audited_FS_FY2025.pdf", F.FY2025, F.FY2024)]:
    for k in ("revenue", "ebitda", "pat", "net_worth"):
        has(fn, ig(cur[k]))
# net worth roll-forward
check(F.FY2024["net_worth"] + F.FY2025["pat"] == F.FY2025["net_worth"],
      "Net worth roll-forward FY2024+PAT2025 == FY2025 net worth")
check(F.FY2023["net_worth"] + F.FY2024["pat"] == F.FY2024["net_worth"],
      "Net worth roll-forward FY2023+PAT2024 == FY2024 net worth")

has("Southgate_Certificate_of_Incorporation.pdf", "U17291TZ2016PTC027431")
has("Southgate_Certificate_of_Incorporation.pdf", "18 March 2016")
has("Southgate_Entity_PAN.pdf", "AAHCS6612M")
# KYC masked, full PANs absent
kyc = norm("".join(texts("Southgate_Director_KYC_Iyer_x2.pdf")[0]))
check("AXXXX1683M" in kyc and "AXXXX1699V" in kyc, "KYC shows masked PANs")
has("Southgate_ITR_FY2024_FY2025.pdf", "2024-25")
has("Southgate_ITR_FY2024_FY2025.pdf", "2025-26")

# Watermark + footer on every page of every file
for fn in os.listdir(OUT):
    if not fn.endswith(".pdf"):
        continue
    ps, nn = texts(fn)
    for i, t in enumerate(ps, 1):
        nt = norm(t)
        check("SPECIMEN" in nt.upper(), "%s p%d has SPECIMEN watermark" % (fn, i))
        check("Synthetic specimen generated for demonstration" in nt,
              "%s p%d has footer" % (fn, i))

# Manifest well-formed; evidence pages within range
man = json.load(open(os.path.join(OUT, "manifest.json")))
check(man["document_count"] == 14, "manifest lists 14 documents")
for d in man["documents"]:
    _, npg = texts(d["filename"])
    for e in d.get("evidence", []):
        check(1 <= e["page"] <= npg, "%s evidence page %d in range" % (d["filename"], e["page"]))
        # snippet actually on that page
        ps, _ = texts(d["filename"])
        check(norm(e["snippet"]) in norm(ps[e["page"] - 1]),
              "%s evidence snippet present on p%d" % (d["filename"], e["page"]))

print("PASSED: %d" % len(oks))
print("FAILED: %d" % len(fails))
for f in fails:
    print("  X", f)
