// Policy norms and the approving authority (FRD TC-26 / F-20 = test plan TC-24; FRD TC-27 /
// F-21 = test plan TC-25). An overview card per family of norms says where it stands, with the
// engine's counts and key norms, and one more says who must approve; below, each family's norms
// with the norm, the actual value and its source, then the authority with the rule applied. The
// norms and the matrix are provisional until RBL supplies its own, and the screen says so.
import { expect, test, type Locator, type Page } from "@playwright/test";
import type { ApprovingAuthority, PolicyAssessment } from "../src/api/types";
import { APPROVAL, KESTREL, MANAGER, POLICY, SAFFRON, comparison } from "./fixtures/data";
import { MockApi, scrollsSideways, signedIn } from "./support/api";

const FAMILIES = ["eligibility", "ratios", "documentation", "security_cover"] as const;

const groupCard = (page: Page, family: string) => page.getByTestId(`policy-group-card-${family}`);
const authorityCard = (page: Page) => page.getByTestId("policy-authority-card");
const section = (page: Page, family: string) => page.getByTestId(`policy-group-${family}`);
const norm = (page: Page, id: string) => page.locator(`[data-testid="norm"][data-norm="${id}"]`);
const keyNorms = (card: Locator) => card.getByTestId("policy-highlight");
const keyNorm = (card: Locator, id: string) =>
  card.locator(`[data-testid="policy-highlight"][data-norm="${id}"]`);

async function openPolicy(page: Page, api = new MockApi(), caseId = KESTREL) {
  await signedIn(page, api);
  await page.goto(`/appraisals/${caseId}/policy`);
  await expect(page.getByTestId("policy-overview")).toBeVisible();
}

/** Each overview card's position and size, in order. */
async function cardBoxes(page: Page) {
  return page.getByTestId("policy-overview").evaluate((el) =>
    [...el.children].map((c) => {
      const box = c.getBoundingClientRect();
      return { x: Math.round(box.x), y: Math.round(box.y), w: box.width, h: box.height };
    }),
  );
}

test("TC-24: the header says where the case stands against the norms", async ({ page }) => {
  await openPolicy(page);
  const header = page.getByTestId("policy-header");
  await expect(header).toContainText(`Appraisal ${KESTREL} · Policy checks`);
  await expect(header.getByRole("heading", { level: 2 })).toHaveText(
    "Policy norms and approving authority",
  );
  // The engine's counts, the year the figures come from, and that the norms are provisional.
  await expect(page.getByTestId("policy-summary-line")).toHaveText(
    "3 deviations · 3 cannot be evaluated · 1 passed · FY 2025-26 · provisional norms",
  );
  await expect(page.getByTestId("policy-interim")).toHaveText(
    "These norms are interim proposals until RBL's own policy norms are supplied.",
  );
});

test("TC-24: a card per family of norms, then the authority, each with the engine's counts", async ({
  page,
}) => {
  await openPolicy(page);
  const cards = page.getByTestId("policy-overview").locator(":scope > *");
  await expect(cards).toHaveCount(5);
  for (const [i, family] of FAMILIES.entries())
    await expect(cards.nth(i)).toHaveAttribute("data-testid", `policy-group-card-${family}`);
  await expect(cards.nth(4)).toHaveAttribute("data-testid", "policy-authority-card");

  const eligibility = groupCard(page, "eligibility");
  await expect(eligibility).toHaveAttribute("data-status", "deviation");
  await expect(eligibility.getByTestId("policy-group-open-section")).toHaveAccessibleName(
    "Eligibility (A norm deviates)",
  );
  await expect(eligibility).toContainText("Whether the borrower qualifies for the loan at all.");
  await expect(eligibility.getByTestId("policy-group-deviations")).toHaveText("1");
  await expect(eligibility).toContainText("1 deviation");
  await expect(eligibility.getByTestId("policy-group-others")).toHaveText(
    "1 cannot be evaluated · 0 passed",
  );

  const ratios = groupCard(page, "ratios");
  await expect(ratios).toHaveAttribute("data-status", "deviation");
  await expect(ratios.getByTestId("policy-group-open-section")).toHaveText(/^Financial ratios/);
  await expect(ratios.getByTestId("policy-group-deviations")).toHaveText("1");
  await expect(ratios.getByTestId("policy-group-others")).toHaveText(
    "2 cannot be evaluated · 1 passed",
  );

  const documentation = groupCard(page, "documentation");
  await expect(documentation.getByTestId("policy-group-deviations")).toHaveText("1");
  await expect(documentation.getByTestId("policy-group-others")).toHaveText("0 passed");

  // No security-cover norm yet: the card says so, with no count.
  const security = groupCard(page, "security_cover");
  await expect(security).toHaveAttribute("data-status", "no_norms");
  await expect(security.getByTestId("policy-group-open-section")).toHaveAccessibleName(
    "Security cover (No norm yet)",
  );
  await expect(security.getByTestId("policy-group-none")).toHaveText("No norm yet");
  await expect(security.getByTestId("policy-group-pending")).toHaveText(
    "No security-cover norm can be evaluated yet.",
  );
  await expect(security.getByTestId("policy-group-deviations")).toHaveCount(0);
  await expect(keyNorms(security)).toHaveCount(0);
});

