/// <reference types="node" />
// A case is created with its documents (plan 2026-11-27): for both products the start button
// waits for a file, Create is blocked again if the files are taken off, and a refusal from the
// engine leaves nothing created and the files on screen.
import { expect, test } from "@playwright/test";
import { MockApi, signedIn } from "./support/api";
import { cell, PDF } from "./support/intake";

for (const product of ["bbg", "lap"]) {
  test(`${product}: no document, no Continue; no document, no Create`, async ({ page }) => {
    const api = new MockApi();
    await signedIn(page, api);
    await page.goto("/appraisals/new");
    await page.getByTestId(`product-${product}`).click();
    await expect(page.getByTestId("box-2-rule")).toHaveText("Required");

    const start = page.getByTestId("start-continue");
    await expect(start).toBeDisabled();
    await expect(page.getByTestId("start-hint")).toHaveText(
      "Add at least one document to continue",
    );
    // A message alone does not do.
    await page.getByTestId("message-input").fill("Client wants a loan.");
    await expect(start).toHaveText("Read the message");
    await expect(start).toBeDisabled();
    await page.getByTestId("message-input").fill("");

    await page.getByTestId("upload-input").setInputFiles([PDF("one.pdf")]);
    await expect(page.getByTestId("start-hint")).toHaveCount(0);
    await expect(start).toBeEnabled();
    await start.click();

    await expect(page.getByTestId("review-files")).toHaveAttribute("data-state", "ok");
    await page.getByTestId("attachments").getByRole("button", { name: "Remove" }).click();
    await expect(page.getByTestId("review-files")).toHaveAttribute("data-state", "missing");
    await expect(page.getByTestId("need-files")).toBeVisible();
    await expect(page.getByTestId("create-application")).toBeDisabled();
    expect(api.called("POST", "/api/cases/intake")).toHaveLength(0);
  });
}

test("a refusal creates nothing and keeps the files on screen", async ({ page }) => {
  const api = new MockApi().on("POST", /^\/api\/cases\/intake$/, () => ({
    status: 422,
    json: {
      detail: {
        code: "too_few_files",
        message: "at least 1 document needed to create the case; 0 received as new documents",
        min_files: 1,
        registered: 0,
      },
    },
  }));
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("upload-input").setInputFiles([PDF("system-file.pdf")]);
  await page.getByTestId("start-continue").click();
  await page.getByTestId("field-borrower").getByRole("textbox").fill("Heron Valves Pvt Ltd");
  await cell(page, "facilities", 0, "facility").getByRole("combobox").selectOption("cash_credit");
  await cell(page, "facilities", 0, "amount_inr").getByRole("textbox").fill("2500000");
  await page.getByTestId("create-application").click();

  await expect(page.getByTestId("error-detail")).toContainText("at least 1 document needed");
  await expect(page).toHaveURL(/\/appraisals\/new$/);
  await expect(page.getByTestId("attachments")).toContainText("system-file.pdf");
});
