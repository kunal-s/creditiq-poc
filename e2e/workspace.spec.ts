// The appraisal workspace (FRD §6): the Overview says what is still needed
// and what waits for a decision; Completeness filters its checklist; links
// to a part of a tab land on it.
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
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