test("TC-24: each family card shows the engine's key norms, actual against required", async ({
  page,
}) => {
  await openPolicy(page);
  // In the engine's order: deviations, then the norms that cannot be evaluated, then passed.
  const ratios = groupCard(page, "ratios");
  await expect(keyNorms(ratios)).toHaveCount(3);
  expect(await keyNorms(ratios).evaluateAll((els) => els.map((e) => e.dataset["norm"]))).toEqual([
    "FR-05",
    "FR-04",
    "FR-06",
  ]);
  const de = keyNorm(ratios, "FR-05");
  await expect(de).toHaveAttribute("data-outcome", "deviation");
  await expect(de.getByTestId("policy-highlight-label")).toHaveText("Debt / equity");
  await expect(de.getByTestId("policy-highlight-fact")).toHaveText("3.00x · at most 2.00x");
  // The deviating value in red; what it is held against beside it.
  await expect(de.getByTestId("policy-highlight-value")).toHaveClass(/text-destructive/);
  await expect(de.getByTestId("policy-highlight-required")).toHaveText("at most 2.00x");
  await expect(de.getByTestId("policy-highlight-note")).toHaveCount(0);

  // A norm that cannot be evaluated says what is missing, or why.
  const coverage = keyNorm(ratios, "FR-04");
  await expect(coverage).toHaveAttribute("data-outcome", "cannot_evaluate");
  await expect(coverage.getByTestId("policy-highlight-fact")).toHaveText(
    "Cannot evaluate · at least 2.50x",
  );
  await expect(coverage.getByTestId("policy-highlight-value")).not.toHaveClass(/text-destructive/);
  await expect(coverage.getByTestId("policy-highlight-note")).toHaveText("Finance costs is zero");
  await expect(keyNorm(ratios, "FR-06").getByTestId("policy-highlight-note")).toHaveText(
    "Waiting for review of Trade receivables",
  );

  const eligibility = groupCard(page, "eligibility");
  await expect(keyNorms(eligibility)).toHaveCount(2);
  await expect(keyNorm(eligibility, "EL-04").getByTestId("policy-highlight-fact")).toHaveText(
    "INR -40.00 lakh · at least INR 0",
  );
  await expect(keyNorm(eligibility, "EL-02").getByTestId("policy-highlight-note")).toHaveText(
    "Commercial bureau rank not on file",
  );
  await expect(
    keyNorm(groupCard(page, "documentation"), "DOC-01").getByTestId("policy-highlight-fact"),
  ).toHaveText("2 · at most 0");
});

