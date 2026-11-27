/// <reference types="node" />
// A loan against property from the New appraisal screen (plan 2026-11-27): the product first, a
// document and no message, then applicants, a co-applicant and a property, the LAP documents in
// the review, and a LAP- case number.
import { expect, test } from "@playwright/test";
import { MockApi, signedIn } from "./support/api";
import { cell, PDF, sentCase } from "./support/intake";

test("a LAP case: document, no message, co-applicant and property, created as LAP-…", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("product-lap").click();
  await expect(page.getByTestId("product-lap")).toHaveAttribute("aria-checked", "true");
  await expect(page.getByTestId("suggested-documents")).toContainText("property papers");
  await page.getByTestId("upload-input").setInputFiles([PDF("kyc.pdf")]);
  const start = page.getByTestId("start-continue");
  await expect(start).toHaveText("Continue");
  await start.click();

  // The LAP form: its own sections, and its minimum.
  await expect(page.getByTestId("group-case")).toBeVisible();
  await expect(page.getByTestId("group-borrower")).toHaveCount(0);
  await expect(page.getByTestId("missing-minimum")).toContainText("Customer type");
  await expect(page.getByTestId("missing-minimum")).toContainText("Tenure");
  await page.getByTestId("field-customer_type").getByRole("combobox").selectOption("salaried");
  // A salaried customer has no business section.
  await expect(page.getByTestId("group-business")).toHaveCount(0);
  await page.getByTestId("field-amount_inr").getByRole("textbox").fill("4500000");
  await page.getByTestId("field-tenure_months").getByRole("textbox").fill("180");

  // The primary applicant, then a co-applicant.
  await expect(page.getByTestId("row-applicants")).toHaveCount(1);
  await cell(page, "applicants", 0, "name").getByRole("textbox").fill("Rohan Kulkarni");
  await page.getByTestId("add-applicants").click();
  await expect(cell(page, "applicants", 1, "role").getByRole("combobox")).toHaveValue(
    "co_applicant",
  );
  await cell(page, "applicants", 1, "name").getByRole("textbox").fill("Meera Kulkarni");
  await cell(page, "applicants", 1, "aadhaar_last4").getByRole("textbox").fill("482199");
  await expect(cell(page, "applicants", 1, "aadhaar_last4").getByRole("textbox")).toHaveValue(
    "4821",
  );

  // A property, owned by both; a second one added and taken away again.
  await cell(page, "properties", 0, "property_type")
    .getByRole("combobox")
    .selectOption("residential");
  await cell(page, "properties", 0, "owners")
    .getByRole("button", { name: "Rohan Kulkarni" })
    .click();
  await cell(page, "properties", 0, "owners")
    .getByRole("button", { name: "Meera Kulkarni" })
    .click();
  await page.getByTestId("add-properties").click();
  await expect(page.getByTestId("row-properties")).toHaveCount(2);
  await page.getByTestId("row-properties").nth(1).getByTestId("remove-row").click();
  await expect(page.getByTestId("row-properties")).toHaveCount(1);

  // The review: the minimum met, the LAP documents this case will need.
  await expect(page.getByTestId("review-minimum")).toHaveAttribute("data-state", "ok");
  const needed = page.getByTestId("documents-needed");
  await expect(needed).toContainText("Property ownership papers");
  await expect(needed).toContainText("Salary slips, last three months");
  await expect(needed).not.toContainText("Income Tax Return");
  await expect(needed.getByTestId("needed-provisional")).toHaveCount(0);
  const preview = api.called("POST", "/api/cases/checklist-preview").slice(-1)[0]!.body;
  expect(preview).toMatchObject({ product: "lap", customer_type: "salaried" });

  await page.getByTestId("create-application").click();
  await expect(page).toHaveURL(/\/appraisals\/LAP-2026-000001$/);
  await expect(page.getByTestId("case-header").getByTestId("product-chip")).toHaveText("LAP");
  // A loan against property names its customer type where business banking names a constitution.
  await expect(page.getByTestId("case-header")).toContainText("Salaried");

  const { body, files } = sentCase(api);
  expect(files).toEqual(["kyc.pdf"]);
  expect(body.product).toBe("lap");
  expect(body.message_text).toBeUndefined();
  expect(body.customer_type).toBe("salaried");
  expect(body.amount_inr).toBe(4_500_000);
  expect(body.tenure_months).toBe(180);
  expect(body.collateral_present).toBe(true);
  expect(body.header?.["product"]).toEqual({ value: "lap", proposed: "bbg", source: "person" });
  const applicants = body.groups?.["applicants"] ?? [];
  expect(applicants.map((r) => [r["name"]?.value, r["role"]?.value])).toEqual([
    ["Rohan Kulkarni", "applicant"],
    ["Meera Kulkarni", "co_applicant"],
  ]);
  expect(applicants[1]?.["aadhaar_last4"]?.value).toBe("4821");
  expect(body.groups?.["properties"]).toEqual([
    expect.objectContaining({
      property_type: { value: "residential", proposed: null, source: "person" },
      owners: { value: "Rohan Kulkarni; Meera Kulkarni", proposed: null, source: "person" },
    }),
  ]);
});
