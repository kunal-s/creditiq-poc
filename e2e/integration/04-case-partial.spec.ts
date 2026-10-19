// Every screen of a case whose file is short: the recorded "partial" set
// (Heronbay, 6 documents) leaves requirements missing and insufficient, raises
// cross-check findings and puts items on the review queue.
import { expect, test, type Page } from "@playwright/test";

import {
  HERONBAY,
  checklistStatuses,
  createCase,
  pinAsOf,
  stageStatusMap,
} from "../support/integration";
import {
  deleteCaseViaUi,
  fixtureSet,
  signIn,
  uploadViaUi,
  waitForStagesOnScreen,
} from "../support/ui";

test.describe.configure({ mode: "serial" });

let page: Page;
let caseId: string;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await signIn(page, "analyst");
  caseId = await createCase(page, HERONBAY);
  pinAsOf(caseId);
  await uploadViaUi(page, caseId, fixtureSet("partial"));
  await waitForStagesOnScreen(page);
});

test.afterAll(async () => {
  if (caseId) await deleteCaseViaUi(page, caseId);
  await page.close();
});

test("the stages that found gaps say they need attention", async () => {
  await page.goto(`/appraisals/${caseId}`);
  const stages = await stageStatusMap(page);
  expect(stages["documents"]).toBe("done");
  expect(stages["extraction"]).toBe("done");
  expect(stages["completeness"]).toBe("needs_attention");
  expect(stages["cross_verification"]).toBe("needs_attention");
  expect(stages["policy"]).toBe("needs_attention");
});

test("Overview says what is still needed", async () => {
  await page.goto(`/appraisals/${caseId}`);
  await expect(page.getByTestId("case-header")).toContainText(HERONBAY);
  await expect(page.getByTestId("header-blocking")).toBeVisible();
  await expect(page.getByTestId("header-ready")).toHaveCount(0);
});

test("Files: the six documents are registered and read", async () => {
  await page.goto(`/appraisals/${caseId}/documents`);
  const tree = page.getByTestId("file-tree");
  // Six uploads plus the sourcing message kept as the case's first document.
  await expect(tree.getByTestId("tree-file")).toHaveCount(7);
  await expect(tree.getByTestId("tree-document")).toHaveCount(14);
});

test("Completeness: four requirements are missing and four are insufficient", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  const statuses = await checklistStatuses(page);
  expect(statuses).toHaveLength(10);
  expect(statuses.filter((s) => s === "missing")).toHaveLength(4);
  expect(statuses.filter((s) => s === "insufficient")).toHaveLength(4);
  expect(statuses.filter((s) => s === "satisfied")).toHaveLength(2);

  await expect(page.getByTestId("gate-banner")).toHaveAttribute("data-ready", "false");
  await expect(page.getByTestId("blocking-gaps")).toBeVisible();
  await expect(page.getByTestId("header-ready")).toHaveCount(0);
});

test("Completeness: a short requirement says exactly what is short about it", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  // The GST returns are on file but do not cover the months the policy asks for.
  const gst = page.locator('[data-testid="checklist-item"][data-item="gst_returns"]');
  await expect(gst).toHaveAttribute("data-status", "insufficient");
  await expect(gst.getByTestId("deficiency")).toBeVisible();
  // The entity PAN was never received.
  await expect(
    page.locator('[data-testid="checklist-item"][data-item="pan_entity"]'),
  ).toHaveAttribute("data-status", "missing");
});

test("Completeness: the blocking filter leaves only the blocking gaps", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  await page.getByTestId("checklist-filter-blocking").click();
  for (const status of await checklistStatuses(page)) {
    expect(["missing", "insufficient", "in_review"]).toContain(status);
  }
  await expect(page.getByTestId("checklist-item")).toHaveCount(8);
});

test("Completeness: the query list groups what to ask for and keeps what is resolved", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  const list = page.getByTestId("query-list");
  await expect(list).toBeVisible();
  await expect(list.getByTestId("query-item")).toHaveCount(15);
  await expect(list.locator('[data-testid="query-item"][data-resolved="true"]')).toHaveCount(6);
  await expect(list.locator('[data-testid="query-item"][data-resolved="false"]')).toHaveCount(9);
});

test("Cross-checks: the two findings are on the board with their sources", async () => {
  await page.goto(`/appraisals/${caseId}/cross-verification`);
  await expect(page.getByTestId("xv-overview")).toBeVisible();
  // Three checks fail on this file: the CIN against the incorporation
  // particulars (ID-07), the declared turnover against the evidenced turnover
  // (TO-04) and the servicing of the borrowings in the books (OB-03). Each
  // discrepancy card carries data-adjudicated.
  const cards = page.locator("[data-adjudicated]");
  await expect(cards).toHaveCount(3);
  await expect(cards.nth(0)).toHaveAttribute("data-rule", "ID-07");
  await expect(cards.nth(1)).toHaveAttribute("data-rule", "TO-04");
  await expect(cards.nth(2)).toHaveAttribute("data-rule", "OB-03");
  await expect(page.getByTestId("xv-area-none")).toHaveCount(1);
  // What could not be checked at all is reported, not silently dropped.
  await expect(page.getByTestId("xv-incomplete").first()).toBeVisible();
});

