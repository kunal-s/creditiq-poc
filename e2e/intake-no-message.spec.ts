/// <reference types="node" />
// A business banking case without a sourcing message (plan 2026-11-27): the message is optional,
// the engine still checks for a matching application, and creating another one needs a reason.
import { expect, test, type Page } from "@playwright/test";
import type { ProposalRequest } from "../src/api/types";
import { CASES, EXISTING, proposal } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";
import { cell, PDF, sentCase } from "./support/intake";

async function fillBusiness(page: Page) {
  await page.getByTestId("field-borrower").getByRole("textbox").fill("Heron Valves Pvt Ltd");
  await cell(page, "facilities", 0, "facility").getByRole("combobox").selectOption("cash_credit");
  await cell(page, "facilities", 0, "amount_inr").getByRole("textbox").fill("2500000");
}

test("a BBG case is created without a message", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await expect(page.getByTestId("box-1-rule")).toHaveText("Optional");
  await page.getByTestId("upload-input").setInputFiles([PDF("gst-returns.pdf")]);
  await page.getByRole("button", { name: "Continue" }).click();

  // Nothing was read: the form starts blank, with its defaults.
  await expect(page.getByTestId("message-view")).toHaveCount(0);
  await expect(page.getByTestId("field-bank_stage").getByTestId("prefilled")).toHaveText("Default");
  await fillBusiness(page);
  await expect(page.getByTestId("field-borrower").getByTestId("typed")).toBeVisible();
  await expect(page.getByTestId("lines-total")).toContainText("25.00 lakh");
  // The engine's duplicate check ran without a message.
  await expect(page.getByTestId("review-duplicates")).toHaveAttribute("data-state", "ok");
  const last = () =>
    api.called("POST", "/api/cases/proposals").slice(-1)[0]?.body as ProposalRequest | undefined;
  await expect.poll(() => last()?.fields?.["borrower"]).toBe("Heron Valves Pvt Ltd");
  expect(last()?.text ?? null).toBeNull();
  expect(last()?.product).toBe("bbg");
  await expect(page.getByTestId("review-sources")).toContainText("typed");

  await page.getByTestId("create-application").click();
  await expect(page).toHaveURL(/\/appraisals\/BBG-2026-000031$/);
  const { body } = sentCase(api);
  expect(body.message_text).toBeUndefined();
  expect(body.borrower).toBe("Heron Valves Pvt Ltd");
  expect(body.facilities).toEqual(["cash_credit"]);
  expect(body.amount_inr).toBe(2_500_000);
  expect(body.header?.["borrower"]).toEqual({
    value: "Heron Valves Pvt Ltd",
    proposed: null,
    source: "person",
  });
});

test("without a message, a matching application needs a reason to create another", async ({
  page,
}) => {
  const api = new MockApi();
  api.proposal = proposal([{ ...CASES[0]!, id: EXISTING }]);
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("upload-input").setInputFiles([PDF()]);
  await page.getByRole("button", { name: "Continue" }).click();
  await fillBusiness(page);

  const warning = page.getByTestId("duplicate-warning");
  await expect(warning).toContainText(EXISTING);
  await expect(page.getByTestId("review-duplicates")).toHaveAttribute("data-state", "warn");
  await expect(page.getByTestId("duplicate-blocker")).toBeVisible();
  await expect(page.getByTestId("create-application")).toBeDisabled();
  await warning.getByRole("button", { name: "Create anyway" }).click();
  await page.getByTestId("override-reason").fill("A separate unit of the group");
  await page.getByTestId("create-application").click();
  await expect(page).toHaveURL(/\/appraisals\/BBG-2026-000031$/);
  expect(sentCase(api).body.duplicate_override_reason).toBe("A separate unit of the group");
});

test("switching product and going back to the start keep what the RM typed", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("upload-input").setInputFiles([PDF()]);
  await page.getByTestId("start-continue").click();
  await page.getByTestId("field-application_id").getByRole("textbox").fill("LOS-77");
  await page.getByTestId("field-borrower").getByRole("textbox").fill("Heron Valves Pvt Ltd");

  // Back to the start and on again: the form is as it was left.
  await page.getByTestId("back-to-start").click();
  await page.getByTestId("start-continue").click();
  await expect(page.getByTestId("field-borrower").getByRole("textbox")).toHaveValue(
    "Heron Valves Pvt Ltd",
  );

  // The other product asks first, then keeps the field both forms share and the document.
  await page.getByTestId("product-lap").click();
  await expect(page.getByTestId("product-switch")).toBeVisible();
  await page.getByTestId("product-switch-confirm").click();
  await expect(page.getByTestId("product-lap")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("field-application_id").getByRole("textbox")).toHaveValue("LOS-77");
  await expect(page.getByTestId("row-applicants")).toHaveCount(1);
  await expect(page.getByTestId("attachments")).toContainText("kyc.pdf");
});