test("TC-24: the cards render the engine's groups and counts as given", async ({ page }) => {
  const api = new MockApi();
  const counts = (d: number, c: number, p: number, n = 0) => ({
    deviations: d,
    cannot_evaluate: c,
    passed: p,
    not_applicable: n,
  });
  api.policy.set(KESTREL, {
    ...POLICY,
    norms: POLICY.norms.filter((n) => n.family !== "documentation"),
    counts: counts(0, 2, 5, 1),
    groups: [
      { family: "eligibility", norms: 5, counts: counts(0, 0, 4, 1), status: "clear" },
      {
        family: "ratios",
        norms: 3,
        counts: counts(0, 2, 1),
        status: "cannot_evaluate",
        highlights: ["FR-04", "FR-01"],
      },
      { family: "documentation", norms: 0, counts: counts(0, 0, 0), status: "no_norms" },
    ],
  } satisfies PolicyAssessment);
  await openPolicy(page, api);
  await expect(page.getByTestId("policy-summary-line")).toHaveText(
    "2 cannot be evaluated · 5 passed · 1 not applicable · FY 2025-26 · provisional norms",
  );
  // Only the families the engine sent, then the authority.
  await expect(page.getByTestId("policy-overview").locator(":scope > *")).toHaveCount(4);
  await expect(groupCard(page, "security_cover")).toHaveCount(0);

  const eligibility = groupCard(page, "eligibility");
  await expect(eligibility).toHaveAttribute("data-status", "clear");
  await expect(eligibility.getByTestId("policy-group-open-section")).toHaveAccessibleName(
    "Eligibility (Every norm met)",
  );
  await expect(eligibility.getByTestId("policy-group-deviations")).toHaveText("0");
  await expect(eligibility).toContainText("0 deviations");
  await expect(eligibility.getByTestId("policy-group-others")).toHaveText(
    "4 passed · 1 not applicable",
  );
  await expect(keyNorms(eligibility)).toHaveCount(0);

  const ratios = groupCard(page, "ratios");
  await expect(ratios).toHaveAttribute("data-status", "cannot_evaluate");
  await expect(ratios.getByTestId("policy-group-open-section")).toHaveAccessibleName(
    "Financial ratios (A norm cannot be evaluated)",
  );
  await expect(ratios.getByTestId("policy-group-others")).toHaveText(
    "2 cannot be evaluated · 1 passed",
  );
  // The key norms the engine picked, and no others.
  expect(await keyNorms(ratios).evaluateAll((els) => els.map((e) => e.dataset["norm"]))).toEqual([
    "FR-04",
    "FR-01",
  ]);
  const passed = keyNorm(ratios, "FR-01");
  await expect(passed).toHaveAttribute("data-outcome", "pass");
  await expect(passed.getByTestId("policy-highlight-fact")).toHaveText("1.50x · at least 1.20x");
  await expect(passed.getByTestId("policy-highlight-value")).not.toHaveClass(/text-destructive/);

  // The sections follow the same groups; a family the engine sent without norms says so.
  await expect(section(page, "documentation").getByTestId("family-pending")).toHaveText(
    "No documentation norm is configured.",
  );
  await expect(section(page, "ratios").getByTestId("policy-group-counts")).toHaveText(
    "3 norms · 2 cannot be evaluated · 1 passed",
  );
});

test("TC-24: a card opens its section and focuses its heading; a key norm opens its row", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await openPolicy(page);
  const documentation = section(page, "documentation");
  const heading = documentation.getByRole("heading", { level: 2, name: "Documentation" });
  await expect(heading).not.toBeInViewport();
  // Anywhere on the card outside its key norms: here, on its count.
  const card = groupCard(page, "documentation");
  const onCount = await card.evaluate((el) => {
    const box = el.getBoundingClientRect();
    const count = el.querySelector('[data-testid="policy-group-deviations"]')!;
    const c = count.getBoundingClientRect();
    return { x: c.x - box.x + c.width / 2, y: c.y - box.y + c.height / 2 };
  });
  await card.click({ position: onCount });
  await expect(heading).toBeInViewport();
  await expect(heading).toBeFocused();

  // By keyboard too: the authority's card opens the authority's section.
  const open = authorityCard(page).getByTestId("policy-authority-open-section");
  await expect(open).toHaveText("Approving authority");
  await open.focus();
  await page.keyboard.press("Enter");
  const authorityHeading = page
    .getByTestId("policy-authority")
    .getByRole("heading", { level: 2, name: "Approving authority" });
  await expect(authorityHeading).toBeFocused();
  await expect(authorityHeading).toBeInViewport();

  // A key norm opens its norm's row, marked until the focus moves on.
  await page.getByTestId("policy-header").scrollIntoViewIfNeeded();
  const cycle = norm(page, "FR-06");
  await expect(cycle).not.toBeInViewport();
  await keyNorm(groupCard(page, "ratios"), "FR-06").click();
  await expect(cycle).toBeInViewport();
  await expect(cycle).toBeFocused();
  await expect(cycle).toHaveAttribute("data-target", "true");
  await page.keyboard.press("Tab");
  await expect(cycle).not.toHaveAttribute("data-target", "true");
});

