/// <reference types="node" />
// The draft CAM and the PD question note (FRD TC-28 / F-23 = test plan TC-26; FRD TC-29 / F-24
// = test plan TC-27), in the layout assumed until RBL's CAM template arrives. The memo's
// numbered sections hold facts, tables, paragraphs, subheadings and notes, every figure opening
// its page; it ends in a summary of findings, checks not completed, deviations and open queries,
// each opening the tab that decides it at the item, and leaves the recommendation and the
// sign-off for credit. The note asks its questions by topic, each tied to the finding, norm or
// gap it comes from, or to the memo section that states an observation it asks about. Both
// number the documents they cite, mark the pages as the downloads mark them, and download as
// Word and as PDF.
import { readFile } from "node:fs/promises";
import { expect, test, type Locator, type Page } from "@playwright/test";
import {
  CAM,
  DISBURSAL_TEXT,
  KESTREL,
  OUTPUT_CONFIG_LABEL,
  OUTPUT_CONFIG_VERSION,
  PD_NOTE,
} from "./fixtures/data";
import { MockApi, attachment, scrollingBoxes, scrollsSideways, signedIn } from "./support/api";

const viewer = (page: Page) => page.getByTestId("evidence-viewer");
const memoSection = (page: Page, id: string) =>
  page.getByTestId("cam").locator(`[data-testid="cam-section"][data-section="${id}"]`);
const fact = (scope: Locator, label: string) =>
  scope.locator(`[data-testid="cam-fact"][data-label="${label}"]`);
const summaryItem = (page: Page, ref: string) =>
  page.locator(`[data-testid="cam-summary-item"][data-ref="${ref}"]`);
const question = (page: Page, id: string) =>
  page.locator(`[data-testid="pd-question"][data-question="${id}"]`);
/** A statement's marks in order: each source's pages, and runs of sources as one. */
const marks = (scope: Locator) =>
  scope.locator('[data-testid="citation"], [data-testid="citation-range"]');

