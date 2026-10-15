// Every screen of a case whose file is complete: the recorded "complete" set
// (Kestrel, 14 documents) is uploaded through the Files screen and each tab is
// then read as a user reads it.
//
// The case is created once for the whole file and deleted after it, because the
// pipeline behind these screens runs for real.
import { expect, test, type Page } from "@playwright/test";

import {
  AS_OF,
  KESTREL,
  checklistStatuses,
  createCase,
  pinAsOf,
  readAsOf,
  stageStatusMap,
} from "../support/integration";
import {
  caseTabs,
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
  caseId = await createCase(page, KESTREL);
  // The frozen date has to be in place before any document is read, because
  // every age and window rule reads it (principle 5).
  pinAsOf(caseId);
  await uploadViaUi(page, caseId, fixtureSet("complete"));
  await waitForStagesOnScreen(page);
});

test.afterAll(async () => {
  if (caseId) await deleteCaseViaUi(page, caseId);
  await page.close();
});

test("the pipeline settles with every stage reported", async () => {
  await page.goto(`/appraisals/${caseId}`);
  const stages = await stageStatusMap(page);
  expect(Object.keys(stages).filter((k) => stages[k] === null)).toEqual([]);
  expect(Object.values(stages)).not.toContain("in_progress");
  expect(Object.values(stages)).not.toContain("not_started");
});

test("Overview carries the case header and the stage bar", async () => {
  await page.goto(`/appraisals/${caseId}`);
  const header = page.getByTestId("case-header");
  await expect(header).toContainText(caseId);
  await expect(header).toContainText(KESTREL);
  await expect(page.getByTestId("stage-progress")).toBeVisible();
  await expect(page.getByTestId("header-stage")).toBeVisible();
});

test("the analyst's case menu holds seven tabs and not Comparison", async () => {
  await page.goto(`/appraisals/${caseId}`);
  await expect(caseTabs(page)).toHaveCount(7);
  await expect(page.getByTestId("case-nav").getByRole("link", { name: "Comparison" })).toHaveCount(
    0,
  );
});

test("Files: every uploaded file is registered and read into documents", async () => {
  await page.goto(`/appraisals/${caseId}/documents`);
  const tree = page.getByTestId("file-tree");
  await expect(tree).toBeVisible();
  // The 14 uploaded documents, plus the sourcing message kept as the first
  // document of the case (F-04.8).
  await expect(tree.getByTestId("tree-file")).toHaveCount(15);
  await expect(
    tree.locator('[data-testid="tree-file"]:not([data-status="registered"])'),
  ).toHaveCount(0);
  await expect(tree.getByTestId("tree-document")).toHaveCount(27);
  // A complete, clean set: nothing unidentified and no label contradicted.
  await expect(page.getByTestId("unclassified")).toHaveCount(0);
  await expect(page.getByTestId("label-mismatch")).toHaveCount(0);
});

test("Files: a document row opens its own checks", async () => {
  await page.goto(`/appraisals/${caseId}/documents`);
  const first = page.getByTestId("document-toggle").first();
  await first.click();
  await expect(page.getByTestId("doc-summary").first()).toBeVisible();
  await expect(page.getByTestId("document-type").first()).toBeVisible();
});

test("Extracted data: the fields read from the documents, with their evidence", async () => {
  await page.goto(`/appraisals/${caseId}/extraction`);
  await expect(page.getByTestId("field-table").first()).toBeVisible();
  await expect(page.getByTestId("field-table-row")).not.toHaveCount(0);
  // The three people the documents name (two directors and the KYC subject).
  await expect(page.getByTestId("party")).toHaveCount(3);

  // A value opens the page it was read from.
  await page.getByTestId("field-value").first().click();
  const viewer = page.getByTestId("evidence-viewer");
  await expect(viewer).toBeVisible();
  await expect(viewer.getByTestId("viewer-page")).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
});

test("Completeness: every requirement is satisfied and the case is ready for credit", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  const statuses = await checklistStatuses(page);
  expect(statuses).toHaveLength(10);
  expect(new Set(statuses)).toEqual(new Set(["satisfied"]));

  await expect(page.getByTestId("gate-banner")).toHaveAttribute("data-ready", "true");
  await expect(page.getByTestId("readiness-score")).toContainText("100");
  await expect(page.getByTestId("header-ready")).toBeVisible();
  await expect(page.getByTestId("header-blocking")).toHaveCount(0);
  // Nothing provisional: the constitution was confirmed when the case was made.
  await expect(page.getByTestId("provisional")).toHaveCount(0);
});

test("Completeness: the checklist filters by status", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  await expect(page.getByTestId("checklist-filters")).toBeVisible();
  await page.getByTestId("checklist-filter-blocking").click();
  // Nothing is blocking on a complete file, so the filter empties the list.
  await expect(page.getByTestId("checklist-item")).toHaveCount(0);
  await page.getByTestId("checklist-filter-satisfied").click();
  await expect(page.getByTestId("checklist-item")).toHaveCount(10);
});

test("Completeness: a requirement states why it is asked for and what satisfies it", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  const item = page.getByTestId("checklist-item").first();
  await item.getByRole("button").first().click();
  await expect(item.getByTestId("linked-document")).not.toHaveCount(0);
});

test("Completeness: the query list is on the same tab", async () => {
  await page.goto(`/appraisals/${caseId}/completeness`);
  const list = page.getByTestId("query-list");
  await expect(list).toBeVisible();
  // Every request the engine raised was met by the complete set.
  await expect(list.locator('[data-testid="query-item"][data-resolved="false"]')).toHaveCount(0);
  await expect(list.locator('[data-testid="query-item"][data-resolved="true"]')).toHaveCount(10);
});

