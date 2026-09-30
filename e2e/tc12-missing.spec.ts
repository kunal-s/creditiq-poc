// TC-12 (C2): every missing item is identified, with a specific request,
// and appears on the pre-login query list (FRD F-13.1, F-14).
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-12: missing items with a specific request", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/completeness`);

  const missing = page.locator('[data-testid="checklist-item"][data-status="missing"]');
  await expect(missing).toHaveCount(2);
  await expect(
    missing.filter({ hasText: "KYC of directors" }).getByTestId("deficiency"),
  ).toHaveText("Missing: 1 of 2 directors (Leela Varghese): PAN and address proof.");
  await expect(
    missing.filter({ hasText: "Valuation report" }).getByTestId("deficiency"),
  ).toHaveText("Missing: valuation report for the property offered as collateral.");
  await expect(page.getByTestId("checklist-summary")).toContainText("Missing2");

  // The query list is on the same tab, below the checklist.
  const needed = page.getByTestId("query-group-documents_needed");
  await expect(needed).toContainText("1.KYC of Leela Varghese: PAN and address proof.");
  await expect(needed).toContainText("2.Valuation report for the property offered as collateral.");
});