async function openView(page: Page, view: "cam" | "pd", api = new MockApi()) {
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/outputs?view=${view}`);
  // The memo opens for review a section at a time; these read it through, as it downloads.
  if (view === "cam") await page.getByTestId("cam-mode-memo").click();
  await expect(page.getByTestId(view === "cam" ? "cam" : "pd-note")).toBeVisible();
  return api;
}

/** Click and wait for the file the browser is handed. */
async function download(page: Page, button: Locator) {
  const [file] = await Promise.all([page.waitForEvent("download"), button.click()]);
  return file;
}

test("the draft CAM: its header, then numbered sections of facts, tables, paragraphs and notes, every figure cited", async ({
  page,
}) => {
  await openView(page, "cam");
  const header = page.getByTestId("cam-header");
  await expect(header.getByTestId("cam-title")).toHaveText("Credit Approval Memo");
  await expect(header.getByTestId("cam-borrower")).toHaveText(
    `Kestrel Polymers Pvt Ltd · Appraisal ${KESTREL}`,
  );
  const meta = header.getByTestId("cam-meta");
  await expect(meta).toContainText("Drafted from the data on file as of 20 Sep 2026");
  // The configuration as Administration counts it; the full version only on hover.
  const config = meta.getByTestId("cam-config");
  await expect(config).toHaveText(`Configuration: ${OUTPUT_CONFIG_LABEL}`);
  await expect(config).toHaveAttribute("title", OUTPUT_CONFIG_VERSION);
  await expect(meta).not.toContainText(OUTPUT_CONFIG_VERSION);
  await expect(meta).toContainText("Cross-check run XR-000021-003");
  await expect(header.getByTestId("cam-template-note")).toHaveText(
    "Draft — layout assumed until RBL's CAM template is received.",
  );

  // Eight sections: six drafted from parts, each part under its subheading, then the risk
  // assessment and the recommendation.
  await expect(page.getByTestId("cam-section-title")).toHaveText([
    "1. Borrower and Group Profile",
    "2. Facility Requested and Purpose",
    "3. Banking Conduct",
    "4. Financial Analysis and Ratios",
    "5. GST and Bureau Findings",
    "6. Cross-Verification Results",
  ]);
  await expect(
    page.locator(
      '[data-testid="cam-memo-section"][data-section="facility"] [data-testid="cam-subheading"]',
    ),
  ).toHaveText([
    "Proposal at a glance",
    "Proposal and facilities",
    "Assessment of working-capital requirement",
  ]);

  // Facts: a label and its value, cited where a document backs it.
  const snapshot = memoSection(page, "snapshot");
  await expect(snapshot.getByTestId("cam-fact")).toHaveCount(16);
  await expect(fact(snapshot, "Approving authority")).toContainText(
    "At least Regional Credit Head (provisional matrix)",
  );
  await expect(fact(snapshot, "Amount requested").getByTestId("citation")).toHaveCount(0);
  const pan = fact(snapshot, "PAN").getByTestId("citation");
  await expect(pan).toHaveText("2 p.1");
  await expect(pan).toHaveAttribute("title", "Source 2: Company PAN, page 1");
  await expect(pan).toHaveCSS("white-space", "nowrap");
  await pan.click();
  await expect(viewer(page).getByTestId("viewer-page")).toContainText("1");
  await page.keyboard.press("Escape");

  // A table: its title, its figures aligned right, each cited on a line of its own under the
  // figure, so that the figures line up whatever the number of pages behind them.
  const financials = memoSection(page, "financials");
  const table = financials.getByTestId("cam-table");
  await expect(table.getByTestId("cam-table-title")).toHaveText("Key financials");
  await expect(table.locator("th").nth(2)).toHaveCSS("text-align", "right");
  const profit = table.getByTestId("cam-table-row").filter({ hasText: "Profit after tax" });
  await expect(profit.locator("td").first()).not.toHaveCSS("text-align", "right");
  const latest = profit.locator("td").nth(2);
  await expect(latest).toHaveAttribute("data-numeric", "true");
  await expect(latest).toHaveCSS("text-align", "right");
  await expect(latest).toContainText("INR -40.00 lakh");
  const [figureBottom, pageTop] = await latest.evaluate((td) => [
    td.querySelector("div > span")?.getBoundingClientRect().bottom ?? 0,
    td.querySelector('[data-testid="citation"]')?.getBoundingClientRect().top ?? 0,
  ]);
  expect(pageTop).toBeGreaterThanOrEqual(figureBottom - 1);
  await latest.getByTestId("citation").click();
  await expect(viewer(page).getByTestId("viewer-page")).toContainText("5");
  await page.keyboard.press("Escape");
  await expect(financials.getByTestId("cam-paragraph")).toHaveCount(3);
  // A source cited at two pages is marked once, as the downloads mark it.
  await expect(financials.getByTestId("cam-paragraph").first().getByTestId("citation")).toHaveText(
    "5 pp.3-4",
  );
  await expect(financials.getByTestId("cam-note")).toHaveText(
    "Figures as on the spread (interim layout).",
  );

  // A note under a table, a note in a section, a subheading with its facts.
  await expect(memoSection(page, "turnover").getByTestId("cam-table-note")).toContainText(
    "Business credits exclude transfers between the borrower's own accounts",
  );
  const note = memoSection(page, "borrower").getByTestId("cam-note");
  await expect(note).toContainText("see XV-000021-03 and XV-000021-04 in section 10");
  // A reference never breaks at its hyphens.
  await expect(note.locator("span", { hasText: "XV-000021-03" })).toHaveCSS(
    "white-space",
    "nowrap",
  );
  const policy = memoSection(page, "policy");
  await expect(policy.getByTestId("cam-subheading")).toHaveText([
    "Compliance with policy norms",
    "Approving authority",
  ]);
  await expect(fact(policy, "Authority required").locator("dd")).toHaveText(
    "At least Regional Credit Head",
  );
  const verification = memoSection(page, "verification");
  await expect(verification.getByTestId("cam-table-title")).toHaveText([
    "By area",
    "Checks not completed",
    "Discrepancies",
  ]);
  const discrepancies = verification.getByTestId("cam-table").nth(2).getByTestId("cam-table-row");
  await expect(discrepancies.nth(3)).toContainText("Not valid");
  await expect(discrepancies.nth(4)).toContainText("Accepted as valid");

  // A combined figure keeps its amount whole and lets the words after it wrap.
  const bureau = memoSection(page, "obligations")
    .getByTestId("cam-table-row")
    .first()
    .locator("td")
    .nth(4);
  await expect(bureau).toContainText("INR 55.00 lakh; outstanding INR 38.00 lakh");
  const amount = bureau.locator("span", { hasText: /^INR 55\.00 lakh$/ });
  await expect(amount).toHaveCSS("white-space", "nowrap");
  await expect(bureau.locator("div > span").first()).not.toHaveCSS("white-space", "nowrap");
});

test("every page a statement rests on is marked, by source number, a run of sources as one that opens into each", async ({
  page,
}) => {
  await openView(page, "cam");
  // The GST figure rests on the eight monthly returns: the first numbered when the memo first
  // cited it, the other seven in a row.
  const gst = memoSection(page, "turnover")
    .getByTestId("cam-table-row")
    .first()
    .locator("td")
    .nth(2);
  await expect(gst).toContainText("INR 14.80 cr (8 of 12 months)");
  await expect(marks(gst)).toHaveText(["3 p.1", "6-12 p.1"]);
  const run = gst.getByTestId("citation-range");
  await expect(run).toHaveAttribute("aria-expanded", "false");
  await expect(run).toHaveAttribute("title", "Sources 6 to 12, p.1");
  await expect(gst.getByText("+", { exact: false })).toHaveCount(0);
  await run.click();
  await expect(run).toHaveAttribute("aria-expanded", "true");
  await expect(gst.getByTestId("citation")).toHaveText([
    "3 p.1",
    ...Array.from({ length: 7 }, (_, i) => `${6 + i} p.1`),
  ]);
  const december = gst.locator('[data-testid="citation"][data-source="9"]');
  await expect(december).toHaveAttribute("title", "Source 9: GSTR-3B · Dec 2025, page 1");
  await december.click();
  await expect(viewer(page).getByTestId("viewer-page")).toContainText("1");
  await page.keyboard.press("Escape");
  await run.click();
  await expect(gst.getByTestId("citation")).toHaveText(["3 p.1"]);

  // Nine pages behind one paragraph: every one marked, none hidden, in the order of the sources.
  const filing = memoSection(page, "turnover").getByTestId("cam-paragraph").last();
  await expect(filing).toContainText("GST returns (GSTR-3B) are on file for 8 months");
  await expect(marks(filing)).toHaveText(["3 p.1", "6-12 p.1", "14 p.1"]);
  await expect(filing.locator("span", { hasText: /^AY 2025-26$/ })).toHaveCSS(
    "white-space",
    "nowrap",
  );
});

test("a section with nothing on file says so", async ({ page }) => {
  const api = new MockApi();
  api.cam = {
    ...structuredClone(CAM),
    sections: CAM.sections.map((s) =>
      s.id === "gst"
        ? {
            ...s,
            blocks: [],
            parts: (s.parts ?? []).map((p) => ({ ...p, blocks: [] })),
            empty: "Nothing on file yet.",
          }
        : s,
    ),
  };
  await openView(page, "cam", api);
  const gst = page.locator('[data-testid="cam-memo-section"][data-section="gst"]');
  await expect(gst.getByTestId("cam-section-empty")).toHaveText("Nothing on file yet.");
  await expect(gst.getByTestId("cam-table")).toHaveCount(0);
});

test("the summary lists each finding as a register entry, the checks not completed with what would complete them, the deviations and the open queries", async ({
  page,
}) => {
  await openView(page, "cam");
  const summary = page.getByTestId("cam-summary");
  await expect(summary.locator("h3")).toHaveText("7. Risk Assessment and Rating");
  await expect(summary.getByTestId("cam-summary-finding")).toContainText("Findings (6)");
  await expect(summary.getByTestId("cam-summary-incomplete")).toContainText(
    "Checks not completed (2)",
  );
  await expect(summary.getByTestId("cam-summary-deviation")).toContainText(
    "Deviations from policy (3)",
  );
  await expect(summary.getByTestId("cam-summary-unassessed")).toContainText(
    "Norms not assessed (3)",
  );
  await expect(summary.getByTestId("cam-summary-query")).toContainText("Open queries (6)");

  // A finding: reference, severity, title cited, status, whether it blocks submission; its
  // explanation is in section 10, not repeated here.
  const pan = summaryItem(page, "XV-000021-03");
  await expect(pan).toContainText("Serious");
  await expect(pan).toContainText("Entity PAN differs between documents");
  await expect(pan).not.toContainText("The entity PAN differs between documents:");
  await expect(pan.getByTestId("cam-summary-status")).toHaveText("Open");
  await expect(pan.getByTestId("blocks-submission")).toHaveText("Blocks submission");
  await expect(pan.getByTestId("citation")).toHaveText(["2 p.1", "17 p.1"]);
  const facilities = summaryItem(page, "XV-000021-02");
  await expect(facilities.getByTestId("cam-summary-status")).toHaveText("Escalated");
  await expect(facilities.getByTestId("blocks-submission")).toHaveCount(0);
  // Accepted means the finding is valid, not that it is cleared.
  await expect(summaryItem(page, "XV-000021-06").getByTestId("cam-summary-status")).toHaveText(
    "Accepted as valid",
  );
  await expect(summary.getByTestId("blocks-submission")).toHaveCount(2);

  // A check not completed: the check, why, and what would complete it.
  const gst = summaryItem(page, "TO-01");
  await expect(gst).toHaveAttribute("data-kind", "incomplete");
  await expect(gst.getByTestId("cam-summary-ref")).toHaveText("TO-01");
  await expect(gst).toContainText("Audited turnover against GST outward supplies · FY 2025-26");
  await expect(gst).toContainText(
    "GST outward supplies covers 8 of 12 months (Apr 2025 to Jul 2025 absent).",
  );
  await expect(gst.getByTestId("cam-summary-request")).toHaveText(
    "What would complete it: GSTR-3B returns for Apr 2025 to Jul 2025",
  );
  await expect(summaryItem(page, "ID-04").getByTestId("cam-summary-request")).toHaveText(
    "What would complete it: the director KYC",
  );

  // Each reference opens the tab that decides it at the item.
  await expect(pan.getByTestId("cam-summary-ref")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/cross-verification?finding=XV-000021-03`,
  );
  await expect(gst.getByTestId("cam-summary-ref")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/cross-verification?finding=TO-01`,
  );
  for (const norm of ["EL-04", "FR-05", "DOC-01", "EL-02", "FR-04", "FR-06"]) {
    await expect(summaryItem(page, norm).getByTestId("cam-summary-ref")).toHaveAttribute(
      "href",
      `/appraisals/${KESTREL}/policy?norm=${norm}`,
    );
  }
  await expect(summaryItem(page, "FR-05")).toContainText(
    "Financial norms: Debt / equity 3.00x against at most 2.00x.",
  );

  // The open queries, grouped as the query list groups them and numbered through.
  const queries = summary.getByTestId("cam-summary-query");
  await expect(queries.getByTestId("cam-summary-group")).toHaveText([
    "Documents needed",
    "Documents to redo",
    "Clarifications",
  ]);
  await expect(queries.locator("ol")).toHaveCount(3);
  await expect(queries.locator("ol").nth(1)).toHaveAttribute("start", "4");
  await expect(queries.getByTestId("cam-summary-ref")).toHaveCount(0);
  await expect(queries.getByTestId("cam-summary-query-list")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/completeness#queries`,
  );
});