test("the review queue holds the findings this case raised", async () => {
  await page.goto("/review");
  await expect(page.getByTestId("kind-all")).toBeVisible();
  const rows = page.getByTestId("review-row").filter({ hasText: caseId });
  await expect(rows).toHaveCount(3);
  await expect(rows.first().getByTestId("decide")).toBeVisible();
});

test("Cross-checks: a finding is accepted with a comment, and the decision is kept", async () => {
  await page.goto(`/appraisals/${caseId}/cross-verification`);
  // The board opens the engine's top finding as it loads, so it is already the
  // card in front of the reader.
  const card = page.locator("[data-adjudicated]").first();
  await expect(card).toHaveAttribute("data-expanded", "true");

  await card.getByTestId("xv-decision-accept").check();
  const save = card.getByTestId("xv-save-decision");
  // A decision is not recorded without a comment.
  await expect(save).toBeDisabled();
  await card.getByTestId("xv-comment").fill("Accepted: the discrepancy is real and goes on query.");
  await expect(save).toBeEnabled();
  await save.click();
  await expect(card.getByTestId("xv-recorded-decision")).toBeVisible();

  // It survives a reload: the card is marked adjudicated on the board, and the
  // decision itself is there when the card is opened again.
  await page.reload();
  const decided = page.locator('[data-adjudicated][data-rule="ID-07"]');
  await expect(decided).toHaveAttribute("data-adjudicated", "true");
  await decided.getByTestId("xv-card-toggle").click();
  await expect(decided.getByTestId("xv-recorded-decision")).toBeVisible();
});

test("Policy: three deviations and two norms that cannot be evaluated", async () => {
  await page.goto(`/appraisals/${caseId}/policy`);
  await expect(page.getByTestId("norm").first()).toBeVisible();
  await expect(page.getByTestId("norm")).toHaveCount(13);
  await expect(page.locator('[data-testid="norm"][data-outcome="deviation"]')).toHaveCount(3);
  await expect(page.locator('[data-testid="norm"][data-outcome="cannot_evaluate"]')).toHaveCount(2);
  await expect(page.locator('[data-testid="norm"][data-outcome="pass"]')).toHaveCount(8);
});

test("Financials: the spread has one audited year and says it is interim", async () => {
  await page.goto(`/appraisals/${caseId}/policy`);
  const financials = page.getByTestId("financials");
  await expect(financials.getByTestId("spread-row")).toHaveCount(23);
  await expect(financials.getByTestId("spread-interim")).toBeVisible();
  // One audited year is on file: the row label column and one figure column.
  await expect(
    financials.getByTestId("spread-profit_and_loss").getByRole("columnheader"),
  ).toHaveCount(2);
});

test("Outputs: the PD note asks after every gap and deviation", async () => {
  await page.goto(`/appraisals/${caseId}/outputs`);
  await page.getByTestId("view-pd").click();
  await expect(page.getByTestId("pd-question").first()).toBeVisible();
  await expect(page.getByTestId("pd-question")).toHaveCount(20);
});

test("a review decision never changes the published configuration version", async () => {
  // The version on record before anything is decided.
  await page.goto("/admin");
  const before = (await page.getByTestId("config-version").first().innerText()).trim();
  expect(before).not.toBe("");

  // Decide a finding that is still open on the board.
  await page.goto(`/appraisals/${caseId}/cross-verification`);
  const open = page.locator('[data-adjudicated="false"]').first();
  await expect(open).toBeVisible();
  // Hold on to the rule, because the card stops matching "not yet decided" the
  // moment the decision is saved.
  const rule = await open.getAttribute("data-rule");
  const card = page.locator(`[data-adjudicated][data-rule="${rule}"]`);
  if ((await card.getAttribute("data-expanded")) !== "true") {
    await card.getByTestId("xv-card-toggle").click();
  }
  await expect(card).toHaveAttribute("data-expanded", "true");
  await card.getByTestId("xv-decision-dismiss").check();
  await card.getByTestId("xv-comment").fill("Dismissed: explained by the lease already on file.");
  await card.getByTestId("xv-save-decision").click();
  await expect(card.getByTestId("xv-recorded-decision")).toBeVisible();

  // A decision is case data; it never republishes configuration (principle 4).
  await page.goto("/admin");
  const version = page.getByTestId("config-version").first();
  await expect(version).toBeVisible();
  await expect.poll(async () => (await version.innerText()).trim()).toBe(before);
});
