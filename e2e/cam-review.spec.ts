// The CAM draft and review (FRD F-23): the memo's eight sections one at a time, the draft's state,
// and in each section Edit in my words, Regenerate with copilot, Override a figure and Request more
// data. The engine keeps every change with who and when; the screen sends what a person did.
import { expect, test, type Page } from "@playwright/test";
import { CAM, KESTREL } from "./fixtures/data";
import { MockApi, scrollsSideways, signedIn } from "./support/api";

async function openReview(page: Page, api = new MockApi()) {
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/outputs?view=cam`);
  await expect(page.getByTestId("cam-review")).toBeVisible();
  return api;
}

const nav = (page: Page) => page.getByTestId("cam-review-nav-item");
const section = (page: Page) => page.getByTestId("cam-review-section");
const open = (page: Page, id: string) =>
  page.locator(`[data-testid="cam-review-nav-item"][data-section="${id}"]`).click();

test("the memo is reviewed a section at a time: eight sections, the draft's state, the blocking banner", async ({
  page,
}) => {
  await openReview(page);
  await expect(nav(page)).toHaveText([
    "1Borrower and Group Profile",
    "2Facility Requested and Purpose",
    "3Banking Conduct",
    "4Financial Analysis and Ratios",
    "5GST and Bureau Findings",
    "6Cross-Verification Results",
    "7Risk Assessment and Rating",
    "8Recommendation",
  ]);
  // The first section is shown, as the engine drafted it.
  await expect(section(page)).toHaveAttribute("data-section", "profile");
  await expect(section(page).getByTestId("cam-section-kicker")).toHaveText(
    "Section 1 of 8 · Credit Approval Memo",
  );
  await expect(section(page).getByTestId("cam-section-title")).toHaveText(
    "Borrower and Group Profile",
  );
  await expect(section(page).getByTestId("cam-section-purpose")).toContainText(
    "promoters and management",
  );
  await expect(section(page).getByTestId("cam-section-badge")).toHaveText("Machine-drafted");
  await expect(section(page).getByTestId("cam-subheading")).toHaveText([
    "Borrower profile",
    "Promoters and management",
  ]);
  // The draft's state: pages cited, nothing changed yet, and no rating model to give a rating.
  await expect(page.getByTestId("cam-state-edited")).toHaveText("0 of 8");
  await expect(page.getByTestId("cam-state-overrides")).toHaveText("0");
  await expect(page.getByTestId("cam-state-rating")).toHaveText("Not rated");
  expect(Number(await page.getByTestId("cam-state-citations").textContent())).toBeGreaterThan(0);
  // A blocking discrepancy is open: drafting goes on, submission waits; the banner leads to it.
  const banner = page.getByTestId("cam-review-banner");
  await expect(banner).toContainText("submission stays closed until it is dealt with");
  await banner.getByRole("link").click();
  await expect(page).toHaveURL(/\/cross-verification\?finding=XV-/);
});

test("the risk assessment says it is not rated, and the recommendation is left for credit", async ({
  page,
}) => {
  await openReview(page);
  await open(page, "summary");
  await expect(section(page).getByTestId("cam-section-title")).toHaveText(
    "Risk Assessment and Rating",
  );
  await expect(section(page).getByTestId("cam-rating-note")).toHaveText(
    "Not rated: RBL's rating model is not configured.",
  );
  await expect(section(page).getByTestId("cam-summary")).toBeVisible();
  await open(page, "recommendation");
  await expect(section(page).getByTestId("cam-recommendation-prompt")).toHaveCount(4);
});

test("an override is recorded with the value drafted, your value and the reason", async ({
  page,
}) => {
  const api = await openReview(page);
  await open(page, "facility");
  await section(page).getByTestId("cam-action-override").click();
  const panel = page.getByTestId("cam-override-panel");
  const save = panel.getByTestId("cam-override-save");
  await expect(save).toBeDisabled();
  await panel.getByTestId("cam-override-figure").fill("Assessed drawing power");
  await panel.getByTestId("cam-override-original").fill("INR 1.50 cr");
  await panel.getByTestId("cam-override-value").fill("INR 1.25 cr");
  await panel.getByTestId("cam-override-reason").fill("Sized on independently evidenced turnover");
  await save.click();
  await expect(panel).toHaveCount(0);
  expect(api.camCalls.at(-1)).toEqual({
    kind: "override",
    section: "facility",
    body: {
      figure: "Assessed drawing power",
      original: "INR 1.50 cr",
      value: "INR 1.25 cr",
      reason: "Sized on independently evidenced turnover",
    },
  });
  await expect(page.getByTestId("cam-state-overrides")).toHaveText("1");
});

test("a section in my words is saved with my name, and the draft can be restored", async ({
  page,
}) => {
  const api = await openReview(page);
  await open(page, "analysis");
  await section(page).getByTestId("cam-action-edit").click();
  const text = page.getByTestId("cam-edit-text");
  const drafted = await text.inputValue();
  expect(drafted.length).toBeGreaterThan(0);
  await text.fill("Revenue grew, and the margin held.\n\nThe ratios are within the norms.");
  await page.getByTestId("cam-edit-save").click();
  expect(api.camCalls.at(-1)).toEqual({
    kind: "words",
    section: "analysis",
    body: {
      paragraphs: ["Revenue grew, and the margin held.", "The ratios are within the norms."],
      source: "person",
    },
  });
  await expect(section(page).getByTestId("cam-section-badge")).toHaveText(
    "Edited by Ananya Krishnan",
  );
  // My words, and the citations of the paragraph in their place.
  const first = section(page).getByTestId("cam-paragraph").first();
  await expect(first).toContainText("Revenue grew, and the margin held.");
  await expect(first.getByTestId("citation").first()).toBeVisible();
  await expect(page.getByTestId("cam-state-edited")).toHaveText("1 of 8");
  await expect(section(page).getByTestId("cam-action-restore")).toBeVisible();
});

test("more data asked for from a section goes on the query list", async ({ page }) => {
  const api = await openReview(page);
  await open(page, "conduct");
  await section(page).getByTestId("cam-action-request").click();
  await page.getByTestId("cam-request-text").fill("Please provide the debtors' ageing.");
  await page.getByTestId("cam-request-save").click();
  expect(api.camCalls.at(-1)).toMatchObject({
    kind: "request",
    section: "conduct",
    body: { text: "Please provide the debtors' ageing." },
  });
  await expect(section(page).getByTestId("cam-section-requests")).toContainText(
    "Requested: Please provide the debtors' ageing.",
  );
  await expect(page.getByTestId("cam-state-requests")).toHaveText("1");
});

test("the copilot redrafts only when configured, and nothing is kept until a person keeps it", async ({
  page,
}) => {
  // Without its key, the button says why it is off.
  await openReview(page);
  await expect(section(page).getByTestId("cam-action-regenerate")).toBeDisabled();
  await expect(section(page).getByTestId("cam-action-regenerate")).toHaveAttribute(
    "title",
    "The copilot is not configured: its key is not set.",
  );

  const api = new MockApi();
  api.cam = { ...structuredClone(CAM), copilot: true };
  await openReview(page, api);
  await open(page, "analysis");
  await section(page).getByTestId("cam-action-regenerate").click();
  await page.getByTestId("cam-regenerate-instruction").fill("Shorter.");
  await page.getByTestId("cam-regenerate-run").click();
  const preview = page.getByTestId("cam-regenerate-preview");
  await expect(preview).toContainText(
    "Redrafted by gpt-5.4-nano. Nothing is kept until you keep it.",
  );
  await expect(preview).toContainText("Redrafted: ");
  // Nothing kept yet.
  await expect(section(page).getByTestId("cam-section-badge")).toHaveText("Machine-drafted");
  await page.getByTestId("cam-regenerate-keep").click();
  expect(api.camCalls.at(-1)).toMatchObject({
    kind: "words",
    section: "analysis",
    body: { source: "copilot", model: "gpt-5.4-nano" },
  });
  await expect(section(page).getByTestId("cam-section-badge")).toHaveText(
    "Copilot redraft, kept by Ananya Krishnan",
  );
});

test("the whole memo reads top to bottom, and the choice is kept for the session", async ({
  page,
}) => {
  await openReview(page);
  await page.getByTestId("cam-mode-memo").click();
  await expect(page.getByTestId("cam")).toBeVisible();
  await expect(page.getByTestId("cam-review")).toHaveCount(0);
  await page.reload();
  await expect(page.getByTestId("cam")).toBeVisible();
  await page.getByTestId("cam-mode-sections").click();
  await expect(page.getByTestId("cam-review")).toBeVisible();
});

test("on a phone the review stacks without scrolling sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openReview(page);
  expect(await scrollsSideways(page)).toBe(false);
});
