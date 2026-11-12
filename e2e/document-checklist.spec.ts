// The document checklist is no longer drawn on the Files step or on the Overview: the Files step
// keeps to the files received, and the Overview to where the case stands.
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("the Files step lists the files received, without the checklist", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("files-received")).toBeVisible();
  await expect(page.getByTestId("add-documents")).toBeVisible();
  await expect(page.getByTestId("document-checklist")).toHaveCount(0);
  await expect(page.getByTestId("document-readiness")).toHaveCount(0);
  await expect(page.getByTestId("step-header").getByRole("heading", { level: 1 })).toHaveText(
    "Files",
  );
});

test("the Overview draws no requirement list", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  await expect(page.getByTestId("journey-folded")).toBeVisible();
  await expect(page.getByTestId("document-checklist")).toHaveCount(0);
  await expect(page.getByTestId("journey-item")).toHaveCount(0);
});
