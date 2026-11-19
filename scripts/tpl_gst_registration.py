"""The GST registration certificate (Form GST REG-06) as the GST portal prints it, drawn at the positions measured on
a real certificate of the amended kind: A4 with a heavy page border, dark-blue Times headings and Helvetica 10 text,
the numbered particulars table in 0.5 pt rules, the approving authority's block, the note and the closing sentence;
then Annexure A (additional places of business) and Annexure B (the directors), one page each.

Not drawn (CLAUDE.md rule 8): the national emblem at the head of every page, the diagonal background lettering, the
QR code in the registration-type row, the digital-signature appearance in the signature row and the photographs in
Annexure B. Their places are left plain.
"""

from __future__ import annotations

from datetime import date, timedelta

import template_pages as TP
from tests import docsets as D

BLUE = "#000099"
HV, HB = "Helvetica", "Helvetica-Bold"
TB, TI = "Times-Bold", "Times-Italic"
# baseline below a word's top, per point of size, as the template's own fonts report it
TPL_ASC = {"Helvetica": 0.793, "Times": 0.783}
GST_START = date(2017, 7, 1)         # registrations that migrated are valid from the day GST began
LABELS = ["Floor No.:", "Building No./Flat No.:", "Name Of Premises/Building:", "Road/Street:",
          "Locality/Sub Locality:", "City/Town/Village:", "District:", "State:", "PIN Code:"]


class _Page(TP.Sheet):
    """Text placed by the template's word tops: the baseline is set from the template font's ascent."""

    def put(self, x, top, s, font=HV, size=10.0, *, align="l"):
        fam = "Times" if font.startswith("Times") else "Helvetica"
        self.text(x, top + (TPL_ASC[fam] - TP._asc(font)) * size, s, font, size, align=align, colour=BLUE)

    def border(self):
        self.box(0.0, 0.0, 595.0, 842.0, 5.0)

    def rects(self, top, bottom, edges):
        for x0, x1 in zip(edges, edges[1:]):
            self.box(x0, top, x1, bottom, 0.5)


def _address(office: str, district: dict) -> list[tuple[str, str]]:
    """The office address split into the portal's labelled lines; a line the address does not fill is left out."""
    parts = [p.strip() for p in office.split(",")]
    state = parts[-1]
    city, pin = parts[-2], ""
    if city[-6:].isdigit():
        city, pin = city[:-6].strip(), city[-6:]
    prem = parts[:-2]
    got = {"Floor No.:": next((p for p in prem if "floor" in p.lower()), "")}
    prem = [p for p in prem if p != got["Floor No.:"]]
    got["Building No./Flat No.:"] = prem[0] if prem else ""
    if len(prem) >= 2:
        got["Locality/Sub Locality:"] = prem[-1]
    middle = prem[1:-1]
    if len(middle) == 1:
        got["Road/Street:"] = middle[0]
    elif len(middle) >= 2:
        got["Name Of Premises/Building:"] = middle[0]
        got["Road/Street:"] = ", ".join(middle[1:])
    got.update({"City/Town/Village:": city, "District:": district.get(city, city), "State:": state, "PIN Code:": pin})
    return [(k, got[k]) for k in LABELS if got.get(k)]


