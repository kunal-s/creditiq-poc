// CreditIQ against RBL's record (FRD F-25): the deviations area is test plan TC-24's pass rule
// ("agrees with RBL's deviation record"), the approving-authority area TC-25's ("agrees with
// the matrix"; not scored while the matrix is provisional). Only the Credit Manager, as RBL's
// reviewer, sees and adjudicates it; decisions sit beside the output and never change it.
import { expect, test } from "@playwright/test";
import { KESTREL, MANAGER, comparison, staleComparison } from "./fixtures/data";
import { MockApi, scrollsSideways, signedIn } from "./support/api";

const item = (page: import("@playwright/test").Page, key: string) =>
  page.locator(`[data-testid="comparison-item"][data-key="${key}"]`);

test("the analyst neither sees nor reaches the comparison", async ({ page }) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison());
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/policy`);
  await expect(page.getByRole("link", { name: "Comparison", exact: true })).toHaveCount(0);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(page.getByTestId("state-forbidden")).toBeVisible();
  await expect(page.getByTestId("comparison-item")).toHaveCount(0);
});

test("with no record imported, the comparison waits for it", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(page.getByTestId("comparison-waiting")).toHaveText(
    "RBL's record for this appraisal has not been imported yet.",
  );
  await expect(page.getByTestId("comparison-other-areas")).toBeVisible();
});

test("the reviewer confirms an imported record before adjudicating", async ({ page }) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison(false));
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  const bar = page.getByTestId("record-status");
  await expect(bar).toContainText("Record imported from kestrel-record.xlsx");
  await expect(bar).toContainText("Not yet confirmed by the reviewer");
  // Unconfirmed: nothing can be adjudicated yet.
  await expect(page.getByTestId("adjudicate-valid")).toHaveCount(0);
  const before = api.calls.length;
  await page.getByTestId("record-confirm").click();
  await expect(bar).toContainText("Confirmed by Meenal Kulkarni");
  // Confirming refreshes the comparison and nothing else.
  expect(
    api.calls
      .slice(before)
      .filter((c) => c.key.startsWith("GET "))
      .map((c) => c.key),
  ).toEqual([`GET /api/cases/${KESTREL}/comparison`]);
  expect(api.called("POST", `/api/cases/${KESTREL}/reference/confirm`)).toHaveLength(1);
  await expect(item(page, "EL-04").getByTestId("adjudicate-valid")).toBeVisible();
});

test("the person who imported the record cannot confirm it", async ({ page }) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison(false, MANAGER.id));
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(page.getByTestId("record-confirm")).toBeDisabled();
  await expect(page.getByTestId("record-self-confirm")).toHaveText(
    "The record must be confirmed by someone other than who imported it.",
  );
});

test("TC-24: deviations are compared with RBL's record, each with its evidence", async ({
  page,
}) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(page.getByTestId("comparison-counts")).toHaveText(
    "Deviations: Agree 1 · Differ 1 · New 1 · Missed 3",
  );
  await expect(page.getByTestId("comparison-provisional-norms")).toBeVisible();
  await expect(item(page, "FR-05")).toHaveAttribute("data-status", "agree");
  await expect(item(page, "FR-05")).toContainText("CAM p.14, deviation table row 1");
  await item(page, "FR-05").getByTestId("comparison-creditiq-evidence").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("4");
  await page.keyboard.press("Escape");

  await expect(item(page, "DOC-01").getByTestId("comparison-note")).toHaveText(
    "Value differs: 2 against 3 items",
  );
  await expect(item(page, "FR-01").getByTestId("comparison-note")).toHaveText(
    "CreditIQ assessed it as passed: 1.50x against at least 1.20x",
  );
  await expect(item(page, "EL-02").getByTestId("comparison-note")).toHaveText(
    "CreditIQ could not evaluate it: Commercial bureau rank",
  );
  await expect(item(page, "REC-6").getByTestId("comparison-note")).toHaveText(
    "No norm in the policy covers this deviation.",
  );
  // Missed and agreed items are never adjudicated.
  for (const key of ["FR-05", "EL-02", "FR-01", "REC-6"])
    await expect(item(page, key).getByTestId("adjudicate-valid")).toHaveCount(0);
  await expect(page.locator('[data-testid="area-score"][data-area="deviations"]')).toHaveText(
    "2 of 5 deviations in RBL's record found · 1 of 3 CreditIQ deviations upheld (2 awaiting a decision)",
  );
});

test("a new deviation is adjudicated with a reason", async ({ page }) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(page.getByTestId("comparison-filter-toAdjudicate")).toHaveText("To decide (3)");
  await page.getByTestId("comparison-filter-toAdjudicate").click();
  await expect(page.getByTestId("comparison-item")).toHaveCount(3);

  const row = item(page, "EL-04");
  await expect(row).toHaveAttribute("data-status", "new");
  await row.getByTestId("adjudicate-valid").click();
  const save = row.getByTestId("adjudication-save");
  await expect(save).toBeDisabled();
  await row.getByTestId("adjudication-reason").fill("ok");
  await expect(save).toBeDisabled();
  await row.getByTestId("adjudication-reason").fill("Loss confirmed in the audited statements");
  await expect(save).toBeEnabled();
  const before = api.calls.length;
  await save.click();
  // Decided, it leaves the list of items still to decide.
  await expect(page.getByTestId("comparison-filter-toAdjudicate")).toHaveText("To decide (2)");
  // Saving sends the decision and refreshes the comparison, nothing else (F-25.5).
  expect(api.calls.slice(before).map((c) => c.key)).toEqual([
    `PUT /api/cases/${KESTREL}/comparison/deviations/EL-04/adjudication`,
    `GET /api/cases/${KESTREL}/comparison`,
  ]);
  await expect(row).toHaveCount(0);
  await page.getByTestId("comparison-filter-all").click();
  await expect(row.getByTestId("adjudication-decided")).toContainText("Valid · Meenal Kulkarni");
  await expect(row.getByTestId("adjudication-change")).toBeVisible();
  const put = api.called("PUT", `/api/cases/${KESTREL}/comparison/deviations/EL-04/adjudication`);
  expect(put).toHaveLength(1);
  expect(put[0]!.body).toEqual({
    verdict: "valid",
    reason: "Loss confirmed in the audited statements",
  });
});

test("once RBL's matrix is in force, the authority is scored in its own words", async ({
  page,
}) => {
  const api = new MockApi();
  const scored = comparison();
  scored.provisional_matrix = false;
  scored.items.find((i) => i.area === "approving_authority")!.scored = true;
  scored.scores.push({
    area: "approving_authority",
    scored: true,
    found_in_record: 0,
    recorded_total: 1,
    valid: 0,
    flagged_total: 1,
    pending: 1,
  });
  api.comparisons.set(KESTREL, scored);
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(
    page.locator('[data-testid="area-score"][data-area="approving_authority"]'),
  ).toHaveText("Recorded approval agrees with the matrix: 0 of 1 (1 awaiting a decision)");
  await expect(page.getByTestId("comparison-not-scored")).toHaveCount(0);
});

test("TC-25: the recorded authority is compared with the rule applied, not scored", async ({
  page,
}) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(page.getByTestId("comparison-not-scored")).toHaveText(
    "Not scored while the approval matrix is provisional.",
  );
  const row = item(page, "approval");
  await expect(row).toHaveAttribute("data-status", "differ");
  await expect(row).toContainText("Regional Credit Head · Level 2");
  await expect(row).toContainText("Zonal Credit Committee");
  await expect(row.getByTestId("comparison-note")).toHaveText(
    "The recorded approval is above the required authority.",
  );
  await expect(row.getByTestId("comparison-authority-detail")).toContainText(
    "Rule applied: Eligibility deviation (EL-04)",
  );
  await expect(row.getByTestId("comparison-authority-on-record")).toHaveText(
    "On RBL's recorded deviations, the matrix requires Regional Credit Head.",
  );
  await expect(
    page.locator('[data-testid="area-score"][data-area="approving_authority"]'),
  ).toHaveCount(0);
});

test("a decision on an item that has changed since is shown stale", async ({ page }) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, staleComparison());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  const row = item(page, "DOC-01");
  await expect(row.getByTestId("adjudication-stale")).toHaveText(
    "CreditIQ's result or the record has changed since this decision; decide again.",
  );
  await expect(row.getByTestId("adjudicate-valid")).toBeVisible();
});

test("at phone width the comparison rows stack without sideways scrolling", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 800 });
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/comparison`);
  await expect(page.getByTestId("comparison-item").first()).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
});
