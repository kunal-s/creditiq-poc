// Traceability of the case's figures: every extracted value says where it was read (its file, page and
// printed line); a figure worked out from others shows its working with an (i) on each figure it rests on,
// in place of any pencil; a statement figure is changed only on the Extractions tab, which the working
// links to; and the Extractions tab lists what each approved change moved when the case was recalculated.
import { expect, test, type Page } from "@playwright/test";
import type { CellSource, FieldValue, Recalculation, Spread } from "../src/api/types";
import { DOCUMENTS, FACTS, KESTREL, POLICY, norm } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

const FILE = "annual-report-fy2025-26.pdf";

function source(extra: Partial<CellSource>): CellSource {
  return {
    document_id: "doc-bs",
    document: "Audited Financial Statements",
    file_name: FILE,
    page: 117,
    row_label: "Equity share capital",
    printed: "1,248.47",
    printed_value: 1248.47,
    unit_label: "INR crores",
    scale: 1e7,
    column: "current_period",
    line: "Equity share capital 1,248.47 1,242.80",
    bbox: [0.1, 0.4, 0.9, 0.42],
    field_id: "fv-share-capital",
    changed: false,
    document_value: null,
    ...extra,
  };
}

const SPREAD: Spread = {
  case_id: KESTREL,
  interim: true,
  columns: [{ key: "audited-2026", fy: "FY 2025-26", period_end: "2026-03-31", basis: "audited" }],
  rows: [
    {
      key: "share_capital",
      label: "Share capital",
      section: "balance_sheet",
      kind: "line",
      unit: "inr",
      formula: null,
      cells: [
        {
          value: 12_484_700_000,
          evidence: [{ document_id: "doc-bs", page: 117 }],
          relies_on_manual: false,
          working: { state: "printed", source: source({}), inputs: [] },
        },
      ],
    },
    {
      key: "net_worth",
      label: "Net worth",
      section: "balance_sheet",
      kind: "line",
      unit: "inr",
      formula: null,
      cells: [
        {
          value: 722_333_000_000,
          evidence: [{ document_id: "doc-bs", page: 117 }],
          relies_on_manual: true,
          working: {
            state: "derived",
            formula: "Share capital + Reserves and surplus",
            substituted: "12,48,47,00,000 + 7,09,84,83,00,000",
            inputs: [
              {
                key: "share_capital",
                label: "Share capital",
                value: 12_484_700_000,
                sign: 1,
                unit: "inr",
                state: "printed",
                parts: [],
                source: source({}),
              },
              {
                key: "reserves_and_surplus",
                label: "Reserves and surplus",
                value: 709_848_300_000,
                sign: 1,
                unit: "inr",
                state: "printed",
                parts: [],
                source: source({
                  row_label: "Other equity",
                  printed: "70,984.83",
                  printed_value: 70984.83,
                  line: "Other equity 70,984.83 66,351.00",
                  field_id: "fv-other-equity",
                  changed: true,
                  document_value: 70884.83,
                }),
              },
            ],
          },
        },
      ],
    },
  ],
  working_capital: {
    method: "turnover",
    reason: "",
    column: null,
    steps: [],
    eligible: null,
    requested: 50_000_000,
    missing: [],
  },
};

const FIELD: FieldValue = {
  id: "fv-share-capital",
  case_id: KESTREL,
  document_id: "doc-bs",
  field: "balance_sheet[23].current_period",
  value: 1248.47,
  raw: "1,248.47",
  evidence: {
    document_id: "doc-bs",
    page: 117,
    bbox: [0.1, 0.4, 0.9, 0.42],
    line: "Equity share capital 1,248.47 1,242.80",
  },
  method: "deterministic",
  confidence: 0.97,
  confidence_components: {},
  status: "accepted",
  missing_reason: null,
  corrected_value: null,
};

