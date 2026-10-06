// Navigation: a case's two flows with their sub-tabs show above the case
// (top tabs and sub-tabs) and in the side menu; Help explains the steps.
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("a case groups its steps into two flows with sub-tabs", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  await expect(page.getByTestId("flow-ingestion")).toHaveText("Documents and data");
  await expect(page.getByTestId("flow-verification")).toHaveText("Verification and policy");
  // Sub-tabs show only inside their flow.
  await expect(page.getByTestId("tab-extraction")).toHaveCount(0);
  await page.getByTestId("flow-ingestion").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/documents$`));
  await page.getByTestId("tab-extraction").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/extraction$`));
  await page.getByTestId("flow-verification").click();
  await expect(page.getByTestId("tab-crossVerification")).toBeVisible();
  await expect(page.getByTestId("tab-policy")).toBeVisible();
  await expect(page.getByTestId("tab-extraction")).toHaveCount(0);
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
