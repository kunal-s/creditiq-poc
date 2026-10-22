"""A bank statement for the Banking view demonstration: the Kestrel K11 statement's rows with further entries added
(two round trips with a fictional counterparty each, a month heavy in cash deposits, a returned cheque, and a few
narrations the rules cannot settle), every running balance recomputed, in the same layout as the other Kestrel
statements. Every name and number is fictional; the document carries only the single-line footer.

    python scripts/make_banking_demo.py BASE_STATEMENT.pdf OUT_STATEMENT.pdf

The base statement is read in place (workflow/docs/reference/fixtures/kestrel/K11_obligations/09_Bank_Statement_Harbour_CA.pdf)
and nothing is copied out of it but its rows.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date, datetime

from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

OPENING = 25_000_000
ACCOUNT, PERIOD = "602010345567", ("01 Apr 2025", "30 Sep 2026")
FOOTER = "Synthetic specimen for software testing. All names and numbers are fictional."

# (date, narration, reference, debit, credit): added to the base statement's rows.
ADDED = [
    # A round trip: paid out, and about the same coming back from the same party within a week.
    ("2025-05-14", "RTGS DR HALCYON ENGINEERING", "UTR/50333101", 2_500_000, 0),
    ("2025-05-20", "NEFT CR HALCYON ENGINEERING", "NEFT/40333102", 0, 2_460_000),
    # A second, to the rupee.
    ("2025-12-09", "RTGS DR VANTAGE ALLOYS", "UTR/50333103", 1_800_000, 0),
    ("2025-12-15", "NEFT CR VANTAGE ALLOYS", "NEFT/40333104", 0, 1_800_000),
    # A month heavy in cash.
    ("2025-07-22", "CASH DEPOSIT CDM TALOJA", "CDM/70001", 0, 5_500_000),
    ("2025-07-29", "CASH DEPOSIT CDM TALOJA", "CDM/70002", 0, 1_200_000),
    # A cheque returned unpaid.
    ("2025-08-18", "CHQ RET 004412 INSUFF FUNDS", "CLG/004412", 350_000, 0),
    # Narrations the rules cannot settle.
    ("2025-06-09", "ZZ-SETTLEMENT 77/ADJ", "ADJ/77", 1_250, 0),
    ("2025-06-12", "BY 004419 AMBER OILS", "TRF/004419", 0, 310_000),
    ("2025-07-03", "TRF-INB 8841 K MEHTA AGRO", "INB/8841", 84_000, 0),
]


def inr(n: int) -> str:
    """Indian digit grouping: 1,14,08,000."""
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def read_rows(pdf: str) -> list[tuple[str, str, str, int, int]]:
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout
    opening = OPENING
    prev, rows = opening, []
    for line in text.splitlines():
        m = re.match(r"(\d{2} \w{3} \d{4})\s+(.+?)\s{2,}(\S+/\S+)", line)
        nums = re.findall(r"(?<![\w/])\d[\d,]*(?=\s|$)", line)
        if not m or len(nums) < 2:
            continue
        balance, amount = (int(n.replace(",", "")) for n in nums[-2:][::-1])
        when = datetime.strptime(m[1], "%d %b %Y").date().isoformat()
        credit = balance > prev
        rows.append((when, m[2].strip(), m[3], 0 if credit else amount, amount if credit else 0))
        prev = balance
    return rows


def draw(rows: list[tuple[str, str, str, int, int]], out: str) -> None:
    c = canvas.Canvas(out, pagesize=(595, 842))
    top = lambda y: 842 - y   # PDF y from a distance below the top edge
    c.setTitle("Statement of Account")

    def text(x, y, s, font="Helvetica", size=10, right=False):
        c.setFont(font, size)
        (c.drawRightString if right else c.drawString)(x, top(y), s)

    text(50, 42, "Harbour Commercial Bank", "Helvetica-Bold", 11)
    text(50, 58, "Taloja Branch - Statement of Account")
    for i, (k, v) in enumerate([("Account Name", "Kestrel Fabricators Private Limited"), ("Account Number", ACCOUNT),
                                ("Branch / IFSC", "Taloja / HCBL0004417"), ("Statement", f"{PERIOD[0]} to {PERIOD[1]}"),
                                ("Currency", "INR")]):
        text(50, 90 + 16 * i, k)
        text(200, 90 + 16 * i, v)
    text(50, 170, f"Opening Balance ({PERIOD[0]})")
    text(382.82, 170, inr(OPENING), right=True)
    y = 202
    text(50, y, "Date"); text(125, y, "Particulars"); text(320, y, "Reference")
    text(462, y, "Debit", right=True); text(525, y, "Credit", right=True); text(588, y, "Balance", right=True)
    y += 16
    balance, credits, debits = OPENING, 0, 0
    for when, narration, ref, debit, credit in rows:
        if stringWidth(narration, "Helvetica", 10) > 188:   # it would run into the reference column
            raise ValueError(f"narration too wide for its column: {narration!r}")
        if y > 800:
            c.showPage()
            y = 58
        balance += credit - debit
        credits, debits = credits + credit, debits + debit
        text(50, y, datetime.fromisoformat(when).strftime("%d %b %Y"))
        text(125, y, narration)
        text(320, y, ref)
        if debit:
            text(462, y, inr(debit), right=True)
        if credit:
            text(525, y, inr(credit), right=True)
        text(588, y, inr(balance), right=True)
        y += 16
    if y > 700:
        c.showPage()
        y = 58
    y += 24
    text(50, y, "Statement Summary", "Helvetica-Bold", 11)
    for i, (k, v) in enumerate([(f"Account {ACCOUNT} - {PERIOD[0]} to {PERIOD[1]}", ""),
                                (f"Opening Balance ({PERIOD[0]})", inr(OPENING)), ("Total Credits during period", inr(credits)),
                                ("Total Debits during period", inr(debits)), (f"Closing Balance ({PERIOD[1]})", inr(balance))]):
        text(50, y + 18 + 16 * i, k)
        if v:
            text(382.82, y + 18 + 16 * i, v, right=True)
    text(50, 820, FOOTER, size=8)
    c.save()


def main(base: str, out: str) -> None:
    rows = read_rows(base)
    merged = sorted([*rows, *ADDED], key=lambda r: (r[0], r[2]))
    draw(merged, out)
    print(f"{len(rows)} rows read, {len(ADDED)} added, {len(merged)} written to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
