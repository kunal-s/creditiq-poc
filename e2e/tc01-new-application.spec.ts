// TC-01 (C3): a pasted message becomes a proposed case; every field is
// found, unclear or not found with its span; nothing is created until the
// RM confirms (FRD F-04).
import { expect, test } from "@playwright/test";
import type { CaseCreate } from "../src/api/types";
import { CASES, EXISTING, MESSAGE, proposal, spanOf } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";
import type { CaseSummary } from "../src/api/types";

test("TC-01: paste, verify every field, confirm, create", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");

  await page.getByTestId("channel-email").click();
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

  // The application group comes first (T2.1): a case type read from the message, product and
  // stage at their configured defaults, the branch at the RM's own.
  const app = page.getByTestId("group-application");
  await expect(app.getByTestId("field-case_type").getByRole("combobox")).toHaveValue("renewal");
  await expect(status("case_type")).toHaveText("Found");
  await expect(app.getByTestId("field-product").getByRole("combobox")).toHaveValue("bbg");
  await expect(app.getByTestId("field-product").getByTestId("prefilled")).toHaveText("Default");
  await expect(app.getByTestId("field-branch").getByRole("combobox")).toHaveValue("mumbai_hub");
  await expect(app.getByTestId("field-branch").getByTestId("prefilled")).toHaveText("Your branch");
  await expect(app.getByTestId("field-bank_stage").getByRole("combobox")).toHaveValue("login");
  await expect(page.getByTestId("group-borrower").getByTestId("field-borrower")).toBeVisible();
  // The RM moves the case to another stage: no longer a default.
  await app.getByTestId("field-bank_stage").getByRole("combobox").selectOption("pd");
  await expect(app.getByTestId("field-bank_stage").getByTestId("prefilled")).toHaveCount(0);

  // Headers set aside before reading are shown greyed, never proposed from.
  await expect(page.locator('mark[data-mark="stripped"]').first()).toContainText("From: RM desk");

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

  await expect(page).toHaveURL(/\/appraisals\/BBG-2026-000031\/documents$/);
  const [create] = api.called("POST", "/api/cases");
  const body = create!.body as CaseCreate;
  expect(body.borrower).toBe("Kestrel Polymers Pvt Ltd");
  expect(body.constitution).toBe("private_limited");
  expect(body.facilities).toEqual(["cash_credit", "term_loan"]);
  expect(body.amount_inr).toBe(5_500_000);
  expect(body.channel).toBe("email");
  expect(body.pan).toBe("AAACK1234K");
  expect(body.message_text).toBe(MESSAGE);
  const amount = spanOf("50L");
  expect(body.header?.["amount_inr"]).toEqual({
    value: "5500000",
    proposed: "5000000",
    source: `message:${amount.start}-${amount.end}`,
  });
  expect(body.product).toBe("bbg");
  expect(body.case_type).toBe("renewal");
  expect(body.branch).toBe("mumbai_hub");
  expect(body.bank_stage).toBe("pd");
  expect(body.application_id).toBeNull();
  expect(body.header?.["product"]).toEqual({
    value: "bbg",
    proposed: "bbg",
    source: "default:config",
  });
  expect(body.header?.["branch"]?.source).toBe("default:rm");
  expect(body.header?.["bank_stage"]).toEqual({ value: "pd", proposed: null, source: "person" });
  const renewal = spanOf("renewal");
  expect(body.header?.["case_type"]?.source).toBe(`message:${renewal.start}-${renewal.end}`);
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
  // Five earlier applications for the borrower: three are named, the rest counted.
  api.proposal = proposal(
    [EXISTING, "BBG-2026-000015", "BBG-2026-000016", "BBG-2026-000017", "BBG-2026-000018"].map(
      (id) => ({ ...CASES[0]!, id }),
    ),
  );
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  for (const key of ["constitution", "declared_turnover_inr"]) {
    await page.getByTestId(`confirm-${key}`).click();
  }

  const warning = page.getByTestId("duplicate-warning");
  await expect(warning).toContainText(EXISTING);
  await expect(warning.getByRole("link", { name: "Open it" }).first()).toHaveAttribute(
    "href",
    `/appraisals/${EXISTING}`,
  );
  await expect(warning.getByRole("link", { name: "Open it" })).toHaveCount(3);
  await expect(warning.getByTestId("more-duplicates")).toHaveText(
    "and 2 more applications for this borrower",
  );
  // The disabled button says why: the only thing left is the duplicate.
  await expect(page.getByTestId("create-application")).toBeDisabled();
  await expect(page.getByTestId("create-blockers")).toHaveText(
    "An application for this borrower already exists. Choose Create anyway above and give a reason, or open the existing one.",
  );
  await warning.getByRole("button", { name: "Create anyway" }).click();
  await expect(page.getByTestId("create-application")).toBeDisabled();
  await page.getByTestId("override-reason").fill("Separate unit with its own GST registration");
  await expect(page.getByTestId("create-blockers")).toHaveCount(0);
  await page.getByTestId("create-application").click();

  await expect(page).toHaveURL(/\/appraisals\/BBG-2026-000031\/documents$/);
  const body = api.called("POST", "/api/cases")[0]!.body as CaseCreate;
  expect(body.duplicate_override_reason).toBe("Separate unit with its own GST registration");
});

