// The appraisal workspace (FRD §6): the Overview says what is still needed
// and what waits for a decision; Completeness filters its checklist; links
// to a part of a tab land on it.
import { expect, test } from "@playwright/test";
import { FINDING_ITEM, KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("Overview lists what is still needed and what waits for a decision", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  const needed = page.getByTestId("still-needed");
  await expect(needed).toContainText("KYC of directors");
  await expect(needed).toContainText("Valuation report");
  const waiting = page.getByTestId("waiting-decision");
  await expect(waiting.getByRole("link")).toHaveCount(2);
  await expect(waiting.getByRole("link").first()).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/documents`,
  );
});

test("Completeness filters the checklist by status", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const items = page.getByTestId("checklist-item");
  await expect(items).toHaveCount(9);
  await page.getByTestId("checklist-filter-blocking").click();
  for (const status of await items.evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-status")),
  ))
    expect(["missing", "insufficient", "in_review"]).toContain(status);
  await page.getByTestId("checklist-filter-satisfied").click();
  for (const status of await items.evaluateAll((els) =>
    els.map((e) => e.getAttribute("data-status")),
  ))
    expect(["satisfied", "waived"]).toContain(status);
});

test("a link to the query list lands on it", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.setViewportSize({ width: 1024, height: 700 });
  await page.goto(`/appraisals/${KESTREL}/completeness#queries`);
  await expect(page.getByTestId("query-list")).toBeInViewport();
});

test("an extracted value in review is confirmed from its row", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  const decision = page.locator('[data-testid="field-decision"][data-field="monthly[2].credits"]');
  await decision.getByTestId("field-confirm").click();
  await expect(page.getByText("Decision recorded")).toBeVisible();
  const [call] = api.called("POST", "/api/review/r-field/decision");
  expect(call?.body).toEqual({ decision: "confirm", value: null, reason: null });
});

test("a correction is made beside the source page", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  const decision = page.locator('[data-testid="field-decision"][data-field="monthly[2].credits"]');
  await decision.getByTestId("field-correct").click();
  const viewer = page.getByTestId("evidence-viewer");
  await expect(viewer.getByTestId("viewer-page")).toContainText("7");
  await expect(viewer.getByTestId("viewer-save")).toBeDisabled();
  await viewer.getByTestId("viewer-value-input").fill("41,23,000");
  await viewer.getByTestId("viewer-reason-input").fill("Misread 2 as 0");
  await viewer.getByTestId("viewer-save").click();
  await expect(page.getByText("Decision recorded")).toBeVisible();
  const [call] = api.called("POST", "/api/review/r-field/decision");
  expect(call?.body).toEqual({ decision: "correct", value: 4123000, reason: "Misread 2 as 0" });
});

test("the extracted data is grouped by kind of document", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  await expect(page.getByTestId("field-section-banking")).toContainText("Bank statement");
  await expect(page.getByTestId("field-section-financials")).toContainText("Balance sheet");
});

test("when processing finishes, the rest of the appraisal refreshes", async ({ page }) => {
  const api = new MockApi();
  let calls = 0;
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/progress$`), () => {
    const progress = api.progress(KESTREL);
    calls += 1;
    if (calls <= 2) progress.stages[0]!.status = "in_progress";
    return { json: progress };
  });
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  await expect(page.getByTestId("still-needed")).toBeVisible();
  const before = api.called("GET", `/api/cases/${KESTREL}/checklist`).length;
  await expect.poll(() => calls, { timeout: 15_000 }).toBeGreaterThan(2);
  await expect
    .poll(() => api.called("GET", `/api/cases/${KESTREL}/checklist`).length)
    .toBeGreaterThan(before);
});

test("Cross-verification shows each finding with its sources and their evidence", async ({
  page,
}) => {
  const api = new MockApi();
  api.review.push(structuredClone(FINDING_ITEM));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);
  await expect(page.getByTestId("xv-summary-line")).toContainText("7 discrepancies found");
  const turnover = page.getByTestId("xv-area-turnover");
  await expect(turnover.getByTestId("xv-incomplete").getByRole("heading")).toHaveText(
    "Could not be checked (3)",
  );
  await expect(
    page.getByTestId("xv-area-identity").getByTestId("xv-passed").locator("summary"),
  ).toContainText("Passed (4)");
  // The first card on the board is open; the greatest gap on the board (OB-02, further down) opens
  // with its sources side by side.
  await expect(page.getByTestId("xv-card-fnd-id1")).toHaveAttribute("data-expanded", "true");
  const ob2 = page.getByTestId("xv-card-fnd-ob2");
  await expect(ob2).toHaveAttribute("data-expanded", "false");
  await ob2.getByTestId("xv-card-toggle").click();
  await expect(ob2).toHaveAttribute("data-expanded", "true");
  await expect(ob2).toContainText("ASHWOOD FINSERV");
  await expect(ob2.locator('[data-testid^="xv-column-"][data-differs]')).toHaveCount(2);
  await ob2.getByTestId("xv-column-instalments").getByTestId("xv-trace").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("7");
  await page.keyboard.press("Escape");

  await expect(
    turnover.locator('[data-testid="xv-incomplete-row"][data-rule="TO-01"]'),
  ).toContainText("8 of 12 months");
  // Each area's facts behind its checks.
  const accounts = page.getByTestId("xv-area-accounts").getByTestId("xv-facts");
  await accounts.locator("summary").click();
  await expect(accounts.getByTestId("facts-credits")).toContainText("Loan disbursal");
  const obligations = page.getByTestId("xv-area-obligations").getByTestId("xv-facts");
  await obligations.locator("summary").click();
  await expect(obligations.getByTestId("facts-obligations")).toContainText("ASHWOOD FINSERV");
});

test("a finding is accepted as valid, or dismissed as not valid, each with a comment", async ({
  page,
}) => {
  const api = new MockApi();
  api.review.push(structuredClone(FINDING_ITEM));
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/cross-verification`);
  const ob2 = page.getByTestId("xv-card-fnd-ob2");
  await ob2.getByTestId("xv-card-toggle").click();
  await ob2.getByTestId("xv-decision-dismiss").check();
  await expect(ob2.getByTestId("xv-save-decision")).toBeDisabled();
  await ob2.getByTestId("xv-comment").fill("Instalments are for an equipment lease");
  await ob2.getByTestId("xv-save-decision").click();
  await expect(page.getByText("Decision recorded")).toBeVisible();
  const [call] = api.called(
    "POST",
    `/api/cases/${KESTREL}/cross-verification/findings/fnd-ob2/decision`,
  );
  expect(call?.body).toEqual({
    decision: "dismiss",
    comment: "Instalments are for an equipment lease",
  });
  await expect(ob2.getByTestId("xv-recorded-decision")).toContainText("Dismissed");
  // Its review item is decided with it: dismissed is waived, with the comment as the reason.
  expect(api.review.find((r) => r.id === "r-finding")).toMatchObject({
    status: "decided",
    decision: "waive",
    reason: "Instalments are for an equipment lease",
  });

  const ba1 = page.getByTestId("xv-card-fnd-ba1");
  await ba1.getByTestId("xv-card-toggle").click();
  await ba1.getByTestId("xv-decision-accept").check();
  await ba1.getByTestId("xv-comment").fill("A valid finding: the statement is requested.");
  await ba1.getByTestId("xv-save-decision").click();
  await expect(ba1.getByTestId("xv-recorded-decision")).toContainText("Accepted");
});

