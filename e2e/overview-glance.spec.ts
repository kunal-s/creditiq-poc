// The Overview opens with the readiness glance: the verdict and the gate conditions, the score
// against the gate (the same figure as the case header), what blocks the case by name, the
// requirements counted by status (each count a filter for the checklist below), the requirements
// by section, and a rail with what to do next and what to ask the customer. The checklist follows
// in bands: what blocks the case, what does not, what waits for a person, what came in that no
// requirement asks for, and what is done.
import { expect, test, type Page } from "@playwright/test";
import type { CaseProgress, Readiness } from "@/api/types";
import { KESTREL, MANAGER, ORIEL, SAFFRON } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test.use({ viewport: { width: 1440, height: 900 } });

const scoreOf = async (page: Page, testId: string) =>
  /(\d+(?:\.\d)?)%/.exec((await page.getByTestId(testId).textContent()) ?? "")?.[1];

async function overview(page: Page, api = new MockApi(), caseId = KESTREL) {
  await signedIn(page, api);
  await page.goto(`/appraisals/${caseId}`);
  await expect(page.getByTestId("journey-verdict")).not.toHaveAttribute("data-state", "loading");
  return api;
}

function withProgress(api: MockApi, change: (p: CaseProgress) => CaseProgress) {
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/progress$`), () => ({
    json: change(api.progress(KESTREL)),
  }));
}

function withChecklist(api: MockApi, caseId: string, change: Partial<Readiness>) {
  api.checklists.set(caseId, { ...api.checklists.get(caseId)!, ...change });
}

/** How far the page itself (not the content pane) could scroll. */
const pageOverflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollHeight - innerHeight);

test("the verdict, the gate conditions and the score answer whether the case can go to credit review", async ({
  page,
}) => {
  await overview(page);
  const hero = page.getByTestId("journey-verdict");
  await expect(hero).toHaveAttribute("data-state", "blocked");
  await expect(hero.locator("> div").first()).toHaveClass(/bg-destructive/);
  await expect(hero.getByRole("heading", { level: 2 })).toHaveText("Not ready for credit review");

  const conditions = page.getByTestId("journey-conditions").getByRole("listitem");
  await expect(conditions).toHaveCount(2);
  await expect(conditions.nth(0)).toContainText("Review gate · 27 points to go");
  await expect(conditions.nth(0)).toHaveAttribute("data-met", "false");
  await expect(conditions.nth(1)).toContainText("Blocking items · 2 still open");

  await expect(page.getByTestId("journey-score")).toHaveText("58%");
  expect(await scoreOf(page, "journey-score")).toBe(await scoreOf(page, "header-readiness"));
  const meter = page.getByTestId("journey-meter");
  await expect(meter).toHaveAttribute("aria-valuenow", "58");
  await expect(meter).toHaveAttribute(
    "aria-valuetext",
    "Readiness score 58%, review gate 85%, 27 points to go",
  );
  await expect(meter).toContainText("Review gate 85%");

  // The whole card, the rail included, fits the first screen.
  const box = (await hero.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(900);
});

test("near the gate the score keeps a decimal, in the header and the hero alike", async ({
  page,
}) => {
  const api = new MockApi();
  withChecklist(api, KESTREL, { score_pct: 84.6 });
  await overview(page, api);
  await expect(page.getByTestId("journey-score")).toHaveText("84.6%");
  // The header prints the same figure, never the gate's.
  expect(await scoreOf(page, "header-readiness")).toBe("84.6");
  await expect(page.getByTestId("journey-conditions")).toContainText(
    "Review gate · 0.4 points to go",
  );

  // One point short is said in the singular.
  const one = new MockApi();
  withChecklist(one, KESTREL, { score_pct: 84 });
  await overview(page, one);
  await expect(page.getByTestId("journey-conditions")).toContainText("Review gate · 1 point to go");
  await expect(page.getByTestId("journey-meter")).toHaveAttribute(
    "aria-valuetext",
    "Readiness score 84%, review gate 85%, 1 point to go",
  );
});

test("what blocks the case is named, and each name opens its row", async ({ page }) => {
  await overview(page);
  const chips = page.getByTestId("journey-blocker");
  await expect(chips).toHaveCount(2);
  await expect(chips.nth(0)).toHaveText("KYC of directors · Missing");
  await expect(chips.nth(1)).toHaveText("Board resolution · Insufficient");

  await chips.nth(1).click();
  const row = page.locator("#req-board_resolution");
  await expect(row).toBeInViewport();
  await expect(row).toHaveClass(/bg-accent/);
  await expect
    .poll(() => page.evaluate(() => document.activeElement?.id))
    .toBe("req-board_resolution-name");
  // The flash fades after a moment.
  await expect(row).not.toHaveClass(/bg-accent/, { timeout: 3000 });
  // The jump scrolls the content, never the page under the top bar.
  expect(await page.evaluate(() => document.documentElement.scrollTop)).toBe(0);

  // From the keyboard the name it lands on shows its focus ring.
  await chips.nth(0).focus();
  await page.keyboard.press("Enter");
  await expect
    .poll(() => page.evaluate(() => document.activeElement?.id))
    .toBe("req-kyc_directors-name");
  expect(
    await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle),
  ).not.toBe("none");
});

test("the page itself never scrolls: only the content beside the menu does", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await overview(page);
  expect(await pageOverflow(page)).toBeLessThanOrEqual(0);
  await page.getByTestId("journey-done-toggle").click();
  expect(await pageOverflow(page)).toBeLessThanOrEqual(0);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("journey-done-toggle")).toBeVisible();
  expect(await pageOverflow(page)).toBeLessThanOrEqual(0);
});

test("the status tiles count the requirements and filter the checklist", async ({ page }) => {
  await overview(page);
  await expect(page.getByTestId("journey-filter-blocking")).toContainText(
    /Blocking gaps\s*2\s*cannot reach credit review yet/,
  );
  await expect(page.getByTestId("journey-filter-todo")).toContainText(
    /Outstanding\s*6\s*Missing 2 · Insufficient 4/,
  );
  await expect(page.getByTestId("journey-filter-in_review")).toContainText(
    /In review\s*1\s*waiting for a person/,
  );
  await expect(page.getByTestId("journey-filter-satisfied")).toContainText(/Satisfied\s*2\s*of 9/);

  const items = page.getByTestId("journey-item");
  const todo = page.getByTestId("journey-filter-todo");
  await todo.click();
  await expect(todo).toHaveAttribute("aria-pressed", "true");
  await expect(items).toHaveCount(6);
  for (const status of await items.evaluateAll((els) => els.map((e) => e.dataset["status"])))
    expect(["missing", "insufficient"]).toContain(status);
  await expect(page.getByTestId("journey-showing")).toContainText("Showing: Outstanding");
  await expect(page.getByTestId("journey-showing-live")).toHaveText(
    "Showing: Outstanding, 6 in the list",
  );
  await expect(page.getByTestId("journey-filter-all")).toHaveText("Show all (9)");
  await expect(page.getByTestId("journey-filter-all")).not.toHaveAttribute("aria-pressed");
  await expect(page.getByTestId("journey-unmatched")).toHaveCount(0);

  // Pressed again, the tile clears its filter.
  await todo.click();
  await expect(todo).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByTestId("journey-showing")).toHaveCount(0);
  await expect(page.getByTestId("journey-unmatched")).toBeVisible();

  // So does the cross on the indicator.
  await todo.click();
  await page.getByTestId("journey-filter-clear").click();
  await expect(todo).toHaveAttribute("aria-pressed", "false");
  await expect(items.filter({ hasText: "Bank statements" })).toHaveCount(1);

  // The satisfied filter opens what is done.
  await page.getByTestId("journey-filter-satisfied").click();
  await expect(page.getByTestId("journey-done-toggle")).toHaveAttribute("aria-expanded", "true");
  await expect(items).toHaveCount(2);
  await page.getByTestId("journey-filter-all").click();
  await expect(page.getByTestId("journey-filter-satisfied")).toHaveAttribute(
    "aria-pressed",
    "false",
  );
});

test("the section map draws every requirement, done first, with its glyph", async ({ page }) => {
  await overview(page);
  const cells = page.getByTestId("journey-cell");
  await expect(cells).toHaveCount(9);
  for (const svgs of await cells.evaluateAll((els) =>
    els.map((e) => e.querySelectorAll("svg").length),
  ))
    expect(svgs).toBe(1);
  const kyc = page
    .getByRole("listitem")
    .filter({ hasText: "Constitution and KYC: 1 of 3 satisfied" });
  expect(
    await kyc.getByTestId("journey-cell").evaluateAll((els) => els.map((e) => e.dataset["status"])),
  ).toEqual(["satisfied", "insufficient", "missing"]);
  await expect(kyc).toContainText("1 of 3 satisfied");
});

test("the checklist is banded by what each requirement does to the case", async ({ page }) => {
  await overview(page);
  const list = page.getByTestId("document-checklist");
  const order = await list
    .locator("[data-testid^='journey-band-'], [data-testid='journey-unmatched']")
    .evaluateAll((els) => els.map((e) => e.getAttribute("data-testid")));
  expect(order).toEqual([
    "journey-band-blocking",
    "journey-band-nonblocking",
    "journey-band-inreview",
    "journey-unmatched",
    "journey-band-done",
  ]);
  const names = (band: string) =>
    page
      .getByTestId(`journey-band-${band}`)
      .getByTestId("journey-item")
      .evaluateAll((els) => els.map((e) => e.querySelector("[id$='-name']")?.textContent));
  expect(await names("blocking")).toEqual(["KYC of directors", "Board resolution"]);
  for (const cls of await page
    .getByTestId("journey-band-blocking")
    .getByTestId("journey-item")
    .evaluateAll((els) => els.map((e) => e.className)))
    expect(cls).toContain("border-l-destructive");
  expect(await names("nonblocking")).toEqual([
    "Provisional financial statements FY26",
    "GST returns (12 months)",
    "Stock statement",
    "Valuation report",
  ]);
  expect(await names("inreview")).toEqual(["Bank statements (12 months)"]);
  await expect(page.getByTestId("journey-band-inreview")).toContainText("Waiting for a person.");
  await expect(page.getByTestId("journey-unmatched").getByTestId("journey-doc")).toHaveCount(2);

  const done = page.getByTestId("journey-done-toggle");
  await expect(done).toHaveAttribute("aria-expanded", "false");
  await expect(done).toContainText(
    "Certificate of incorporation · Audited financial statements FY24, FY25",
  );
  // No row repeats "Blocking": the band and its rule say it.
  await expect(list.getByTestId("journey-item").getByText("Blocking", { exact: true })).toHaveCount(
    0,
  );
  await done.click();
  await expect(page.getByTestId("journey-band-done").getByTestId("journey-item")).toHaveCount(2);
});

test("the rail says what to do next and what to ask the customer, ready to copy", async ({
  page,
  context,
}) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  await overview(page);
  const next = page.getByTestId("next-action");
  await expect(next).toContainText(
    "Quality and classification · 4 of 5 documents classified · 1 need attention",
  );
  await expect(next.getByRole("link", { name: "Open" })).toBeVisible();

  const ask = page.getByTestId("journey-ask");
  await expect(ask).toContainText("Ask the customer · 6 open · 1 resolved");
  await expect(page.getByTestId("journey-ask-counts").getByRole("listitem")).toHaveText([
    "Documents needed 3",
    "Documents to redo 2",
    "Clarifications 1",
  ]);

  const copyList = page.getByTestId("journey-copy-list");
  const width = (await copyList.boundingBox())!.width;
  await copyList.click();
  await expect(copyList.getByText("Copied")).toBeVisible();
  await expect(copyList).toHaveAccessibleName("Copied");
  // Saying so does not move anything.
  expect((await copyList.boundingBox())!.width).toBe(width);
  const text = await page.evaluate(() => navigator.clipboard.readText());
  expect(text.startsWith("Documents needed\n1. KYC of Leela Varghese")).toBe(true);
  expect(text).toContain("Clarifications\n6. Bank statements show a monthly EMI");
  expect(text).not.toContain("ITR acknowledgement");

  await page.getByTestId("journey-copy-email").click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toContain(
    "Kestrel Polymers Pvt Ltd",
  );

  const toggle = page.getByTestId("journey-requests-toggle");
  await expect(toggle).toHaveAttribute("aria-expanded", "false");
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-expanded", "true");
  const requests = page.getByTestId("journey-requests").getByRole("listitem");
  await expect(requests).toHaveCount(6);
  await expect(requests.nth(5)).toContainText(/^6\./);
  await expect(requests.nth(5).getByRole("button")).toHaveAccessibleName("Copy request 6");
});

test("a case ready for credit reads as finished throughout", async ({ page }) => {
  await overview(page, new MockApi(), SAFFRON);
  const hero = page.getByTestId("journey-verdict");
  await expect(hero).toHaveAttribute("data-state", "ready");
  await expect(hero.getByRole("heading", { level: 2 })).toHaveText("Ready for credit");
  await expect(page.getByTestId("journey-meter-fill")).toHaveAttribute("style", /width: 100%/);
  await expect(page.getByTestId("journey-meter-fill")).toHaveClass(/bg-positive/);
  const cells = page.getByTestId("journey-cell");
  await expect(cells).toHaveCount(9);
  for (const status of await cells.evaluateAll((els) => els.map((e) => e.dataset["status"])))
    expect(status).toBe("satisfied");
  await expect(page.getByTestId("journey-filter-blocking")).toContainText(/0\s*nothing blocking/);
  await expect(page.getByTestId("journey-filter-todo")).toContainText(/0\s*nothing outstanding/);
  await expect(page.getByTestId("journey-blocker")).toHaveCount(0);
  await expect(page.getByTestId("journey-band-blocking")).toHaveText(
    "No blocking gap remains on this case.",
  );
  await expect(page.getByTestId("journey-done-toggle")).toHaveAttribute("aria-expanded", "true");
  await expect(page.getByTestId("journey-ask")).toContainText(
    "Nothing is needed from the customer right now.",
  );
  await expect(page.getByTestId("journey-copy-list")).toHaveCount(0);
});

test("a provisional checklist is never ready for credit, and says so", async ({ page }) => {
  await overview(page, new MockApi(), ORIEL);
  const hero = page.getByTestId("journey-verdict");
  await expect(hero.getByRole("heading", { level: 2 })).toContainText("provisional");
  await expect(hero.getByTestId("journey-provisional")).toBeVisible();
  await expect(page.getByTestId("journey-meter-fill")).toHaveClass(/pattern-stripes/);
  await expect(hero).not.toContainText("Ready for credit");
  // Nothing satisfied yet is not shown as a success.
  await expect(
    page.getByTestId("journey-filter-satisfied").locator(".tabular").first(),
  ).toHaveClass(/text-muted-foreground/);

  // Even when the engine would call it ready.
  const api = new MockApi();
  withChecklist(api, SAFFRON, { provisional: true });
  await overview(page, api, SAFFRON);
  await expect(hero).toHaveAttribute("data-state", "gateMet");
  await expect(hero.getByRole("heading", { level: 2 })).toContainText("Review gate met");
  await expect(hero).not.toContainText("Ready for credit");
});

test("with the assessment gate known, the files condition joins the verdict", async ({ page }) => {
  const gate = {
    open: false,
    can_open: false,
    open_exceptions: 1,
    blocking_open: 2,
    score_pct: 58,
    gate_pct: 85,
  };
  const api = new MockApi();
  withProgress(api, (p) => ({ ...p, gate }));
  await overview(page, api);
  const third = page.getByTestId("journey-conditions").getByRole("listitem").nth(2);
  await expect(third).toContainText("1 file(s) could not be read");
  await expect(third.getByRole("link")).toHaveAttribute("href", `/appraisals/${KESTREL}/documents`);

  const clear = new MockApi();
  withProgress(clear, (p) => ({ ...p, gate: { ...gate, open_exceptions: 0, can_open: true } }));
  await overview(page, clear);
  await expect(third).toContainText("Every file was read");
  await expect(third).toHaveAttribute("data-met", "true");
  // Ready to create the case: the next step says so.
  await expect(page.getByTestId("next-action")).toContainText("Ready to create the case");
  await expect(page.getByTestId("next-action").getByRole("link")).toHaveText("Go to completeness");

  const opened = new MockApi();
  withProgress(opened, (p) => ({ ...p, gate: { ...gate, open_exceptions: 0, open: true } }));
  await overview(page, opened);
  await expect(
    page.getByTestId("journey-verdict").getByRole("heading", { level: 2 }),
  ).toContainText("Case created");
});

test("a file sent from a blocking row keeps the row in place while the score moves", async ({
  page,
}) => {
  const api = new MockApi();
  let read = false;
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/progress$`), () => {
    const progress = api.progress(KESTREL);
    if (!read) progress.stages[0]!.status = "in_progress";
    return { json: progress };
  });
  await overview(page, api);
  const live = page.getByTestId("journey-live");
  await expect(live).toHaveText("");
  const row = page.locator('[data-testid="journey-item"][data-item="kyc_directors"]');
  // The outcome's live region is in place before the first file is sent.
  await expect(row.getByTestId("journey-received")).toBeAttached();
  await expect(row.getByTestId("journey-received")).toBeEmpty();
  await row.getByTestId("journey-upload").focus();
  await row
    .getByTestId("journey-upload-input")
    .setInputFiles([
      { name: "kyc-leela.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") },
    ]);
  await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "reading");
  await expect(row.getByTestId("stage-track")).toBeVisible();

  // The engine reads it: the requirement is now satisfied and the score moves.
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
  read = true;
  await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "counted", {
    timeout: 15_000,
  });
  await expect(row).toHaveAttribute("data-status", "satisfied");
  await expect(page.getByTestId("journey-band-blocking").locator("#req-kyc_directors")).toHaveCount(
    1,
  );
  await expect(row).toContainText("Satisfied");
  await expect(page.getByTestId("journey-score")).toHaveText("70%");
  await expect(page.getByTestId("journey-meter-fill")).toHaveAttribute("style", /width: 70%/);
  await expect(live).toHaveText("Readiness score 70%. Not ready for credit review");
  // The Upload button went with the open requirement; the focus is on the row's name.
  await expect
    .poll(() => page.evaluate(() => document.activeElement?.id))
    .toBe("req-kyc_directors-name");

  // Every count goes by where the requirements stand now: the band counts one, the satisfied
  // row has lost its red rule, and each tile shows as many rows as it says.
  const band = page.getByTestId("journey-band-blocking");
  await expect(band.locator("#journey-band-blocking-title + span")).toHaveText("1");
  await expect(row).not.toHaveClass(/border-l-destructive/);
  await expect(page.locator("#req-board_resolution")).toHaveClass(/border-l-destructive/);
  const items = page.getByTestId("journey-item");
  await page.getByTestId("journey-filter-blocking").click();
  await expect(page.getByTestId("journey-filter-blocking")).toContainText(/Blocking gaps\s*1/);
  await expect(items).toHaveCount(1);
  await page.getByTestId("journey-filter-todo").click();
  await expect(page.getByTestId("journey-filter-todo")).toContainText(/Outstanding\s*5/);
  await expect(items).toHaveCount(5);
  // Back in the full list the row is where the file was sent, its outcome with it.
  await page.getByTestId("journey-filter-clear").click();
  await expect(band.locator("#req-kyc_directors")).toHaveCount(1);
  await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "counted");
  // The done band counts it too, as the Satisfied tile does, and says where its row is.
  await expect(page.getByTestId("journey-filter-satisfied")).toContainText(/Satisfied\s*3/);
  await expect(page.getByTestId("journey-done-count")).toHaveText("3");
  await expect(page.getByTestId("journey-done-toggle")).toContainText("KYC of directors");
  await page.getByTestId("journey-done-toggle").click();
  await expect(page.getByTestId("journey-band-done").getByTestId("journey-item")).toHaveCount(2);
  await expect(page.getByTestId("journey-done-above")).toHaveText(
    "Shown above, where a file was sent from it: KYC of directors",
  );
});