const RECALCULATION: Recalculation = {
  id: "RC-41",
  case_id: KESTREL,
  at: "2026-11-18T10:20:00Z",
  approved_by: "Meenal Kulkarni",
  trigger: {
    field_value_id: "fv-other-equity",
    field: "balance_sheet[24].current_period",
    label: "Other equity, current year",
    document_id: "doc-bs",
    document: "Audited Financial Statements",
    file_name: FILE,
    from_value: "70,884.83",
    to_value: "70,984.83",
    reason: "Auditor's letter revises other equity",
    changed_by: "Ananya Krishnan",
  },
  changes: [
    {
      area: "figure",
      key: "net_worth",
      label: "Net worth, FY 2025-26",
      kind: "amount",
      before: 721_333_000_000,
      after: 722_333_000_000,
    },
    {
      area: "norm",
      key: "FR-05",
      label: "FR-05 Debt / equity",
      kind: "outcome",
      before: "deviation",
      after: "pass",
      detail_before: "2.10x",
      detail_after: "1.95x",
    },
    {
      area: "check",
      key: "TO-01",
      label: "TO-01 Audited turnover against GST outward supplies",
      kind: "outcome",
      before: "pass",
      after: "fail",
    },
  ],
};

async function open(page: Page, path: string) {
  const api = new MockApi();
  api.documents.set(KESTREL, DOCUMENTS);
  api.spreads.set(KESTREL, SPREAD);
  api.facts.set(KESTREL, FACTS);
  api.policy.set(KESTREL, {
    ...POLICY,
    period: "FY 2025-26",
    norms: [
      norm({
        id: "FR-01",
        family: "ratios",
        label: "Current ratio",
        outcome: "cannot_evaluate",
        required: "at least 1.20x",
        unit: "x",
        missing: ["Share capital"],
      }),
    ],
  });
  const label: FieldValue = {
    ...FIELD,
    id: "fv-share-capital-label",
    field: "balance_sheet[23].particulars",
    value: "Equity share capital",
    raw: "Equity share capital",
  };
  api.fields.set(KESTREL, [...(api.fields.get(KESTREL) ?? []), label, FIELD]);
  api.recalculations.set(KESTREL, [RECALCULATION]);
  await signedIn(page, api);
  await page.goto(path);
  return api;
}

