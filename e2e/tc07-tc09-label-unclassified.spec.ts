// TC-07: a balance sheet labelled as a bank statement is shown by its
// content, with the label mismatch reported. TC-09: a document outside the
// closed list is shown as unclassified with its top candidates, is not
// assigned to a checklist item, and goes to the review queue, where a
// person assigns a type from the published list (FRD F-09, F-10, F-17).
import { expect, test } from "@playwright/test";
import { KESTREL, RM } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-07: label mismatch visible in the register and the document checks", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);

  await page.goto(`/appraisals/${KESTREL}/documents`);
  const bs = page.getByTestId("section-files").locator('[data-document-id="doc-bs"]');
  await expect(bs.getByTestId("document-type")).toHaveText("Balance sheet");
  await expect(bs.getByTestId("label-mismatch")).toHaveText("label says: bank statement");

  // The row's checks say why.
  await bs.getByTestId("document-toggle").click();
  await expect(bs).toContainText(
    "The file is labelled bank statement; its content reads as Balance sheet.",
  );
});

test("TC-09: unclassified document with candidates, routed for review", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);

  await page.goto(`/appraisals/${KESTREL}/documents`);
  const unc = page.getByTestId("section-files").locator('[data-document-id="doc-unc"]');
  await expect(unc.getByTestId("unclassified")).toHaveText("Not identified");
  await expect(unc.getByTestId("stage-track")).toHaveAttribute("data-state", "attention");
  // Its top candidates are offered on the row, for a person to assign.
  await expect(unc.getByTestId("assign-candidate")).toHaveText([
    "Utility bill 41%",
    "ITR acknowledgement 22%",
    "Bank statement 10%",
  ]);
  await page.getByTestId("filter-attention").click();
  await expect(unc).toBeVisible();

  await unc.getByTestId("document-toggle").click();
  await expect(unc.getByTestId("candidates")).toHaveText(
    "Utility bill 41% · ITR acknowledgement 22% · Bank statement 10%",
  );
  await expect(unc.getByTestId("exit-tier")).toHaveText("Not classified");

  // Not assigned to any checklist item.
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const items = page.getByTestId("checklist-item");
  await expect(items).toHaveCount(9);
  let linked = 0;
  for (let i = 0; i < 9; i++) {
    await items.nth(i).getByRole("button").first().click();
    linked += await page.getByTestId("linked-document").count();
    await expect(
      page.getByTestId("linked-document").filter({ hasText: "Not identified" }),
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

test("TC-09: a candidate type is assigned from the Documents row", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const unc = page.getByTestId("section-files").locator('[data-document-id="doc-unc"]');
  await unc.getByTestId("assign-candidate").first().click();
  await expect(page.getByText("Assigned as Utility bill")).toBeVisible();
  const [call] = api.called("POST", "/api/review/r-type/decision");
  expect(call?.body).toEqual({ decision: "assign", value: "utility_bill", reason: null });
});

test("TC-09: an RM sees the flag but not the decision", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, RM);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const unc = page.getByTestId("section-files").locator('[data-document-id="doc-unc"]');
  await expect(unc.getByTestId("unclassified")).toBeVisible();
  await expect(unc.getByTestId("assign-candidate")).toHaveCount(0);
  await expect(unc.getByTestId("waiting-review")).toHaveText("Waiting for credit review");
});
