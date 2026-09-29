/// <reference types="node" />
// Endpoints the engine declares before their feature is live answer 501.
// Every screen shows a designed "not available yet" state, never a crash.
import { expect, test } from "@playwright/test";
import { KESTREL, MESSAGE } from "./fixtures/data";
import { MockApi, NOT_YET, signedIn } from "./support/api";

test("501 from the Wave 1 endpoints reads as not available yet", async ({ page }) => {
  const api = new MockApi()
    .on("POST", /^\/api\/cases\/proposals$/, () => NOT_YET)
    .on("POST", /\/files$/, () => NOT_YET)
    .on("GET", /\/parties$/, () => NOT_YET)
    .on("GET", /\/pages\/\d+$/, () => NOT_YET)
    .on("POST", /\/decision$/, () => NOT_YET);
  await signedIn(page, api);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/appraisals/new");
  await page.getByTestId("message-input").fill(MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  await expect(page.getByTestId("state-notAvailable")).toContainText("Not available yet");

  await page.goto(`/appraisals/${KESTREL}/identity`);
  await expect(page.getByTestId("parties").getByTestId("state-notAvailable")).toBeVisible();

  await page.goto(`/appraisals/${KESTREL}/data`);
  await page.getByTestId("field-value").first().click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("state-notAvailable")).toBeVisible();
  await page.keyboard.press("Escape");

  await page.goto(`/appraisals/${KESTREL}/upload`);
  await page.getByTestId("upload-input").setInputFiles({
    name: "gst.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF"),
  });
  await expect(
    page.getByTestId("files-received").locator("..").getByTestId("state-notAvailable"),
  ).toBeVisible();

  await page.goto("/exceptions");
  await page.getByTestId("decide").first().click();
  await page.getByTestId("assign-type").selectOption("utility_bill");
  await page.getByTestId("record-decision").click();
  await expect(page.getByTestId("decision-dialog").getByTestId("state-notAvailable")).toBeVisible();

  expect(errors).toEqual([]);
});

test("a role without the permission sees a designed state", async ({ page }) => {
  const api = new MockApi().on("GET", /\/fields$/, () => ({
    status: 403,
    json: { detail: "forbidden" },
  }));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/data`);
  await expect(page.getByTestId("state-forbidden")).toContainText("Not part of your role");
});