test("Cross-checks: the four areas are reported, with the one check the file fails", async () => {
  await page.goto(`/appraisals/${caseId}/cross-verification`);
  await expect(page.getByTestId("xv-overview")).toBeVisible();
  await expect(page.getByTestId("xv-area-identity")).toBeVisible();
  await expect(page.getByTestId("xv-area-turnover")).toBeVisible();
  await expect(page.getByTestId("xv-area-accounts")).toBeVisible();
  await expect(page.getByTestId("xv-area-obligations")).toBeVisible();

  // Even on a complete file one check fails: the turnover the RM declared when
  // the case was made is cross-checked against what the documents evidence
  // (TO-04). It is mild and not blocking, so no banner is raised.
  const cards = page.locator("[data-adjudicated]");
  await expect(cards).toHaveCount(1);
  await expect(cards).toHaveAttribute("data-rule", "TO-04");
  await expect(cards).toHaveAttribute("data-severity", "mild");
  await expect(page.getByTestId("xv-banner")).toHaveCount(0);
  // The other three areas have nothing in discrepancy at all.
  await expect(page.getByTestId("xv-area-none")).toHaveCount(3);
  await expect(page.getByTestId("xv-discrepancies")).toHaveCount(1);
});

test("Policy: all thirteen norms are listed, the deviation first in its family", async () => {
  await page.goto(`/appraisals/${caseId}/policy`);
  await expect(page.getByTestId("policy-page")).toBeVisible();
  await expect(page.getByTestId("norm").first()).toBeVisible();
  await expect(page.getByTestId("norm")).toHaveCount(13);
  // Working-capital cycle is over its ceiling on this file; DSCR cannot be
  // evaluated because the instalments on the proposed term loan are not stated.
  await expect(page.locator('[data-testid="norm"][data-outcome="deviation"]')).toHaveCount(1);
  await expect(page.locator('[data-testid="norm"][data-norm="FR-06"]')).toHaveAttribute(
    "data-outcome",
    "deviation",
  );
  await expect(page.locator('[data-testid="norm"][data-norm="FR-03"]')).toHaveAttribute(
    "data-outcome",
    "cannot_evaluate",
  );
  await expect(page.locator('[data-testid="norm"][data-outcome="pass"]')).toHaveCount(11);
  // A norm that cannot be evaluated says so rather than being left out (F-23).
  await expect(page.getByTestId("norm-missing").first()).toBeVisible();
});

test("Policy: a norm's figure opens the page it was read from", async () => {
  await page.goto(`/appraisals/${caseId}/policy`);
  const norm = page.locator('[data-testid="norm"][data-norm="FR-06"]');
  await norm.getByTestId("norm-input").first().getByRole("button").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toBeVisible();
  await page.keyboard.press("Escape");
});

test("Policy: the approving authority is worked out from the ask", async () => {
  await page.goto(`/appraisals/${caseId}/policy`);
  const card = page.getByTestId("policy-authority-card");
  await expect(card).toBeVisible();
  await expect(card.getByTestId("policy-authority-level")).toBeVisible();
  // It is a lower bound while a norm is still unevaluated (F-27).
  await expect(card.getByTestId("policy-authority-at-least")).toBeVisible();
});

test("Outputs: the spread holds every row over two audited years", async () => {
  await page.goto(`/appraisals/${caseId}/outputs`);
  await expect(page.getByTestId("spread-table")).toBeVisible();
  await expect(page.getByTestId("spread-row")).toHaveCount(28);
  // Two audited years are on file, so the spread has two columns of figures.
  await expect(page.getByTestId("spread-table").getByRole("columnheader")).toHaveCount(3);
  await expect(page.getByTestId("wc-verdict")).toBeVisible();

  // A figure is traceable to its page.
  await page
    .locator('[data-testid="spread-row"][data-row="revenue_from_operations"]')
    .getByTestId("spread-value")
    .first()
    .click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toBeVisible();
  await page.keyboard.press("Escape");
});

test("Outputs: the draft CAM cites its figures and lists what is unassessed", async () => {
  await page.goto(`/appraisals/${caseId}/outputs`);
  await page.getByTestId("view-cam").click();
  await expect(page.getByTestId("cam")).toBeVisible();
  await expect(page.getByTestId("cam-section")).toHaveCount(10);
  await expect(page.getByTestId("citation").first()).toBeVisible();
  // The deviation and the norm that could not be assessed are both on the summary.
  await expect(page.getByTestId("cam-summary")).toBeVisible();
});

test("Outputs: the PD note asks a question for each thing left open", async () => {
  await page.goto(`/appraisals/${caseId}/outputs`);
  await page.getByTestId("view-pd").click();
  // One per thing left open: the deviation, the norm not assessed, the failed
  // cross-check and the checks that could not run.
  await expect(page.getByTestId("pd-question")).toHaveCount(7);
  // Each question links to the tab that raised it.
  await expect(page.getByTestId("pd-question").first().getByRole("link")).toBeVisible();
});

test("the case's as_of is never moved by anything downstream", async () => {
  expect(readAsOf(caseId)).toBe(AS_OF);
});

test("the failed cross-check is on the review queue", async () => {
  await page.goto("/review");
  await expect(page.getByTestId("kind-all")).toBeVisible();
  const rows = page.getByTestId("review-row").filter({ hasText: caseId });
  await expect(rows).toHaveCount(1);
  await expect(rows).toHaveAttribute("data-kind", "finding");
  await expect(rows).toHaveAttribute("data-status", "open");
});
