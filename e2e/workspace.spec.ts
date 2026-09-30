// The appraisal workspace (FRD §6): the Overview says what is still needed
// and what waits for a decision; Completeness filters its checklist; links
// to a part of a tab land on it.
import { expect, test } from "@playwright/test";
import { FINDING_ITEM, KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("Overview lists what is still needed and what waits for a decision", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  const needed = page.getByTestId("still-needed");
  await expect(needed).toContainText("KYC of directors");
  await expect(needed).toContainText("Valuation report");
  const waiting = page.getByTestId("waiting-decision");
  await expect(waiting.getByRole("link")).toHaveCount(2);
  await expect(waiting.getByRole("link").first()).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/documents`,
  );
});

test("Completeness filters the checklist by status", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const items = page.getByTestId("checklist-item");
  await expect(items).toHaveCount(9);
  await page.getByTestId("checklist-filter-blocking").click();
  for (const status of await items.evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-status")),
  ))
    expect(["missing", "insufficient", "in_review"]).toContain(status);
  await page.getByTestId("checklist-filter-satisfied").click();
  for (const status of await items.evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-status")),
  ))
    expect(["satisfied", "waived"]).toContain(status);
});

test("a link to the query list lands on it", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.setViewportSize({ width: 1024, height: 700 });
  await page.goto(`/appraisals/${KESTREL}/completeness#queries`);
  await expect(page.getByTestId("query-list")).toBeInViewport();
});

test("an extracted value in review is confirmed from its row", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  const decision = page.locator('[data-testid="field-decision"][data-field="monthly[2].credits"]');
  await decision.getByTestId("field-confirm").click();
  await expect(page.getByText("Decision recorded")).toBeVisible();
  const [call] = api.called("POST", "/api/review/r-field/decision");
  expect(call?.body).toEqual({ decision: "confirm", value: null, reason: null });
});

test("a correction is made beside the source page", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  const decision = page.locator('[data-testid="field-decision"][data-field="monthly[2].credits"]');
  await decision.getByTestId("field-correct").click();
  const viewer = page.getByTestId("evidence-viewer");
  await expect(viewer.getByTestId("viewer-page")).toContainText("7");
  await expect(viewer.getByTestId("viewer-save")).toBeDisabled();
  await viewer.getByTestId("viewer-value-input").fill("41,23,000");
  await viewer.getByTestId("viewer-reason-input").fill("Misread 2 as 0");
  await viewer.getByTestId("viewer-save").click();
  await expect(page.getByText("Decision recorded")).toBeVisible();
  const [call] = api.called("POST", "/api/review/r-field/decision");
  expect(call?.body).toEqual({ decision: "correct", value: 4123000, reason: "Misread 2 as 0" });
});

test("the extracted data is grouped by kind of document", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  await expect(page.getByTestId("field-section-banking")).toContainText("Bank statement");
  await expect(page.getByTestId("field-section-financials")).toContainText("Balance sheet");
});

