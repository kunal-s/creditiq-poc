// The Cross-checks tab (FRD F-19, F-16.2): the area cards and each area's discrepancies, ranked by
// credit impact within the area, show where the file stands at a glance; a failed check marks
// the value that differs and shows its sources side by side, page beside page; an incomplete
// check names what is not on file, and the checks that passed stay closed. The board itself is
// covered in cross-verification-board.spec.ts; these checks run on a board of their own.
import { expect, test } from "@playwright/test";
import { KESTREL, xvColumn, xvFinding, xvItem, xvRow, xvSide, xvView } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

const onPage = (documentId: string, page: number) => [{ document_id: documentId, page }];

function board() {
  const cin = xvFinding({
    id: "fnd-id5",
    rule_id: "ID-05",
    title: "CIN consistent across documents",
    finding_title: "CIN differs between documents",
    area: "identity",
    outcome: "fail",
    severity: "serious",
    blocking: true,
    ref: "XV-000021-02",
    explanation:
      "The CIN differs between documents: U28999MH2015PTC123456 (Certificate of incorporation) · U28999MH2015PTC123465 (Memorandum and articles of association).",
    sides: [
      xvSide("Certificate of incorporation", "U28999MH2015PTC123456", onPage("doc-bs", 1)),
      xvSide(
        "Memorandum and articles of association",
        "U28999MH2015PTC123465",
        onPage("doc-bank", 3),
        {
          differs: true,
        },
      ),
    ],
    columns: [
      xvColumn("statement-0", "Certificate of incorporation", "U28999MH2015PTC123456", {
        coverage: "Page 1",
        evidence: onPage("doc-bs", 1),
        row_columns: ["Field", "Value"],
        rows: [xvRow(["CIN", "U28999MH2015PTC123456"], onPage("doc-bs", 1))],
      }),
      xvColumn("statement-1", "Memorandum and articles of association", "U28999MH2015PTC123465", {
        differs: true,
        coverage: "Page 3",
        evidence: onPage("doc-bank", 3),
        row_columns: ["Field", "Value"],
        rows: [xvRow(["CIN", "U28999MH2015PTC123465"], onPage("doc-bank", 3))],
      }),
    ],
    reference: "U28999MH2015PTC123456",
    mismatch:
      "Memorandum and articles of association gives U28999MH2015PTC123465; the other source gives U28999MH2015PTC123456.",
    query: "Please confirm the company's CIN.",
  });
  const name = xvFinding({
    id: "fnd-id3",
    rule_id: "ID-03",
    title: "Legal name consistent across documents",
    finding_title: "Company name differs between documents",
    area: "identity",
    outcome: "fail",
    severity: "moderate",
    blocking: false,
    ref: "XV-000021-03",
    explanation:
      "The legal name reads differently across documents: Kestrel Polymers Pvt Ltd (Certificate of incorporation) · Kestrel Polymer Industries (Commercial bureau report).",
    mismatch:
      "Commercial bureau report reads Kestrel Polymer Industries; the other source reads Kestrel Polymers Pvt Ltd.",
  });
  const lender = xvFinding({
    id: "fnd-ob2",
    rule_id: "OB-02",
    title: "Instalments in bank statements go to declared lenders",
    finding_title: "Instalments to a lender that was not declared",
    area: "obligations",
    outcome: "fail",
    severity: "serious",
    blocking: false,
    ref: "XV-000021-01",
    explanation:
      "Regular debits to lender(s) not declared: ASHWOOD FINSERV (₹1,45,000 a month in 6 months, Lotuscrest Bank ·1234).",
    amount: 1_740_000,
  });
  const window = xvFinding({
    id: "fnd-to5",
    rule_id: "TO-05",
    title: "GST outward supplies against bank credits, months both cover",
    area: "turnover",
    outcome: "incomplete",
    severity: "moderate",
    blocking: false,
    explanation: "GSTR-3B not on file.",
    missing: ["GSTR-3B"],
    request: "the GSTR-3B",
  });
  const audited = xvFinding({
    id: "fnd-to1",
    rule_id: "TO-01",
    title: "Audited turnover against GST outward supplies · FY 2024-25",
    compares: "Audited turnover against GST outward supplies",
    finding_title: "Audited turnover differs from GST returns",
    area: "turnover",
    outcome: "pass",
    severity: "moderate",
    blocking: false,
    scope: "FY 2024-25",
    tolerance: "10%",
    explanation: "Variance 1.7% within 10%.",
    gaps: [
      {
        label: "Gap against audited",
        amount: 2_000_000,
        pct: 1.7,
        base: "GST outward supplies",
        legs: "audited against GST outward supplies",
        breached: false,
      },
    ],
    gap_tolerance: "10%",
    amount: 2_000_000,
  });
  const accounts = xvFinding({
    id: "fnd-ba2",
    rule_id: "BA-02",
    title: "Accounts on file are declared",
    area: "accounts",
    outcome: "pass",
    severity: "moderate",
    blocking: false,
    explanation: "Every account on file is declared.",
  });
  // Given in no particular order: the board is assembled as the engine assembles it.
  return xvView(KESTREL, [
    xvItem(audited),
    xvItem(name, { review_item_id: "r-id3" }),
    xvItem(window),
    xvItem(lender, { review_item_id: "r-ob2" }),
    xvItem(accounts),
    xvItem(cin, { review_item_id: "r-id5" }),
  ]);
}