test("a run that found no discrepancy says so in the summary rather than leaving the findings out", async ({
  page,
}) => {
  const api = new MockApi();
  api.cam = { ...structuredClone(CAM), summary: CAM.summary.filter((i) => i.kind !== "finding") };
  await openView(page, "cam", api);
  const findings = page.getByTestId("cam-summary-finding");
  await expect(findings).toHaveText(
    "Findings (0): no discrepancy in cross-check run XR-000021-003",
  );
  await expect(findings.getByTestId("cam-summary-item")).toHaveCount(0);
  await expect(page.getByTestId("cam-summary-incomplete")).toContainText(
    "Checks not completed (2)",
  );
});

test("a summary reference opens the board at its finding, or at the check not completed", async ({
  page,
}) => {
  await openView(page, "cam");
  await summaryItem(page, "XV-000021-01").getByTestId("cam-summary-ref").click();
  await expect(page).toHaveURL(
    new RegExp(`/appraisals/${KESTREL}/cross-verification\\?finding=XV-000021-01$`),
  );
  const card = page.getByTestId("xv-card-fnd-ob2");
  await expect(card).toHaveAttribute("data-expanded", "true");
  await expect(card).toBeInViewport();
  await expect(card.getByTestId("xv-card-toggle")).toBeFocused();
  // The board opens at the linked card instead of its top one.
  await expect(page.getByTestId("xv-card-fnd-id1")).toHaveAttribute("data-expanded", "false");

  await page.goBack();
  await expect(page.getByTestId("cam")).toBeVisible();
  await summaryItem(page, "TO-01").getByTestId("cam-summary-ref").click();
  const row = page.locator('[data-testid="xv-incomplete-row"][data-rule="TO-01"]');
  await expect(row).toBeInViewport();
  await expect(row).toBeFocused();
  await expect(row).toHaveAttribute("data-target", "true");
});