test("once nothing blocks, the band says so above the rows kept in it", async ({ page }) => {
  const api = new MockApi();
  await overview(page, api);
  const r = api.checklists.get(KESTREL)!;
  for (const id of ["kyc_directors", "board_resolution"]) {
    const row = page.locator(`[data-testid="journey-item"][data-item="${id}"]`);
    await row
      .getByTestId("journey-upload-input")
      .setInputFiles([
        { name: `${id}.pdf`, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") },
      ]);
    await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "reading");
  }
  const template = api.documents.get(KESTREL)![0]!;
  const added = ["kyc_directors", "board_resolution"].map((id) => ({
    id,
    file: api.files.get(KESTREL)!.find((f) => f.original_name === `${id}.pdf`)!,
  }));
  api.documents.set(KESTREL, [
    ...api.documents.get(KESTREL)!,
    ...added.map(({ id, file }) => ({ ...template, id: `doc-${id}`, file_id: file.id })),
  ]);
  api.checklists.set(KESTREL, {
    ...r,
    score_pct: 80,
    blocking_open: 0,
    items: r.items.map((i) =>
      i.item_id === "kyc_directors" || i.item_id === "board_resolution"
        ? { ...i, status: "satisfied", deficiency: null, document_ids: [`doc-${i.item_id}`] }
        : i,
    ),
  });
  const band = page.getByTestId("journey-band-blocking");
  await expect(band).toHaveAttribute("data-clear", "true", { timeout: 15_000 });
  await expect(band).toContainText("No blocking gap remains on this case.");
  await expect(band).not.toContainText("stops the case");
  await expect(band.getByTestId("journey-item")).toHaveCount(2);
  await expect(page.getByTestId("journey-filter-blocking")).toContainText(/0\s*nothing blocking/);
});