test("TC-24: a link to a norm opens the page at its row once the norms and the authority have loaded", async ({
  page,
}) => {
  const api = new MockApi();
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = () => resolve();
  });
  api.on("GET", /\/approving-authority$/, async () => {
    await held;
    return { json: APPROVAL };
  });
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/policy?norm=DOC-01`);
  await expect(page.getByTestId("policy-overview")).toBeVisible();
  // Not while the authority's card above the rows is still loading: it would move them.
  const blocking = norm(page, "DOC-01");
  await expect(blocking).not.toBeFocused();
  release();
  await expect(blocking).toBeFocused();
  await expect(blocking).toBeInViewport();
  await expect(blocking).toHaveAttribute("data-target", "true");
});

test("TC-24: each family's norms with the required and actual value and their sources", async ({
  page,
}) => {
  await openPolicy(page);
  const ids = (family: string) =>
    section(page, family)
      .getByTestId("norm")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-norm")));
  // Each family's section holds its norms, in the engine's order.
  expect(await ids("eligibility")).toEqual(["EL-02", "EL-04"]);
  expect(await ids("ratios")).toEqual(["FR-05", "FR-01", "FR-04", "FR-06"]);
  expect(await ids("documentation")).toEqual(["DOC-01"]);
  await expect(section(page, "eligibility")).toHaveAttribute("data-status", "deviation");
  await expect(section(page, "eligibility").getByTestId("policy-group-counts")).toHaveText(
    "2 norms · 1 deviation · 1 cannot be evaluated",
  );
  await expect(section(page, "ratios").getByTestId("policy-group-counts")).toHaveText(
    "4 norms · 1 deviation · 2 cannot be evaluated · 1 passed",
  );
  await expect(section(page, "documentation").getByTestId("policy-group-counts")).toHaveText(
    "1 norm · 1 deviation",
  );
  await expect(section(page, "security_cover").getByTestId("policy-group-counts")).toHaveText(
    "No norm yet",
  );
  await expect(section(page, "security_cover").getByTestId("family-pending")).toHaveText(
    "No security-cover norm can be evaluated: no valuation report is among the document types in scope.",
  );
  // The norm filter is gone: every norm shows, each marked provisional.
  await expect(page.locator('[data-testid^="norms-filter-"]')).toHaveCount(0);
  const norms = page.getByTestId("norm");
  await expect(norms).toHaveCount(7);
  for (const n of await norms.all()) await expect(n).toContainText("Provisional norm");

  const de = norm(page, "FR-05");
  await expect(de).toHaveAttribute("data-outcome", "deviation");
  await expect(de.locator(".sr-only")).toHaveText("Deviation");
  await expect(de).toContainText("FR-05");
  await expect(de).toContainText("Financial norms");
  await expect(de).toContainText("at most 2.00x");
  await expect(de.getByTestId("norm-actual")).toHaveText("3.00x");
  // The source: each figure opens the page it was read from.
  await de.getByTestId("norm-input").first().getByRole("button").click();
  await expect(page.getByTestId("evidence-viewer").getByTestId("viewer-page")).toContainText("4");
  await page.keyboard.press("Escape");
  await de.getByTestId("norm-details").locator("summary").click();
  // How it was calculated: the expression, then the same with the figures read, and the test.
  await expect(de.getByTestId("norm-substituted")).toContainText("Total borrowings / Net worth");
  await expect(de.getByTestId("norm-test")).toContainText("not satisfied");
  await expect(de.getByTestId("norm-definition")).toContainText("Total debt ÷ Tangible net worth");
  await expect(de.getByTestId("norm-note")).toContainText("Interim threshold");

  // A loss keeps its sign.
  const profit = norm(page, "EL-04");
  await expect(profit.getByTestId("norm-actual")).toHaveText("INR -40.00 lakh");
  await expect(profit.getByTestId("norm-input")).toContainText("INR -40.00 lakh");

  // Why a norm could not be assessed, in words.
  await expect(norm(page, "EL-02").getByTestId("norm-missing")).toHaveText(
    "Cannot evaluate: Commercial bureau rank not on file.",
  );
  await expect(norm(page, "FR-04").getByTestId("norm-reason")).toHaveText(
    "Cannot evaluate: Finance costs is zero.",
  );
  const cycle = norm(page, "FR-06");
  await expect(cycle.getByTestId("norm-reason")).toHaveText(
    "Cannot evaluate until Trade receivables is reviewed.",
  );
  await expect(cycle.getByTestId("norm-input-awaiting")).toHaveText("Awaiting review");

  // The open blocking items come from the checklist, and link to it.
  await expect(norm(page, "DOC-01").getByTestId("norm-input-checklist")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/completeness`,
  );
});

