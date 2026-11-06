// The CAM as a sheet (F-23): a section at a time as a spreadsheet, its sections as tabs at the foot.
// A paragraph is changed in its cell and kept as the section in a person's words; a figure is
// changed in its cell and kept as an override with its reason. Each change is the engine's own
// record, so it is still there on another tab, in the draft's counts and in the downloads.
import { expect, test, type Page } from "@playwright/test";
import { KESTREL, RM } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

async function openSheet(page: Page, api = new MockApi(), user = api.user) {
  await signedIn(page, api, user);
  await page.goto(`/appraisals/${KESTREL}/outputs?view=cam`);
  await expect(page.getByTestId("cam-sheet")).toBeVisible();
  return api;
}

/** The sheet of the ask: the proposal at a glance, with its key facts. */
async function facilitySheet(page: Page) {
  await page.locator('[data-testid="cam-sheet-tab"][data-section="facility"]').click();
  await expect(page.getByTestId("cam-sheet")).toHaveAttribute("data-section", "facility");
}

/** The value cell of a key fact, found by its label in the row. */
function valueOf(page: Page, label: string) {
  return page
    .getByRole("row")
    .filter({ has: page.getByRole("gridcell", { name: label, exact: true }) })
    .locator('[data-editable="figure"]');
}

test("each section is a sheet: lettered columns, numbered rows, its sections as tabs", async ({
  page,
}) => {
  const api = await openSheet(page);
  const sheet = page.getByTestId("cam-sheet");
  await expect(sheet).toHaveAttribute("data-section", api.cam.sections[0]!.id);
  await expect(sheet.getByRole("columnheader").first()).toHaveText("A");
  await expect(sheet.getByRole("rowheader").first()).toHaveText("1");
  await expect(page.getByTestId("cam-sheet-brand")).toContainText("RBL Bank");
  // The key facts as Field | Value | Source.
  await facilitySheet(page);
  const head = sheet.getByRole("row").filter({ hasText: "Field" }).first();
  await expect(head.getByRole("gridcell")).toHaveText(["Field", "Value", "Source"]);
  await expect(valueOf(page, "Borrower")).toHaveText("Kestrel Polymers Pvt Ltd");
  // Eight tabs, the one shown raised.
  const tabs = page.getByTestId("cam-sheet-tab");
  await expect(tabs).toHaveCount(8);
  await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(tabs.first()).toHaveAttribute("aria-selected", "false");
  await expect(tabs.nth(6)).toHaveText(/^7\. /);
});

test("a tab opens its section's sheet, and the list on the left follows", async ({ page }) => {
  const api = await openSheet(page);
  const second = api.cam.sections[1]!;
  await page.getByTestId("cam-sheet-tab").nth(1).click();
  await expect(page.getByTestId("cam-sheet")).toHaveAttribute("data-section", second.id);
  await expect(page.getByTestId("cam-sheet-tab").nth(1)).toHaveAttribute("aria-selected", "true");
  await expect(
    page.locator(`[data-testid="cam-review-nav-item"][data-section="${second.id}"]`),
  ).toHaveAttribute("aria-current", "true");
});

test("the cell in hand shows its address and what it holds", async ({ page }) => {
  await openSheet(page);
  await facilitySheet(page);
  const cell = valueOf(page, "Amount requested");
  await cell.click();
  const ref = await cell.getAttribute("data-ref");
  expect(ref).toMatch(/^B\d+$/);
  await expect(page.getByTestId("cam-sheet-namebox")).toHaveText(ref!);
  await expect(page.getByTestId("cam-sheet-formula")).toHaveText("INR 50.00 lakh");
});

test("a figure changed in its cell is kept as an override, with the reason asked under it", async ({
  page,
}) => {
  const api = await openSheet(page);
  await facilitySheet(page);
  const section = "facility";
  const cell = valueOf(page, "Amount requested");
  await cell.dblclick();
  await page.getByTestId("cam-sheet-editor").fill("INR 45.00 lakh");
  await page.getByTestId("cam-sheet-editor").press("Enter");
  // Nothing is sent until the reason is given.
  const reason = page.getByTestId("cam-sheet-reason");
  await expect(reason).toBeVisible();
  expect(api.camCalls).toHaveLength(0);
  await page.getByTestId("cam-sheet-reason-input").fill("ok");
  await expect(page.getByTestId("cam-sheet-reason-save")).toBeDisabled();
  await page.getByTestId("cam-sheet-reason-input").fill("Revised ask on the sanction note");
  await page.getByTestId("cam-sheet-reason-input").press("Enter");
  await expect(reason).toHaveCount(0);
  expect(api.camCalls).toEqual([
    {
      kind: "override",
      section,
      body: {
        figure: "Amount requested",
        original: "INR 50.00 lakh",
        value: "INR 45.00 lakh",
        reason: "Revised ask on the sanction note",
      },
    },
  ]);
  // The cell shows the new value, marked, with the value drafted and the reason on hover.
  await expect(cell).toHaveText("INR 45.00 lakh");
  await expect(cell).toHaveAttribute("data-overridden", "true");
  await expect(cell).toHaveAttribute("title", /As drafted: INR 50\.00 lakh/);
  await expect(page.getByTestId("cam-state-overrides")).toHaveText("1");
  // Still there on the way back from another sheet.
  await page.getByTestId("cam-sheet-tab").nth(2).click();
  await facilitySheet(page);
  await expect(valueOf(page, "Amount requested")).toHaveText("INR 45.00 lakh");
});