test("when the checklist cannot be read, or there is none, the rail still says what is next", async ({
  page,
}) => {
  const failing = new MockApi();
  failing.on("GET", new RegExp(`^/api/cases/${KESTREL}/checklist$`), () => ({
    status: 500,
    json: { detail: "unavailable" },
  }));
  await signedIn(page, failing);
  await page.goto(`/appraisals/${KESTREL}`);
  const hero = page.getByTestId("journey-verdict");
  await expect(hero).toHaveAttribute("data-state", "error");
  await expect(hero).toContainText("Readiness not available");
  await expect(hero.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(page.getByTestId("next-action")).toBeVisible();
  await expect(page.getByTestId("journey-meter")).toHaveCount(0);
  await expect(page.getByTestId("document-checklist")).toHaveCount(0);

  // A later read that fails keeps the last one on screen, with what was sent from its rows.
  const flaky = new MockApi();
  let fail = false;
  flaky.on("GET", new RegExp(`^/api/cases/${KESTREL}/checklist$`), () =>
    fail ? { status: 503, json: { detail: "busy" } } : { json: flaky.checklists.get(KESTREL) },
  );
  await overview(page, flaky);
  const row = page.locator('[data-testid="journey-item"][data-item="kyc_directors"]');
  await row
    .getByTestId("journey-upload-input")
    .setInputFiles([{ name: "x.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF") }]);
  await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "reading");
  fail = true;
  const file = flaky.files.get(KESTREL)!.find((f) => f.original_name === "x.pdf")!;
  const template = flaky.documents.get(KESTREL)![0]!;
  flaky.documents.set(KESTREL, [
    ...flaky.documents.get(KESTREL)!,
    { ...template, id: "doc-x", file_id: file.id },
  ]);
  await expect(page.getByTestId("journey-stale").first()).toBeVisible({ timeout: 15_000 });
  await expect(hero).toHaveAttribute("data-state", "blocked");
  await expect(page.getByTestId("document-checklist")).toBeVisible();
  await expect(row.getByTestId("journey-outcome")).toHaveCount(1);
  fail = false;
  await page.getByTestId("journey-stale").getByRole("button", { name: "Try again" }).click();
  await expect(page.getByTestId("journey-stale")).toHaveCount(0);
  await expect(row.getByTestId("journey-outcome")).toHaveCount(1);

  const empty = new MockApi();
  withChecklist(empty, KESTREL, { items: [] });
  await overview(page, empty);
  await expect(hero).toHaveAttribute("data-state", "empty");
  await expect(hero).toContainText("No checklist yet");
  await expect(page.getByTestId("journey-filter-todo")).toHaveCount(0);
  await expect(page.getByTestId("journey-ask")).toBeVisible();
});