test("TC-01: a duplicate found at creation (409) is offered the same way", async ({ page }) => {
  const api = new MockApi();
  const existing: CaseSummary = { ...CASES[0]!, id: EXISTING };
  api.on("POST", /^\/api\/cases$/, (req) => {
    const body = req.postDataJSON() as CaseCreate;
    if (!body.duplicate_override_reason) {
      return {
        status: 409,
        json: { detail: { message: "a case matches", duplicates: [existing] } },
      };
    }
    return { status: 201, json: { ...existing, id: "BBG-2026-000031" } };
  });
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  await page.getByTestId("confirm-constitution").click();
  await page.getByTestId("confirm-declared_turnover_inr").click();
  await page.getByTestId("create-application").click();

  const warning = page.getByTestId("duplicate-warning");
  await expect(warning).toContainText(EXISTING);
  await expect(page.getByTestId("create-application")).toBeDisabled();
  await warning.getByRole("button", { name: "Create anyway" }).click();
  await page.getByTestId("override-reason").fill("Group company, separate borrower");
  await page.getByTestId("create-application").click();
  await expect(page).toHaveURL(/\/appraisals\/BBG-2026-000031\/documents$/);
  expect(api.called("POST", "/api/cases")).toHaveLength(2);
});

test("the documents the application will need follow the fields on screen", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/appraisals/new");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();

  // The constitution is unclear: only what every application needs, marked provisional.
  const needed = page.getByTestId("documents-needed");
  await expect(needed.getByTestId("needed-provisional")).toBeVisible();
  await expect(needed.getByTestId("needed-item")).toHaveCount(2);
  await expect(needed).toContainText("Will need 2 documents");

  // Confirming the constitution brings in the company documents; a supporting item says so.
  await page.getByTestId("field-constitution").getByTestId("candidate").first().click();
  await expect(needed.getByTestId("needed-item")).toHaveCount(4);
  await expect(needed.getByTestId("needed-provisional")).toHaveCount(0);
  // Only the supporting items are set apart; the count names the blocking ones.
  await expect(needed).toContainText("Will need 4 documents (3 blocking)");
  await expect(
    needed.getByTestId("needed-item").filter({ hasText: "Board resolution" }),
  ).toHaveAttribute("data-blocking", "false");
  // One line per item: the name only, the rest is in its hover text.
  await expect(
    needed.getByTestId("needed-item").filter({ hasText: "Certificate of incorporation" }),
  ).toHaveText("Certificate of incorporation");

  const [last] = api.called("POST", "/api/cases/checklist-preview").slice(-1);
  expect(last!.body).toMatchObject({
    constitution: "private_limited",
    facilities: ["cash_credit", "term_loan"],
    product: "bbg",
    case_type: "renewal",
  });
});
