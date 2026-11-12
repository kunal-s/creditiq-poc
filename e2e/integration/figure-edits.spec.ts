// A figure changed on a financial statement against the real engine: the Credit Analyst changes it
// with a reason and a paper, the Credit Manager sees it awaiting check and approves it, and the
// field then reads Corrected with both values kept (engine/figure_edits.py).
import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

import {
  asRole,
  createPinnedCase,
  deleteCase,
  fixtureFile,
  fixtureSet,
  signedInAs,
  waitForProcessing,
} from "../support/engine";

test.describe.configure({ mode: "serial" });

const REASON = "Revised per the auditor's letter on the restated figures";

let api: APIRequestContext;
let caseId: string;
let field: string;

async function pageAs(browser: Browser, role: "analyst" | "manager"): Promise<Page> {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await signedInAs(page, role);
  return page;
}

test.beforeAll(async () => {
  api = await asRole("analyst");
  caseId = await createPinnedCase(api);
  // One file a request: this Playwright build cannot send a list of files in one multipart body.
  for (const name of fixtureSet("complete").filter((n) => n.includes("audited"))) {
    const res = await api.post(`/api/cases/${encodeURIComponent(caseId)}/files`, {
      multipart: { files: fixtureFile(name) },
    });
    expect(res.status()).toBe(202);
  }
  await waitForProcessing(api, caseId);
});

test.afterAll(async () => {
  if (caseId) await deleteCase(api, caseId);
  await api.dispose();
});

test("the Credit Analyst changes a figure with a reason and a paper; it waits for a check", async ({
  browser,
}) => {
  const page = await pageAs(browser, "analyst");
  await page.goto(`/appraisals/${caseId}/extraction`);
  await page.getByTestId("data-filter-all").click();
  // The statements' figures are in their tables (balance sheet, profit and loss), open with the
  // document, and the panel says where a figure is changed.
  const financials = page.getByTestId("field-section-financials");
  await expect(financials.getByTestId("figure-edit-hint").first()).toBeVisible();
  const open = page.locator(
    '[data-testid="field-section-financials"] [data-testid="field-table"] [data-testid="figure-edit-open"]',
  );
  await open.first().scrollIntoViewIfNeeded();
  field = (await open.first().getAttribute("data-field"))!;
  await open.first().click();
  const dialog = page.getByTestId("figure-edit-dialog");
  await dialog.getByTestId("figure-edit-value").fill("12,34,567");
  await dialog.getByTestId("figure-edit-reason-input").fill(REASON);
  await dialog.getByTestId("figure-edit-file").setInputFiles({
    name: "auditor-letter.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7\n%%EOF\n"),
  });
  await dialog.getByTestId("figure-edit-send").click();
  await expect(dialog).toBeHidden();

  const note = page.locator(`[data-testid="figure-edit-pending"][data-field="${field}"]`);
  await expect(note.getByTestId("figure-edit-change")).toContainText("12,34,567");
  await expect(note.getByTestId("figure-edit-reason")).toHaveText(REASON);
  await expect(note.getByTestId("figure-edit-attachment")).toContainText("auditor-letter.pdf");
  await expect(note.getByTestId("figure-edit-waiting")).toBeVisible();
  await expect(note.getByTestId("figure-edit-approve")).toHaveCount(0);
  await page.close();
});

test("the Credit Manager opens on it, reads the paper, and approves it", async ({ browser }) => {
  const page = await pageAs(browser, "manager");
  await page.goto(`/appraisals/${caseId}/extraction`);
  await expect(page.getByTestId("data-filter-awaiting")).toHaveAttribute("aria-pressed", "true");
  const note = page.locator(`[data-testid="figure-edit-pending"][data-field="${field}"]`);
  const download = page.waitForEvent("download");
  await note.getByTestId("figure-edit-attachment").click();
  expect((await download).suggestedFilename()).toBe("auditor-letter.pdf");
  await note.getByTestId("figure-edit-approve").click();
  await expect(note).toBeHidden();

  await page.getByTestId("data-filter-corrected").click();
  const value = page.locator(`[data-testid="field-value"][data-field="${field}"]`).first();
  await expect(value).toContainText("12,34,567");
  await expect(value.getByTestId("system-value")).toBeVisible();
  await page.close();
});