test("under reduced motion the meter shows the score at once", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await overview(page);
  const width = await page
    .getByTestId("journey-meter-fill")
    .evaluate((el) => (el as HTMLElement).style.width);
  expect(width).toBe("58%");
});

test("in forced colours the meter keeps its track, its fill and the gate mark", async ({
  page,
}) => {
  await page.emulateMedia({ forcedColors: "active" });
  await overview(page);
  const fill = page.getByTestId("journey-meter-fill");
  const drawn = await fill.evaluate((el) => {
    const track = el.parentElement!;
    const mark = el.nextElementSibling!;
    const painted = (e: Element) => getComputedStyle(e).backgroundColor !== "rgba(0, 0, 0, 0)";
    return {
      track: getComputedStyle(track).borderTopWidth,
      fill: painted(el),
      mark: painted(mark),
    };
  });
  expect(drawn).toEqual({ track: "1px", fill: true, mark: true });
});

for (const [width, height] of [
  [1440, 900],
  [1366, 768],
] as const) {
  test(`at ${width} px the hero keeps its height while the checklist is read`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height });
    await signedIn(page, new MockApi());
    let release!: () => void;
    const held = new Promise<void>((resolve) => (release = resolve));
    await page.route(new RegExp(`/api/cases/${KESTREL}/checklist$`), async (route) => {
      await held;
      await route.fallback();
    });
    await page.goto(`/appraisals/${KESTREL}`);
    const hero = page.getByTestId("journey-verdict");
    await expect(hero).toHaveAttribute("data-state", "loading");
    await expect(page.getByTestId("journey-ask-counts")).toBeVisible();
    const loading = (await hero.boundingBox())!.height;
    release();
    await expect(hero).toHaveAttribute("data-state", "blocked");
    await expect(page.getByTestId("journey-blocker").first()).toBeVisible();
    const loaded = (await hero.boundingBox())!.height;
    expect(Math.abs(loaded - loading)).toBeLessThanOrEqual(8);
  });
}