test("leaving the reason, or pressing Escape while typing, changes nothing", async ({ page }) => {
  const api = await openSheet(page);
  await facilitySheet(page);
  const cell = valueOf(page, "Amount requested");
  await cell.dblclick();
  await page.getByTestId("cam-sheet-editor").fill("INR 1.00 cr");
  await page.getByTestId("cam-sheet-editor").press("Escape");
  await expect(page.getByTestId("cam-sheet-editor")).toHaveCount(0);
  await expect(cell).toHaveText("INR 50.00 lakh");

  await cell.dblclick();
  await page.getByTestId("cam-sheet-editor").fill("INR 1.00 cr");
  await page.getByTestId("cam-sheet-editor").press("Enter");
  await page.getByTestId("cam-sheet-reason-cancel").click();
  await expect(cell).toHaveText("INR 50.00 lakh");
  expect(api.camCalls).toHaveLength(0);
});

test("typing into a cell starts changing it with what was typed, as a spreadsheet does", async ({
  page,
}) => {
  await openSheet(page);
  await facilitySheet(page);
  const cell = valueOf(page, "Amount requested");
  await cell.click();
  await page.keyboard.type("I");
  await expect(page.getByTestId("cam-sheet-editor")).toHaveValue("I");
  await page.keyboard.press("Escape");
  // The arrows move the cell in hand.
  await cell.click();
  const ref = (await cell.getAttribute("data-ref"))!;
  await page.keyboard.press("ArrowDown");
  await expect(page.getByTestId("cam-sheet-namebox")).toHaveText(`B${Number(ref.slice(1)) + 1}`);
});

test("a paragraph changed in its cell is kept as the section in a person's words", async ({
  page,
}) => {
  const api = await openSheet(page);
  await page.getByTestId("cam-sheet-tab").nth(0).click();
  const section = api.cam.sections.find((s) =>
    (s.blocks ?? []).some((b) => b.kind === "paragraph"),
  )!;
  await page.locator(`[data-testid="cam-sheet-tab"][data-section="${section.id}"]`).click();
  const paragraphs = (section.blocks ?? [])
    .filter((b) => b.kind === "paragraph")
    .map((b) => b.paragraph!.text);
  const cell = page.locator('[data-editable="words"]').first();
  await cell.dblclick();
  await page.getByTestId("cam-sheet-editor").fill("In my own words.");
  await page.getByTestId("cam-sheet-editor").press("Enter");
  // The words replace the paragraph's; the pages it cited stay with it.
  await expect(page.getByTestId("cam-paragraph").first()).toContainText("In my own words.");
  expect(api.camCalls).toEqual([
    {
      kind: "words",
      section: section.id,
      body: { paragraphs: ["In my own words.", ...paragraphs.slice(1)], source: "person" },
    },
  ]);
  await expect(page.getByTestId("cam-section-badge")).toContainText("Edited by Ananya Krishnan");
});

test("a role that reads the memo cannot change a cell", async ({ page }) => {
  await openSheet(page, new MockApi(), RM);
  await facilitySheet(page);
  await expect(page.locator("[data-editable]")).toHaveCount(0);
  const cell = page
    .getByRole("row")
    .filter({ has: page.getByRole("gridcell", { name: "Amount requested", exact: true }) })
    .getByRole("gridcell")
    .nth(1);
  await cell.dblclick();
  await expect(page.getByTestId("cam-sheet-editor")).toHaveCount(0);
});

test("the memo downloads as Excel or PDF; the PD note keeps Word", async ({ page }) => {
  const api = await openSheet(page);
  await expect(page.getByTestId("cam-download-xlsx")).toHaveText("Download Excel");
  await expect(page.getByTestId("cam-download-docx")).toHaveCount(0);
  const [file] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("cam-download-xlsx").click(),
  ]);
  expect(file.suggestedFilename()).toBe(`CAM-draft-${KESTREL}.xlsx`);
  expect(api.downloads.at(-1)).toMatchObject({ output: "cam", format: "xlsx" });
});
