// The Cross-verification tab (FRD F-19, F-16.2; docs/cross-verification-plan.md): the
// outcome tiles and the areas of the file show where it stands at a glance; one area can
// be shown alone; a failed check highlights the value that differs, opens its line-by-line
// detail and shows its sources side by side; an incomplete check names what is not on file.
import { expect, test } from "@playwright/test";
import type { Finding, FindingSide } from "../src/api/types";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

const side = (
  label: string,
  value: string | number,
  documentId: string,
  page: number,
  differs = false,
): FindingSide => ({
  label,
  value,
  evidence: [{ document_id: documentId, page }],
  relies_on_manual: false,
  awaiting_review: false,
  differs,
  field_ids: [],
});

const base = {
  case_id: KESTREL,
  config_version: "v1",
  run_id: null,
  detail: null,
  missing: [],
  scope: null,
};

const CHECKS: Finding[] = [
  {
    ...base,
    id: "fnd-id5",
    rule_id: "ID-05",
    title: "CIN consistent across documents",
    area: "identity",
    outcome: "fail",
    severity: "serious",
    blocking: true,
    explanation:
      "The CIN differs between documents: U28999MH2015PTC123456 (Certificate of incorporation) · U28999MH2015PTC123465 (Memorandum and articles of association).",
    sides: [
      side("Certificate of incorporation", "U28999MH2015PTC123456", "doc-bs", 1),
      side("Memorandum and articles of association", "U28999MH2015PTC123465", "doc-bank", 2, true),
    ],
    tolerance: null,
    query: "Please confirm the company's CIN.",
  },
  {
    ...base,
    id: "fnd-br1",
    rule_id: "BR-01",
    title: "Board resolution covers the amount requested",
    area: "authority",
    outcome: "fail",
    severity: "serious",
    blocking: true,
    explanation:
      "The board resolution authorises borrowing up to INR 2.00 cr; the amount requested is INR 6.50 cr.",
    sides: [
      side("Board resolution limit", 20_000_000, "doc-bs", 3, true),
      side("Amount requested", 65_000_000, "doc-gst", 1),
    ],
    tolerance: null,
    query: "Please provide a board resolution authorising borrowing of INR 6.50 cr.",
  },
  {
    ...base,
    id: "fnd-to5",
    rule_id: "TO-05",
    title: "GST outward supplies against bank credits, months both cover",
    area: "turnover",
    outcome: "incomplete",
    severity: "moderate",
    blocking: false,
    explanation: "GSTR-3B not on file.",
    sides: [],
    missing: ["GSTR-3B"],
    tolerance: null,
    query: null,
  },
  {
    ...base,
    id: "fnd-tx1",
    rule_id: "TX-01",
    title: "Each audited year has its income tax return",
    area: "tax",
    outcome: "pass",
    severity: "mild",
    blocking: false,
    explanation: "Every audited year that is due has its return on file.",
    sides: [side("Income tax returns", "AY 2025-26", "doc-gst", 1)],
    detail: {
      columns: ["Return on file"],
      rows: [{ label: "FY 2024-25", cells: ["✓"], flagged: false }],
    },
    tolerance: null,
    query: null,
  },
];

test("the areas of the file show where it stands, and one area can be shown alone", async ({
  page,
}) => {
  const api = new MockApi();
  api.findings.set(KESTREL, structuredClone(CHECKS));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);

  await expect(page.getByTestId("findings-filter-fail")).toContainText("2");
  await expect(page.getByTestId("findings-filter-fail")).toContainText("2 blocking");
  const card = (area: string) => page.locator(`[data-testid="area-card"][data-area="${area}"]`);
  await expect(card("identity")).toHaveAttribute("data-state", "fail");
  await expect(card("authority")).toHaveAttribute("data-state", "fail");
  await expect(card("turnover")).toHaveAttribute("data-state", "incomplete");
  await expect(card("tax")).toHaveAttribute("data-state", "pass");
  await expect(card("accounts")).toHaveAttribute("data-state", "not_applicable");

  // Failures are grouped by area, identity first.
  const areas = page.getByTestId("finding-area");
  await expect(areas).toHaveCount(2);
  await expect(areas.first()).toHaveAttribute("data-area", "identity");

  await card("authority").click();
  await expect(page.locator('[data-testid="finding"][data-rule="BR-01"]')).toBeVisible();
  await expect(page.locator('[data-testid="finding"][data-rule="ID-05"]')).toHaveCount(0);
  await page.getByTestId("findings-all-areas").click();
  await expect(page.locator('[data-testid="finding"][data-rule="ID-05"]')).toBeVisible();
});

test("a failed check highlights the value that differs and shows its sources side by side", async ({
  page,
}) => {
  const api = new MockApi();
  api.findings.set(KESTREL, structuredClone(CHECKS));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);

  const cin = page.locator('[data-testid="finding"][data-rule="ID-05"]');
  const odd = cin.locator('[data-testid="finding-side"][data-differs="true"]');
  await expect(odd).toHaveCount(1);
  await expect(odd).toContainText("U28999MH2015PTC123465");

  await cin.getByTestId("finding-compare").click();
  const compare = page.getByTestId("evidence-compare");
  await expect(compare.getByTestId("compare-pane")).toHaveCount(2);
  await expect(compare.getByTestId("compare-pane").nth(1)).toContainText("U28999MH2015PTC123465");
  await page.keyboard.press("Escape");
  await expect(compare).toHaveCount(0);
});

test("an incomplete check names what is not on file; a pass keeps its detail closed", async ({
  page,
}) => {
  const api = new MockApi();
  api.findings.set(KESTREL, structuredClone(CHECKS));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);

  await page.getByTestId("findings-filter-incomplete").click();
  const window = page.locator('[data-testid="finding"][data-rule="TO-05"]');
  await expect(window.getByTestId("finding-missing")).toContainText("GSTR-3B");

  await page.getByTestId("findings-filter-pass").click();
  const tax = page.locator('[data-testid="finding"][data-rule="TX-01"]');
  await expect(tax.getByTestId("finding-sources")).not.toHaveAttribute("open", "");
  await expect(tax.getByTestId("finding-detail")).not.toHaveAttribute("open", "");
});
