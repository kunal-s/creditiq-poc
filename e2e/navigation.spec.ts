// Navigation: a case's steps are in the side menu and the stage bar;
// Help explains the steps.
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, showArea, signedIn } from "./support/api";

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
  await expect(page.getByTestId("stage-overview")).not.toHaveAttribute("aria-current");
});

test("the stage bar leads back to the Overview from every step", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  const overview = page.getByTestId("stage-overview");
  await expect(overview).toHaveAttribute("aria-current", "page");
  for (const stage of ["documents", "extraction", "completeness", "cross_verification"]) {
    await page.getByTestId(`stage-${stage}`).click();
    await expect(page.getByTestId(`stage-${stage}`)).toHaveAttribute("aria-current", "page");
    await overview.click();
    await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}$`));
    await expect(page.getByTestId("document-status")).toBeVisible();
  }
});

test("the side menu lists the open case's steps under New appraisal, each with its status", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/");
  await expect(page.getByTestId("case-nav")).toHaveCount(0);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const nav = page.getByTestId("case-nav");
  await expect(nav.getByRole("link", { name: "Identity" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Policy" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Submission" })).toBeVisible();
  await nav.getByRole("link", { name: "Cross-verification" }).click();
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
  const ob2 = page.getByTestId("xv-card-fnd-ob2");
  await showArea(page, "obligations");
  await ob2.getByTestId("xv-card-toggle").click();
  await expect(ob2).toHaveAttribute("data-expanded", "true");
  const lines = ob2.getByTestId("xv-line-by-line");
  await expect(lines).not.toHaveAttribute("open", "");
  await expect(lines.getByTestId("xv-detail-table")).toBeHidden();
  await lines.getByText("Line by line (2)").click();
  await expect(lines.getByTestId("xv-detail-table")).toBeVisible();

  await page.goto(`/appraisals/${KESTREL}/policy`);
  // A norm's figures and working open only when its tile is selected.
  await expect(page.getByTestId("norm").first()).toBeVisible();
  await expect(page.getByTestId("norm-detail")).toHaveCount(0);
  await expect(page.getByTestId("norm-details")).toHaveCount(0);
});
