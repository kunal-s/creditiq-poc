// TC-07: a balance sheet labelled as a bank statement is shown by its
// content, with the label mismatch reported. TC-09: a document outside the
// closed list is shown as unclassified with its top candidates, is not
// assigned to a checklist item, and goes to the review queue, where a
// person assigns a type from the published list (FRD F-09, F-10, F-17).
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-07: label mismatch visible in the register and the document checks", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);

  await page.goto(`/appraisals/${KESTREL}/documents`);
  const bs = page.getByTestId("section-files").locator('[data-document-id="doc-bs"]');
  await expect(bs.getByTestId("document-type")).toHaveText("Balance sheet");
  await expect(bs.getByTestId("label-mismatch")).toHaveText("label says: bank statement");

  const row = page.locator('[data-testid="validation-document"][data-document-id="doc-bs"]');
  await expect(row.getByTestId("label-mismatch")).toBeVisible();
  await row.getByRole("button").first().click();
  await expect(row).toContainText(
    "The file is labelled bank statement; its content reads as Balance sheet.",
  );
});

test("TC-09: unclassified document with candidates, routed for review", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);

  await page.goto(`/appraisals/${KESTREL}/documents`);
  const unc = page.getByTestId("section-files").locator('[data-document-id="doc-unc"]');
  await expect(unc.getByTestId("unclassified")).toHaveText("Unclassified");
  await expect(unc.getByRole("link", { name: "Review queue" })).toHaveAttribute("href", "/review");

  await expect(page.getByTestId("kpi-unclassified")).toContainText("1");
  const row = page.locator('[data-testid="validation-document"][data-document-id="doc-unc"]');
  await row.getByRole("button").first().click();
  await expect(row.getByTestId("candidates")).toHaveText(
    "Utility bill 41% · ITR acknowledgement 22% · Bank statement 10%",
  );
  await expect(row.getByTestId("exit-tier")).toHaveText("Not classified");

  // Not assigned to any checklist item.
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const items = page.getByTestId("checklist-item");
  await expect(items).toHaveCount(9);
  let linked = 0;
  for (let i = 0; i < 9; i++) {
    await items.nth(i).getByRole("button").first().click();
    linked += await page.getByTestId("linked-document").count();
    await expect(
      page.getByTestId("linked-document").filter({ hasText: "Unclassified" }),
    ).toHaveCount(0);
  }
  expect(linked).toBeGreaterThan(0);

  // A person assigns a type from the closed list.
  await page.goto("/review");
  await page.getByTestId("kind-type").click();
  await expect(page.getByTestId("review-row")).toHaveCount(1);
  await page.getByTestId("decide").click();
  const dialog = page.getByTestId("decision-dialog");
  const options = await dialog.getByTestId("assign-type").locator("option").allTextContents();
  expect(options).toEqual([
    "Choose from the published list…",
    "PAN (individual)",
    "GST registration",
    "Bank statement",
    "Balance sheet",
    "Board resolution",
    "ITR acknowledgement",
    "Utility bill",
  ]);
  await expect(dialog.getByTestId("record-decision")).toBeDisabled();
  await dialog.getByTestId("assign-type").selectOption("utility_bill");
  await dialog.getByTestId("record-decision").click();
  await expect(dialog).toHaveCount(0);
  const [call] = api.called("POST", "/api/review/r-type/decision");
  expect(call!.body).toEqual({ decision: "assign", reason: null, value: "utility_bill" });
  await expect(page.getByTestId("review-row")).toHaveCount(0);
});