test("with the assistant open the tiles go four across and stay on the first screen", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await overview(page);
  await page.getByTestId("assistant-launcher").click();
  const tiles = page.locator(
    "[data-testid^='journey-filter-']:not([data-testid='journey-filter-all'])",
  );
  await expect(tiles).toHaveCount(4);
  await expect
    .poll(
      async () =>
        new Set(
          await tiles.evaluateAll((els) =>
            els.map((e) => Math.round(e.getBoundingClientRect().top)),
          ),
        ).size,
    )
    .toBe(1);
  const tile = (await tiles.first().boundingBox())!;
  expect(tile.y + tile.height).toBeLessThanOrEqual(768);
  // One column: the verdict and the score share a row, and the section map waits for room.
  const hero = page.getByTestId("journey-verdict");
  expect((await hero.boundingBox())!.height).toBeLessThanOrEqual(470);
  await expect(page.getByTestId("journey-cell").first()).toBeHidden();

  // On a 1440 x 900 laptop the whole card, what to do next and what to ask included, fits.
  await page.setViewportSize({ width: 1440, height: 900 });
  await expect
    .poll(async () => {
      const box = (await hero.boundingBox())!;
      return box.y + box.height;
    })
    .toBeLessThanOrEqual(900);
  // The counts of what to ask keep their room; the copy buttons never sit over them.
  const counts = (await page.getByTestId("journey-ask-counts").boundingBox())!;
  for (const id of ["journey-copy-list", "journey-copy-email", "journey-requests-toggle"]) {
    const box = (await page.getByTestId(id).boundingBox())!;
    const apart =
      counts.x + counts.width <= box.x ||
      box.x + box.width <= counts.x ||
      counts.y + counts.height <= box.y ||
      box.y + box.height <= counts.y;
    expect(apart, id).toBe(true);
  }
});