test("a summary norm opens the policy tab at its row", async ({ page }) => {
  await openView(page, "cam");
  await summaryItem(page, "FR-06").getByTestId("cam-summary-ref").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/policy\\?norm=FR-06$`));
  const norm = page.locator('[data-testid="norm"][data-norm="FR-06"]');
  await expect(norm).toBeInViewport();
  await expect(norm).toBeFocused();
  await expect(norm).toHaveAttribute("data-target", "true");
});

test("the recommendation is left for credit: each prompt an empty box, then the sign-off", async ({
  page,
}) => {
  await openView(page, "cam");
  const recommendation = page.getByTestId("cam-recommendation");
  await expect(recommendation.locator("h3")).toHaveText("8. Recommendation");
  const prompts = recommendation.getByTestId("cam-recommendation-prompt");
  await expect(prompts).toHaveCount(4);
  await expect(prompts.locator("p")).toHaveText([
    "Recommendation",
    "Terms and conditions",
    "Deviations recommended for approval",
    "Decision of the approving authority",
  ]);
  await expect(recommendation.getByTestId("cam-recommendation-box")).toHaveText(
    Array(4).fill("For credit to complete."),
  );
  const roles = recommendation.getByTestId("cam-sign-off-role");
  await expect(roles.locator("p")).toHaveText(["Prepared by", "Recommended by", "Approved by"]);
  await expect(roles.first().locator("dt")).toHaveText([
    "Name",
    "Designation",
    "Signature",
    "Date",
  ]);
  await expect(roles.first().locator("dd")).toHaveText(["", "", "", ""]);
});

test("the sources are numbered as the citations number them, each opening its first cited page", async ({
  page,
}) => {
  await openView(page, "cam");
  const rows = page.getByTestId("output-sources").getByTestId("output-source");
  await expect(rows).toHaveCount(18);
  await expect(rows.locator("td:first-child")).toHaveText(
    Array.from({ length: 18 }, (_, i) => String(i + 1)),
  );
  const accounts = rows.nth(4);
  await expect(accounts).toHaveAttribute("data-document", "doc-bs");
  await expect(accounts).toContainText("Audited financial statements · FY 2025-26");
  await expect(accounts).toContainText("bank stmt apr-mar.pdf");
  await expect(accounts.locator("td").last()).toHaveText("3, 4, 5");
  await accounts.getByTestId("output-source-open").click();
  await expect(viewer(page).getByTestId("viewer-page")).toContainText("3");
  await page.keyboard.press("Escape");

  // Read top to bottom, each document is numbered when it is first cited (a run of sources
  // counts each of its sources).
  const numbers = await marks(page.getByTestId("cam")).evaluateAll((els) =>
    els.flatMap((e) => {
      const first = Number(e.getAttribute("data-source") ?? e.getAttribute("data-first"));
      const last = Number(e.getAttribute("data-last") ?? first);
      return Array.from({ length: last - first + 1 }, (_, i) => first + i);
    }),
  );
  // Every source is cited (the order follows the sections, which the engine numbers by).
  expect([...new Set(numbers)].sort((a, b) => a - b)).toEqual(
    Array.from({ length: 18 }, (_, i) => i + 1),
  );
});

test("the PD note: whom to meet, the record left blank, and the questions by topic, each tied to its finding, norm, gap or observation", async ({
  page,
}) => {
  await openView(page, "pd");
  const header = page.getByTestId("pd-header");
  await expect(header.getByTestId("pd-title")).toHaveText("Personal discussion — question note");
  await expect(header.getByTestId("pd-subtitle")).toHaveText(
    "11 questions by topic, the most serious first in each, each tied to the finding, norm, gap or CAM observation it comes from.",
  );
  // The header facts as the engine composes them.
  const facts = header.getByTestId("pd-fact");
  await expect(facts.locator("dt")).toHaveText([
    "Borrower",
    "Case ID",
    "Constitution",
    "Proposal",
    "Data as of",
    "Configuration",
  ]);
  await expect(facts.locator("dd")).toHaveText([
    "Kestrel Polymers Pvt Ltd",
    KESTREL,
    "Private limited company",
    "Cash credit and term loan, INR 50.00 lakh",
    "20 Sep 2026",
    OUTPUT_CONFIG_LABEL,
  ]);
  await expect(facts.last().locator("dd")).toHaveAttribute("title", OUTPUT_CONFIG_VERSION);

  const people = page.getByTestId("pd-people").getByTestId("pd-person");
  await expect(people).toHaveCount(2);
  const kabir = people.first().locator("td");
  await expect(kabir.nth(0)).toHaveText("Kabir Rao");
  await expect(kabir.nth(1)).toHaveText("Director");
  await expect(kabir.nth(2)).toHaveText("08812345");
  await expect(kabir.nth(3)).toContainText(
    "KYC received, Memorandum and articles of association, Sourcing message",
  );
  // The pages that name them, cited.
  await expect(kabir.nth(3).getByTestId("citation")).toHaveText(["4 p.2", "10 p.1"]);
  await expect(people.nth(1).locator("td").nth(2)).toHaveText("—");
  const record = page.getByTestId("pd-record").getByTestId("pd-record-field");
  await expect(record.locator("dt")).toHaveText([
    "Date of discussion",
    "Place",
    "Bank officials present",
    "Promoters or representatives present",
  ]);
  await expect(record.locator("dd")).toHaveText(["", "", "", ""]);

  const topics = page.getByTestId("pd-topic");
  await expect(topics.getByTestId("pd-topic-title")).toHaveText([
    "Identity and KYC",
    "Turnover, tax and sales",
    "Bank accounts",
    "Existing borrowings",
    "Policy norms",
  ]);
  expect(await topics.evaluateAll((els) => els.map((e) => e.getAttribute("data-area")))).toEqual([
    "identity",
    "turnover",
    "accounts",
    "obligations",
    "policy",
  ]);
  await expect(topics.nth(3).getByTestId("pd-question")).toHaveCount(3);
  // Numbered across the note, in the order it asks them.
  await expect(page.getByTestId("pd-question-number")).toHaveText(
    Array.from({ length: 11 }, (_, i) => `${i + 1}.`),
  );

  const pan = question(page, "pdq-id1");
  const text = pan.getByTestId("pd-question-text");
  await expect(text).toHaveText(
    "Which PAN is the company's, and has the bureau been asked to correct its record?",
  );
  expect(Number(await text.evaluate((e) => getComputedStyle(e).fontWeight))).toBeGreaterThanOrEqual(
    600,
  );
  // Why we ask: the finding's explanation; its reference and title are on the line below.
  const context = pan.getByTestId("pd-question-context");
  await expect(context).toContainText("Why we ask: The entity PAN differs between documents:");
  await expect(context.getByTestId("citation")).toHaveText(["1 p.1", "2 p.1"]);
  await expect(pan.getByTestId("pd-question-status")).toHaveText("Open");
  const link = pan.getByTestId("pd-question-link");
  await expect(link).toHaveText("XV-000021-03 · Entity PAN differs between documents");
  await expect(link).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/cross-verification?finding=fnd-id1`,
  );
  await context.getByTestId("citation").nth(1).click();
  await expect(viewer(page).getByTestId("viewer-page")).toContainText("1");
  await page.keyboard.press("Escape");

  await expect(question(page, "pdq-ob1").getByTestId("pd-question-status")).toHaveText("Escalated");
  await expect(question(page, "pdq-ba1").getByTestId("pd-question-status")).toHaveText(
    "Accepted as valid",
  );
  const deviation = question(page, "pdq-el04");
  await expect(deviation.getByTestId("pd-question-link")).toHaveText(
    "EL-04 · Profit in the latest year",
  );
  await expect(deviation.getByTestId("pd-question-link")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/policy?norm=EL-04`,
  );
  await expect(deviation).toContainText("Policy deviation");
  await expect(deviation.getByTestId("pd-question-status")).toHaveCount(0);
  const gap = question(page, "pdq-id4");
  await expect(gap).toContainText("Open gap");
  await expect(gap.getByTestId("pd-question-link")).toHaveText(
    "ID-04 · Promoter missing from a source",
  );
  await expect(gap.getByTestId("citation")).toHaveCount(0);
  await expect(gap.getByTestId("pd-question-also")).toHaveCount(0);

  // An observation: a fact the memo states, marked apart from the checks' results, after the
  // findings of its topic; its link opens the draft CAM at the section its key names, and its
  // status names that section. Its key and its rule (OBS) are not shown.
  const observation = question(page, "pdq-obs1");
  await expect(observation).toHaveAttribute("data-source", "observation");
  await expect(observation.getByTestId("pd-question-number")).toHaveText("9.");
  await expect(observation.getByTestId("pd-question-source")).toHaveText("Observation in the CAM");
  await expect(observation.getByTestId("pd-question-context")).toContainText(
    `Why we ask: ${DISBURSAL_TEXT}`,
  );
  await expect(observation.getByTestId("pd-question-context").getByTestId("citation")).toHaveText(
    "6 p.7",
  );
  await expect(observation.getByTestId("pd-question-link")).toHaveText(
    "Draft CAM · Loan disbursal no facility explains",
  );
  await expect(observation.getByTestId("pd-question-link")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/outputs?view=cam#cam-section-banking`,
  );
  await expect(observation).not.toContainText("OBS");
  await expect(observation.getByTestId("pd-question-status")).toHaveText("section 8");
  await expect(question(page, "pdq-ob1").getByTestId("pd-question-source")).toHaveText(
    "Cross-check finding",
  );

  // One question asked for several checks names each of them, each opening its own.
  const merged = question(page, "pdq-to1");
  const also = merged.getByTestId("pd-question-also");
  await expect(also).toContainText("Also covers:");
  await expect(also.getByTestId("pd-also-link")).toHaveText([
    "TO-02 · GST turnover not supported by bank credits",
  ]);
  await expect(also.getByTestId("pd-also-link")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/cross-verification?finding=fnd-to2`,
  );

  const documents = page.getByTestId("pd-documents").getByTestId("pd-document");
  await expect(documents).toHaveCount(5);
  await expect(documents.nth(3)).toContainText(
    "Board resolution: the copy provided is not signed.",
  );
  await expect(documents.nth(3).getByTestId("citation")).toHaveText("10 p.1");

  // The sign-off, from the note: left blank for whoever holds the discussion.
  const signOff = page.getByTestId("pd-sign-off").getByTestId("pd-sign-off-role");
  await expect(signOff.locator("p")).toHaveText(["Discussion held by"]);
  await expect(signOff.locator("dt")).toHaveText(["Name", "Designation", "Signature", "Date"]);
  await expect(signOff.locator("dd")).toHaveText(["", "", "", ""]);
  await expect(page.getByTestId("output-sources").getByTestId("output-source")).toHaveCount(10);
});

test("a question's link opens the board at its finding, or the policy tab at its norm", async ({
  page,
}) => {
  await openView(page, "pd");
  await question(page, "pdq-ob1").getByTestId("pd-question-link").click();
  await expect(page).toHaveURL(
    new RegExp(`/appraisals/${KESTREL}/cross-verification\\?finding=fnd-ob1$`),
  );
  const card = page.getByTestId("xv-card-fnd-ob1");
  await expect(card).toHaveAttribute("data-expanded", "true");
  await expect(card).toBeInViewport();
  await expect(card.getByTestId("xv-card-toggle")).toBeFocused();

  await page.goBack();
  await expect(page.getByTestId("pd-note")).toBeVisible();
  await question(page, "pdq-to1").getByTestId("pd-also-link").click();
  const row = page.locator('[data-testid="xv-incomplete-row"][data-rule="TO-02"]');
  await expect(row).toBeInViewport();
  await expect(row).toBeFocused();

  await page.goBack();
  await expect(page.getByTestId("pd-note")).toBeVisible();
  await question(page, "pdq-fr05").getByTestId("pd-question-link").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/policy\\?norm=FR-05$`));
  const norm = page.locator('[data-testid="norm"][data-norm="FR-05"]');
  await expect(norm).toBeFocused();
  await expect(norm).toHaveAttribute("data-target", "true");
});

