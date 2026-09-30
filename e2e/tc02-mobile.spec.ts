/// <reference types="node" />
// TC-02: at phone width (375 px) an RM signs in, creates a case from a
// message and uploads documents with the same result as on a desktop, and
// no screen scrolls sideways (FRD F-06).
import { expect, test } from "@playwright/test";
import { KESTREL, MESSAGE, RM } from "./fixtures/data";
import { MockApi, scrollsSideways, signedIn } from "./support/api";

test.use({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });

test("TC-02: sign in at 375 px", async ({ page }) => {
  const api = new MockApi();
  api.user = RM;
  await api.install(page);
  await page.goto("/sign-in");
  expect(await scrollsSideways(page)).toBe(false);
  // The form is enabled once the page is interactive.
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email").fill(RM.email);
  await page.getByLabel("Password").fill("local-test-only");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByTestId("counter-in-progress-value")).toHaveText("3");
  expect(await scrollsSideways(page)).toBe(false);

  // Navigation is a menu button; the side navigation is hidden (F-06.2).
  await page.getByRole("button", { name: "Open menu" }).click();
  await expect(page.getByRole("dialog").getByRole("link", { name: "Cases" })).toBeVisible();
  // An RM does not see the governance group.
  await expect(page.getByRole("dialog").getByRole("link", { name: "Review queue" })).toHaveCount(0);
});

test("TC-02: create a case and upload documents at 375 px", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, RM);

  await page.goto("/");
  await expect(page.getByTestId("cases-cards")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);

  await page.goto("/cases/new");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  await expect(page.getByTestId("proposed-case")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
  await page.getByTestId("confirm-constitution").click();
  await page.getByTestId("confirm-declared_turnover_inr").click();

  // Attach files before creating: they go to the new case, which opens on
  // its Overview with processing under way.
  await page.getByTestId("upload-input").setInputFiles([
    { name: "director1_pan.jpg", mimeType: "image/jpeg", buffer: Buffer.from("jpeg") },
    { name: "gst-returns.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") },
  ]);
  await expect(page.getByTestId("attachments").getByRole("listitem")).toHaveCount(2);
  await page.getByTestId("create-application").click();

  await expect(page).toHaveURL(/\/cases\/BBG-2026-000031$/);
  await expect(page.getByTestId("stage-progress")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
  await page.getByTestId("tab-documents").click();
  await expect(page.getByTestId("tree-file")).toHaveCount(2);
  await expect(page.getByTestId("count-registered")).toHaveText("2");
  expect(await scrollsSideways(page)).toBe(false);
  expect(api.called("POST", "/api/cases/BBG-2026-000031/files")).toHaveLength(1);

  // The camera input is offered on a phone.
  await expect(page.getByRole("button", { name: "Take a photo" })).toBeVisible();
});

test("TC-02: overview, completeness and documents at 375 px", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, RM);
  await page.goto(`/cases/${KESTREL}`);
  await expect(page.getByTestId("next-action")).toBeVisible();
  // An RM sees only the tabs their role may open.
  await expect(page.getByTestId("tab-extraction")).toHaveCount(0);
  expect(await scrollsSideways(page)).toBe(false);
  await page.goto(`/cases/${KESTREL}/completeness`);
  await expect(page.getByTestId("checklist")).toBeVisible();
  await expect(page.getByTestId("query-list")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
  await page.goto(`/cases/${KESTREL}/documents`);
  await expect(page.getByTestId("file-tree")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
});