test("TC-24: a ratio over a negative net worth is a deviation with no meaningful value", async ({
  page,
}) => {
  await openPolicy(page, new MockApi(), SAFFRON);
  const tol = norm(page, "FR-02");
  await expect(tol).toHaveAttribute("data-outcome", "deviation");
  await expect(tol.getByTestId("norm-actual")).toHaveText("Unbounded");
  await expect(tol.getByTestId("norm-reason")).toHaveText(
    "Net worth is zero or negative: the ratio has no meaningful value.",
  );
  await expect(
    keyNorm(groupCard(page, "ratios"), "FR-02").getByTestId("policy-highlight-fact"),
  ).toHaveText("Unbounded · at most 3.00x");
  await expect(norm(page, "EL-03").getByTestId("norm-input")).toContainText("INR -4.00 cr");
  // At phone width the long values wrap: the page never scrolls sideways.
  await page.setViewportSize({ width: 375, height: 800 });
  await expect(tol).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
  // No matrix published for this case's version: the norms still show.
  await expect(authorityCard(page)).toHaveAttribute("data-status", "not_published");
  await expect(authorityCard(page).getByTestId("policy-authority-unavailable")).toHaveText(
    "No approval matrix published yet",
  );
  await expect(page.getByTestId("authority-not-published")).toContainText(
    "The approval matrix is not part of the published configuration.",
  );
});

test("TC-25: the authority's card says who must approve, at least, and why", async ({ page }) => {
  await openPolicy(page);
  const card = authorityCard(page);
  await expect(card).toHaveAttribute("data-status", "determined");
  await expect(card.getByTestId("policy-authority-required")).toHaveText("Regional Credit Head");
  await expect(card.getByTestId("policy-authority-level")).toHaveText("Level 2");
  await expect(card.getByTestId("policy-authority-provisional")).toHaveText("Provisional matrix");
  // Norms remain to be assessed, so it is a lower bound; as deviations they would not raise it.
  await expect(card.getByTestId("policy-authority-at-least")).toHaveText("At least");
  const rise = card.getByTestId("policy-authority-rise");
  await expect(rise).toHaveAttribute("data-rises", "false");
  await expect(rise).toHaveText("Would not rise even if EL-02, FR-04 and FR-06 deviated");
  // The amount's authority and each deviation step, the one that decides in bold.
  await expect(card.getByTestId("policy-authority-amount")).toHaveText(
    "Amount: Credit Officer (level 1)",
  );
  const deviations = card.getByTestId("policy-authority-deviations");
  await expect(deviations).toHaveText(
    "Deviations: Eligibility +1 level, at least Regional Credit Head · Financial norms +1 level · Documentation +1 level",
  );
  await expect(deviations.locator('[data-governs="true"]')).toHaveText(
    "Eligibility +1 level, at least Regional Credit Head",
  );
});