test("the area cards show where the file stands, the discrepancies ranked within each area", async ({
  page,
}) => {
  const api = new MockApi();
  api.boards.set(KESTREL, board());
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);

  const identity = page.getByTestId("xv-area-card-identity");
  await expect(identity.getByTestId("xv-area-open")).toHaveText("2");
  await expect(identity.getByTestId("xv-area-severity")).toHaveText("1 serious · 1 moderate");
  await expect(identity.getByTestId("xv-area-blocking")).toBeVisible();
  await expect(identity.getByTestId("xv-area-top")).toHaveText("CIN differs between documents");
  await expect(page.getByTestId("xv-area-card-turnover")).toHaveAttribute(
    "data-status",
    "incomplete",
  );
  await expect(page.getByTestId("xv-area-card-accounts")).toHaveAttribute("data-status", "clear");
  await expect(page.getByTestId("xv-banner")).toContainText(
    "Submission blocked — 1 serious discrepancy unadjudicated",
  );
  await expect(page.getByTestId("xv-meta-line")).toContainText("0 of 3 adjudicated");
  // Ranked by credit impact within the area: the serious discrepancy before the moderate one.
  const ranked = page.getByTestId("xv-area-identity").locator("[data-rank]");
  expect(await ranked.evaluateAll((els) => els.map((e) => e.dataset["rule"]))).toEqual([
    "ID-05",
    "ID-03",
  ]);
  await expect(page.getByTestId("xv-area-obligations").getByTestId("xv-rank")).toHaveText(["1"]);
  // The first card on the board, the top of the first area with an open discrepancy, is open first;
  // the greatest gap on the board (OB-02, further down) stays closed.
  await expect(page.getByTestId("xv-card-fnd-id5")).toHaveAttribute("data-expanded", "true");
  await expect(page.getByTestId("xv-card-fnd-ob2")).toHaveAttribute("data-expanded", "false");
  await expect(page.getByTestId("xv-incomplete-row")).toHaveCount(1);
  await expect(
    page.getByTestId("xv-area-turnover").getByTestId("xv-passed").locator("summary"),
  ).toContainText("Passed (1)");
});

test("a failed check marks the value that differs and shows its sources side by side", async ({
  page,
}) => {
  const api = new MockApi();
  api.boards.set(KESTREL, board());
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);

  const cin = page.getByTestId("xv-card-fnd-id5");
  // The first card on the board opens by default.
  await expect(cin).toHaveAttribute("data-expanded", "true");
  const odd = cin.locator('[data-testid^="xv-column-"][data-differs="true"]');
  await expect(odd).toHaveCount(1);
  await expect(odd).toContainText("U28999MH2015PTC123465");
  await expect(odd.getByTestId("xv-diff")).toHaveText(["65"]);
  await expect(cin.getByTestId("xv-mismatch")).toContainText("gives U28999MH2015PTC123465");

  await cin.getByTestId("xv-compare").click();
  const compare = page.getByTestId("evidence-compare");
  await expect(compare.getByTestId("compare-pane")).toHaveCount(2);
  await expect(compare.getByTestId("compare-pane").nth(1)).toContainText("U28999MH2015PTC123465");
  await expect(compare.getByTestId("compare-pane").nth(1).getByTestId("compare-page")).toHaveText(
    "Page 3 · pages 3–9",
  );
  await page.keyboard.press("Escape");
  await expect(compare).toHaveCount(0);
});

test("an incomplete check names what is not on file; a passed check stays closed", async ({
  page,
}) => {
  const api = new MockApi();
  api.boards.set(KESTREL, board());
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);

  const turnover = page.getByTestId("xv-area-turnover");
  const window = turnover.locator('[data-testid="xv-incomplete-row"][data-rule="TO-05"]');
  await expect(window).toContainText("GSTR-3B not on file.");
  await expect(window.getByTestId("xv-request")).toHaveText("To complete it, provide the GSTR-3B.");
  await expect(window.getByTestId("xv-add-documents")).toBeVisible();

  const passed = turnover.getByTestId("xv-passed");
  await expect(passed).not.toHaveAttribute("open", "");
  const audited = passed.locator('[data-testid="xv-passed-row"][data-rule="TO-01"]');
  await expect(audited).toBeHidden();
  await passed.locator("summary").click();
  // A check that measured a variance says so in the engine's words, with the tolerance it was
  // within.
  await expect(audited).toHaveText(
    "TO-01 · Audited turnover against GST outward supplies · FY 2024-25 · Variance 1.7% within 10%.",
  );
  await expect(
    page
      .getByTestId("xv-area-accounts")
      .locator('[data-testid="xv-passed-row"][data-rule="BA-02"]'),
  ).toBeHidden();
});