test("an observation's link opens the draft CAM at the section that states it, or at its top where none does", async ({
  page,
}) => {
  await openView(page, "pd");
  await question(page, "pdq-obs1").getByTestId("pd-question-link").click();
  await expect(page).toHaveURL(
    new RegExp(`/appraisals/${KESTREL}/outputs\\?view=cam#cam-section-banking$`),
  );
  // The memo opens for review at the section that holds the part, scrolled to the part.
  const section = page.getByTestId("cam-review-section");
  await expect(section).toHaveAttribute("data-section", "conduct");
  await expect(section.getByTestId("cam-section-title")).toHaveText("Banking Conduct");
  await expect(page.locator("#cam-section-banking")).toBeInViewport();
  await expect(
    section.getByTestId("cam-paragraph").filter({ hasText: DISBURSAL_TEXT }),
  ).toHaveCount(1);

  // A key that names no section: the link opens the draft CAM at its top.
  const api = new MockApi();
  api.pdNote = {
    ...structuredClone(PD_NOTE),
    questions: PD_NOTE.questions.map((q) =>
      q.id === "pdq-obs1" ? { ...q, ref: "collateral", status: null } : q,
    ),
  };
  await openView(page, "pd", api);
  const link = question(page, "pdq-obs1").getByTestId("pd-question-link");
  await expect(link).toHaveText("Draft CAM · Loan disbursal no facility explains");
  await expect(link).toHaveAttribute("href", `/appraisals/${KESTREL}/outputs?view=cam`);
});