def gst_registration_certificate(e: D.Entity = D.BASE, *, officer: str = "SANJAY PATIL",
                                 office: str = "PANVEL") -> bytes:
    """Form GST REG-06, three pages: the certificate with its particulars and approving authority, Annexure A and
    Annexure B. The validity runs from the later of incorporation and 1 July 2017; the certificate is an amended one,
    issued later. Date of Liability is left blank, as the portal prints it."""
    import realistic_docs as R

    d, m, y = R.parse_date(e.incorporated)
    start = max(date(y, m, d), GST_START)
    issued = max(date(2023, 8, 14), start + timedelta(days=4))
    who = e.name.upper()
    k = R.kind(e)
    issue = issued.strftime("%d/%m/%Y")

    s = _Page(595.0, 842.0, footer_x=36.0, footer_y=12.0)

    # --- page 1: the certificate (the emblem at 270-325 x 58-114 is not drawn)
    s.border()
    s.put(559.0, 43.07, "(Amended)", HB, 10, align="r")
    s.put(297.5, 122.60, "Government of India", TB, 12, align="c")
    s.put(297.5, 139.89, "Form GST REG-06", TB, 11, align="c")
    s.put(265.42, 155.67, "[See Rule 10(1)]", TI, 10)
    s.put(297.5, 172.10, "Registration Certificate", TB, 12, align="c")
    s.put(71.75, 189.39, f"Registration Number : {e.gstin}", TB, 11)

    E3 = [36.0, 62.99, 208.08, 559.0]
    for top, bottom in ((216, 236), (236, 256), (256, 291), (291, 311), (486, 506), (566, 586)):
        s.rects(top, bottom, E3)
    s.rects(506, 526, [36.0, 62.99, 208.08, 275.565, 383.54, 451.025, 559.0])
    s.rects(526, 566, E3[:3])                      # the value cell has only its right edge, beside the QR code's place
    s.line(559.0, 526, 559.0, 566, 0.5)
    for x in E3:                                     # the address row is drawn with lines, closed by the row below
        s.line(x, 311, x, 486, 0.5)
    for x0, x1 in zip(E3, E3[1:]):
        s.line(x0, 311, x1, 311, 0.5)
    s.box(36.0, 586, 559.0, 651, 0.5)                # signature row (the digital-signature appearance is not drawn)
    for top in (651, 671, 691, 711):
        s.rects(top, top + 20, [36.0, 210.33, 559.0])
    s.box(36.0, 731, 559.0, 766, 0.5)

    def num(top, n):
        s.put(43.56, top, f"{n}.", HV, 10)

    for n, top, label in ((1, 220.07, "Legal Name"), (2, 240.07, "Trade Name, if any"),
                          (4, 295.07, "Constitution of Business")):
        num(top, n)
        s.put(64.99, top, label, HB, 10)
    s.put(210.08, 220.07, who, HV, 10)
    s.put(210.08, 240.07, who, HV, 10)
    num(260.07, 3)
    s.put(64.99, 260.07, "Additional trade names, if", HB, 10)
    s.put(64.99, 270.07, "any", HB, 10)
    s.put(210.08, 295.07, R.CONSTITUTION[k], HV, 10)
    num(315.07, 5)
    s.put(64.99, 315.07, "Address of Principal Place of", HB, 10)
    s.put(64.99, 325.07, "Business", HB, 10)
    gap = TP.width(" ", HB, 10)
    for i, (label, value) in enumerate(_address(e.office, R.DISTRICT)):
        top = 317.57 + 12.5 * i
        s.put(210.08, top, label, HB, 10)
        s.put(210.08 + TP.width(label, HB, 10) + gap, top, value, HV, 10)
    num(490.07, 6)
    s.put(67.77, 490.07, "Date of Liability", HB, 10)
    num(510.07, 7)
    s.put(67.77, 510.07, "Date of Validity", HB, 10)
    s.put(210.08, 510.07, "From", HV, 10)
    s.put(277.57, 510.07, start.strftime("%d/%m/%Y"), HV, 10)
    s.put(385.54, 510.07, "To", HV, 10)
    s.put(453.03, 510.07, "Not Applicable", HV, 10)
    num(530.07, 8)
    s.put(67.77, 530.07, "Type of Registration", HB, 10)
    s.put(210.08, 535.07, "Regular", HV, 10)     # the QR code at 446-482 x 528-564 is not drawn
    num(570.07, 9)
    s.put(64.99, 570.07, "Particulars of Approving", HB, 10)    # the cell is one line high; "Authority" is cut off
    s.put(212.86, 570.07, f"{e.state} Goods and Services Tax Act, 2017", HV, 10)
    s.put(38.0, 590.07, "Signature", HB, 10)
    for top, label, value in ((655.07, "Name", officer), (675.07, "Designation", "Deputy State Tax Officer"),
                              (695.07, "Jurisdictional Office", office),
                              (715.07, "Date of issue of Certificate", issue)):
        s.put(38.0, top, label, HB, 10)
        s.put(212.33, top, value, HV, 10)
    s.put(38.0, 735.07, "Note: The registration certificate is required to be prominently displayed at all places of "
                        "Business/Office(s) in the", HV, 10)
    s.put(38.0, 745.07, "State.", HV, 10)
    s.put(36.0, 772.36, "This is a system generated digitally signed Registration Certificate issued based on the "
                        "approval of application granted", HB, 9)
    s.put(36.0, 785.86, f"on {issue} by the jurisdictional authority.", HB, 9)

    def names(top):
        s.put(64.15, top, "Legal Name", HB, 10)
        s.put(200.80, top, who, HV, 10)
        s.put(64.15, top + 20, "Trade Name, if any", HB, 10)
        s.put(200.80, top + 20, who, HV, 10)
        s.put(64.15, top + 40, "Additional trade names, if", HB, 10)
        s.put(64.15, top + 50, "any", HB, 10)

    # --- page 2: Annexure A
    s.page()
    s.border()
    s.put(559.0, 43.07, "Annexure A", HB, 10, align="r")
    s.put(63.80, 157.07, f"Goods and Services Tax Identification Number: {e.gstin}", HB, 10)
    s.put(63.80, 190.07, "Details of Additional Place of Business(s)", HB, 10)
    names(220.07)
    s.put(63.80, 311.07, "Total Number of Additional Places of Business(s) in the State", HB, 10)
    s.put(393.89, 311.07, "0", HB, 10)

    # --- page 3: Annexure B (each person's photograph at 80-128 x 286-346 is not drawn)
    s.page()
    s.border()
    s.put(559.0, 43.07, "Annexure B", HB, 10, align="r")
    s.put(63.80, 139.07, f"Goods and Services Tax Identification Number: {e.gstin}", HB, 10)
    names(169.07)
    heading = {"company": "Details of  Managing / Whole-time Directors and Key Managerial Persons",
               "firm": "Details of  Managing / Authorized Partners", "individual": "Details of  Proprietor"}[k]
    s.put(63.80, 260.07, heading, HB, 10)
    for i, p in enumerate(e.persons):
        top = 290.07 + 60 * i
        home = p.address.split(",")[-1].strip() or e.state
        s.put(69.71, top, str(i + 1), HV, 10)
        s.put(200.86, top, "Name", HV, 10)
        s.put(341.51, top, p.name.upper(), HV, 10)
        s.put(200.86, top + 20, "Designation/Status", HV, 10)
        s.put(343.17, top + 20, p.designation.upper(), HV, 10)
        s.put(200.86, top + 40, "Resident of State", HV, 10)
        s.put(344.29, top + 40, home, HV, 10)
    return s.render()
