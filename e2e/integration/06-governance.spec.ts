// Governance and help: the review queue, the audit trail, the scorecard
// placeholder and the guide to the steps, against the real engine.
import { expect, test } from "@playwright/test";

import { signIn } from "../support/ui";

test("the review queue is grouped by the kind of item it holds", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/review");
  // The queue's kind filters are present whether or not anything is queued.
  await expect(page.getByTestId("kind-type")).toBeVisible();
  await expect(page.getByTestId("kind-field")).toBeVisible();
  await expect(page.getByTestId("kind-finding")).toBeVisible();
});

test("the audit trail lists what has happened, in words, and can be filtered", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/audit");
  await expect(page.getByTestId("audit-entry").first()).toBeVisible();
  // Sign-in alone puts an entry on the trail, so the list is never empty here.
  await expect(page.getByTestId("audit-entry")).not.toHaveCount(0);
  // The actor and action filters are built from what is on the trail.
  await expect(page.getByRole("combobox")).not.toHaveCount(0);
  // Nothing on the trail reads as a raw event key.
  await expect(page.getByTestId("audit-entry").first()).not.toContainText("auth.login");
});

test("the audit trail names the person who acted", async ({ page }) => {
  await signIn(page, "analyst");
  await page.goto("/audit");
  await expect(page.getByTestId("audit-entry").first()).toContainText("Ananya Krishnan");
});

test("the scorecard is a designed placeholder, not a crash", async ({ page }) => {
  const errors: string[] = [];
  await signIn(page, "manager");
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/scorecard");
  await expect(page.locator('[data-feature="F-26"]')).toBeVisible();
  expect(errors).toEqual([]);
});

test("the scorecard is closed to the analyst", async ({ page }) => {
  await signIn(page, "analyst");
  await expect(page.getByRole("link", { name: "Scorecard" })).toHaveCount(0);
});

test("Help explains each step and each status", async ({ page }) => {
  await signIn(page, "analyst");
  await page.getByRole("link", { name: "Guide to the steps" }).first().click();
  await expect(page).toHaveURL(/\/help$/);
  for (const step of [
    "documents",
    "extraction",
    "completeness",
    "crossVerification",
    "policy",
    "outputs",
  ]) {
    await expect(page.getByTestId(`help-step-${step}`)).toBeVisible();
  }
});

test("Help is open to every role", async ({ page }) => {
  await signIn(page, "rm");
  await page.goto("/help");
  await expect(page.getByTestId("help-step-documents")).toBeVisible();
});

test("an address that is not a screen says so rather than crashing", async ({ page }) => {
  const errors: string[] = [];
  await signIn(page, "analyst");
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/no-such-screen");
  await expect(page.getByTestId("cases-table")).toHaveCount(0);
  expect(errors).toEqual([]);
});