test("TC-25: the authority required is shown with the rule applied", async ({ page }) => {
  await openPolicy(page);
  const panel = page.getByTestId("policy-authority").getByTestId("approving-authority");
  await expect(panel.getByTestId("authority-required")).toContainText(
    "Required: Regional Credit Head",
  );
  await expect(panel.getByTestId("authority-required")).toContainText("Level 2");
  await expect(panel.getByTestId("authority-provisional")).toHaveText("Provisional matrix");
  await expect(panel).toContainText("INR 50.00 lakh requested · Working capital, Term loan");

  const steps = panel.getByTestId("authority-step");
  await expect(steps).toHaveCount(5);
  await expect(panel.locator('[data-testid="authority-step"][data-governs="true"]')).toHaveCount(1);
  const governing = panel.locator('[data-testid="authority-step"][data-governs="true"]');
  await expect(governing).toHaveAttribute("data-rule", "deviations.eligibility");
  await expect(governing).toContainText(
    "Eligibility deviation (EL-04): 1 level(s) above the amount authority, and at least Regional Credit Head, so Regional Credit Head",
  );
  await expect(governing).toContainText("Decides");
  await expect(steps.first()).toHaveText(
    "Working capital: INR 50.00 lakh is up to INR 2.00 cr, so Credit Officer",
  );
  await expect(panel.getByTestId("authority-lower-bound")).toHaveText(
    "3 norm(s) could not be evaluated (Commercial bureau rank, Interest coverage, Working-capital cycle); as deviations they would not change the authority.",
  );

  // A norm id in a step leads to the norm's row.
  await panel
    .locator('[data-testid="authority-step"][data-rule="deviations.documentation"]')
    .getByTestId("authority-norm")
    .click();
  await expect(norm(page, "DOC-01")).toBeInViewport();
  await expect(norm(page, "DOC-01")).toBeFocused();

  // The analyst has no way to the comparison (the API refuses it too).
  await expect(panel.getByTestId("authority-compare")).toHaveCount(0);
});

test("TC-25: the authority may rise once the unassessed norms are known", async ({ page }) => {
  const api = new MockApi();
  api.authority.set(KESTREL, {
    ...APPROVAL,
    could_rise_to: { key: "zonal_credit_committee", label: "Zonal Credit Committee", level: 3 },
  });
  await openPolicy(page, api);
  const rise = authorityCard(page).getByTestId("policy-authority-rise");
  await expect(rise).toHaveAttribute("data-rises", "true");
  await expect(rise).toHaveText(
    "Would rise to Zonal Credit Committee (level 3) if EL-02, FR-04 and FR-06 deviated",
  );
  await expect(page.getByTestId("authority-lower-bound")).toHaveText(
    "3 norm(s) could not be evaluated (Commercial bureau rank, Interest coverage, Working-capital cycle). If they are deviations, the matrix would require Zonal Credit Committee.",
  );
});

test("TC-25: once every norm is assessed the authority is not a lower bound", async ({ page }) => {
  const api = new MockApi();
  api.authority.set(KESTREL, {
    ...APPROVAL,
    lower_bound: false,
    unevaluated: [],
    unevaluated_labels: [],
    could_rise_to: null,
    provisional: false,
    steps: APPROVAL.steps.filter((s) => s.kind === "amount"),
  } satisfies ApprovingAuthority);
  await openPolicy(page, api);
  const card = authorityCard(page);
  await expect(card.getByTestId("policy-authority-required")).toHaveText("Regional Credit Head");
  await expect(card.getByTestId("policy-authority-at-least")).toHaveCount(0);
  await expect(card.getByTestId("policy-authority-rise")).toHaveCount(0);
  await expect(card.getByTestId("policy-authority-provisional")).toHaveCount(0);
  await expect(card.getByTestId("policy-authority-deviations")).toHaveText(
    "No deviation raises it",
  );
});

test("TC-25: without a published matrix the norms still show", async ({ page }) => {
  const api = new MockApi();
  api.authority.delete(KESTREL);
  await openPolicy(page, api);
  await expect(authorityCard(page)).toHaveAttribute("data-status", "not_published");
  await expect(authorityCard(page).getByTestId("policy-authority-unavailable")).toHaveText(
    "No approval matrix published yet",
  );
  await expect(authorityCard(page).getByTestId("policy-authority-provisional")).toHaveCount(0);
  await expect(page.getByTestId("authority-not-published")).toBeVisible();
  await expect(page.getByTestId("norm")).toHaveCount(7);
  // Its card still opens the section that says so.
  await authorityCard(page).getByTestId("policy-authority-open-section").click();
  await expect(page.getByTestId("authority-not-published")).toBeInViewport();
});

