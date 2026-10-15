// What each role may see of a case (config/roles.yaml): the tabs on offer, the
// screens that stay closed, and the fact that a case a role may not see is
// absent rather than forbidden.
import { expect, test, type Page } from "@playwright/test";

import { createCase, pinAsOf } from "../support/integration";
import { caseTabs, deleteCaseViaUi, signIn, signOut } from "../support/ui";

test.describe.configure({ mode: "serial" });

let page: Page;
let analystCase: string;
let rmCase: string;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await signIn(page, "analyst");
  analystCase = await createCase(page, `Access Analyst ${Date.now()} Pvt Ltd`);
  pinAsOf(analystCase);
  await signOut(page);
  await signIn(page, "rm");
  rmCase = await createCase(page, `Access Desk ${Date.now()} Pvt Ltd`);
  pinAsOf(rmCase);
});

test.afterAll(async () => {
  await signOut(page).catch(() => undefined);
  await signIn(page, "analyst");
  if (rmCase) await deleteCaseViaUi(page, rmCase);
  if (analystCase) await deleteCaseViaUi(page, analystCase);
  await page.close();
});

test("a relationship manager's own case offers three tabs", async () => {
  await signOut(page);
  await signIn(page, "rm");
  await page.goto(`/appraisals/${rmCase}`);
  await expect(page.getByTestId("case-header")).toContainText(rmCase);
  await expect(caseTabs(page)).toHaveCount(3);
  const nav = page.getByTestId("case-nav");
  await expect(nav.getByRole("link", { name: "Extracted data" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Cross-checks" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Policy" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Outputs" })).toHaveCount(0);
  await expect(nav.getByRole("link", { name: "Comparison" })).toHaveCount(0);
});

test("a case the relationship manager may not see is not there at all", async () => {
  await page.goto(`/appraisals/${analystCase}`);
  // Absent, not forbidden: the engine answers 404 for a case outside the role's
  // reach, so the screen shows nothing was found rather than a refusal.
  await expect(page.getByTestId("case-header")).toHaveCount(0);
  await expect(page.getByTestId("state-forbidden")).toHaveCount(0);
  // The screen offers the way back to the list instead.
  await expect(page.getByRole("link", { name: "Appraisals" }).first()).toBeVisible();
});

test("a tab outside the relationship manager's role shows a designed state, not a crash", async () => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`/appraisals/${rmCase}/extraction`);
  // Their own case, so the header is there; the data on the tab is not.
  await expect(page.getByTestId("case-header")).toContainText(rmCase);
  await expect(page.getByTestId("state-forbidden").first()).toBeVisible();
  expect(errors).toEqual([]);
});

test("an analyst's case offers seven tabs, Comparison excepted", async () => {
  await signOut(page);
  await signIn(page, "analyst");
  await page.goto(`/appraisals/${analystCase}`);
  await expect(caseTabs(page)).toHaveCount(7);
  await expect(page.getByTestId("case-nav").getByRole("link", { name: "Comparison" })).toHaveCount(
    0,
  );
});

test("Comparison is closed to the analyst even by its own address", async () => {
  await page.goto(`/appraisals/${analystCase}/comparison`);
  // The role lacks the permission, so the screen says the role does not cover it.
  await expect(page.getByTestId("state-forbidden").first()).toBeVisible();
});

test("a credit manager's case offers all eight tabs, Comparison among them", async () => {
  await signOut(page);
  await signIn(page, "manager");
  await page.goto(`/appraisals/${analystCase}`);
  await expect(caseTabs(page)).toHaveCount(8);
  await expect(
    page.getByTestId("case-nav").getByRole("link", { name: "Comparison" }),
  ).toBeVisible();
});

test("a credit manager cannot upload documents", async () => {
  await page.goto(`/appraisals/${analystCase}/documents`);
  await expect(page.getByTestId("case-header")).toContainText(analystCase);
  await expect(page.getByTestId("upload-zone")).toHaveCount(0);
  await expect(page.getByTestId("upload-input")).toHaveCount(0);
});

test("a credit manager cannot reach the New appraisal screen", async () => {
  await page.goto("/appraisals/new");
  await expect(page.getByTestId("message-input")).toHaveCount(0);
});

test("the audit trail and Administration are closed to a relationship manager", async () => {
  await signOut(page);
  await signIn(page, "rm");
  await page.goto("/audit");
  await expect(page.getByTestId("audit-entry")).toHaveCount(0);
  await page.goto("/admin");
  await expect(page.getByTestId("config-version")).toHaveCount(0);
  await page.goto("/review");
  await expect(page.getByTestId("review-row")).toHaveCount(0);
});