test("a blocking cross-check finding shows on the Completeness summary", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  await expect(page.getByTestId("blocking-findings")).toHaveText(
    "2 blocking cross-check finding(s) to decide →",
  );
  await page.getByTestId("blocking-findings").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/cross-verification$`));
  await expect(page.getByTestId("xv-banner")).toContainText("2 serious discrepancies");
});

test("Policy lists every norm with its required and actual value, deviations first", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/policy`);
  await expect(page.getByTestId("policy-summary-line")).toContainText("3 deviations");
  // Each family's card leads with its deviations.
  await expect(
    page.getByTestId("policy-group-card-ratios").getByTestId("policy-highlight").first(),
  ).toContainText("Debt / equity");
  await expect(
    page.getByTestId("policy-group-card-eligibility").getByTestId("policy-highlight").first(),
  ).toContainText("Profit in the latest year");
  const de = page.locator('[data-testid="norm"][data-norm="FR-05"]');
  await expect(de).toContainText("at most 2.00x");
  await expect(de.getByTestId("norm-actual")).toHaveText("3.00x");
  await de.getByTestId("norm-input").first().getByRole("button").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("4");
  await page.keyboard.press("Escape");
  const rank = page.locator('[data-testid="norm"][data-norm="EL-02"]');
  await expect(rank.getByTestId("norm-missing")).toHaveText(
    "Cannot evaluate: Commercial bureau rank not on file.",
  );
});

test("Financials: the spread and the working-capital assessment, each figure cited", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/policy`);
  const financials = page.getByTestId("financials");
  await expect(financials.getByTestId("spread-interim")).toBeVisible();
  await financials.getByTestId("financials-tab-profit_and_loss").click();
  await financials
    .locator('[data-testid="spread-row"][data-row="revenue_from_operations"]')
    .getByTestId("spread-figure")
    .click();
  await financials.getByTestId("spread-source-open").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("4");
  await page.keyboard.press("Escape");
  await expect(financials.getByTestId("wc-verdict")).toContainText("INR 6.00 cr");
});

test("Outputs: the draft CAM and the PD note, each figure cited", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/outputs`);
  await expect(page.getByTestId("view-spread")).toHaveCount(0);
  await page.getByTestId("view-cam").click();
  const cam = page.getByTestId("cam");
  const financials = cam.locator('[data-section="financials"]');
  await expect(financials.getByTestId("cam-section-title")).toHaveText("5. Financial performance");
  await financials.getByTestId("cam-paragraph").first().getByTestId("citation").first().click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("3");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("cam-summary")).toContainText("Findings (6)");
  await expect(page.getByTestId("cam-summary")).toContainText("Deviations from policy (3)");
  // A norm that could not be assessed is listed, not left out (F-23).
  await expect(page.getByTestId("cam-summary")).toContainText("Norms not assessed (3)");
  await expect(page.getByTestId("cam-recommendation")).toContainText("For credit to complete.");

  await page.getByTestId("view-pd").click();
  const questions = page.getByTestId("pd-question");
  await expect(questions).toHaveCount(11);
  await expect(questions.first()).toContainText("Which PAN is the company's");
  await expect(questions.first().getByRole("link")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/cross-verification?finding=fnd-id1`,
  );
  await expect(
    page.locator('[data-testid="pd-question"][data-rule="FR-05"]').getByRole("link"),
  ).toHaveAttribute("href", `/appraisals/${KESTREL}/policy?norm=FR-05`);
  // A bureau cross-check's question goes to the Cross-checks tab, as the engine routes it.
  await expect(
    page.locator('[data-testid="pd-question"][data-rule="OB-01"]').getByRole("link"),
  ).toHaveAttribute("href", `/appraisals/${KESTREL}/cross-verification?finding=fnd-ob1`);
});
