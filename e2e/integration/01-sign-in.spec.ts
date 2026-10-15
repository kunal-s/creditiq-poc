// Sign-in screen and the session it opens, against the real engine (F-03).
import { expect, test } from "@playwright/test";

import { PASSWORD, USERS, navLinkNames, signIn, signOut } from "../support/ui";

/** Sonner marks each toast and its kind with data attributes. */
const ERROR_TOAST = '[data-sonner-toast][data-type="error"]';

test("the sign-in screen asks for an email and a password", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page.getByLabel("Email")).toBeVisible();
  await expect(page.getByLabel("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
});

test("an unauthenticated visit to the workbench lands on sign-in", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in/);
});

test("a wrong password is refused and the session does not open", async ({ page }) => {
  await page.goto("/sign-in");
  // The form is controlled, so wait until it is live before typing into it.
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email").fill(USERS.analyst.email);
  await page.getByLabel("Password").fill("not-the-password");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(ERROR_TOAST)).toBeVisible();
  await expect(page).toHaveURL(/\/sign-in/);

  // And the workbench is still closed.
  await page.goto("/");
  await expect(page).toHaveURL(/\/sign-in/);
});

test("an unknown email is refused", async ({ page }) => {
  await page.goto("/sign-in");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email").fill("nobody@rblbank.com");
  await page.getByLabel("Password").fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.locator(ERROR_TOAST)).toBeVisible();
  await expect(page).toHaveURL(/\/sign-in/);
});

for (const role of ["rm", "analyst", "manager"] as const) {
  test(`${role} signs in, is named with their role, and signs out`, async ({ page }) => {
    await signIn(page, role);
    const banner = page.getByRole("banner");
    await expect(banner).toContainText(USERS[role].name);
    await expect(banner).toContainText(USERS[role].role);
    await signOut(page);
    await page.goto("/");
    await expect(page).toHaveURL(/\/sign-in/);
  });
}

test("the relationship manager's menu holds neither Governance nor Administration", async ({
  page,
}) => {
  await signIn(page, "rm");
  const names = await navLinkNames(page);
  expect(names).toContain("Appraisals");
  expect(names).toContain("New appraisal");
  expect(names).toContain("Guide to the steps");
  expect(names).not.toContain("Review queue");
  expect(names).not.toContain("Audit trail");
  expect(names).not.toContain("Configuration");
  expect(names).not.toContain("Scorecard");
});

test("the analyst's menu holds Governance and Administration but not the Scorecard", async ({
  page,
}) => {
  await signIn(page, "analyst");
  const names = await navLinkNames(page);
  expect(names).toContain("Review queue");
  expect(names).toContain("Audit trail");
  expect(names).toContain("Configuration");
  expect(names).toContain("Policy norms");
  expect(names).toContain("Checklist");
  expect(names).toContain("Document types");
  expect(names).toContain("Users and roles");
  expect(names).not.toContain("Scorecard");
});

test("the credit manager's menu holds the Scorecard and cannot create an appraisal", async ({
  page,
}) => {
  await signIn(page, "manager");
  const names = await navLinkNames(page);
  expect(names).toContain("Scorecard");
  expect(names).toContain("Review queue");
  expect(names).toContain("Audit trail");
  expect(names).not.toContain("New appraisal");
});