test("a note with one question says so in the singular", async ({ page }) => {
  const api = new MockApi();
  const only = PD_NOTE.questions[0]!;
  api.pdNote = {
    ...structuredClone(PD_NOTE),
    questions: [only],
    topics: [{ area: "identity", title: "Identity and KYC", question_ids: [only.id] }],
  };
  await openView(page, "pd", api);
  await expect(page.getByTestId("pd-subtitle")).toHaveText(
    "1 question, tied to the finding, norm, gap or CAM observation it comes from.",
  );
});

test("a note with nothing to ask still names whom to meet, the record and the downloads", async ({
  page,
}) => {
  const api = new MockApi();
  api.pdNote = { ...structuredClone(PD_NOTE), questions: [], topics: [], documents_to_collect: [] };
  await openView(page, "pd", api);
  await expect(page.getByTestId("pd-no-questions")).toContainText("No questions yet");
  await expect(page.getByTestId("pd-topic")).toHaveCount(0);
  await expect(page.getByTestId("pd-subtitle")).toHaveCount(0);
  await expect(page.getByTestId("pd-download-docx")).toBeVisible();
  await expect(page.getByTestId("pd-download-pdf")).toBeVisible();
  await expect(page.getByTestId("pd-people").getByTestId("pd-person")).toHaveCount(2);
  await expect(page.getByTestId("pd-record").getByTestId("pd-record-field")).toHaveCount(4);
  await expect(page.getByTestId("pd-sign-off")).toBeVisible();
});

