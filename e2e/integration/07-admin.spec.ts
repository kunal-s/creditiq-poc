// Administration (FRD §6): read-only views of the published configuration.
// Nothing here is editable from a screen; a publish happens off the service.
import { expect, test } from "@playwright/test";

import { signIn } from "../support/ui";

test("Administration names the published version", async ({ page }) => {
  await signIn(page, "analyst");
  await page.getByRole("link", { name: "Configuration" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByTestId("config-version").first()).toBeVisible();
});

test("Policy norms are listed by family with their required values", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/admin/policy");
  await expect(page.getByTestId("admin-norm")).toHaveCount(13);
});

test("the checklist configuration lists its gates", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/admin/checklist");
  await expect(page.getByTestId("admin-gates")).toBeVisible();
  await expect(page.getByTestId("admin-item")).not.toHaveCount(0);
});

test("the document types are the closed published list", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/admin/document-types");
  await expect(page.getByTestId("admin-document-type")).not.toHaveCount(0);
});

test("the people and their roles are listed", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/admin/users");
  await expect(page.getByTestId("admin-user")).toHaveCount(3);
  await expect(page.getByTestId("admin-role")).not.toHaveCount(0);
});

test("every Administration screen is reachable from the menu", async ({ page }) => {
  await signIn(page, "analyst");
  for (const [name, url] of [
    ["Policy norms", /\/admin\/policy$/],
    ["Checklist", /\/admin\/checklist$/],
    ["Document types", /\/admin\/document-types$/],
    ["Users and roles", /\/admin\/users$/],
  ] as const) {
    await page.goto("/");
    await page.getByRole("link", { name }).click();
    await expect(page).toHaveURL(url);
  }
});

test("Administration is open to the credit manager too", async ({ page }) => {
  await signIn(page, "manager");
  await page.goto("/admin");
  await expect(page.getByTestId("config-version").first()).toBeVisible();
});
