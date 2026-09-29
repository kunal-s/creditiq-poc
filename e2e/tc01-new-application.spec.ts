// TC-01 (C3): a pasted message becomes a proposed case; every field is
// found, unclear or not found with its span; nothing is created until the
// RM confirms (FRD F-04).
import { expect, test } from "@playwright/test";
import type { CaseCreate } from "../src/api/types";
import { CASES, EXISTING, MESSAGE, proposal, spanOf } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-01: paste, verify every field, confirm, create", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");

  await page.getByTestId("channel").selectOption("email");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();

  // Each field with its status.
  const status = (key: string) => page.getByTestId(`field-${key}`).getByTestId("proposed-status");
  await expect(status("borrower")).toHaveText("Found");
  await expect(status("constitution")).toHaveText("Unclear");
  await expect(status("gstin")).toHaveText("Not found");
  await expect(status("declared_turnover_inr")).toHaveText("Unclear");
  await expect(page.getByTestId("field-borrower").getByRole("textbox")).toHaveValue(
    "Kestrel Polymers Pvt Ltd",
  );
  await expect(page.getByTestId("field-amount_inr").getByRole("textbox")).toHaveValue("5000000");

  // Clicking a field highlights its span in the message.
  await page.getByTestId("field-pan").click();
  await expect(page.locator('mark[data-mark="selected"]')).toHaveText("AAACK1234K");
  await page.getByTestId("field-borrower").click();
  await expect(page.locator('mark[data-mark="selected"]')).toHaveText("Kestrel Polymers Pvt Ltd");

  // Unclear items block creation until settled.
  await expect(page.getByTestId("needs-confirmation")).toContainText(
    "To confirm before creating: 2",
  );
  await expect(page.getByTestId("create-application")).toBeDisabled();

  // Choosing a candidate settles the field and highlights the candidate's span.
  await page.getByTestId("field-constitution").getByTestId("candidate").first().click();
  await expect(page.getByTestId("field-constitution").getByRole("combobox")).toHaveValue(
    "private_limited",
  );
  await expect(page.locator('mark[data-mark="selected"]')).toHaveText("Pvt Ltd");
  await page.getByTestId("confirm-declared_turnover_inr").click();
  await expect(page.getByTestId("needs-confirmation")).toHaveCount(0);

  // The RM edits a proposed value: both values are kept.
  await page.getByTestId("field-amount_inr").getByRole("textbox").fill("5500000");

  expect(api.called("POST", "/api/cases")).toHaveLength(0);
  await page.getByTestId("create-application").click();

  await expect(page).toHaveURL(/\/docready\/BBG-2026-000031\/checklist$/);
  const [create] = api.called("POST", "/api/cases");
  const body = create!.body as CaseCreate;
  expect(body.borrower).toBe("Kestrel Polymers Pvt Ltd");
  expect(body.constitution).toBe("private_limited");
  expect(body.facilities).toEqual(["cash_credit", "term_loan"]);
  expect(body.amount_inr).toBe(5_500_000);
  expect(body.channel).toBe("email");
  expect(body.pan).toBe("AAACK1234K");
  const amount = spanOf("50L");
  expect(body.header?.["amount_inr"]).toEqual({
    value: "5500000",
    proposed: "5000000",
    source: `message:${amount.start}-${amount.end}`,
  });
  const pvt = spanOf("Pvt Ltd", 1);
  expect(body.header?.["constitution"]?.source).toBe(`message:${pvt.start}-${pvt.end}`);
});

test("TC-01: nothing is created without confirmation", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  await expect(page.getByTestId("create-application")).toBeDisabled();

  // Missing minimum fields also block creation.
  await page.getByTestId("field-borrower").getByRole("textbox").fill("");
  await expect(page.getByTestId("missing-minimum")).toContainText("Borrower");

  await page.getByRole("button", { name: "Discard" }).click();
  await expect(page.getByTestId("message-input")).toHaveValue("");
  expect(api.called("POST", "/api/cases")).toHaveLength(0);
});

test("TC-01: a duplicate is offered, and creating anyway needs a reason", async ({ page }) => {
  const api = new MockApi();
  api.proposal = proposal([{ ...CASES[0]!, id: EXISTING }]);
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  for (const key of ["constitution", "declared_turnover_inr"]) {
    await page.getByTestId(`confirm-${key}`).click();
  }

  const warning = page.getByTestId("duplicate-warning");
  await expect(warning).toContainText(EXISTING);
  await expect(warning.getByRole("link", { name: "Open it" })).toHaveAttribute(
    "href",
    `/docready/${EXISTING}/checklist`,
  );
  await expect(page.getByTestId("create-application")).toBeDisabled();
  await warning.getByRole("button", { name: "Create anyway" }).click();
  await expect(page.getByTestId("create-application")).toBeDisabled();
  await page.getByTestId("override-reason").fill("Separate unit with its own GST registration");
  await page.getByTestId("create-application").click();

  await expect(page).toHaveURL(/\/docready\/BBG-2026-000031\/checklist$/);
  const body = api.called("POST", "/api/cases")[0]!.body as CaseCreate;
  expect(body.duplicate_override_reason).toBe("Separate unit with its own GST registration");
});
