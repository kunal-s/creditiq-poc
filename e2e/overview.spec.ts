// The Overview, a stand-up view of the case: one line on whether it can go to credit review, then
// document readiness (satisfied of all, and why the rest are not), then every document under its
// section with its mark and status, then what waits for a decision.
// The requirement list itself lives on the Files and Document readiness steps.
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
  expect(await scoreOf(page, "journey-verdict")).toBe(
    await scoreOf(page, "header-readiness-score"),
  );
  // A stand-up view: the status, document readiness and what waits; no requirement list here.
  await expect(page.getByTestId("journey-readiness")).toBeVisible();
  await expect(page.getByTestId("waiting-decision")).toBeVisible();
  await expect(page.getByTestId("document-checklist")).toHaveCount(0);
  await expect(page.getByTestId("journey-item")).toHaveCount(0);
});

test("document readiness opens on its counts: every requirement once, the rest by why", async ({
  page,
}) => {
  await overview(page);
  const panel = page.getByTestId("readiness-panel-readiness");
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId("document-readiness-total")).toHaveText("2 / 9");
  await expect(panel.getByTestId("document-readiness-satisfied")).toContainText(/2\s*Satisfied/);
  await expect(panel.getByTestId("document-readiness-not_satisfied")).toContainText(
    /7\s*Not satisfied/,
  );
  await expect(panel.getByTestId("document-readiness-breakdown")).toContainText(
    "Of the 7 not satisfied",
  );
  await expect(panel.getByTestId("document-readiness-missing")).toContainText(/Missing\s*2/);
  await expect(panel.getByTestId("document-readiness-insufficient")).toContainText(
    /Insufficient\s*4/,
  );
  await expect(panel.getByTestId("document-readiness-in_review")).toContainText(/In review\s*1/);
  await expect(panel.getByTestId("document-readiness-blocking")).toHaveText(
    "Blocking credit review: 2",
  );
  // Figures to read, not filters: nothing below them to filter.
  await expect(panel.getByRole("button")).toHaveCount(0);
});

test("document readiness and document status are shown one under the other", async ({ page }) => {
  await overview(page);
  const readiness = page.getByTestId("readiness-panel-readiness");
  const status = page.getByTestId("readiness-panel-status");
  await expect(readiness).toContainText("Document readiness");
  await expect(status).toContainText("Document status");
  await expect(readiness).toBeVisible();
  await expect(status.getByTestId("document-status-item").first()).toBeVisible();
  // No tabs: both at once, the counts first and the documents under them.
  await expect(page.getByRole("tablist")).toHaveCount(0);
  const top = async (l: typeof readiness) => (await l.boundingBox())!.y;
  expect(await top(status)).toBeGreaterThan(await top(readiness));
  // Each as wide as the other.
  expect((await status.boundingBox())!.width).toBe((await readiness.boundingBox())!.width);
});

test("document status names every document under its section, with its mark and its word", async ({
  page,
}) => {
  await overview(page);
  const sections = page.getByTestId("document-status-section");
  expect(await sections.evaluateAll((els) => els.map((e) => e.dataset["section"]))).toEqual([
    "Constitution and KYC",
    "Financials",
    "Banking and operations",
    "Collateral and security",
  ]);
  await expect(page.getByTestId("document-status-item")).toHaveCount(9);
  const rows = sections
    .filter({ hasText: "Constitution and KYC" })
    .getByTestId("document-status-item");
  expect(await rows.evaluateAll((els) => els.map((e) => e.dataset["status"]))).toEqual([
    "satisfied",
    "insufficient",
    "missing",
  ]);
  await expect(rows.nth(0)).toContainText("Certificate of incorporation");
  await expect(rows.nth(0)).toContainText("Satisfied");
  await expect(rows.nth(2)).toContainText("KYC of directors");
  await expect(rows.nth(2)).toContainText("Missing");
  await expect(rows.nth(2)).toContainText("Blocks credit review");
  // Every row has its mark; no section says "x of y satisfied" instead of naming them.
  for (const marks of await page
    .getByTestId("document-status-item")
    .evaluateAll((els) => els.map((e) => e.querySelectorAll("svg").length)))
    expect(marks).toBe(1);
  await expect(page.getByTestId("journey-readiness")).not.toContainText(/\d+ of \d+ satisfied/);
});

test("the Overview and the Document readiness step count the same requirements", async ({
  page,
}) => {
  await overview(page);
  await expect(page.getByTestId("document-readiness-total")).toHaveText("2 / 9");
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  await expect(page.getByTestId("checklist-filter-all")).toHaveText("All (9)");
  await expect(page.getByTestId("checklist-filter-not_satisfied")).toHaveText("Not satisfied (7)");
  await expect(page.getByTestId("checklist-filter-satisfied")).toHaveText("Satisfied (2)");
  await expect(page.getByTestId("checklist-filter-blocking")).toHaveText(
    "Blocks credit review (2)",
  );
});

test("a case ready for credit says so", async ({ page }) => {
  await overview(page, new MockApi(), SAFFRON);
  const status = page.getByTestId("journey-verdict");
  await expect(status).toHaveAttribute("data-state", "ready");
  await expect(status).toContainText("Ready for credit review");
  await expect(page.getByTestId("document-readiness-total")).toHaveText("9 / 9");
  await expect(page.getByTestId("journey-readiness")).toContainText(
    "Every requirement is satisfied.",
  );
});

test("a provisional checklist says so over the counts", async ({ page }) => {
  const api = new MockApi();
  api.checklists.set(KESTREL, { ...api.checklists.get(KESTREL)!, provisional: true });
  await overview(page, api);
  await expect(page.getByTestId("journey-provisional")).toContainText("provisional");
  await expect(page.getByTestId("document-readiness-total")).toBeVisible();
});

test("on a phone the counts and the documents fit, and nothing scrolls sideways", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await overview(page);
  await expect(page.getByTestId("document-readiness-total")).toHaveText("2 / 9");
  await page.getByTestId("document-status-item").first().scrollIntoViewIfNeeded();
  await expect(page.getByTestId("document-status-item").first()).toBeVisible();
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
  // No counts until there is something to count.
  await expect(page.getByTestId("journey-readiness")).toHaveCount(0);
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
  await expect(page.getByTestId("journey-readiness")).toHaveCount(0);
  await expect(page.getByTestId("header-readiness")).toContainText(
    new RegExp(`Reading documents · \\d+ of ${docs.length}`),
  );
  await expect(page.getByTestId("header-blocking")).toHaveCount(0);
});

test("when the checklist cannot be read the Overview says so and offers a retry", async ({
  page,
}) => {
  const api = new MockApi();
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/checklist$`), () => ({
    status: 500,
    json: { detail: "down" },
  }));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  const notice = page.getByTestId("journey-verdict");
  await expect(notice).toHaveAttribute("data-state", "error", { timeout: 15_000 });
  await expect(notice.getByRole("button")).toBeVisible();
});
