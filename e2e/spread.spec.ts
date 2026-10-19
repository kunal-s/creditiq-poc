// The Spread tab (FRD F-22, F-18.1, F-20): the audited years line by line, turnover from every
// source year by year coloured by what the cross-checks concluded, and the ratios against the
// policy norms in the band the engine placed them. The screen arranges; it decides nothing.
import { expect, test, type Page } from "@playwright/test";
import type { CaseFacts, Spread, TurnoverFigure } from "../src/api/types";
import {
  DOCUMENTS,
  FACTS,
  KESTREL,
  POLICY,
  XV_DOCUMENTS,
  XV_DOCUMENT_TYPES,
  norm,
  xvFinding,
  xvItem,
  xvSide,
  xvView,
} from "./fixtures/data";
import { MockApi, scrollsSideways, signedIn } from "./support/api";

const SPREAD_PATH = `/appraisals/${KESTREL}/spread`;
const page14 = [{ document_id: "doc-bs", page: 4 }];

const SPREAD: Spread = {
  case_id: KESTREL,
  interim: true,
  columns: [
    { key: "audited-2025", fy: "FY 2024-25", period_end: "2025-03-31", basis: "audited" },
    { key: "audited-2026", fy: "FY 2025-26", period_end: "2026-03-31", basis: "audited" },
  ],
  rows: [
    {
      key: "revenue_from_operations",
      label: "Revenue from operations",
      section: "profit_and_loss",
      kind: "line",
      unit: "inr",
      formula: null,
      cells: [
        { value: 100_000_000, evidence: page14, relies_on_manual: false },
        { value: 120_000_000, evidence: page14, relies_on_manual: false },
      ],
    },
    {
      key: "current_liabilities",
      label: "Current liabilities",
      section: "balance_sheet",
      kind: "line",
      unit: "inr",
      formula: null,
      cells: [
        { value: 30_000_000, evidence: page14, relies_on_manual: false },
        {
          value: 32_700_000,
          evidence: [{ document_id: "doc-bs", page: 12 }],
          relies_on_manual: true,
        },
      ],
    },
    {
      key: "wc-cycle",
      label: "Working-capital cycle",
      section: "ratios",
      kind: "ratio",
      unit: "days",
      formula: null,
      cells: [
        { value: 71, evidence: page14, relies_on_manual: false },
        { value: 87, evidence: page14, relies_on_manual: false },
      ],
    },
    {
      key: "ebitda_margin",
      label: "EBITDA margin",
      section: "profit_and_loss",
      kind: "derived",
      unit: "%",
      formula: null,
      cells: [
        { value: 11.0, evidence: page14, relies_on_manual: false },
        { value: 12.5, evidence: page14, relies_on_manual: false },
      ],
    },
  ],
  working_capital: {
    method: "not_applicable",
    reason: "",
    column: null,
    steps: [],
    eligible: null,
    requested: 50_000_000,
    missing: [],
  },
};

const figure = (
  source: TurnoverFigure["source"],
  label: string,
  value: number,
): TurnoverFigure => ({
  source,
  label,
  value,
  months_covered: source === "gst" || source === "bank" ? 12 : null,
  months_missing: [],
  evidence: [{ document_id: "doc-bs", page: 4 }],
  field_ids: [],
  relies_on_manual: false,
  awaiting_review: false,
});

const FACTS_TWO_YEARS: CaseFacts = {
  ...FACTS,
  turnover: [
    {
      fy: "FY 2025-26",
      fy_end: "2026-03-31",
      figures: [
        figure("financials", "Audited financial statements", 120_000_000),
        figure("gst", "GST outward supplies", 119_500_000),
        figure("bank", "Business credits in bank statements", 98_000_000),
      ],
    },
    {
      fy: "FY 2024-25",
      fy_end: "2025-03-31",
      figures: [figure("financials", "Audited financial statements", 100_000_000)],
    },
  ],
};