test("the memo and the note download as Word and as PDF, fetched with the session's token", async ({
  page,
}) => {
  const api = await openView(page, "cam");
  const files: [string, string, string][] = [
    ["cam-download-docx", `CAM-draft-${KESTREL}.docx`, "PK"],
    ["cam-download-pdf", `CAM-draft-${KESTREL}.pdf`, "%PDF"],
  ];
  for (const [button, name, magic] of files) {
    const file = await download(page, page.getByTestId(button));
    expect(file.suggestedFilename()).toBe(name);
    const bytes = await readFile(await file.path());
    expect(bytes.subarray(0, magic.length).toString("latin1")).toBe(magic);
  }
  await expect(page.getByTestId("cam-download-docx")).toHaveText("Download Word");
  await expect(page.getByTestId("cam-download-pdf")).toHaveText("Download PDF");

  await page.getByTestId("view-pd").click();
  for (const format of ["docx", "pdf"] as const) {
    const file = await download(page, page.getByTestId(`pd-download-${format}`));
    expect(file.suggestedFilename()).toBe(`PD-note-${KESTREL}.${format}`);
  }
  expect(api.downloads).toEqual([
    { output: "cam", format: "docx", authorization: "Bearer session-token" },
    { output: "cam", format: "pdf", authorization: "Bearer session-token" },
    { output: "pd_note", format: "docx", authorization: "Bearer session-token" },
    { output: "pd_note", format: "pdf", authorization: "Bearer session-token" },
  ]);
});

