// Case fields (T2.1): product, case type, application ID, bank stage and branch are shown
// in the case header and the appraisals list; a case from before they were recorded says so.
import { expect, test } from "@playwright/test";
import { KESTREL, ORIEL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("the case header shows the case's place in the bank's process", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const header = page.getByTestId("case-header");
  await expect(header.getByTestId("header-product")).toHaveText("Business banking · Renewal");
  await expect(header).toContainText("Application ID LA123456");
  await expect(header.getByTestId("header-bank-stage")).toHaveText("Personal discussion");
  await expect(header.getByTestId("header-rm")).toHaveText("Arjun Deshpande · Mumbai hub");
});

test("a case from before the fields were recorded says so", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${ORIEL}/completeness`);
  const header = page.getByTestId("case-header");
  await expect(header.getByTestId("header-product")).toHaveText("Business banking · Not recorded");
  await expect(header.getByTestId("header-bank-stage")).toHaveText("Not recorded");
  await expect(header.getByTestId("header-rm")).toHaveText("Arjun Deshpande");
  await expect(header).not.toContainText("Application ID");
});

test("the appraisals lists show product and case type", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals");
  const card = (borrower: string) =>
    page.getByTestId("appraisal-card").filter({ hasText: borrower });
  await expect(card("Kestrel Polymers").getByTestId("case-kind")).toHaveText(
    "Business banking · Renewal",
  );
  await expect(card("Kestrel Polymers")).toContainText("Personal discussion");
  await expect(card("Oriel Castings").getByTestId("case-kind")).toHaveText("Business banking");

  await page.goto("/");
  const row = (borrower: string) =>
    page.getByTestId("cases-table").getByRole("row").filter({ hasText: borrower });
  await expect(row("Kestrel Polymers").getByTestId("case-kind")).toHaveText(
    "Business banking · Renewal",
  );
});