/** Audited against GST passes; audited against bank credits fails on the bank side. */
function board() {
  const side = (label: string, value: number, sources: string[], differs = false) =>
    xvSide(label, value, [], { sources, differs });
  return xvView(KESTREL, [
    xvItem(
      xvFinding({
        id: "t-bank",
        rule_id: "TO-03",
        title: "Audited turnover against cleansed bank credits · FY 2025-26",
        finding_title: "Bank credits fall short of audited turnover",
        area: "turnover",
        outcome: "fail",
        severity: "moderate",
        blocking: false,
        scope: "FY 2025-26",
        ref: "XV-000021-03",
        explanation: "Business credits INR 9.80 cr against audited turnover INR 12.00 cr.",
        sides: [
          side("Audited financial statements", 120_000_000, ["audited_financial_statements"]),
          side("Business credits in bank statements", 98_000_000, ["bank_statement"], true),
        ],
      }),
    ),
    xvItem(
      xvFinding({
        id: "t-gst",
        rule_id: "TO-01",
        title: "Audited turnover against GST outward supplies · FY 2025-26",
        area: "turnover",
        outcome: "pass",
        severity: "moderate",
        blocking: false,
        scope: "FY 2025-26",
        explanation: "",
        sides: [
          side("Audited financial statements", 120_000_000, ["audited_financial_statements"]),
          side("GST outward supplies", 119_500_000, ["gstr_3b"]),
        ],
      }),
    ),
  ]);
}

const ratioNorm = (
  id: string,
  label: string,
  outcome: "pass" | "deviation" | "cannot_evaluate",
  band: "within" | "marginal" | "outside" | null,
  actual: number | null,
  unit: string,
  required: string,
) =>
  norm({
    id,
    family: "ratios",
    label,
    outcome,
    band,
    actual,
    unit,
    required,
    marginal_text: unit === "days" ? "95 days" : "1.10x",
  });

const POLICY_BANDS = {
  ...POLICY,
  period: "FY 2025-26",
  norms: [
    ratioNorm("FR-01", "Current ratio", "pass", "within", 1.28, "x", "at least 1.20x"),
    ratioNorm(
      "FR-06",
      "Working-capital cycle",
      "deviation",
      "marginal",
      87,
      "days",
      "at most 75 days",
    ),
    ratioNorm("FR-02", "TOL / TNW", "deviation", "outside", 4.1, "x", "at most 3.00x"),
    ratioNorm("FR-03", "DSCR", "cannot_evaluate", null, null, "x", "at least 1.50x"),
  ],
};

async function openSpread(page: Page) {
  const api = new MockApi();
  api.documents.set(KESTREL, [...DOCUMENTS, ...XV_DOCUMENTS]);
  api.documentTypes = XV_DOCUMENT_TYPES;
  api.spreads.set(KESTREL, SPREAD);
  api.facts.set(KESTREL, FACTS_TWO_YEARS);
  api.policy.set(KESTREL, POLICY_BANDS);
  api.boards.set(KESTREL, board());
  await signedIn(page, api);
  await page.goto(SPREAD_PATH);
  await expect(page.getByTestId("spread-page")).toBeVisible();
  return api;
}

const cell = (page: Page, source: string, fy: string) =>
  page.locator(
    `[data-testid="spread-turnover-row"][data-source="${source}"] [data-testid="spread-turnover-cell"][data-fy="${fy}"]`,
  );

test("the Spread tab sits with Cross-checks and Policy, and opens on the latest year", async ({
  page,
}) => {
  await openSpread(page);
  await expect(page.getByTestId("page-header")).toContainText(`Appraisal ${KESTREL} · Spread`);
  await expect(page.getByRole("link", { name: "Spread", exact: true }).first()).toBeVisible();
  await expect(page.getByTestId("spread-period-FY 2025-26")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByTestId("spread-period")).toContainText("Year ended 31 Mar 2026 · Audited");
  await page.getByTestId("spread-period-FY 2024-25").click();
  await expect(page.getByTestId("spread-period-FY 2024-25")).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByTestId("spread-period")).toContainText("Year ended 31 Mar 2025");
});

test("turnover is laid out year by year, each figure coloured by what the cross-checks concluded", async ({
  page,
}) => {
  await openSpread(page);
  const rows = page.getByTestId("spread-turnover-row");
  await expect(rows).toHaveCount(3);
  expect(await rows.evaluateAll((els) => els.map((e) => e.dataset["source"]))).toEqual([
    "financials",
    "gst",
    "bank",
  ]);
  // Oldest year first.
  await expect(page.getByTestId("spread-turnover").locator("thead th").nth(1)).toHaveText(
    "FY 2024-25",
  );

  await expect(cell(page, "gst", "FY 2025-26")).toHaveAttribute("data-verdict", "agrees");
  await expect(cell(page, "gst", "FY 2025-26").getByTestId("spread-figure")).toHaveClass(
    /text-positive/,
  );
  await expect(cell(page, "bank", "FY 2025-26")).toHaveAttribute("data-verdict", "differs");
  await expect(cell(page, "bank", "FY 2025-26").getByTestId("spread-figure")).toHaveClass(
    /text-destructive/,
  );
  await expect(cell(page, "bank", "FY 2025-26")).toContainText("9.80");
  // The audited figure agrees with GST and is not the differing side against the bank.
  await expect(cell(page, "financials", "FY 2025-26")).toHaveAttribute("data-verdict", "agrees");
  // No check read the earlier year.
  await expect(cell(page, "financials", "FY 2024-25")).toHaveAttribute("data-verdict", "none");
  await expect(page.getByTestId("spread-turnover-legend")).toContainText(
    "Differs outside tolerance",
  );
});