test("when processing finishes, the rest of the appraisal refreshes", async ({ page }) => {
  const api = new MockApi();
  let calls = 0;
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/progress$`), () => {
    const progress = api.progress(KESTREL);
    calls += 1;
    if (calls <= 2) progress.stages[0]!.status = "in_progress";
    return { json: progress };
  });
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  await expect(page.getByTestId("still-needed")).toBeVisible();
  const before = api.called("GET", `/api/cases/${KESTREL}/checklist`).length;
  await expect.poll(() => calls, { timeout: 15_000 }).toBeGreaterThan(2);
  await expect
    .poll(() => api.called("GET", `/api/cases/${KESTREL}/checklist`).length)
    .toBeGreaterThan(before);
});

test("Cross-verification shows each finding with both sides and its evidence", async ({ page }) => {
  const api = new MockApi();
  api.review.push(structuredClone(FINDING_ITEM));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);
  const findings = page.getByTestId("findings");
  await expect(findings).toContainText("1 finding(s) · 1 incomplete · 1 passed");
  const ob2 = page.locator('[data-testid="finding"][data-rule="OB-02"]');
  await expect(ob2).toContainText("ASHWOOD FINSERV");
  await expect(ob2.getByTestId("finding-side")).toHaveCount(2);
  await ob2.getByTestId("finding-evidence").first().click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("7");
  await page.keyboard.press("Escape");

  await page.getByTestId("findings-filter-incomplete").click();
  await expect(page.locator('[data-testid="finding"][data-rule="TO-01"]')).toContainText(
    "8 of 12 months",
  );
  await expect(page.getByTestId("facts-credits")).toContainText("Loan disbursal");
  await expect(page.getByTestId("facts-obligations")).toContainText("ASHWOOD FINSERV");
});

test("a finding is accepted as valid, or found not valid with a reason", async ({ page }) => {
  const api = new MockApi();
  api.review.push(structuredClone(FINDING_ITEM));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);
  const ob2 = page.locator('[data-testid="finding"][data-rule="OB-02"]');
  await ob2.getByTestId("finding-not-valid").click();
  await expect(ob2.getByTestId("finding-waive")).toBeDisabled();
  await ob2.getByTestId("finding-reason").fill("Instalments are for an equipment lease");
  await ob2.getByTestId("finding-waive").click();
  await expect(page.getByText("Decision recorded")).toBeVisible();
  const [call] = api.called("POST", "/api/review/r-finding/decision");
  expect(call?.body).toEqual({
    decision: "waive",
    value: null,
    reason: "Instalments are for an equipment lease",
  });
});

test("a blocking cross-check finding shows on the Completeness summary", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  await expect(page.getByTestId("blocking-findings")).toHaveText(
    "1 blocking cross-check finding(s) to decide →",
  );
  await page.getByTestId("blocking-findings").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/cross-verification$`));
});

test("Policy lists every norm with its required and actual value, deviations first", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/policy`);
  await expect(page.getByTestId("deviation-summary")).toContainText("1 deviation(s) from policy");
  await expect(page.getByTestId("deviation-summary")).toContainText(
    "Financial norms: Debt / equity",
  );
  const de = page.locator('[data-testid="norm"][data-norm="FR-05"]');
  await expect(de).toContainText("at most 2.00x");
  await expect(de.getByTestId("norm-actual")).toHaveText("3.00x");
  await de.getByTestId("norm-input").first().getByRole("button").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("4");
  await page.keyboard.press("Escape");
  const rank = page.locator('[data-testid="norm"][data-norm="EL-02"]');
  await expect(rank.getByTestId("norm-missing")).toHaveText(
    "Cannot evaluate: Commercial bureau rank not on file.",
  );
});

test("Outputs: the spread, the draft CAM and the PD note, each figure cited", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/outputs`);
  await expect(page.getByTestId("spread-interim")).toBeVisible();
  const revenue = page.locator('[data-testid="spread-row"][data-row="revenue_from_operations"]');
  await revenue.getByTestId("spread-value").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("4");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("wc-verdict")).toContainText("INR 6.00 cr");

  await page.getByTestId("view-cam").click();
  const cam = page.getByTestId("cam");
  await expect(cam.locator('[data-section="financials"]').getByTestId("citation")).toHaveCount(1);
  await expect(cam.locator('[data-section="banking"]')).toContainText("Nothing on file yet.");
  await expect(page.getByTestId("cam-summary")).toContainText("Findings (1)");
  await expect(page.getByTestId("cam-recommendation")).toContainText("For credit to complete.");

  await page.getByTestId("view-pd").click();
  const questions = page.getByTestId("pd-question");
  await expect(questions).toHaveCount(2);
  await expect(questions.first()).toContainText("What are these payments for?");
  await expect(questions.first().getByRole("link")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/cross-verification`,
  );
  await expect(questions.nth(1).getByRole("link")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/policy`,
  );
});
