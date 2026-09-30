// TC-11 (C2): a complete file shows every item satisfied and is marked
// ready for credit (FRD F-13.1, F-13.5).
import { expect, test } from "@playwright/test";
import { SAFFRON } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-11: complete file is ready for credit", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);

  await page.goto(`/appraisals/${SAFFRON}/completeness`);
  await expect(page.getByTestId("checklist-status")).toHaveCount(9);
  const statuses = await page.getByTestId("checklist-status").allTextContents();
  expect(statuses.length).toBe(9);
  expect(new Set(statuses)).toEqual(new Set(["Satisfied"]));
  await expect(page.getByTestId("header-ready")).toHaveText("Ready for credit");
  await expect(page.getByTestId("header-readiness")).toContainText("100%");

  // Readiness is on the same tab, above the checklist.
  await expect(page.getByTestId("gate-banner")).toHaveAttribute("data-ready", "true");
  await expect(page.getByTestId("blocking-gaps")).toContainText("No blocking gap remains");
  await expect(page.getByTestId("gate").first()).toContainText("Met");

  await page.goto("/");
  await expect(page.getByTestId("counter-ready-value")).toHaveText("1");
});