test("TC-25: an authority that cannot be determined says why", async ({ page }) => {
  const api = new MockApi();
  api.authority.set(KESTREL, {
    ...APPROVAL,
    outcome: "cannot_determine",
    required: null,
    reason: "no_product",
    unmapped_facilities: ["bank_guarantee"],
    steps: [],
    lower_bound: false,
    unevaluated: [],
    unevaluated_labels: [],
    could_rise_to: null,
  } satisfies ApprovingAuthority);
  await openPolicy(page, api);
  const card = authorityCard(page);
  await expect(card).toHaveAttribute("data-status", "cannot_determine");
  await expect(card.getByTestId("policy-authority-unavailable")).toHaveText("Cannot be determined");
  await expect(card).toContainText("no product in the matrix covers Bank guarantee");
  await expect(page.getByTestId("authority-cannot-determine")).toContainText(
    "no product in the matrix covers Bank guarantee",
  );
});

test("TC-25: the reviewer is pointed to the comparison, which alone shows RBL's record", async ({
  page,
}) => {
  const api = new MockApi();
  api.comparisons.set(KESTREL, comparison());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/policy`);
  const link = page.getByTestId("authority-compare");
  await expect(link).toHaveAttribute("href", `/appraisals/${KESTREL}/comparison`);
  // Even for the reviewer, the Policy tab shows only the required authority, never RBL's record.
  await expect(page.getByTestId("approving-authority")).toContainText("Regional Credit Head");
  await expect(authorityCard(page)).toContainText("Regional Credit Head");
  await expect(page.getByText("Zonal Credit Committee")).toHaveCount(0);
  await expect(page.getByText("Sanction note p.1")).toHaveCount(0);
  expect(api.called("GET", `/api/cases/${KESTREL}/comparison`)).toHaveLength(0);
  await link.click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/comparison$`));
  await expect(page.getByTestId("comparison-counts")).toBeVisible();
});

test.describe("at 1366 px, beside the side menu", () => {
  test.use({ viewport: { width: 1366, height: 768 } });

  test("the five cards share a row at one height, and nothing scrolls sideways", async ({
    page,
  }) => {
    await openPolicy(page);
    await expect(page.getByTestId("case-nav")).toBeVisible();
    const boxes = await cardBoxes(page);
    expect(boxes).toHaveLength(5);
    expect(new Set(boxes.map((b) => b.y)).size).toBe(1);
    expect(new Set(boxes.map((b) => b.h)).size).toBe(1);
    expect(await scrollsSideways(page)).toBe(false);
    for (const details of await page.getByTestId("norm-details").all())
      await details.locator("summary").click();
    expect(await scrollsSideways(page)).toBe(false);
  });
});

test.describe("on a narrower screen", () => {
  test.use({ viewport: { width: 1024, height: 768 } });

  test("three cards a row, the authority's spanning two beside the last family", async ({
    page,
  }) => {
    await openPolicy(page);
    const [a, b, c, d, e] = await cardBoxes(page);
    expect(new Set([a!.y, b!.y, c!.y]).size).toBe(1);
    expect(d!.y).toBe(e!.y);
    expect(d!.y).toBeGreaterThan(a!.y);
    expect(e!.w).toBeGreaterThan(d!.w * 1.9);
    expect(await scrollsSideways(page)).toBe(false);
  });
});

test.describe("at phone width", () => {
  test.use({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });

  test("the cards stack, one under another, without scrolling sideways", async ({ page }) => {
    await openPolicy(page);
    const boxes = await cardBoxes(page);
    const tops = boxes.map((b) => b.y);
    expect([...tops].sort((x, y) => x - y)).toEqual(tops);
    expect(new Set(tops).size).toBe(5);
    expect(new Set(boxes.map((b) => b.x)).size).toBe(1);
    expect(await scrollsSideways(page)).toBe(false);
    for (const details of await page.getByTestId("norm-details").all())
      await details.locator("summary").click();
    expect(await scrollsSideways(page)).toBe(false);
    // A card still opens its section.
    await groupCard(page, "ratios").getByTestId("policy-group-open-section").click();
    await expect(section(page, "ratios").getByRole("heading", { level: 2 })).toBeFocused();
  });
});
