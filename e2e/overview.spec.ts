// The Overview: one line on whether the case can go to credit review, then what the appraisal
// needs, one line a requirement. A row opens to show its files, what to ask the customer and the
// upload; the rest of the detail lives on the Files and Completeness steps.
import { expect, test, type Page } from "@playwright/test";
import { KESTREL, SAFFRON } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test.use({ viewport: { width: 1440, height: 900 } });

async function overview(page: Page, api = new MockApi(), caseId = KESTREL) {
  await signedIn(page, api);
  await page.goto(`/appraisals/${caseId}`);
  await expect(page.getByTestId("journey-verdict")).toBeVisible();
  return api;
}

const scoreOf = async (page: Page, testId: string) =>
  /(\d+(?:\.\d)?)%/.exec((await page.getByTestId(testId).textContent()) ?? "")?.[1];

test("the Overview opens with one line on whether the case can go to credit review", async ({
  page,
}) => {
  await overview(page);
  const status = page.getByTestId("journey-verdict");
  await expect(status).toHaveAttribute("data-state", "not_ready");
  await expect(status).toContainText(
    /Not ready for credit review: .*85% review gate, \d+ blocking/,
  );
  // The same score as the case header.
  expect(await scoreOf(page, "journey-verdict")).toBe(await scoreOf(page, "header-readiness"));
  // No dashboard: no tiles, meter or rail.
  await expect(page.locator("[data-testid^='journey-filter-']")).toHaveCount(0);
  await expect(page.getByTestId("next-action")).toHaveCount(0);
  await expect(page.getByTestId("waiting-decision")).toBeVisible();
});

test("a case ready for credit says so", async ({ page }) => {
  await overview(page, new MockApi(), SAFFRON);
  const status = page.getByTestId("journey-verdict");
  await expect(status).toHaveAttribute("data-state", "ready");
  await expect(status).toContainText("Ready for credit review");
  await expect(page.getByTestId("journey-band-blocking")).toHaveText(
    "No blocking gap remains on this case.",
  );
});

test("each requirement is one line; its files, the request and the upload open on demand", async ({
  page,
}) => {
  await overview(page);
  const row = page.locator('[data-testid="journey-item"][data-item="kyc_directors"]');
  await expect(row.getByTestId("journey-item-detail")).toContainText("Constitution and KYC · ");
  await expect(row).toContainText("Missing");
  await expect(row.getByTestId("journey-upload")).toHaveCount(0);
  await expect(row.getByTestId("journey-why")).toHaveCount(0);

  const toggle = row.getByTestId("journey-item-toggle");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  await expect(row.getByTestId("journey-upload")).toBeVisible();
  await expect(row.getByTestId("journey-why")).toBeVisible();
  await toggle.click();
  await expect(row.getByTestId("journey-upload")).toHaveCount(0);
});

test("a file sent from an opened row is read where it was sent, and the status line moves", async ({
  page,
}) => {
  const api = await overview(page);
  const row = page.locator('[data-testid="journey-item"][data-item="kyc_directors"]');
  await row.getByTestId("journey-item-toggle").click();
  await row
    .getByTestId("journey-upload-input")
    .setInputFiles([
      { name: "kyc-leela.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") },
    ]);
  await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "reading");

  const added = api.files.get(KESTREL)!.find((f) => f.original_name === "kyc-leela.pdf")!;
  const template = api.documents.get(KESTREL)![0]!;
  api.documents.set(KESTREL, [
    ...api.documents.get(KESTREL)!,
    { ...template, id: "doc-kyc-new", file_id: added.id },
  ]);
  const r = api.checklists.get(KESTREL)!;
  api.checklists.set(KESTREL, {
    ...r,
    score_pct: 70,
    blocking_open: 1,
    items: r.items.map((i) =>
      i.item_id === "kyc_directors"
        ? { ...i, status: "satisfied", deficiency: null, document_ids: ["doc-kyc-new"] }
        : i,
    ),
  });
  await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "counted", {
    timeout: 15_000,
  });
  await expect(row).toHaveAttribute("data-status", "satisfied");
  await expect(page.getByTestId("journey-verdict")).toContainText(
    "70% against the 85% review gate, 1 blocking",
  );
});

test("on a phone each row keeps its status, and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await overview(page);
  const row = page.locator('[data-testid="journey-item"][data-item="kyc_directors"]');
  await expect(row).toContainText("Missing");
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(sideways).toBe(false);
});

test("before any document is in, readiness waits for documents instead of scoring 0", async ({
  page,
}) => {
  const api = new MockApi();
  api.documents.set(KESTREL, []);
  await overview(page, api);
  const status = page.getByTestId("journey-verdict");
  await expect(status).toHaveAttribute("data-state", "waiting-documents");
  await expect(status).toContainText("Waiting for documents");
  await expect(status.getByTestId("verdict-upload")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/documents`,
  );
  const header = page.getByTestId("header-readiness");
  await expect(header).toHaveAttribute("data-state", "waiting-documents");
  await expect(header).toContainText("Waiting for documents");
  await expect(header).not.toContainText("%");
  await expect(page.getByTestId("header-blocking")).toHaveCount(0);
});

test("while the documents are read, readiness says so and counts them", async ({ page }) => {
  const api = new MockApi();
  const docs = api.documents.get(KESTREL)!;
  api.documents.set(KESTREL, [{ ...docs[0]!, status: "received" }, ...docs.slice(1)]);
  await overview(page, api);
  const status = page.getByTestId("journey-verdict");
  await expect(status).toHaveAttribute("data-state", "waiting-reading");
  await expect(status).toContainText(
    new RegExp(`Reading the documents \\(\\d+ of ${docs.length}\\)`),
  );
  await expect(page.getByTestId("header-readiness")).toContainText(
    new RegExp(`Reading documents · \\d+ of ${docs.length}`),
  );
  await expect(page.getByTestId("header-blocking")).toHaveCount(0);
});