test("a user who cannot upload is not told to upload", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}`);
  const list = page.getByTestId("document-checklist");
  await expect(list).toContainText("Documents this appraisal needs: 9.");
  await expect(list).not.toContainText("Upload on a row");
  await expect(list.getByTestId("journey-upload")).toHaveCount(0);
});

for (const width of [375, 320]) {
  test(`at ${width} px the glance fits the phone`, async ({ page }) => {
    await page.setViewportSize({ width, height: 812 });
    // A file on a satisfied requirement wants a person: the collapsed done band says so.
    const api = new MockApi();
    api.files.set(
      KESTREL,
      api.files.get(KESTREL)!.map((f) =>
        f.id === "f-bs"
          ? {
              ...f,
              integrity_status: {
                state: "review_recommended",
                passed: 9,
                not_applicable: 0,
              } as never,
            }
          : f,
      ),
    );
    await overview(page, api);
    await expect(page.getByTestId("journey-done-toggle")).toContainText(
      "1 on a file that needs a person",
    );
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth - innerWidth),
    ).toBeLessThanOrEqual(0);
    // Two by two.
    const tops = await page
      .locator("[data-testid^='journey-filter-']:not([data-testid='journey-filter-all'])")
      .evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().top)));
    expect(tops[0]).toBe(tops[1]);
    expect(tops[2]).toBe(tops[3]);
    expect(tops[2]).toBeGreaterThan(tops[0]!);
    // By section waits for a wider screen; the rows say their section.
    await expect(page.getByTestId("journey-cell").first()).toBeHidden();
    // A tile's note is read in full, on a second line where the tile is narrow (no pointer to
    // hover for the rest).
    const note = page
      .getByTestId("journey-filter-blocking")
      .getByText("cannot reach credit review yet");
    expect(
      await note.evaluate(
        (e) => e.scrollWidth <= e.clientWidth + 0.5 && e.scrollHeight <= e.clientHeight + 0.5,
      ),
    ).toBe(true);
    // Kept short: at most two lines a tile note, the next step's link on its label's line.
    expect((await page.getByTestId("journey-verdict").boundingBox())!.height).toBeLessThanOrEqual(
      width === 375 ? 755 : 825,
    );
    // From the keyboard a tile filters without taking the screen away from it.
    const todo = page.getByTestId("journey-filter-todo");
    await todo.focus();
    await page.keyboard.press("Enter");
    await expect(todo).toHaveAttribute("aria-pressed", "true");
    await expect(todo).toBeInViewport();
    await expect(todo).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(todo).toHaveAttribute("aria-pressed", "false");
    const droppable = page.locator(
      '[data-testid="journey-item"]:is([data-status="missing"], [data-status="insufficient"])',
    );
    const n = await droppable.count();
    expect(n).toBe(6);
    for (let i = 0; i < n; i++) {
      const row = droppable.nth(i);
      const name = await row.locator("[id$='-name']").textContent();
      await expect(row.getByTestId("journey-upload")).toHaveCount(1);
      await expect(row.getByTestId("journey-upload-input")).toHaveCount(1);
      const upload = row.getByTestId("journey-upload");
      await expect(upload).toHaveText("Upload");
      await expect(upload).toHaveAttribute("aria-label", `Upload for ${name}`);
      expect((await upload.boundingBox())!.height).toBeGreaterThanOrEqual(40);
    }
  });
}
