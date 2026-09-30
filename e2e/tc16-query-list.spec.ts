// TC-16 (C6): one pre-login query list, grouped in three sections, numbered,
// resolved items shown as resolved; copied as email or plain text; nothing
// is sent from the system (FRD F-14).
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test.use({ permissions: ["clipboard-read", "clipboard-write"] });

test("TC-16: grouped list, resolved shown, copy as email and text", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/cases/${KESTREL}/completeness`);

  const list = page.getByTestId("query-list");
  await expect(list).toContainText("6 open · 1 resolved");
  await expect(
    page.getByTestId("query-group-documents_needed").getByTestId("query-item"),
  ).toHaveCount(3);
  await expect(
    page.getByTestId("query-group-documents_to_redo").getByTestId("query-item"),
  ).toHaveCount(3);
  await expect(
    page.getByTestId("query-group-clarifications").getByTestId("query-item"),
  ).toHaveCount(1);

  const resolved = page.locator('[data-testid="query-item"][data-resolved="true"]');
  await expect(resolved).toHaveCount(1);
  await expect(resolved).toContainText("Resolved");
  await expect(resolved).toContainText("ITR acknowledgement FY25");

  await page.getByRole("button", { name: "Copy as email" }).click();
  const email = await page.evaluate(() => navigator.clipboard.readText());
  expect(email).toContain(
    "Subject: Documents and clarifications for Kestrel Polymers Pvt Ltd (BBG-2026-000021)",
  );
  expect(email).toContain("Documents needed\n1. KYC of Leela Varghese: PAN and address proof.");
  expect(email).toContain("Clarifications\n6. Bank statements show a monthly EMI");
  expect(email).not.toContain("ITR acknowledgement FY25");

  await page.getByRole("button", { name: "Copy", exact: true }).click();
  const text = await page.evaluate(() => navigator.clipboard.readText());
  expect(text.startsWith("Documents needed\n1. KYC of Leela Varghese")).toBe(true);
  expect(text).toContain(
    "Documents to redo\n4. Board resolution: the copy provided is not signed.",
  );

  // A clarification links to its evidence.
  await page
    .getByTestId("query-group-clarifications")
    .getByRole("button", { name: "Evidence" })
    .click();
  await expect(page.getByTestId("evidence-viewer")).toBeVisible();
  await expect(page.getByTestId("viewer-page")).toContainText("Page 7");

  // Nothing is sent: no write request was made.
  expect(api.calls.filter((c) => !c.key.startsWith("GET"))).toEqual([]);
});
