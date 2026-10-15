// The workbench (FRD §6): the appraisals in flight, the counters above them
// and the filters over the list, against the real engine.
import { expect, test } from "@playwright/test";

import { createCase } from "../support/integration";
import { USERS, deleteCaseViaUi, signIn } from "../support/ui";

test.describe.configure({ mode: "serial" });

test("a new appraisal appears on the workbench and is counted in flight", async ({ page }) => {
  await signIn(page, "analyst");
  // The counter shows a placeholder until the appraisals have been fetched.
  const inFlight = page.getByTestId("counter-in-progress-value");
  await expect(inFlight).toHaveText(/^\d+$/);
  const before = Number(await inFlight.innerText());

  const caseId = await createCase(page, `Workbench Metals ${Date.now()} Pvt Ltd`);
  try {
    await page.goto("/");
    const table = page.getByTestId("cases-table");
    await expect(table).toContainText(caseId);
    await expect(inFlight).toHaveText(String(before + 1));

    // Nothing is ready for credit before a single document is in.
    await expect(page.getByTestId("counter-ready-value")).toHaveText("0");
  } finally {
    await deleteCaseViaUi(page, caseId);
  }
});

test("the three counters and the filters are on the workbench", async ({ page }) => {
  await signIn(page, "analyst");
  await expect(page.getByTestId("counter-in-progress")).toBeVisible();
  await expect(page.getByTestId("counter-review")).toBeVisible();
  await expect(page.getByTestId("counter-ready")).toBeVisible();
  await expect(page.getByTestId("case-filters")).toBeVisible();
});

test("the owner filter is offered only to a role that sees every appraisal", async ({ page }) => {
  await signIn(page, "analyst");
  const filters = page.getByTestId("case-filters");
  // The stage list, the owner toggle and the review toggle.
  await expect(filters.getByRole("combobox")).toHaveCount(1);
  await expect(filters.getByRole("button")).toHaveCount(2);

  await page.getByRole("button", { name: "Sign out" }).click();
  await signIn(page, "rm");
  // An RM sees only their own, so there is nothing to filter by owner.
  await expect(page.getByTestId("case-filters").getByRole("button")).toHaveCount(1);
});

test("a relationship manager sees only their own appraisals", async ({ page }) => {
  await signIn(page, "analyst");
  const analystCase = await createCase(page, `Analyst Only ${Date.now()} Pvt Ltd`);
  try {
    await page.goto("/");
    await expect(page.getByTestId("cases-table")).toContainText(analystCase);

    await page.getByRole("button", { name: "Sign out" }).click();
    await signIn(page, "rm");
    // The RM owns nothing here, so there is no list at all; either way the
    // analyst's case is nowhere to be opened from.
    await expect(page.locator(`a[href$="${analystCase}"]`)).toHaveCount(0);

    // And its screens are not reachable: unseen, not merely forbidden.
    await page.goto(`/appraisals/${analystCase}`);
    await expect(page.getByTestId("case-header")).toHaveCount(0);
  } finally {
    await page.getByRole("button", { name: "Sign out" }).click();
    await signIn(page, "analyst");
    await deleteCaseViaUi(page, analystCase);
  }
});

test("a credit manager sees every appraisal but is offered no way to create one", async ({
  page,
}) => {
  await signIn(page, "analyst");
  const caseId = await createCase(page, `Manager Reads ${Date.now()} Pvt Ltd`);
  try {
    await page.getByRole("button", { name: "Sign out" }).click();
    await signIn(page, "manager");
    await expect(page.getByTestId("cases-table")).toContainText(caseId);
    await expect(page.getByRole("link", { name: "New appraisal" })).toHaveCount(0);
    await expect(page.getByRole("banner")).toContainText(USERS.manager.role);
  } finally {
    await page.getByRole("button", { name: "Sign out" }).click();
    await signIn(page, "analyst");
    await deleteCaseViaUi(page, caseId);
  }
});
