/// <reference types="node" />
// The identifier boxes of the start screen, per product (plan 2026-11-27): each optional, with its
// format hint; a typed identifier fills its field on the form with the source "identifier".
import { expect, test } from "@playwright/test";
import { MockApi, signedIn } from "./support/api";
import { cell, PDF, sentCase } from "./support/intake";

const boxes = (page: import("@playwright/test").Page) =>
  page.getByTestId("identifier-fields").locator('[data-testid^="identifier-"]');

test("business banking offers entity PAN, GSTIN, CIN or LLPIN, Udyam and the LOS ID", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await expect(boxes(page)).toHaveCount(5);
  await expect(page.getByTestId("identifier-pan")).toContainText("Entity PAN");
  await expect(page.getByTestId("identifier-cin")).toContainText("CIN or LLPIN");
  await expect(page.getByTestId("identifier-co_applicant_pan")).toHaveCount(0);
  await expect(page.getByTestId("identifier-gstin").getByTestId("format-hint")).toContainText(
    "27AAACK1234K1Z5",
  );
  const pan = page.getByTestId("identifier-pan").getByRole("textbox");
  await pan.fill("aacpk12");
  // Judged once the field is left (or the code is complete), never from the first letter.
  await expect(page.getByTestId("identifier-pan").getByTestId("format-check")).toHaveCount(0);
  await pan.blur();
  await expect(page.getByTestId("identifier-pan").getByTestId("format-check")).toBeVisible();
  await pan.fill("aaack1234k");
  await expect(pan).toHaveValue("AAACK1234K");
  await expect(page.getByTestId("identifier-pan").getByTestId("format-check")).toHaveCount(0);

  // The typed PAN fills the borrower's PAN, marked as an identifier.
  await page.getByTestId("upload-input").setInputFiles([PDF()]);
  await page.getByTestId("start-continue").click();
  const field = page.getByTestId("field-pan");
  await expect(field.getByRole("textbox")).toHaveValue("AAACK1234K");
  await expect(field.getByTestId("prefilled")).toHaveText("Identifier");

  await page.getByTestId("field-borrower").getByRole("textbox").fill("Kestrel Polymers Pvt Ltd");
  await cell(page, "facilities", 0, "facility").getByRole("combobox").selectOption("term_loan");
  await cell(page, "facilities", 0, "amount_inr").getByRole("textbox").fill("1000000");
  await expect(page.getByTestId("review-sources")).toContainText("1 from identifiers");
  await page.getByTestId("create-application").click();
  await expect(page).toHaveURL(/\/appraisals\/BBG-2026-000031$/);
  const { body } = sentCase(api);
  expect(body.pan).toBe("AAACK1234K");
  expect(body.header?.["pan"]).toEqual({
    value: "AAACK1234K",
    proposed: "AAACK1234K",
    source: "identifier",
  });
});

test("a loan against property offers applicant and co-applicant PAN; more by customer and case type", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("product-lap").click();
  await expect(page.getByTestId("identifier-pan")).toContainText("Applicant PAN");
  await expect(page.getByTestId("identifier-co_applicant_pan")).toBeVisible();
  await expect(page.getByTestId("identifier-application_id")).toBeVisible();
  await expect(page.getByTestId("identifier-gstin")).toHaveCount(0);
  await expect(page.getByTestId("identifier-udyam")).toHaveCount(0);
  await expect(page.getByTestId("identifier-existing_loan_account")).toHaveCount(0);

  // A business's GSTIN and Udyam for a self-employed customer; the loan account for a transfer.
  await page.getByTestId("start-choice-customer_type").selectOption("self_employed");
  await expect(page.getByTestId("identifier-gstin")).toContainText("Business GSTIN");
  await expect(page.getByTestId("identifier-udyam")).toBeVisible();
  await page.getByTestId("start-choice-case_type").selectOption("balance_transfer");
  await expect(page.getByTestId("identifier-existing_loan_account")).toBeVisible();
  await page.getByTestId("start-choice-customer_type").selectOption("salaried");
  await expect(page.getByTestId("identifier-gstin")).toHaveCount(0);

  // An individual's PAN has P as its fourth letter: the hint says so.
  await expect(page.getByTestId("identifier-pan").getByTestId("format-hint")).toContainText(
    "P as the 4th letter",
  );
  await page.getByTestId("identifier-pan").getByRole("textbox").fill("ABCPK1234F");
  await page.getByTestId("identifier-co_applicant_pan").getByRole("textbox").fill("BCDPK5678G");
  await page.getByTestId("identifier-existing_loan_account").getByRole("textbox").fill("HL-0042");
  await page.getByTestId("upload-input").setInputFiles([PDF()]);
  await page.getByTestId("start-continue").click();

  // The applicant's and the co-applicant's PAN in their rows; the loan account in its field.
  await expect(cell(page, "applicants", 0, "pan").getByRole("textbox")).toHaveValue("ABCPK1234F");
  await expect(cell(page, "applicants", 0, "pan").getByTestId("cell-source")).toHaveText(
    "Identifier",
  );
  await expect(cell(page, "applicants", 1, "role").getByRole("combobox")).toHaveValue(
    "co_applicant",
  );
  await expect(cell(page, "applicants", 1, "pan").getByRole("textbox")).toHaveValue("BCDPK5678G");
  await expect(page.getByTestId("field-customer_type").getByRole("combobox")).toHaveValue(
    "salaried",
  );
  const account = page.getByTestId("field-existing_loan_account");
  await expect(account.getByRole("textbox")).toHaveValue("HL-0042");
  await expect(account.getByTestId("prefilled")).toHaveText("Identifier");
});
