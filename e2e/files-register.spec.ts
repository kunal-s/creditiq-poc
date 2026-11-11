// The Files step: one register of the files received and, at its head, every required document
// not yet uploaded, each a white row with its own upload. A file sent from a row is read; its
// content decides where it counts, and the row says so. A role that cannot upload sees the rows
// without the upload.
import { expect, test, type Page } from "@playwright/test";
import { KESTREL, MANAGER } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

async function files(page: Page, api = new MockApi(), user = api.user) {
  await signedIn(page, api, user);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("files-received")).toBeVisible();
  return api;
}

const PDF = (name: string) => ({
  name,
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.7"),
});

test("every required document not uploaded heads the one register, named and marked missing", async ({
  page,
}) => {
  await files(page);
  const register = page.getByTestId("files-received");
  // One register: the missing documents are a section of it, before the files that came in.
  await expect(register.getByTestId("register-head")).toHaveCount(1);
  const missing = register.getByTestId("register-missing");
  await expect(missing).toHaveAttribute("data-count", "2");
  await expect(missing.getByRole("heading")).toHaveText("Not uploaded · 2");
  const sections = await register
    .locator("[data-testid='register-missing'], [data-testid^='section-']")
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  expect(sections[0]).toBe("register-missing");

  const rows = missing.getByTestId("register-missing-row");
  expect(await rows.evaluateAll((els) => els.map((e) => e.getAttribute("data-item")))).toEqual(
    expect.arrayContaining(["kyc_directors", "valuation"]),
  );
  const kyc = missing.locator('[data-item="kyc_directors"]');
  await expect(kyc).toContainText("Not uploaded");
  await expect(kyc).toContainText("KYC of directors");
  await expect(kyc).toContainText("Missing: 1 of 2 directors (Leela Varghese)");
  await expect(kyc).toContainText("Blocks credit review");
  await expect(kyc.locator("svg").first()).toBeVisible();
  // A white row like any other: no tinted area (section, heading, row) and no second status word;
  // the colour is in the mark and the blocking note only.
  const tinted = await missing.evaluate((section) =>
    [section, ...section.querySelectorAll("h3, li, li > div")].some((el) =>
      [...el.classList].some((c) => /^bg-(critical|destructive)/.test(c)),
    ),
  );
  expect(tinted).toBe(false);
  await expect(kyc.getByText("Missing", { exact: true })).toHaveCount(0);
  // No separate list of what is missing anywhere on the step.
  await expect(page.getByTestId("document-checklist")).toHaveCount(0);
});

test("a file uploaded from a missing row is read, and the row says where it counts", async ({
  page,
}) => {
  const api = await files(page);
  const row = page.locator('[data-testid="register-missing-row"][data-item="kyc_directors"]');
  await row.getByTestId("register-missing-upload-input").setInputFiles([PDF("kyc-leela.pdf")]);
  const outcome = row.getByTestId("register-missing-outcome");
  await expect(outcome).toHaveAttribute("data-state", "reading");
  await expect(outcome).toContainText("kyc-leela.pdf");
  expect(api.called("POST", `/api/cases/${KESTREL}/files`)).toHaveLength(1);

  // The engine reads it: a document on the new file, now counted toward the requirement.
  const added = api.files.get(KESTREL)!.find((f) => f.original_name === "kyc-leela.pdf")!;
  const template = api.documents.get(KESTREL)![0]!;
  api.documents.set(KESTREL, [
    ...api.documents.get(KESTREL)!,
    { ...template, id: "doc-kyc-new", file_id: added.id },
  ]);
  const r = api.checklists.get(KESTREL)!;
  api.checklists.set(KESTREL, {
    ...r,
    items: r.items.map((i) =>
      i.item_id === "kyc_directors" ? { ...i, document_ids: ["doc-kyc-new"] } : i,
    ),
  });
  await expect(outcome).toHaveAttribute("data-state", "counted", { timeout: 15_000 });
  await expect(outcome).toContainText("counts toward KYC of directors");
});

test("a second file sent from the same row keeps the first one's line", async ({ page }) => {
  const api = await files(page);
  const row = page.locator('[data-testid="register-missing-row"][data-item="kyc_directors"]');
  const outcomes = row.getByTestId("register-missing-outcome");
  for (const name of ["kyc-first-director.pdf", "kyc-second-director.pdf"]) {
    await row.getByTestId("register-missing-upload-input").setInputFiles([PDF(name)]);
    await expect(outcomes.filter({ hasText: name })).toHaveCount(1);
  }
  await expect(outcomes).toHaveCount(2);
  expect(api.called("POST", `/api/cases/${KESTREL}/files`)).toHaveLength(2);
});

test("files dropped on a missing row are uploaded from it", async ({ page }) => {
  const api = await files(page);
  const row = page.locator('[data-testid="register-missing-row"][data-item="valuation"]');
  const dataTransfer = await page.evaluateHandle(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(["%PDF-1.7"], "valuation-report.pdf", { type: "application/pdf" }));
    return dt;
  });
  await row.dispatchEvent("dragover", { dataTransfer });
  await expect(row).toContainText("Drop to upload for Valuation report");
  await row.dispatchEvent("drop", { dataTransfer });
  await expect(row.getByTestId("register-missing-outcome")).toContainText("valuation-report.pdf");
  expect(api.called("POST", `/api/cases/${KESTREL}/files`)).toHaveLength(1);
});

test("a role that cannot upload sees what is missing, without the upload", async ({ page }) => {
  await files(page, new MockApi(), MANAGER);
  const missing = page.getByTestId("register-missing");
  await expect(missing.getByTestId("register-missing-row")).toHaveCount(2);
  await expect(missing.getByTestId("register-missing-upload")).toHaveCount(0);
});

test("with no file received yet, what the appraisal needs is still listed", async ({ page }) => {
  const api = new MockApi();
  api.files.set(KESTREL, []);
  api.documents.set(KESTREL, []);
  await files(page, api);
  await expect(page.getByTestId("register-missing-row")).toHaveCount(2);
});

test("on a phone each missing row is a card and nothing scrolls sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await files(page);
  await expect(page.getByTestId("register-missing-row").first()).toBeVisible();
  const sideways = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(sideways).toBe(false);
});

test("the register's columns line up: figures sit right under their title, and no cell runs into the next", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await files(page);
  const layout = await page.getByTestId("file-tree").evaluate((tree) => {
    const head = tree.querySelector("[data-testid='register-head']")!.children;
    const right = (el: Element) => Math.round(el.getBoundingClientRect().right);
    // Where a title's words start, past any padding of its cell.
    const textLeft = (el: Element) => {
      const range = document.createRange();
      range.selectNodeContents(el);
      return Math.round(range.getBoundingClientRect().left);
    };
    const confidence = [...tree.querySelectorAll("[data-testid='document-confidence']")];
    const rows = [
      ...tree.querySelectorAll(
        "[data-testid='tree-document'] > div, [data-testid='tree-file'] > div",
      ),
    ];
    return {
      title: right(head[3]!),
      figures: confidence.map((c) => right(c)),
      gap: textLeft(head[4]!) - right(head[3]!),
      overflow: rows.flatMap((r) =>
        [...r.children]
          .filter((c) => (c as HTMLElement).scrollWidth > (c as HTMLElement).clientWidth + 1)
          .map((c) => c.textContent),
      ),
    };
  });
  expect(layout.figures.length).toBeGreaterThan(0);
  for (const r of layout.figures) expect(Math.abs(r - layout.title)).toBeLessThanOrEqual(1);
  expect(layout.gap).toBeGreaterThanOrEqual(24);
  expect(layout.overflow).toEqual([]);
});
