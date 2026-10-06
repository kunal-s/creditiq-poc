// Navigation: a case's steps are in the side menu and the stage bar;
// Help explains the steps.
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("a case's steps are reached from the side menu and the stage bar", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  // One way in: no tab row above the case.
  await expect(page.getByTestId("tab-extraction")).toHaveCount(0);
  await expect(page.getByTestId("flow-ingestion")).toHaveCount(0);
  const nav = page.getByTestId("case-nav");
  await nav.getByRole("link", { name: "Files" }).click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/documents$`));
  await page.getByTestId("stage-extraction").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/extraction$`));
});

test("the side menu lists the open case's flows and statuses", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/");
  await expect(page.getByTestId("case-nav")).toHaveCount(0);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const nav = page.getByTestId("case-nav");
  await expect(nav).toContainText("Documents and data");
  await expect(nav).toContainText("Verification and policy");
  await expect(nav.getByRole("link", { name: "Policy" })).toBeVisible();
  await nav.getByRole("link", { name: "Cross-checks" }).click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/cross-verification$`));
});

test("Help explains each step and status", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/");
  await page.getByRole("link", { name: "Guide to the steps" }).first().click();
  await expect(page).toHaveURL(/\/help$/);
  await expect(page.getByTestId("help-step-crossVerification")).toBeVisible();
  await expect(page.getByText("Needs attention").first()).toBeVisible();
});

test("technical detail stays closed until asked for", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);
  const finding = page.getByTestId("finding-details").first();
  await expect(finding).not.toHaveAttribute("open", "");
  await expect(finding.getByText("Check reference")).toBeHidden();
  await finding.getByText("How was this decided").click();
  await expect(finding.getByText("Check reference")).toBeVisible();

  await page.goto(`/appraisals/${KESTREL}/policy`);
  const norm = page.getByTestId("norm-details").first();
  await expect(norm).not.toHaveAttribute("open", "");
  await expect(norm.getByText("How it is calculated")).toBeHidden();
});