test("a derived figure opens its working, each input with an (i) to where it was read; nothing is edited there", async ({
  page,
}) => {
  await open(page, `/appraisals/${KESTREL}/policy`);
  await page.getByTestId("financials-tab-balance_sheet").click();
  const netWorth = page
    .getByTestId("spread-balance_sheet")
    .locator('[data-row="net_worth"] [data-testid="spread-figure"]');
  await expect(netWorth.getByTestId("spread-figure-info")).toBeVisible();
  await netWorth.click();
  const working = page.getByTestId("spread-source").getByTestId("figure-working");
  await expect(working.getByTestId("figure-calculation")).toContainText(
    "Share capital + Reserves and surplus",
  );
  // No pencil anywhere on the working: a figure is changed on the Extractions tab.
  await expect(
    working.locator("[data-testid^='figure-edit'], [data-testid='figure-revert']"),
  ).toHaveCount(0);
  const inputs = working.getByTestId("figure-input");
  await expect(inputs).toHaveCount(2);
  // A worked-out figure never says it was read from the document (this one rests on an approved change).
  await expect(page.getByTestId("spread-source")).not.toContainText("Read from the document");
  // Each traced figure opens its own page with the eye, as the working-capital steps do.
  await expect(inputs.getByTestId("figure-input-open")).toHaveCount(2);
  await inputs.nth(0).getByTestId("figure-input-open").click();
  await expect(page.getByTestId("evidence-viewer")).toBeVisible();
  await page.keyboard.press("Escape");
  await inputs.nth(1).getByTestId("figure-input-info").click();
  const reserves = inputs.nth(1).getByTestId("figure-input-source");
  await expect(reserves.getByTestId("figure-source-file")).toHaveText(`${FILE} · page 117`);
  await expect(reserves.getByTestId("figure-source-line")).toHaveText(
    "Other equity 70,984.83 66,351.00",
  );
  await expect(reserves.getByTestId("figure-source-changed")).toHaveText(
    "Changed on the Extractions tab and approved. The statement printed 70,884.83.",
  );
  await expect(reserves.getByTestId("figure-source-change")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/extraction?field=fv-other-equity`,
  );
});

test("a statement figure's source leads to its value on the Extractions tab", async ({ page }) => {
  await open(page, `/appraisals/${KESTREL}/policy`);
  await page.getByTestId("financials-tab-balance_sheet").click();
  await page
    .getByTestId("spread-balance_sheet")
    .locator('[data-row="share_capital"] [data-testid="spread-figure"]')
    .click();
  const working = page.getByTestId("spread-source").getByTestId("figure-working");
  await expect(working.getByTestId("figure-source-line")).toHaveText(
    "Equity share capital 1,248.47 1,242.80",
  );
  await expect(working.getByTestId("figure-change-hint")).toBeVisible();
  await working.getByTestId("figure-source-change").click();
  await expect(page).toHaveURL(
    new RegExp(`/appraisals/${KESTREL}/extraction\\?field=fv-share-capital$`),
  );
  const focused = page.getByTestId("field-focused");
  await expect(focused).toContainText("Equity share capital · Current period · 1,248.47");
  await expect(focused).toContainText("page 117");
  await expect(focused).toContainText("Equity share capital 1,248.47 1,242.80");
  await expect(page.locator('[data-focused="true"]')).toHaveCount(1);
});

test("a ratio missing a statement figure points to the Extractions tab, not to an entry box", async ({
  page,
}) => {
  await open(page, `/appraisals/${KESTREL}/policy`);
  const supply = page.getByTestId("ratio-supply");
  await expect(supply).toHaveText("Supply Share capital on the Extractions tab");
  await expect(supply).toHaveAttribute("href", `/appraisals/${KESTREL}/extraction`);
  await expect(page.getByTestId("ratio-enter")).toHaveCount(0);
});

test("the Extractions tab says where each value was read and what an approved change moved", async ({
  page,
}) => {
  await open(page, `/appraisals/${KESTREL}/extraction`);
  await page.getByTestId("data-filter-all").click();
  await expect(page.getByTestId("field-source").first()).toContainText("Page");
  const panel = page.getByTestId("recalc-panel");
  const entry = panel.getByTestId("recalc-entry");
  await expect(entry).toHaveAttribute("data-field", "fv-other-equity");
  await expect(entry).toContainText("Other equity, current year");
  await expect(entry.getByTestId("recalc-from-to")).toHaveText("70,884.83 → 70,984.83");
  await expect(entry).toContainText("Changed by Ananya Krishnan · approved by Meenal Kulkarni");
  await expect(entry.locator('[data-area="figure"][data-key="net_worth"]')).toContainText("→");
  await expect(entry.locator('[data-area="norm"][data-key="FR-05"]')).toContainText(
    "Deviation (2.10x)",
  );
  await expect(entry.locator('[data-area="norm"][data-key="FR-05"]')).toContainText(
    "Passed (1.95x)",
  );
  await expect(entry.locator('[data-area="check"][data-key="TO-01"]')).toContainText("Agrees");
  await expect(entry.locator('[data-area="check"][data-key="TO-01"]')).toContainText("Differs");
});

test("a statement whose rows the model mapped says so on its table", async ({ page }) => {
  const api = await open(page, `/appraisals/${KESTREL}/extraction`);
  const mapped = (api.fields.get(KESTREL) ?? []).map((f) =>
    f.field.startsWith("balance_sheet[") ? { ...f, method: "model" as const } : f,
  );
  api.fields.set(KESTREL, mapped);
  await page.reload();
  await page.getByTestId("data-filter-all").click();
  await expect(page.getByTestId("field-table-by-model")).toHaveText(
    "Rows mapped by the model · figures read from the page",
  );
});