test("an open turnover discrepancy heads the tab and leads to Cross-checks", async ({ page }) => {
  await openSpread(page);
  const banner = page.getByTestId("spread-banner");
  await expect(banner).toContainText("Bank credits fall short of audited turnover");
  await expect(banner).toContainText("Business credits in bank statements — 9.80 cr");
  await banner.getByTestId("spread-banner-open").click();
  await expect(page).toHaveURL(/\/cross-verification\?finding=XV-000021-03$/);
});

test("the statements are line by line, and a person's entry is named for confirmation", async ({
  page,
}) => {
  await openSpread(page);
  const pl = page.getByTestId("spread-profit_and_loss");
  await expect(pl.locator('[data-row="revenue_from_operations"]')).toContainText("10.00");
  await expect(pl.locator('[data-row="revenue_from_operations"]')).toContainText("12.00");
  const bs = page.getByTestId("spread-balance_sheet");
  await expect(bs.getByTestId("spread-manual-note")).toHaveText(
    "Current liabilities FY 2025-26 relies on a person's entry; confirm it against page 12 before the spread is relied on.",
  );
  await expect(page.getByTestId("spread-status")).toContainText("Relying on a person's entry");
});

test("a figure shows where it was read from, and opens its page", async ({ page }) => {
  await openSpread(page);
  const source = page.getByTestId("spread-source");
  await expect(source).toContainText("Select any figure");
  await page
    .getByTestId("spread-profit_and_loss")
    .locator('[data-row="revenue_from_operations"] [data-testid="spread-figure"]')
    .last()
    .click();
  await expect(source).toContainText("Revenue from operations · FY 2025-26");
  await expect(source).toContainText("12.00");
  await expect(source).toContainText("Page 4");
  await source.getByTestId("spread-source-open").click();
  await expect(page.getByTestId("evidence-viewer")).toBeVisible();
});

test("the ratios read in the band the engine placed them, beside the norm", async ({ page }) => {
  await openSpread(page);
  const tiles = page.getByTestId("spread-ratio");
  // The norms arrive after the spread: wait for every tile before reading their order.
  await expect(tiles).toHaveCount(5);
  expect(
    await tiles.evaluateAll((els) => els.map((e) => `${e.dataset["ratio"]}:${e.dataset["band"]}`)),
  ).toEqual([
    "FR-01:within",
    "FR-06:marginal",
    "FR-02:outside",
    "FR-03:cannot",
    "ebitda_margin:noNorm",
  ]);
  const tile = (id: string) => page.locator(`[data-testid="spread-ratio"][data-ratio="${id}"]`);
  await expect(tile("FR-01")).toContainText("Within policy");
  await expect(tile("FR-06")).toContainText("Marginal");
  await expect(tile("FR-06")).toContainText("Policy at most 75 days · marginal 95 days");
  await expect(tile("FR-02")).toContainText("Outside policy");
  await expect(tile("FR-03")).toContainText("Cannot evaluate");
  await expect(tile("ebitda_margin")).toContainText("No policy norm");
  await expect(page.getByTestId("spread-ratios")).toContainText("Computed on FY 2025-26 figures");
});

test("the trend notes describe the move from the year before", async ({ page }) => {
  await openSpread(page);
  await expect(page.getByTestId("spread-trend-turnover")).toContainText(
    "Turnover grew 20.0% in FY 2025-26",
  );
  await expect(page.getByTestId("spread-trend-cycle")).toContainText(
    "Working-capital cycle lengthened by 16 days in FY 2025-26",
  );
});

test("on a phone the tab reads in one column without scrolling sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openSpread(page);
  expect(await scrollsSideways(page)).toBe(false);
});
