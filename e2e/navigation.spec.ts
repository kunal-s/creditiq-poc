// Navigation: a case's steps are on one strip under its header, each step ends with the way on to
// the next, and the side menu names the open case; Help explains the steps.
import { expect, test } from "@playwright/test";
import { KESTREL, RM } from "./fixtures/data";
import { MockApi, showArea, signedIn } from "./support/api";

test("every step of a case is on one strip under the header, in the order a case moves", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  const strip = page.getByTestId("stage-progress");
  const tabs = strip.locator('[data-testid^="stage-"]');
  await expect(tabs).toHaveCount(10);
  const names = await tabs.allInnerTexts();
  expect(names.map((n) => n.trim())).toEqual([
    "Overview",
    "Files",
    "Extracted data",
    "Identity",
    "Document readiness",
    "Cross-verification",
    "Financials and Policy",
    "Outputs",
    "Rating and recommendation",
    "Submission",
  ]);
  // Three groups after the Overview, each named for assistive technology.
  await expect(strip.getByRole("list", { name: "Documents and data" })).toBeVisible();
  await expect(strip.getByRole("list", { name: "Assessment" })).toBeVisible();
  await expect(strip.getByRole("list", { name: "Memo and decision" })).toBeVisible();

  await page.getByTestId("stage-identity").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/identity$`));
  await expect(page.getByTestId("stage-identity")).toHaveAttribute("aria-current", "page");
  await page.getByTestId("stage-submission").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/submission$`));
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
    await expect(page.getByTestId("case-progress")).toBeVisible();
  }
});

test("every step ends with the way on to the next, in the strip's order", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const order = [
    "extraction",
    "identity",
    "completeness",
    "crossVerification",
    "policy",
    "outputs",
    "rating",
    "submission",
  ];
  for (const to of order) {
    const link = page.getByTestId("next-step-link");
    await expect(link).toHaveAttribute("data-to", to);
    await link.click();
    await expect(page.getByTestId("next-step")).toHaveAttribute("data-step", to);
  }
  // The last step leads to the Memo Library.
  await expect(page.getByTestId("next-step-link")).toHaveAttribute("data-to", "memos");
});

test("the side menu names the open case and leads to its Overview; its steps are on the strip", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/");
  await expect(page.getByTestId("case-nav")).toHaveCount(0);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const nav = page.getByTestId("case-nav");
  await expect(nav.getByRole("link")).toHaveCount(1);
  await nav.getByRole("link", { name: `Appraisal ${KESTREL}` }).click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}$`));
});

test("a step the role may not open is on the strip, locked, and the Next bar says so", async ({
  page,
}) => {
  await signedIn(page, new MockApi(), RM);
  await page.goto(`/appraisals/${KESTREL}`);
  for (const stage of ["extraction", "cross_verification", "policy", "outputs"]) {
    const tab = page.getByTestId(`stage-${stage}`);
    await expect(tab).toHaveAttribute("aria-disabled", "true");
    await expect(tab).toHaveAttribute("title", /your role does not include this step/);
  }
  await expect(page.getByTestId("stage-documents")).not.toHaveAttribute("aria-disabled");
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("next-step-locked")).toBeVisible();
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