test("a download shows it is being prepared, and says so when the file cannot be had", async ({
  page,
}) => {
  const api = new MockApi();
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = () => resolve();
  });
  api.on("GET", /\/pd-note\/download$/, async () => {
    await held;
    return attachment("pd_note", KESTREL, "pdf");
  });
  await openView(page, "pd", api);
  const pdf = page.getByTestId("pd-download-pdf");
  const docx = page.getByTestId("pd-download-docx");
  const waiting = page.waitForEvent("download");
  await pdf.click();
  await expect(pdf).toHaveAttribute("aria-busy", "true");
  await expect(pdf).toHaveText("Preparing…");
  await expect(pdf).toBeDisabled();
  await expect(docx).toBeDisabled();
  release();
  expect((await waiting).suggestedFilename()).toBe(`PD-note-${KESTREL}.pdf`);
  await expect(pdf).toHaveText("Download PDF");
  await expect(pdf).toBeEnabled();

  api.on("GET", /\/pd-note\/download$/, () => ({
    status: 503,
    json: { detail: "no published configuration" },
  }));
  let downloaded = false;
  page.on("download", () => (downloaded = true));
  await docx.click();
  await expect(page.getByText("The file could not be downloaded")).toBeVisible();
  await expect(
    page.getByText("The checklist and document configuration has not been published yet."),
  ).toBeVisible();
  await expect(docx).toBeEnabled();
  expect(downloaded).toBe(false);
});

test("the file takes the name the engine gives it, or the same pattern when the page cannot read the header", async ({
  page,
}) => {
  const api = new MockApi();
  api.on("GET", /\/cam\/download$/, (req) =>
    new URL(req.url()).searchParams.get("format") === "docx"
      ? {
          ...attachment("cam", KESTREL, "docx"),
          headers: {
            "content-disposition": `attachment; filename="memo.docx"; filename*=UTF-8''CAM%20draft%20${KESTREL}.docx`,
            "access-control-expose-headers": "content-disposition",
          },
        }
      : {
          ...attachment("cam", KESTREL, "pdf"),
          headers: { "content-disposition": 'attachment; filename="memo.pdf"' },
        },
  );
  await openView(page, "cam", api);
  const named = await download(page, page.getByTestId("cam-download-docx"));
  expect(named.suggestedFilename()).toBe(`CAM draft ${KESTREL}.docx`);
  const unread = await download(page, page.getByTestId("cam-download-pdf"));
  expect(unread.suggestedFilename()).toBe(`CAM-draft-${KESTREL}.pdf`);
});

test("at phone width every table of the memo and the note fits its box: the wide ones as a card per row", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openView(page, "cam");
  await expect(page.getByTestId("cam-download-pdf")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
  expect(await scrollingBoxes(page.getByTestId("cam"))).toEqual([]);
  // Four columns or more: a card per row, each value beside its column's label.
  const tables = page.getByTestId("cam-table");
  const layouts = await tables.evaluateAll((figures) =>
    figures.map((f) => ({
      columns: f.querySelectorAll("th").length,
      stacked: getComputedStyle(f.querySelector("table")!).display === "block",
    })),
  );
  expect(layouts.length).toBeGreaterThan(10);
  for (const { columns, stacked } of layouts) expect(stacked).toBe(columns >= 4);
  const tidewater = memoSection(page, "obligations").getByTestId("cam-table-row").first();
  const declared = tidewater.locator("td").nth(2);
  await expect(declared).toHaveAttribute("data-label", "Declared");
  expect(
    await declared.evaluate((td) => getComputedStyle(td, "::before").content.replace(/"/g, "")),
  ).toBe("Declared");

  await page.getByTestId("view-pd").click();
  await expect(page.getByTestId("pd-note")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
  expect(await scrollingBoxes(page.getByTestId("pd-note"))).toEqual([]);
});

test("on a laptop the memo's tables keep their columns and fit their boxes", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 900 });
  await openView(page, "cam");
  expect(await scrollingBoxes(page.getByTestId("cam"))).toEqual([]);
  const stacked = await page
    .getByTestId("cam-table")
    .evaluateAll(
      (figures) =>
        figures.filter((f) => getComputedStyle(f.querySelector("table")!).display === "block")
          .length,
    );
  expect(stacked).toBe(0);
});
