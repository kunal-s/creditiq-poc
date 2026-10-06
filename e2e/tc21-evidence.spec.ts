// TC-21 (C7): clicking a value opens its source page with the region
// highlighted, the document type, file name, page, grade, confidence and
// method; a correction shows both values (FRD F-16, F-17).
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-21: a value opens its evidence page", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);

  const value = page.locator('[data-testid="field-value"][data-field="monthly[2].credits"]');
  await expect(value).toHaveText("41,02,300");
  await value.click();

  const viewer = page.getByTestId("evidence-viewer");
  await expect(viewer).toBeVisible();
  await expect(page.getByTestId("viewer-type")).toHaveText("Bank statement");
  await expect(page.getByTestId("viewer-file")).toHaveText("merged_docs.pdf · p3–9");
  await expect(page.getByTestId("viewer-page")).toHaveText("Page 7 · pages 3–9");
  await expect(page.getByTestId("viewer-value")).toHaveText("41,02,300");
  await expect(viewer).toContainText("Confidence 62%");
  await expect(viewer).toContainText("Method Read from the page text");
  await expect(viewer).toContainText("Readable");
  await expect(page.getByTestId("viewer-image")).toBeVisible();
  await expect(page.getByTestId("viewer-bbox")).toBeVisible();
  expect(api.called("GET", `/api/cases/${KESTREL}/documents/doc-bank/pages/7`)).toHaveLength(1);

  // Previous and next page within the document; the region shows on its page only.
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.getByTestId("viewer-page")).toHaveText("Page 8 · pages 3–9");
  await expect(page.getByTestId("viewer-bbox")).toHaveCount(0);
  await page.getByRole("button", { name: "Back to page 7" }).click();
  await expect(page.getByTestId("viewer-bbox")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
});

test("TC-21: every field carries a confidence and a page link; corrections show both values", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  const fields = page.getByTestId("section-fields");

  const rows = fields.getByTestId("field-row");
  await expect(rows).toHaveCount(6);
  // Every extracted (non-missing) value is a link to its page with a confidence.
  await expect(fields.getByTestId("field-value")).toHaveCount(5);
  await expect(fields.getByTestId("confidence")).toHaveCount(5);

  const corrected = page.locator('[data-testid="field-value"][data-field="monthly[1].credits"]');
  await expect(corrected).toContainText("39,85,000");
  await expect(corrected.getByTestId("system-value")).toHaveText("38,95,000");

  // Composition on hover.
  await expect(page.getByTestId("confidence").first().locator("xpath=../..")).toHaveAttribute(
    "title",
    /Classification 96%/,
  );

  // The same correction in the review queue, both values shown.
  await page.goto("/review");
  await page.getByLabel("Show decided").check();
  await expect(page.getByTestId("both-values")).toHaveText(
    "System 38,95,000 · corrected 39,85,000",
  );
});

test("TC-21: checklist evidence opens the document", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  await page.locator('[data-item="gst_returns"]').getByRole("button").first().click();
  await page.getByTestId("linked-document").click();
  await expect(page.getByTestId("viewer-type")).toHaveText("GST registration");
  await expect(page.getByTestId("viewer-page")).toHaveText("Page 1 · pages 1–2");
});
