// TC-14 (C2): each outdated document is identified with its date and the
// permitted age, measured from the case's as_of (FRD F-13.2).
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-14: outdated document with date and permitted age", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/docready/${KESTREL}/checklist`);

  const stock = page.locator('[data-testid="checklist-item"][data-item="stock_statement"]');
  await expect(stock).toHaveAttribute("data-status", "insufficient");
  await expect(stock.getByTestId("checklist-status")).toHaveText("Insufficient");
  const deficiency = stock.getByTestId("deficiency");
  await expect(deficiency).toContainText("31 Jan 2026");
  await expect(deficiency).toContainText("60 days");

  await page
    .getByRole("navigation", { name: "Case tabs" })
    .getByRole("link", { name: "Queries" })
    .click();
  await expect(page.getByTestId("query-group-documents_to_redo")).toContainText(
    "Stock statement dated within the last 60 days (latest is 31 Jan 2026).",
  );
});
