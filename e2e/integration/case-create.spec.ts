// Case creation through the New appraisal screen, against the real engine
// (F-04). Every step is a user action on screen; nothing is set up over the API.
import { expect, test } from "@playwright/test";

import {
  SOURCING_MESSAGE,
  caseIdFromUrl,
  createCaseViaUi,
  deleteCaseViaUi,
  settleProposedFields,
  signIn,
} from "../support/ui";

test("paste, read, confirm and create: the engine proposes the fields it found", async ({
  page,
}) => {
  await signIn(page, "analyst");
  await page.goto("/appraisals/new");

  // Nothing can be read before a channel and a message are given.
  const read = page.getByRole("button", { name: "Read the message" });
  await expect(read).toBeDisabled();

  await page.getByTestId("channel").selectOption("email");
  await page.getByTestId("message-input").fill(SOURCING_MESSAGE);
  await expect(read).toBeEnabled();
  await read.click();

  // The engine's proposal, field by field, each with a status.
  await expect(page.getByTestId("proposed-case")).toBeVisible();
  const status = (key: string) => page.getByTestId(`field-${key}`).getByTestId("proposed-status");

  // This message names a second business ("Pvt Ltd or maybe LLP"), so neither
  // the borrower nor the constitution is settled: each is unclear and carries
  // the candidates the RM chooses between (F-04.3).
  await expect(status("borrower")).toHaveText("Unclear");
  await expect(page.getByTestId("field-borrower").getByTestId("candidate")).toHaveCount(2);
  await expect(page.getByTestId("field-borrower").getByTestId("candidate").first()).toHaveText(
    "Kestrel Polymers Pvt Ltd",
  );
  await expect(status("constitution")).toHaveText("Unclear");

  // What the deterministic pass read with certainty.
  await expect(status("pan")).toHaveText("Found");
  await expect(page.getByTestId("field-pan").getByRole("textbox")).toHaveValue("AAACK1234K");
  await expect(status("amount_inr")).toHaveText("Found");
  await expect(page.getByTestId("field-amount_inr").getByRole("textbox")).toHaveValue("5000000");
  await expect(status("facilities")).toHaveText("Found");
  await expect(status("gstin")).toHaveText("Not found");

  // A minimum field the message did not settle, so creation is blocked twice
  // over: by the minimum and by the confirmations outstanding (F-04.4, F-04.6).
  await expect(page.getByTestId("missing-minimum")).toBeVisible();
  await expect(page.getByTestId("needs-confirmation")).toBeVisible();
  await expect(page.getByTestId("create-application")).toBeDisabled();

  // Choosing a candidate fills the field and settles it.
  await page.getByTestId("field-borrower").getByTestId("candidate").first().click();
  await expect(page.getByTestId("field-borrower").getByRole("textbox")).toHaveValue(
    "Kestrel Polymers Pvt Ltd",
  );

  const borrower = `Paste Flow ${Date.now()} Pvt Ltd`;
  await page.getByTestId("field-borrower").getByRole("textbox").fill(borrower);
  await settleProposedFields(page);

  await expect(page.getByTestId("needs-confirmation")).toHaveCount(0);
  const create = page.getByTestId("create-application");
  await expect(create).toBeEnabled();
  await create.click();

  // The case exists; the screen goes straight on to Files, where the documents
  // are added next (appraisals.new.tsx).
  await expect(page).toHaveURL(/\/appraisals\/BBG-\d{4}-\d{6}\/documents$/, { timeout: 30_000 });
  const caseId = caseIdFromUrl(page);
  await page.goto(`/appraisals/${caseId}`);
  await expect(page.getByTestId("case-header")).toContainText(borrower);
  await expect(page.getByTestId("case-header")).toContainText(caseId);

  // And it is on the workbench.
  await page.goto("/");
  await expect(page.getByTestId("cases-table")).toContainText(caseId);

  await deleteCaseViaUi(page, caseId);
});

test("nothing is created while the message is only read", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/");
  const rows = () => page.getByTestId("cases-table").getByRole("row").count();
  const before = await rows();

  await page.goto("/appraisals/new");
  await page.getByTestId("channel").selectOption("email");
  await page.getByTestId("message-input").fill(SOURCING_MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  await expect(page.getByTestId("proposed-case")).toBeVisible();

  // Reading stores nothing (F-04): the workbench holds exactly what it did.
  await page.goto("/");
  await expect.poll(rows).toBe(before);
});

test("a message without an amount says what is still needed", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/appraisals/new");
  await page.getByTestId("channel").selectOption("email");
  await page.getByTestId("message-input").fill("Client Vireo Castings Pvt Ltd is asking for CC.");
  await page.getByRole("button", { name: "Read the message" }).click();

  await expect(page.getByTestId("proposed-case")).toBeVisible();
  await expect(page.getByTestId("missing-minimum")).toBeVisible();
  await expect(page.getByTestId("missing-minimum")).toContainText("Still needed");
  await expect(page.getByTestId("create-application")).toBeDisabled();
});

test("a second application for the same borrower is offered the existing one", async ({ page }) => {
  await signIn(page, "analyst");
  const borrower = `Twin Mills ${Date.now()} Pvt Ltd`;
  const first = await createCaseViaUi(page, { borrower });

  try {
    // The same borrower again: the screen offers the case that already exists.
    await page.goto("/appraisals/new");
    await page.getByTestId("channel").selectOption("email");
    await page.getByTestId("message-input").fill(SOURCING_MESSAGE);
    await page.getByRole("button", { name: "Read the message" }).click();
    await page.getByTestId("field-borrower").getByRole("textbox").fill(borrower);
    await settleProposedFields(page);

    const warning = page.getByTestId("duplicate-warning");
    await expect(warning).toBeVisible({ timeout: 30_000 });
    await expect(warning).toContainText(first);
    // The case already on file is offered by name, with a way straight into it.
    await expect(
      warning.getByRole("link", { name: "Open it" }).and(page.locator(`[href$="${first}"]`)),
    ).toBeVisible();

    // Creating anyway is refused until a reason is given.
    await warning.getByRole("button", { name: "Create anyway" }).click();
    const reason = page.getByTestId("override-reason");
    await expect(reason).toBeVisible();
    await expect(page.getByTestId("create-application")).toBeDisabled();

    await reason.fill("Separate facility for the same borrower; approved by credit.");
    await expect(page.getByTestId("create-application")).toBeEnabled();
  } finally {
    await deleteCaseViaUi(page, first);
  }
});

test("Discard clears the proposal and leaves the screen empty", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/appraisals/new");
  await page.getByTestId("channel").selectOption("email");
  await page.getByTestId("message-input").fill(SOURCING_MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  await expect(page.getByTestId("proposed-case")).toBeVisible();

  await page.getByRole("button", { name: "Discard" }).click();
  await expect(page.getByTestId("proposed-case")).toHaveCount(0);
  await expect(page.getByTestId("message-input")).toHaveValue("");
});
