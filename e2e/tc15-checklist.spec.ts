// TC-15 (C2): the checklist applied to the case is shown by section, in the
// published order and weights, each item with why and basis; while the
// constitution is unknown it is marked provisional (FRD F-12).
import { expect, test } from "@playwright/test";
import { KESTREL, ORIEL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-15: sections in published order with weights", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/docready/${KESTREL}/checklist`);

  const sections = page.getByTestId("checklist-section");
  await expect(sections).toHaveCount(4);
  await expect(sections.locator("p").first()).toContainText("Constitution and KYC");
  const headings = await sections.evaluateAll((els) =>
    els.map((el) => el.querySelector("p")?.textContent ?? ""),
  );
  expect(headings).toEqual([
    "Constitution and KYCweight 20%",
    "Financialsweight 30%",
    "Banking and operationsweight 30%",
    "Collateral and securityweight 20%",
  ]);
  await expect(page.getByTestId("checklist")).toContainText(
    "9 requirements derived from the private limited constitution and the cash credit, term loan ask.",
  );

  const coi = page.locator('[data-item="coi"]');
  await expect(coi).toContainText("Blocking");
  await coi.getByRole("button").first().click();
  await expect(coi).toContainText(
    "Certificate of incorporation is required for this constitution and facility.",
  );
  await expect(coi).toContainText("Published credit policy.");
  await expect(page.getByTestId("provisional")).toHaveCount(0);
});

test("TC-15: provisional while the constitution is unknown", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/docready/${ORIEL}/checklist`);
  await expect(page.getByTestId("provisional")).toBeVisible();
  await expect(page.getByTestId("docready-header")).toContainText("Not yet confirmed");
});
