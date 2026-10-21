// The cross-verification board, the Cross-checks tab (FRD F-19, F-16, F-14): every source lined
// up against every other, by area. An overview card per area (identity, turnover, bank accounts,
// existing obligations) says where it stands and opens its section; each section holds the
// area's discrepancies ranked by credit impact within the area, each with its sources side by
// side, the gap on each leg, the rows and pages behind every figure, and a decision with a
// comment; then the area's checks that could not run, those that passed, and the facts behind
// them. Submission is blocked while a blocking discrepancy is open. The board is the engine's
// view: the screen ranks, measures, counts and decides nothing itself.
import { expect, test, type Locator, type Page } from "@playwright/test";
import type { SessionUser, XvItem } from "../src/api/types";
import {
  ANALYST,
  DOCUMENTS,
  ESCALATED_ITEM,
  FINDING_ITEM,
  KESTREL,
  MANAGER,
  SAFFRON,
  XV_DECIDED_AT,
  XV_DOCUMENTS,
  XV_DOCUMENT_TYPES,
  XV_RULES,
  kestrelBoard,
  xvColumn,
  xvDecision,
  xvFinding,
  xvItem,
  xvSide,
  xvView,
} from "./fixtures/data";
import { MockApi, scrollsSideways, showArea, showAreaOf, signedIn } from "./support/api";

// Times read as the bank's users see them, in India.
test.use({ timezoneId: "Asia/Kolkata" });

const BOARD = `/appraisals/${KESTREL}/cross-verification`;
const AREAS = ["identity", "turnover", "accounts", "obligations"];
const decisionPath = (id: string) =>
  `/api/cases/${KESTREL}/cross-verification/findings/${id}/decision`;

const card = (page: Page, id: string) => page.getByTestId(`xv-card-${id}`);
const areaCard = (page: Page, area: string) => page.getByTestId(`xv-area-card-${area}`);
const section = (page: Page, area: string) => page.getByTestId(`xv-area-${area}`);
const rules = (rows: Locator) => rows.evaluateAll((els) => els.map((e) => e.dataset["rule"]));
const outcomes = (rows: Locator) => rows.evaluateAll((els) => els.map((e) => e.dataset["outcome"]));
const testIds = (els: Locator) =>
  els.evaluateAll((all) => all.map((e) => e.getAttribute("data-testid")));
/** An area card's key figures, in order. */
const keyFigures = (page: Page, area: string) =>
  areaCard(page, area).getByTestId("xv-area-highlight");

async function openBoard(page: Page, api = new MockApi(), user: SessionUser = ANALYST) {
  // The documents the board's evidence points to, each with its configured type.
  api.documents.set(KESTREL, [...DOCUMENTS, ...XV_DOCUMENTS]);
  api.documentTypes = XV_DOCUMENT_TYPES;
  await signedIn(page, api, user);
  await page.goto(BOARD);
  await expect(page.getByTestId("xv-overview")).toBeVisible();
  return api;
}

/** Select a turnover comparison: its card or check shows beside the Figures compared list. */
async function pick(page: Page, id: string): Promise<void> {
  const row = page.locator(`[data-testid="xv-figure-row"][data-finding="${id}"]`);
  await showAreaOf(page, row);
  if ((await row.getAttribute("data-selected")) !== "true")
    await row.getByTestId("xv-figure-select").click();
}

async function expand(page: Page, id: string): Promise<Locator> {
  const c = card(page, id);
  await expect(page.getByTestId("xv-overview")).toBeVisible();
  // A turnover discrepancy's card is beside the figures only while its comparison is selected.
  if ((await c.count()) === 0) await pick(page, id);
  await showAreaOf(page, c);
  if ((await c.getAttribute("data-expanded")) !== "true")
    await c.getByTestId("xv-card-toggle").click();
  await expect(c).toHaveAttribute("data-expanded", "true");
  return c;
}

async function decide(
  page: Page,
  id: string,
  decision: "accept" | "dismiss" | "escalate",
  comment: string,
): Promise<Locator> {
  const c = await expand(page, id);
  await c.getByTestId(`xv-decision-${decision}`).check();
  await c.getByTestId("xv-comment").fill(comment);
  await c.getByTestId("xv-save-decision").click();
  return c;
}

/** Kestrel's board with its items changed (`change` returns the items to keep), assembled as
 * the engine would assemble it. */
function boardWith(change: (items: XvItem[]) => XvItem[]) {
  return xvView(KESTREL, change(kestrelBoard().items));
}

test("the header sums up the board, the decisions made and the run, and locks the draft while submission is blocked", async ({
  page,
}) => {
  await openBoard(page);
  const header = page.getByTestId("xv-header");
  await expect(header).toContainText(`Appraisal ${KESTREL} · Cross-verification`);
  await expect(
    header.getByRole("heading", { name: "Cross-verification and discrepancy" }),
  ).toBeVisible();
  await expect(page.getByTestId("xv-summary-line")).toHaveText(
    "Every source lined up against every other. 7 discrepancies found for this borrower, ranked by credit impact, each with its evidence attached and a decision required from you.",
  );
  // Under the summary: the decisions made, then the run the board shows.
  await expect(page.getByTestId("xv-meta-line")).toHaveText(
    "1 of 7 adjudicated · XR-000021-003 · 18 rules across 9 sources · 09 Oct 2026, 14:00",
  );
  await expect(page.getByTestId("xv-back-spread")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/policy#financials`,
  );
  await expect(page.getByTestId("xv-exception-queue")).toHaveAttribute("href", "/review");

  const next = page.getByTestId("xv-continue");
  await expect(next).toHaveText("Continue to draft");
  await expect(next).toHaveAttribute("aria-disabled", "true");
  await expect(next).toHaveAttribute(
    "title",
    "Submission is blocked until every blocking discrepancy is accepted or dismissed.",
  );
  await expect(next).not.toHaveAttribute("href", /./);
  await next.click({ force: true });
  await expect(page).toHaveURL(new RegExp(`${BOARD}$`));

  // No severity band and no board-wide lists: everything sits in its area.
  await expect(page.getByTestId("xv-band-serious")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Ranked discrepancies" })).toHaveCount(0);
  await expect(page.getByTestId("xv-board").locator("details[data-testid='xv-facts']")).toHaveCount(
    4,
  );

  await page.getByTestId("xv-exception-queue").click();
  await expect(page).toHaveURL(/\/review$/);
  await page.goBack();
  await page.getByTestId("xv-back-spread").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/policy#financials$`));
  // The board's Spread button opens the Financials section of the Financials and Policy tab.
  await expect(page.getByTestId("financials")).toBeInViewport();
});

test("the overview has a card per area, in the engine's order, each saying where the area stands", async ({
  page,
}) => {
  await openBoard(page);
  const cards = page.getByTestId("xv-overview").locator("[data-testid^='xv-area-card-']");
  expect(await testIds(cards)).toEqual(AREAS.map((a) => `xv-area-card-${a}`));

  const expected = {
    identity: {
      title: "Identity consistency",
      purpose: "PAN, GSTIN, CIN, name and directors agree across every document.",
      open: "2",
      severity: "2 serious",
      decided: "0 of 2 decided",
      others: "1 could not be checked · 4 passed · 1 not applicable",
      top: "Entity PAN differs between documents",
    },
    turnover: {
      title: "Turnover",
      purpose: "Audited, GST, banked and declared turnover agree within tolerance.",
      open: "1",
      severity: "1 moderate",
      decided: "1 of 2 decided",
      others: "3 could not be checked · 0 passed",
      top: "GST and bank credits diverge over the months both cover",
    },
    accounts: {
      title: "Bank accounts",
      purpose: "Every declared account has a statement; every account on file was declared.",
      open: "1",
      severity: "1 moderate",
      decided: "0 of 1 decided",
      others: "0 could not be checked · 1 passed",
      top: "Declared account without a statement",
    },
    obligations: {
      title: "Existing obligations",
      purpose: "Declared facilities agree with sanction letters, the bureau and the bank.",
      open: "2",
      severity: "2 serious",
      decided: "0 of 2 decided",
      others: "0 could not be checked · 1 passed",
      top: "Instalments to a lender that was not declared",
    },
  };
  for (const [area, want] of Object.entries(expected)) {
    const c = areaCard(page, area);
    await expect(c).toHaveAttribute("data-status", "open");
    await expect(c).toContainText(want.title);
    await expect(c).toContainText(want.purpose);
    await expect(c.getByTestId("xv-area-open")).toHaveText(want.open);
    await expect(c.getByTestId("xv-area-severity")).toHaveText(want.severity);
    await expect(c.getByTestId("xv-area-decided")).toHaveText(want.decided);
    await expect(c.getByTestId("xv-area-others")).toHaveText(want.others);
    await expect(c.getByTestId("xv-area-top")).toHaveText(want.top);
  }
  await expect(areaCard(page, "turnover")).toContainText("1 open discrepancy");
  await expect(areaCard(page, "identity")).toContainText("2 open discrepancies");
  // Only identity holds an open blocking discrepancy.
  await expect(areaCard(page, "identity").getByTestId("xv-area-blocking")).toHaveText("Blocking");
  for (const area of ["turnover", "accounts", "obligations"])
    await expect(areaCard(page, area).getByTestId("xv-area-blocking")).toHaveCount(0);
});

test("an area card opens its section and focuses its heading", async ({ page }) => {
  await openBoard(page);
  const obligations = section(page, "obligations");
  const heading = obligations.getByRole("heading", { level: 2, name: "Existing obligations" });
  await expect(heading).not.toBeInViewport();
  // Anywhere on the card outside its key figures: here, on its count.
  const obligationsCard = areaCard(page, "obligations");
  const onCount = await obligationsCard.evaluate((el) => {
    const box = el.getBoundingClientRect();
    const count = el.querySelector('[data-testid="xv-area-open"]')!.getBoundingClientRect();
    return { x: count.x - box.x + count.width / 2, y: count.y - box.y + count.height / 2 };
  });
  await obligationsCard.click({ position: onCount });
  await expect(heading).toBeInViewport();
  await expect(heading).toBeFocused();

  // By keyboard too: the card's button, named after the area and where it stands.
  const identity = section(page, "identity");
  const open = areaCard(page, "identity").getByTestId("xv-area-open-section");
  await expect(open).toHaveAccessibleName("Identity consistency (Open discrepancies)");
  await open.focus();
  await page.keyboard.press("Enter");
  await expect(identity.getByRole("heading", { level: 2 })).toBeFocused();
  await expect(identity.getByRole("heading", { level: 2 })).toBeInViewport();
});

test("each area card carries the engine's key figures, the open discrepancies first", async ({
  page,
}) => {
  await openBoard(page);
  const values = (line: Locator) => line.getByTestId("xv-highlight-value");

  // Identity: the two PANs, the bureau's marked; the two CINs; then the GSTIN every source
  // gives. A fourth line (the company name, also agreed) is left out: three at most.
  const identity = keyFigures(page, "identity");
  expect(await rules(identity)).toEqual(["ID-01", "ID-05", "ID-02"]);
  expect(await outcomes(identity)).toEqual(["fail", "fail", "pass"]);
  const pan = identity.nth(0);
  await expect(pan.getByTestId("xv-highlight-label")).toHaveText("PAN");
  await expect(values(pan)).toHaveText(["AAACK1234K", "AAACK1243K"]);
  const facts = pan.getByTestId("xv-highlight-fact");
  await expect(facts.nth(0)).toHaveAttribute("data-differs", "false");
  await expect(facts.nth(0)).toContainText("4 documents and the sourcing message");
  await expect(facts.nth(1)).toHaveAttribute("data-differs", "true");
  await expect(facts.nth(1)).toContainText("Commercial bureau report");
  // An identifier in monospace, so its characters can be compared; the differing one in red.
  await expect(values(pan).nth(1)).toHaveClass(/font-mono/);
  await expect(values(pan).nth(1)).toHaveClass(/text-destructive/);
  await expect(values(pan).nth(0)).not.toHaveClass(/text-destructive/);
  await expect(pan.getByTestId("xv-highlight-note")).toHaveCount(0);
  await expect(values(identity.nth(1))).toHaveText([
    "U28999MH2015PTC123456",
    "U28999MH2015PTC123465",
  ]);
  await expect(identity.nth(2)).toContainText("GSTIN");
  await expect(identity.nth(2).getByTestId("xv-highlight-note")).toHaveText(
    "same across 3 sources",
  );

  // Turnover: the open discrepancy, then the decided one, then a check that could not run; the
  // amounts in crores, the smaller marked, and how far apart against the tolerance.
  const turnover = keyFigures(page, "turnover");
  expect(await rules(turnover)).toEqual(["TO-05", "TO-04", "TO-01"]);
  expect(await outcomes(turnover)).toEqual(["fail", "fail", "incomplete"]);
  const window = turnover.nth(0);
  await expect(window.getByTestId("xv-highlight-label")).toHaveText(
    "GST against bank credits · Aug 2025 to Mar 2026",
  );
  await expect(values(window)).toHaveText(["INR 14.80 cr", "INR 17.19 cr"]);
  await expect(values(window).nth(0)).toHaveClass(/text-destructive/);
  await expect(values(window).nth(0)).not.toHaveClass(/font-mono/);
  await expect(window.getByTestId("xv-highlight-fact").nth(1)).toContainText("Bank credits");
  await expect(window.getByTestId("xv-highlight-note")).toHaveText("13.9% apart · tolerance 10%");
  await expect(values(turnover.nth(1))).toHaveText(["INR 3.00 cr", "INR 30.00 cr"]);
  await expect(turnover.nth(2).getByTestId("xv-highlight-fact")).toHaveCount(0);
  await expect(turnover.nth(2).getByTestId("xv-highlight-note")).toHaveText(
    "GSTR-3B returns for Apr 2025 to Jul 2025 needed",
  );

  // Bank accounts: the account without a statement, then what every other account confirms.
  const accounts = keyFigures(page, "accounts");
  expect(await rules(accounts)).toEqual(["BA-01", "BA-02"]);
  await expect(accounts.nth(0).getByTestId("xv-highlight-label")).toHaveText(
    "Lotuscrest Bank ·5678",
  );
  await expect(accounts.nth(0).getByTestId("xv-highlight-note")).toHaveText(
    "declared, no statement",
  );

  // Existing obligations: the undeclared instalments, then a line per lender of the facilities
  // that do not reconcile; the passed check behind them does not fit.
  const obligations = keyFigures(page, "obligations");
  expect(await rules(obligations)).toEqual(["OB-02", "OB-01", "OB-01"]);
  await expect(obligations.nth(0)).toContainText("ASHWOOD FINSERV");
  await expect(obligations.nth(0).getByTestId("xv-highlight-note")).toHaveText(
    "INR 1.45 lakh a month in the bank statements, not declared",
  );
  const tidewater = obligations.nth(1);
  await expect(tidewater.getByTestId("xv-highlight-label")).toHaveText("Tidewater Finance");
  await expect(values(tidewater)).toHaveText([
    "INR 40.00 lakh",
    "INR 55.00 lakh",
    "INR 55.00 lakh",
  ]);
  await expect(tidewater.getByTestId("xv-highlight-fact")).toHaveText([
    /Declared/,
    /Sanction letter/,
    /Bureau/,
  ]);
  await expect(tidewater.getByTestId("xv-highlight-fact").nth(0)).toHaveAttribute(
    "data-differs",
    "true",
  );
  await expect(tidewater.getByTestId("xv-highlight-note")).toHaveText("27.3% apart · tolerance 5%");
  await expect(obligations.nth(2).getByTestId("xv-highlight-note")).toHaveText(
    "not declared · INR 12.00 lakh in the bureau report",
  );
});

test("a key figure opens its finding: the card of a discrepancy, the row of any other check", async ({
  page,
}) => {
  await openBoard(page);
  // A discrepancy's line scrolls to its card and opens it, as Adjudicate now does.
  const ob1 = card(page, "fnd-ob1");
  await expect(ob1).toHaveAttribute("data-expanded", "false");
  await expect(ob1).not.toBeInViewport();
  await keyFigures(page, "obligations").nth(2).click();
  await expect(ob1).toHaveAttribute("data-expanded", "true");
  await expect(ob1).toBeInViewport();
  await expect(ob1.getByTestId("xv-card-toggle")).toBeFocused();
  await expect(section(page, "obligations").getByTestId("xv-card-fnd-ob1")).toHaveCount(1);

  // A check that could not run: its row, focused.
  await page.getByTestId("xv-overview").scrollIntoViewIfNeeded();
  const to1 = page.locator('[data-testid="xv-incomplete-row"][data-rule="TO-01"]');
  await expect(to1).not.toBeInViewport();
  await keyFigures(page, "turnover").nth(2).click();
  await expect(to1).toBeInViewport();
  await expect(to1).toBeFocused();
  // Marked as the row the line opened, until the reader moves on.
  await expect(to1).toHaveAttribute("data-target", "true");

  // A passed check: the area's passed list opens at its row.
  const passed = section(page, "identity").getByTestId("xv-passed");
  await expect(passed).not.toHaveAttribute("open", "");
  // By keyboard: the card's button, then its key figures in order.
  await areaCard(page, "identity").getByTestId("xv-area-open-section").focus();
  for (let i = 0; i < 3; i++) await page.keyboard.press("Tab");
  await expect(keyFigures(page, "identity").nth(2)).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(passed).toHaveAttribute("open", "");
  const id2 = passed.locator('[data-testid="xv-passed-row"][data-rule="ID-02"]');
  await expect(id2).toBeInViewport();
  await expect(id2).toBeFocused();
  await expect(id2).toHaveAttribute("data-target", "true");
  // The incomplete row lost its mark when the focus left it; this one loses it in turn.
  await expect(to1).not.toHaveAttribute("data-target");
  await page.keyboard.press("Tab");
  await expect(id2).not.toHaveAttribute("data-target");
});

test("a link to a finding opens the board at it: a discrepancy's card, or any other check's row", async ({
  page,
}) => {
  const api = new MockApi();
  api.documents.set(KESTREL, [...DOCUMENTS, ...XV_DOCUMENTS]);
  api.documentTypes = XV_DOCUMENT_TYPES;
  await signedIn(page, api);
  // By its XV reference (the draft CAM's summary): its card open and focused, the board's top
  // card left closed.
  await page.goto(`${BOARD}?finding=XV-000021-02`);
  const ob1 = card(page, "fnd-ob1");
  await expect(ob1).toHaveAttribute("data-expanded", "true");
  await expect(ob1).toBeInViewport();
  await expect(ob1.getByTestId("xv-card-toggle")).toBeFocused();
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-expanded", "false");

  // By its finding id (the PD note), a passed check: the passed list opens at its row.
  await page.goto(`${BOARD}?finding=fnd-id2`);
  const passed = section(page, "identity").getByTestId("xv-passed");
  await expect(passed).toHaveAttribute("open", "");
  const id2 = passed.locator('[data-testid="xv-passed-row"][data-rule="ID-02"]');
  await expect(id2).toBeInViewport();
  await expect(id2).toBeFocused();
  await expect(id2).toHaveAttribute("data-target", "true");

  // A finding no longer on the board: the board as it opens without a link.
  await page.goto(`${BOARD}?finding=fnd-gone`);
  await expect(page.getByTestId("xv-overview")).toBeVisible();
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-expanded", "true");
  await expect(passed).not.toHaveAttribute("open", "");
});

test("the key figures follow the decisions, the open discrepancies' first", async ({ page }) => {
  await openBoard(page);
  await decide(page, "fnd-id1", "accept", "The bureau report is wrong; a correction is requested.");
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-adjudicated", "true");
  // The PAN, decided, now follows the CIN, still open.
  const identity = keyFigures(page, "identity");
  await expect(identity.getByTestId("xv-highlight-label")).toHaveText(["CIN", "PAN", "GSTIN"]);
  expect(await outcomes(identity)).toEqual(["fail", "fail", "pass"]);
});

test("an area whose findings carry no key figures shows its card without them", async ({
  page,
}) => {
  // Cards stored before the key figures existed: the overview reads as before.
  const api = new MockApi();
  const board = kestrelBoard();
  for (const item of board.items) item.finding.highlights = [];
  api.boards.set(KESTREL, board);
  await openBoard(page, api);
  await expect(page.getByTestId("xv-area-highlights")).toHaveCount(0);
  await expect(page.getByTestId("xv-area-highlight")).toHaveCount(0);
  await expect(areaCard(page, "identity").getByTestId("xv-area-top")).toHaveText(
    "Entity PAN differs between documents",
  );
  const tops = await cardTops(page);
  expect(new Set(tops).size).toBe(1);
});

test("the decided, could-not-be-checked and clear areas read as such", async ({ page }) => {
  const api = new MockApi();
  api.boards.set(
    KESTREL,
    boardWith((items) => {
      for (const item of items) {
        if (item.finding.rule_id === "BA-01") {
          item.adjudicated = true;
          item.decision = xvDecision("accept", "The statement is requested.", XV_DECIDED_AT);
        }
      }
      // Turnover and obligations without discrepancies.
      return items.filter(
        (i) =>
          i.finding.outcome !== "fail" || !["turnover", "obligations"].includes(i.finding.area),
      );
    }),
  );
  await openBoard(page, api);

  const accounts = areaCard(page, "accounts");
  await expect(accounts).toHaveAttribute("data-status", "decided");
  await expect(accounts.getByTestId("xv-area-open")).toHaveText("0");
  await expect(accounts.getByTestId("xv-area-severity")).toHaveCount(0);
  await expect(accounts.getByTestId("xv-area-decided")).toHaveText("1 of 1 decided");
  await expect(accounts.getByTestId("xv-area-top")).toHaveText("Every discrepancy decided");

  const turnover = areaCard(page, "turnover");
  await expect(turnover).toHaveAttribute("data-status", "incomplete");
  await expect(turnover.getByTestId("xv-area-decided")).toHaveCount(0);
  await expect(turnover.getByTestId("xv-area-others")).toHaveText(
    "3 could not be checked · 0 passed",
  );
  await expect(turnover.getByTestId("xv-area-top")).toHaveText("No discrepancy");

  const obligations = areaCard(page, "obligations");
  await expect(obligations).toHaveAttribute("data-status", "clear");
  await expect(obligations.getByTestId("xv-area-top")).toHaveText("No discrepancy");
  await expect(areaCard(page, "identity")).toHaveAttribute("data-status", "open");

  // A section without discrepancies says so quietly; the rest of it stays.
  for (const area of ["turnover", "obligations"]) {
    await expect(section(page, area).getByTestId("xv-area-none")).toHaveText(
      "No discrepancy in this area.",
    );
    await expect(section(page, area).locator("[data-rank]")).toHaveCount(0);
  }
  await expect(section(page, "turnover").getByTestId("xv-incomplete-row")).toHaveCount(3);
  await expect(section(page, "accounts").getByTestId("xv-area-none")).toHaveCount(0);
  // The top discrepancy now open is the first open one on the board.
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-expanded", "true");
});

test("a name's line by line marks the part that differs", async ({ page }) => {
  // ID-09: inside the match the other identity checks make, each person's first, middle and last
  // name; the cell a row is flagged for stands out, and a part neither name has does not.
  const api = new MockApi();
  api.xvRules = [...XV_RULES.slice(0, 8), ["ID-09", "identity"], ...XV_RULES.slice(8)];
  const board = kestrelBoard();
  const row = (label: string, cells: string[], flagged_cells: number[] = []) => ({
    label,
    cells,
    flagged: flagged_cells.length > 0,
    flagged_cells,
  });
  board.items.push(
    xvItem(
      xvFinding({
        id: "fnd-id9",
        rule_id: "ID-09",
        title: "Names of people agree in full across documents",
        finding_title: "A person's name differs in part between documents",
        area: "identity",
        outcome: "fail",
        severity: "mild",
        blocking: false,
        ref: "XV-000021-09",
        explanation:
          "Names differ in part: Tarun S. Velankar: middle name missing in KYC received.",
        detail: {
          columns: ["Document", "As written", "First name", "Middle name", "Last name"],
          rows: [
            row("Tarun S. Velankar", ["KYC received", "Tarun Velankar", "✓", "Missing", "✓"], [3]),
            row("Tarun S. Velankar", [
              "Commercial bureau report",
              "Tarun S. Velankar",
              "✓",
              "✓",
              "✓",
            ]),
            row("Ishita Barve", ["KYC received", "Ishita Barve", "✓", "", "✓"]),
          ],
        },
      }),
      { review_item_id: "r-id9" },
    ),
  );
  api.boards.set(KESTREL, board);
  await openBoard(page, api);
  const lines = (await expand(page, "fnd-id9")).getByTestId("xv-line-by-line");
  await lines.locator("summary").click();
  const table = lines.getByTestId("xv-detail-table");
  await expect(table.locator('[data-flagged-cell="true"]')).toHaveText(["Missing"]);
  await expect(table.locator('[data-flagged-cell="true"]')).toHaveClass(/text-destructive/);
  const none = table.locator("tbody tr").nth(2).locator("td").nth(4);
  await expect(none).toHaveText("—");
  await expect(none).not.toHaveClass(/text-destructive/);
});

test("the cards and sections follow the areas the engine sends", async ({ page }) => {
  // The borrowing-authority rules switched back on: their area appears where configuration
  // puts it, with its own card and section.
  const api = new MockApi();
  const [identity, rest] = [XV_RULES.slice(0, 8), XV_RULES.slice(8)];
  api.xvRules = [...identity, ["BR-01", "authority"], ...rest];
  const board = kestrelBoard();
  board.items.push(
    xvItem(
      xvFinding({
        id: "fnd-br1",
        rule_id: "BR-01",
        title: "Board resolution covers the amount requested",
        finding_title: "Board resolution does not cover the amount requested",
        area: "authority",
        outcome: "fail",
        severity: "serious",
        blocking: true,
        ref: "XV-000021-08",
        explanation:
          "The board resolution authorises borrowing up to INR 40.00 lakh; the amount requested is INR 50.00 lakh.",
        columns: [
          xvColumn("limit", "Board resolution limit", 4_000_000, { unit: "inr", differs: true }),
          xvColumn("requested", "Amount requested", 5_000_000, { unit: "inr" }),
        ],
        amount: 1_000_000,
      }),
      { review_item_id: "r-br1" },
    ),
  );
  api.boards.set(KESTREL, board);
  await openBoard(page, api);

  const cards = page.getByTestId("xv-overview").locator("[data-testid^='xv-area-card-']");
  expect(await testIds(cards)).toEqual([
    "xv-area-card-identity",
    "xv-area-card-authority",
    "xv-area-card-turnover",
    "xv-area-card-accounts",
    "xv-area-card-obligations",
  ]);
  const authority = areaCard(page, "authority");
  await expect(authority).toContainText("Borrowing authority");
  await expect(authority.getByTestId("xv-area-blocking")).toBeVisible();
  await expect(authority.getByTestId("xv-area-top")).toHaveText(
    "Board resolution does not cover the amount requested",
  );
  const sections = page.locator("section[data-testid^='xv-area-']");
  expect(await testIds(sections)).toEqual([
    "xv-area-identity",
    "xv-area-authority",
    "xv-area-turnover",
    "xv-area-accounts",
    "xv-area-obligations",
  ]);
  await expect(section(page, "authority").getByTestId("xv-rank")).toHaveText(["1"]);
  // No facts panel serves that area on this screen.
  await expect(section(page, "authority").getByTestId("xv-facts")).toHaveCount(0);
  // The greatest blocking gap in rupees now heads the banner.
  await expect(page.getByTestId("xv-banner")).toContainText("XV-000021-08");
  await expect(page.getByTestId("xv-adjudicate-now")).toHaveAttribute("data-target", "fnd-br1");
  // The card open by default is still the first on the board, not the banner's.
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-expanded", "true");
  await expect(card(page, "fnd-br1")).toHaveAttribute("data-expanded", "false");
});

test("the banner points at the engine's first blocking discrepancy, and Adjudicate now opens it", async ({
  page,
}) => {
  await openBoard(page);
  const banner = page.getByTestId("xv-banner");
  await expect(banner).toContainText("Submission blocked — 2 serious discrepancies unadjudicated");
  // The engine's first_blocking: its reference, explanation and policy.
  await expect(banner).toContainText("XV-000021-03");
  await expect(banner).toContainText(
    "The entity PAN differs between documents: AAACK1234K (Company PAN, GSTR-3B (PAN within the GSTIN), Income tax return, Declaration of existing facilities, Sourcing message) · AAACK1243K (Commercial bureau report).",
  );
  await expect(banner).toContainText("Credit policy 3.2: identity of the borrower");
  const now = page.getByTestId("xv-adjudicate-now");
  await expect(now).toHaveAttribute("data-target", "fnd-id1");

  const id1 = card(page, "fnd-id1");
  // It is the first card, so it opens by default: close it and move away, then let the banner bring it back.
  await expect(id1).toHaveAttribute("data-expanded", "true");
  await id1.getByTestId("xv-card-toggle").click();
  await expect(id1).toHaveAttribute("data-expanded", "false");
  // Another area's tab hides it; Adjudicate now switches back to its area.
  await showArea(page, "obligations");
  await expect(id1).not.toBeInViewport();
  await now.click();
  await expect(id1).toHaveAttribute("data-expanded", "true");
  await expect(id1).toBeInViewport();
  await expect(id1.getByTestId("xv-card-toggle")).toBeFocused();
  await expect(id1.getByTestId("xv-adjudication")).toBeVisible();
  // The card it opened sits in its area.
  await expect(section(page, "identity").getByTestId("xv-card-fnd-id1")).toHaveCount(1);
});

test("the banner says blocking when an open blocking discrepancy is not serious", async ({
  page,
}) => {
  const api = new MockApi();
  api.boards.set(
    KESTREL,
    boardWith((items) => {
      for (const item of items) {
        if (item.finding.rule_id === "ID-01" || item.finding.rule_id === "ID-05") {
          item.adjudicated = true;
          item.decision = xvDecision("accept", "The registrar's record settles it.", XV_DECIDED_AT);
        }
        if (item.finding.rule_id === "BA-01") item.finding.blocking = true;
      }
      return items;
    }),
  );
  await openBoard(page, api);
  const banner = page.getByTestId("xv-banner");
  await expect(banner).toContainText("Submission blocked — 1 blocking discrepancy unadjudicated");
  await expect(banner).toContainText("XV-000021-06");
  await expect(page.getByTestId("xv-adjudicate-now")).toHaveAttribute("data-target", "fnd-ba1");
  await expect(card(page, "fnd-ba1")).toContainText("Blocks submission");
  await expect(card(page, "fnd-id1")).not.toContainText("Blocks submission");
  await expect(areaCard(page, "accounts").getByTestId("xv-area-blocking")).toBeVisible();
  await expect(areaCard(page, "identity").getByTestId("xv-area-blocking")).toHaveCount(0);
  await expect(areaCard(page, "identity")).toHaveAttribute("data-status", "decided");
  // Three different cards: the banner's (BA-01), the first rendered (ID-01, decided), and the one
  // open by default, the top of the first area with an open discrepancy (TO-05).
  await expect(card(page, "fnd-to5")).toHaveAttribute("data-expanded", "true");
  await expect(card(page, "fnd-ba1")).toHaveAttribute("data-expanded", "false");
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-expanded", "false");
  expect(await testIds(page.locator("[data-testid^='xv-card-'][data-rank]").first())).toEqual([
    "xv-card-fnd-id1",
  ]);
});

test("each section ranks its discrepancies within the area, the top one on the board open", async ({
  page,
}) => {
  await openBoard(page);
  const sections = page.locator("section[data-testid^='xv-area-']");
  expect(await testIds(sections)).toEqual(AREAS.map((a) => `xv-area-${a}`));

  const expected: Record<string, { heading: string; counts: string; ranked: string[] }> = {
    identity: {
      heading: "Identity consistency",
      counts: "8 rules · 2 discrepancies · 1 could not be checked · 4 passed · 1 not applicable",
      ranked: ["ID-01", "ID-05"],
    },
    turnover: {
      heading: "Turnover",
      counts: "5 rules · 2 discrepancies · 3 could not be checked",
      ranked: ["TO-05", "TO-04"],
    },
    accounts: {
      heading: "Bank accounts",
      counts: "2 rules · 1 discrepancy · 1 passed",
      ranked: ["BA-01"],
    },
    obligations: {
      heading: "Existing obligations",
      counts: "3 rules · 2 discrepancies · 1 passed",
      ranked: ["OB-02", "OB-01"],
    },
  };
  for (const [area, want] of Object.entries(expected)) {
    const s = section(page, area);
    await showArea(page, area);
    await expect(s.getByRole("heading", { level: 2 })).toHaveText(want.heading);
    await expect(s.getByTestId("xv-area-counts")).toHaveText(want.counts);
    // The engine's order within the area, each card numbered by its rank there. Turnover lists its
    // discrepancies among the figures compared, the selected one's card beside them.
    if (area === "turnover") {
      const fails = s.locator('[data-testid="xv-figure-row"][data-outcome="fail"]');
      expect(await rules(fails)).toEqual(want.ranked);
      await expect(s.getByTestId("xv-figure-panel").getByTestId("xv-rank")).toHaveText("1");
    } else {
      expect(await rules(s.locator("[data-rank]"))).toEqual(want.ranked);
      await expect(s.getByTestId("xv-rank")).toHaveText(want.ranked.map((_, i) => String(i + 1)));
    }
  }
  await expect(section(page, "identity")).toContainText(
    "PAN, GSTIN, CIN, name and directors agree across every document.",
  );

  // The first card on the board (the top of the first area with an open discrepancy) is open;
  // every other is closed, the greatest on the board (OB-02, further down) included.
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-expanded", "true");
  for (const id of ["fnd-ob2", "fnd-ob1", "fnd-id5", "fnd-ba1"])
    await expect(card(page, id)).toHaveAttribute("data-expanded", "false");
  // So is the discrepancy beside the turnover figures, the area's first; its second is not shown.
  await expect(card(page, "fnd-to5")).toHaveAttribute("data-expanded", "true");
  await expect(card(page, "fnd-to4")).toHaveCount(0);

  // Collapsed: what it is, how serious, and whether it blocks or is decided.
  const id1 = card(page, "fnd-id1");
  await expect(id1).toHaveAttribute("data-severity", "serious");
  await expect(id1).toHaveAttribute("data-rank", "1");
  await expect(id1).toContainText("Serious");
  await expect(id1).toContainText("Blocks submission");
  await expect(id1).toContainText("XV-000021-03 · ID-01");
  await expect(id1).toContainText("Entity PAN differs between documents");
  await expect(card(page, "fnd-ob2")).not.toContainText("Blocks submission");
  await expect(card(page, "fnd-ob1")).toContainText("Escalated");
  await expect(card(page, "fnd-to5")).toContainText("XV-000021-05 · TO-05 · Aug 2025 to Mar 2026");
  await pick(page, "fnd-to4");
  const to4 = card(page, "fnd-to4");
  await expect(card(page, "fnd-to5")).toHaveCount(0);
  await expect(to4).toHaveAttribute("data-rank", "2");
  await expect(to4).toHaveAttribute("data-adjudicated", "true");
  await expect(to4).toContainText("Dismissed");
  await expect(to4).toContainText("Mild");
});

test("a collapsed card with amounts shows its figures large, the differing one marked", async ({
  page,
}) => {
  await openBoard(page);
  // Turnover: the two figures the engine's key-figure line gives, then how far apart they are.
  const to5 = card(page, "fnd-to5");
  // It opens beside the turnover figures; closed, it shows its figures.
  await showArea(page, "turnover");
  await to5.getByTestId("xv-card-toggle").click();
  await expect(to5).toHaveAttribute("data-expanded", "false");
  const figures = to5.getByTestId("xv-card-figures");
  const values = figures.getByTestId("xv-card-figure");
  await expect(values).toHaveCount(2);
  await expect(values.nth(0)).toHaveText(/INR 14\.80 cr\s*Differs\s*GST outward supplies/);
  await expect(values.nth(0)).toHaveAttribute("data-differs", "true");
  await expect(values.nth(1)).toHaveText(/INR 17\.19 cr\s*Bank credits/);
  await expect(values.nth(1)).toHaveAttribute("data-differs", "false");
  await expect(figures.getByTestId("xv-card-figures-note")).toHaveText(
    "13.9% apart · tolerance 10%",
  );
  // Open, the source columns carry the figures instead.
  await showAreaOf(page, to5);
  await to5.getByTestId("xv-card-toggle").click();
  await expect(to5).toHaveAttribute("data-expanded", "true");
  await expect(to5.getByTestId("xv-card-figures")).toHaveCount(0);
  // A check without amounts shows none.
  await expect(card(page, "fnd-ba1").getByTestId("xv-card-figures")).toHaveCount(0);
});

test("an open card lines up the sources, the gap on each leg and the tolerance", async ({
  page,
}) => {
  await openBoard(page);
  const columns = (c: Locator) => c.locator('[data-testid^="xv-column-"][data-differs]');

  // Obligations: an undeclared lender's annual outflow, no percentage tolerance.
  const ob2 = await expand(page, "fnd-ob2");
  await expect(ob2.getByTestId("xv-rule-line")).toHaveText(
    "Rule OB-02 — Instalments in bank statements go to declared lenders · owner not yet assigned",
  );
  await expect(columns(ob2)).toHaveCount(2);
  const instalments = ob2.getByTestId("xv-column-instalments");
  await expect(instalments).toHaveAttribute("data-differs", "true");
  await expect(instalments).toContainText("Instalments in bank statements");
  await expect(instalments).toContainText("Borrower-supplied");
  await expect(instalments).toContainText("Apr 2025 to Mar 2026 · Lotuscrest Bank ·1234");
  await expect(instalments.getByTestId("xv-column-value")).toHaveText(
    "ASHWOOD FINSERV, Tidewater Finance",
  );
  await expect(ob2.getByTestId("xv-column-declaration")).toContainText("Declared");
  const leg = ob2.getByTestId("xv-gap-leg");
  await expect(leg).toHaveAttribute("data-breached", "true");
  await expect(leg).toContainText(
    "Annual outflow to ASHWOOD FINSERV (INR 1.45 lakh a month), not declared",
  );
  await expect(leg).toContainText("INR 17.40 lakh");
  await expect(ob2.getByTestId("xv-tolerance-line")).toHaveCount(0);

  // Turnover: the gap as a share of the larger figure, and the bank's tolerance it breaches.
  const to5 = await expand(page, "fnd-to5");
  await expect(to5.getByTestId("xv-rule-line")).toHaveText(
    "Rule TO-05 — GST outward supplies against bank credits, months both cover, tolerance 10% · owner not yet assigned",
  );
  await expect(to5.getByTestId("xv-column-gst").getByTestId("xv-column-value")).toHaveText(
    "INR 14.80 cr",
  );
  await expect(to5.getByTestId("xv-column-gst")).toContainText("Aug 2025 to Mar 2026 · 8 returns");
  await expect(to5.getByTestId("xv-column-bank").getByTestId("xv-column-value")).toHaveText(
    "INR 17.19 cr",
  );
  await expect(to5.getByTestId("xv-gap-leg")).toContainText("Gap against GST outward supplies");
  await expect(to5.getByTestId("xv-gap-leg")).toContainText("INR 2.39 cr · 13.9% of bank credits");
  await expect(to5.getByTestId("xv-tolerance-line")).toContainText("RBL tolerance");
  await expect(to5.getByTestId("xv-tolerance-line")).toContainText(
    "10% — breached on GST outward supplies against bank credits",
  );

  // Identity, more than four documents: a column per group that agrees, the characters that
  // differ from the value most sources give marked, the difference in words, the policy.
  const id1 = await expand(page, "fnd-id1");
  await expect(id1.getByTestId("xv-rule-line")).toHaveText(
    "Rule ID-01 — Entity PAN consistent across documents · owner not yet assigned · Credit policy 3.2: identity of the borrower",
  );
  await expect(columns(id1)).toHaveCount(2);
  const group = id1.getByTestId("xv-column-group-0");
  await expect(group).toContainText(
    "Company PAN, GSTR-3B (PAN within the GSTIN), Income tax return, Declaration of existing facilities, Sourcing message",
  );
  await expect(group).toContainText("4 documents and the sourcing message");
  const bureau = id1.getByTestId("xv-column-group-1");
  await expect(bureau).toHaveAttribute("data-differs", "true");
  await expect(bureau).toContainText("Independent");
  await expect(bureau.getByTestId("xv-column-value")).toHaveText("AAACK1243K");
  await expect(bureau.getByTestId("xv-diff")).toHaveText(["43"]);
  await expect(group.getByTestId("xv-diff")).toHaveCount(0);
  await expect(id1.getByTestId("xv-gap-row")).toHaveCount(0);
  await expect(id1.getByTestId("xv-mismatch")).toHaveText(
    "Commercial bureau report gives AAACK1243K; the other 5 sources give AAACK1234K.",
  );

  // Identity, four documents: a column each.
  const id5 = await expand(page, "fnd-id5");
  await expect(columns(id5)).toHaveCount(4);
  const moa = id5.getByTestId("xv-column-statement-1");
  await expect(moa).toHaveAttribute("data-differs", "true");
  await expect(moa.getByTestId("xv-column-value")).toHaveText("U28999MH2015PTC123465");
  await expect(moa.getByTestId("xv-diff")).toHaveText(["65"]);
  await expect(id5.getByTestId("xv-column-statement-0").getByTestId("xv-diff")).toHaveCount(0);
  await expect(id5.getByTestId("xv-column-statement-2")).toContainText("Independent");
  await expect(id5.getByTestId("xv-column-statement-3")).toContainText("Declared");
  await expect(id5.getByTestId("xv-mismatch")).toHaveText(
    "Memorandum and articles of association gives U28999MH2015PTC123465; the other 3 sources give U28999MH2015PTC123456.",
  );

  // The escalated card: its owner, and the legs breached against the facility tolerance. A lender
  // not declared at all has no percentage: it stays in the gap row, and the tolerance line names
  // only the legs measured against the tolerance.
  const ob1 = await expand(page, "fnd-ob1");
  await expect(ob1.getByTestId("xv-rule-line")).toHaveText(
    "Rule OB-01 — Declared facilities reconcile with sanction letters and the bureau, tolerance 5% · owner Ananya Krishnan",
  );
  const legs = ob1.getByTestId("xv-gap-leg");
  await expect(legs).toHaveCount(3);
  await expect(legs.nth(2)).toHaveAttribute("data-breached", "true");
  await expect(legs.nth(2).locator("dt")).toHaveText("Lotuscrest Bank: not declared");
  await expect(legs.nth(2).locator("dd")).toHaveText("INR 12.00 lakh");
  await expect(ob1.getByTestId("xv-tolerance-line").locator("dd")).toHaveText(
    "5% — breached on Tidewater Finance declared against sanction letter and Tidewater Finance declared against bureau",
  );
});

test("a source's evidence lists the rows behind its figure, totals and exclusions apart", async ({
  page,
}) => {
  await openBoard(page);
  const to5 = await expand(page, "fnd-to5");
  const bank = to5.getByTestId("xv-column-bank");
  await expect(to5.getByTestId("xv-evidence-panel")).toHaveCount(0);
  await bank.getByTestId("xv-open-evidence").click();
  await expect(bank).toHaveAttribute("data-active", "true");
  await expect(bank.getByTestId("xv-open-evidence")).toHaveText("Hide the evidence");
  const panel = to5.getByTestId("xv-evidence-panel");
  await expect(panel).toHaveAttribute("data-column", "bank");
  await expect(panel.getByRole("columnheader")).toHaveText([
    "Month",
    "Account",
    "Credits",
    "Excluded credits",
    "Page",
  ]);
  await expect(panel.locator('[data-kind="row"]')).toHaveCount(8);
  await expect(panel.locator('[data-kind="row"]').nth(1)).toContainText("Sep 2025");
  await expect(panel.locator('[data-kind="row"]').nth(1)).toContainText("2,31,00,000");
  await expect(panel.locator('[data-kind="row"]').nth(1)).toContainText("20,00,000");
  const total = panel.locator('[data-kind="total"]');
  await expect(total).toContainText("Total Aug 2025 to Mar 2026");
  await expect(total).toContainText("17,54,00,000");
  await expect(total).toContainText("35,00,000");
  // The credits left out of the count follow, each with its date, account and narration.
  await expect(panel).toContainText("Excluded from the count");
  const excluded = panel.locator('[data-kind="excluded"]');
  await expect(excluded).toHaveCount(2);
  await expect(excluded.first()).toContainText("12 Sep 2025");
  await expect(excluded.first()).toContainText(
    "Transfer between the borrower's own accounts: NEFT CR OWN ACCOUNT TRANSFER",
  );
  await expect(excluded.first()).toContainText("20,00,000");

  // Another source's evidence replaces it; its own toggle closes it.
  const gst = to5.getByTestId("xv-column-gst");
  await gst.getByTestId("xv-open-evidence").click();
  await expect(panel).toHaveAttribute("data-column", "gst");
  await expect(bank).toHaveAttribute("data-active", "false");
  await expect(panel.getByRole("columnheader")).toHaveText([
    "Period",
    "Filed",
    "3.1(a)+(b)+(c) outward supplies",
    "Page",
  ]);
  await expect(panel.locator('[data-kind="row"]')).toHaveCount(8);
  await expect(panel.locator('[data-kind="total"]')).toContainText(
    "Aggregate Aug 2025 to Mar 2026",
  );
  await expect(panel.locator('[data-kind="excluded"]')).toHaveCount(0);
  await gst.getByTestId("xv-open-evidence").click();
  await expect(panel).toHaveCount(0);
});

test("Trace to the source opens the page a figure was read from", async ({ page }) => {
  const api = await openBoard(page);
  const ob2 = await expand(page, "fnd-ob2");
  await ob2.getByTestId("xv-column-instalments").getByTestId("xv-trace").click();
  const viewer = page.getByTestId("evidence-viewer");
  await expect(viewer.getByTestId("viewer-type")).toHaveText("Bank statement");
  await expect(viewer.getByTestId("viewer-page")).toHaveText("Page 7 · pages 3–9");
  await expect
    .poll(() => api.called("GET", `/api/cases/${KESTREL}/documents/doc-bank/pages/7`).length)
    .toBeGreaterThan(0);
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);

  // Each source opens its own document, not the first column's or the first side's.
  await ob2.getByTestId("xv-column-declaration").getByTestId("xv-trace").click();
  await expect(viewer.getByTestId("viewer-type")).toHaveText("Declaration of existing facilities");
  await expect(viewer.getByTestId("viewer-page")).toHaveText("Page 1");
  await page.keyboard.press("Escape");
  const id1 = await expand(page, "fnd-id1");
  await id1.getByTestId("xv-column-group-1").getByTestId("xv-trace").click();
  await expect(viewer.getByTestId("viewer-type")).toHaveText("Commercial bureau report");
  await expect(viewer.getByTestId("viewer-page")).toHaveText("Page 1 · pages 1–4");
  await page.keyboard.press("Escape");
  // A group of documents opens the first of them.
  await id1.getByTestId("xv-column-group-0").getByTestId("xv-trace").click();
  await expect(viewer.getByTestId("viewer-type")).toHaveText("Company PAN");
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
});

test("every evidence row opens its own page, by click or from its page button", async ({
  page,
}) => {
  await openBoard(page);
  const viewer = page.getByTestId("evidence-viewer");
  const to5 = await expand(page, "fnd-to5");
  await to5.getByTestId("xv-column-bank").getByTestId("xv-open-evidence").click();
  const panel = to5.getByTestId("xv-evidence-panel");
  await panel.locator('[data-kind="excluded"]').last().click();
  await expect(viewer.getByTestId("viewer-page")).toHaveText("Page 8 · pages 3–9");
  await page.keyboard.press("Escape");
  await expect(viewer).toHaveCount(0);
  // A total has no page of its own.
  await expect(panel.locator('[data-kind="total"]').getByTestId("xv-evidence-page")).toHaveCount(0);

  await to5.getByTestId("xv-column-gst").getByTestId("xv-open-evidence").click();
  const december = panel.locator('[data-kind="row"]').nth(4);
  await expect(december).toContainText("Dec 2025");
  const pageButton = december.getByTestId("xv-evidence-page");
  // An eye on its own; the page is in its label.
  await expect(pageButton).toHaveText("");
  await expect(pageButton).toHaveAccessibleName("Open page 2");
  await pageButton.focus();
  await page.keyboard.press("Enter");
  await expect(viewer.getByTestId("viewer-type")).toHaveText("GSTR-3B");
  await expect(viewer.getByTestId("viewer-page")).toHaveText("Page 2 · pages 1–2");
  await page.keyboard.press("Escape");

  // The rows of a group of documents each open their own document, not the column's first.
  const id1 = await expand(page, "fnd-id1");
  await id1.getByTestId("xv-column-group-0").getByTestId("xv-open-evidence").click();
  const rows = id1.getByTestId("xv-evidence-panel").getByTestId("xv-evidence-row");
  const opens: [string, string, string][] = [
    ["Income tax return", "Income tax return", "Page 1 · pages 1–3"],
    ["Declaration of existing facilities", "Declaration of existing facilities", "Page 1"],
    ["GSTR-3B (PAN within the GSTIN)", "GSTR-3B", "Page 1 · pages 1–2"],
  ];
  for (const [document, type, at] of opens) {
    await rows.filter({ hasText: document }).click();
    await expect(viewer.getByTestId("viewer-type")).toHaveText(type);
    await expect(viewer.getByTestId("viewer-page")).toHaveText(at);
    await page.keyboard.press("Escape");
    await expect(viewer).toHaveCount(0);
  }
  // The sourcing message has no page.
  await expect(
    rows.filter({ hasText: "Sourcing message" }).getByTestId("xv-evidence-page"),
  ).toHaveCount(0);
});

test("the pages of the sources open side by side", async ({ page }) => {
  await openBoard(page);
  const id5 = await expand(page, "fnd-id5");
  await id5.getByTestId("xv-compare").click();
  const compare = page.getByTestId("evidence-compare");
  const panes = compare.getByTestId("compare-pane");
  // Three at most, the one that differs among them, in the card's order.
  await expect(panes).toHaveCount(3);
  await expect(panes.nth(2)).toContainText("Commercial bureau report: U28999MH2015PTC123456");
  await expect(panes.nth(0)).toContainText("Certificate of incorporation: U28999MH2015PTC123456");
  await expect(panes.nth(1)).toContainText(
    "Memorandum and articles of association: U28999MH2015PTC123465",
  );
  await expect(panes.nth(1).getByTestId("compare-page")).toHaveText("Page 2 · pages 1–12");
  await page.keyboard.press("Escape");
  await expect(compare).toHaveCount(0);
  // A source without a page of its own (the accounts named in the sourcing message) leaves a
  // single page: nothing to compare.
  const ba1 = await expand(page, "fnd-ba1");
  await expect(ba1.getByTestId("xv-compare")).toHaveCount(0);
});

test("a decision needs a choice and a comment of at least three characters", async ({ page }) => {
  const api = await openBoard(page);
  const id1 = await expand(page, "fnd-id1");
  const form = id1.getByTestId("xv-adjudication");
  await expect(form.getByRole("radiogroup")).toBeVisible();
  await expect(form.getByRole("radio")).toHaveCount(3);
  await expect(form).toContainText("A valid finding; it stays on the query list");
  await expect(form).toContainText("Not a valid finding");
  await expect(form).toContainText("Hand to the Credit Manager; stays open and blocking");
  const save = form.getByTestId("xv-save-decision");
  await expect(save).toBeDisabled();
  await form.getByTestId("xv-comment").fill("The bureau misreads two digits of the PAN.");
  await expect(save).toBeDisabled();
  await form.getByTestId("xv-decision-dismiss").check();
  await expect(save).toBeEnabled();
  // Spaces do not count.
  await form.getByTestId("xv-comment").fill("  ok  ");
  await expect(save).toBeDisabled();
  await form.getByTestId("xv-comment").fill("     ");
  await expect(save).toBeDisabled();
  expect(api.called("POST", decisionPath("fnd-id1"))).toHaveLength(0);
  await form.getByTestId("xv-comment").fill("Yes");
  await expect(save).toBeEnabled();
});

test("accepting, dismissing and escalating update the card, its area, the header and the banner", async ({
  page,
}) => {
  const api = await openBoard(page);
  const banner = page.getByTestId("xv-banner");
  const meta = page.getByTestId("xv-meta-line");
  const identity = areaCard(page, "identity");
  const progress = () => api.called("GET", `/api/cases/${KESTREL}/progress`).length;
  const progressBefore = progress();

  // Accept: recorded on the card; the area and the board count one open discrepancy fewer.
  const accepted = "The bureau report is wrong; the PAN card and the returns agree.";
  const id1 = await decide(page, "fnd-id1", "accept", accepted);
  await expect(page.getByText("Decision recorded").first()).toBeVisible();
  const recorded = id1.getByTestId("xv-recorded-decision");
  await expect(recorded).toHaveAttribute("data-decision", "accept");
  await expect(recorded).toContainText("Accepted");
  await expect(recorded).toContainText("Ananya Krishnan · 09 Oct 2026, 15:15");
  await expect(recorded).toContainText(accepted);
  await expect(id1).toHaveAttribute("data-adjudicated", "true");
  await expect(id1).not.toContainText("Blocks submission");
  await expect(id1.getByTestId("xv-rule-line")).toContainText("owner Ananya Krishnan");
  expect(api.called("POST", decisionPath("fnd-id1")).map((c) => c.body)).toEqual([
    { decision: "accept", comment: accepted },
  ]);
  await expect(identity.getByTestId("xv-area-open")).toHaveText("1");
  await expect(identity.getByTestId("xv-area-severity")).toHaveText("1 serious");
  await expect(identity.getByTestId("xv-area-decided")).toHaveText("1 of 2 decided");
  await expect(identity.getByTestId("xv-area-top")).toHaveText("CIN differs between documents");
  await expect(meta).toContainText("2 of 7 adjudicated");
  // The banner moves on to the next blocking discrepancy.
  await expect(banner).toContainText("Submission blocked — 1 serious discrepancy unadjudicated");
  await expect(banner).toContainText("XV-000021-04");
  await expect(page.getByTestId("xv-adjudicate-now")).toHaveAttribute("data-target", "fnd-id5");
  // The stage progress refreshes with it, without reloading the page.
  await expect.poll(progress).toBeGreaterThan(progressBefore);

  // Escalate: the discrepancy stays open and blocking, now with the Credit Manager.
  const escalated = "The registrar's record is needed to settle the CIN.";
  const id5 = await decide(page, "fnd-id5", "escalate", escalated);
  const note = id5.getByTestId("xv-escalation-note");
  await expect(note).toContainText(
    "Escalated to the Credit Manager by Ananya Krishnan · 09 Oct 2026, 15:15",
  );
  await expect(note).toContainText(escalated);
  await expect(id5).toHaveAttribute("data-adjudicated", "false");
  await expect(id5.getByTestId("xv-card-toggle")).toContainText("Escalated");
  await expect(id5.getByTestId("xv-card-toggle")).toContainText("Blocks submission");
  await expect(id5.getByTestId("xv-waiting-manager")).toBeVisible();
  expect(api.called("POST", decisionPath("fnd-id5")).map((c) => c.body)).toEqual([
    { decision: "escalate", comment: escalated },
  ]);
  await expect(identity.getByTestId("xv-area-open")).toHaveText("1");
  await expect(identity.getByTestId("xv-area-blocking")).toBeVisible();
  await expect(meta).toContainText("2 of 7 adjudicated");
  await expect(banner).toContainText("1 serious discrepancy unadjudicated");
  await expect(page.getByTestId("xv-continue")).toHaveAttribute("aria-disabled", "true");

  // Dismiss: the area's only discrepancy decided.
  const ba1 = await decide(page, "fnd-ba1", "dismiss", "Closed in March; the letter is on file.");
  await expect(ba1.getByTestId("xv-recorded-decision")).toHaveAttribute("data-decision", "dismiss");
  await expect(ba1.getByTestId("xv-card-toggle")).toContainText("Dismissed");
  const accounts = areaCard(page, "accounts");
  await expect(accounts).toHaveAttribute("data-status", "decided");
  await expect(accounts.getByTestId("xv-area-open")).toHaveText("0");
  await expect(accounts.getByTestId("xv-area-decided")).toHaveText("1 of 1 decided");
  await expect(accounts.getByTestId("xv-area-top")).toHaveText("Every discrepancy decided");
  await expect(section(page, "accounts")).toHaveAttribute("data-status", "decided");
  await expect(meta).toContainText("3 of 7 adjudicated");
});

test("Continue to draft opens only once every blocking discrepancy is decided", async ({
  page,
}) => {
  await openBoard(page);
  const next = page.getByTestId("xv-continue");
  await decide(page, "fnd-id1", "accept", "The bureau report is wrong; a correction is requested.");
  await expect(card(page, "fnd-id1")).toHaveAttribute("data-adjudicated", "true");
  await expect(next).toHaveAttribute("aria-disabled", "true");
  await decide(
    page,
    "fnd-id5",
    "dismiss",
    "A typing slip in the memorandum; the certificate governs.",
  );
  await expect(page.getByTestId("xv-banner")).toHaveCount(0);
  await expect(page.getByTestId("xv-area-blocking")).toHaveCount(0);
  await expect(areaCard(page, "identity")).toHaveAttribute("data-status", "decided");
  await expect(next).not.toHaveAttribute("aria-disabled", "true");
  await expect(next).toHaveAttribute("href", `/appraisals/${KESTREL}/outputs?view=cam`);
  // The serious discrepancies that do not block stay open.
  await expect(areaCard(page, "obligations").getByTestId("xv-area-severity")).toHaveText(
    "2 serious",
  );
  await next.click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/outputs\\?view=cam$`));
  await expect(page.getByTestId("cam-review")).toBeVisible();
});

test("an escalated discrepancy is read-only for the analyst until the Credit Manager decides", async ({
  page,
}) => {
  const api = new MockApi();
  api.review.push(structuredClone(ESCALATED_ITEM));
  await openBoard(page, api);
  const ob1 = await expand(page, "fnd-ob1");
  const note = ob1.getByTestId("xv-escalation-note");
  await expect(note).toContainText(
    "Escalated to the Credit Manager by Ananya Krishnan · 08 Oct 2026, 16:50",
  );
  await expect(note).toContainText("the Credit Manager should decide");
  await expect(ob1.getByTestId("xv-decision-accept")).toBeDisabled();
  await expect(ob1.getByTestId("xv-decision-dismiss")).toBeDisabled();
  await expect(ob1.getByTestId("xv-decision-escalate")).toHaveCount(0);
  await expect(ob1.getByTestId("xv-comment")).toBeDisabled();
  await expect(ob1.getByTestId("xv-save-decision")).toBeDisabled();
  await expect(ob1.getByTestId("xv-waiting-manager")).toHaveText("Waiting for the Credit Manager");

  // The review queue says so too.
  await page.goto("/review");
  const row = page.getByTestId("review-row").filter({ has: page.getByTestId("review-escalated") });
  await expect(row).toHaveCount(1);
  await expect(row.getByTestId("review-escalated")).toHaveText("Escalated");
  await expect(row.getByTestId("decide-waiting")).toBeDisabled();
  await expect(row).toContainText("Waiting for the Credit Manager");
  await expect(row.getByTestId("decide")).toHaveCount(0);
});

test("the Credit Manager decides an escalated discrepancy on the board", async ({ page }) => {
  const api = new MockApi();
  api.review.push(structuredClone(ESCALATED_ITEM));
  await signedIn(page, api, MANAGER);
  await page.goto("/review");
  const row = page.getByTestId("review-row").filter({ has: page.getByTestId("review-escalated") });
  await expect(row.getByTestId("decide")).toBeEnabled();
  await expect(row.getByTestId("decide-waiting")).toHaveCount(0);

  await page.goto(BOARD);
  const ob1 = await expand(page, "fnd-ob1");
  await expect(ob1.getByTestId("xv-waiting-manager")).toHaveCount(0);
  // Already with the Credit Manager: accept or dismiss, not escalate again.
  await expect(ob1.getByTestId("xv-decision-escalate")).toHaveCount(0);
  const comment = "The sanction letter governs: INR 55 lakh; a corrected declaration is requested.";
  await ob1.getByTestId("xv-decision-accept").check();
  await ob1.getByTestId("xv-comment").fill(comment);
  await ob1.getByTestId("xv-save-decision").click();
  const recorded = ob1.getByTestId("xv-recorded-decision");
  await expect(recorded).toContainText("Accepted");
  await expect(recorded).toContainText("Meenal Kulkarni · 09 Oct 2026, 15:15");
  // The escalation stays on the record beside the decision.
  await expect(ob1.getByTestId("xv-escalation-note")).toContainText("Ananya Krishnan");
  await expect(ob1.getByTestId("xv-rule-line")).toContainText("owner Meenal Kulkarni");
  await expect(ob1.getByTestId("xv-card-toggle")).not.toContainText("Escalated");
  expect(api.called("POST", decisionPath("fnd-ob1")).map((c) => c.body)).toEqual([
    { decision: "accept", comment },
  ]);
  const obligations = areaCard(page, "obligations");
  await expect(obligations.getByTestId("xv-area-severity")).toHaveText("1 serious");
  await expect(obligations.getByTestId("xv-area-decided")).toHaveText("1 of 2 decided");

  // Decided, it leaves the open review queue: once the queue has loaded, its other items are
  // there and the escalated one is not.
  expect(api.review.find((r) => r.id === "r-ob1")).toMatchObject({
    status: "decided",
    decision: "confirm",
    reason: comment,
  });
  await page.goto("/review");
  await expect(page.getByTestId("review-row")).toHaveCount(2);
  await expect(page.getByTestId("review-row").filter({ hasText: "OB-01" })).toHaveCount(0);
  await expect(page.getByTestId("review-escalated")).toHaveCount(0);
});

test.describe("in the review queue, a discrepancy is decided with a comment", () => {
  const HINT =
    "Every decision on a discrepancy is recorded with a comment of at least 3 characters, whether it is confirmed or waived.";

  test("an escalated one needs the comment to confirm as well as to waive", async ({ page }) => {
    const api = new MockApi();
    api.review.push(structuredClone(ESCALATED_ITEM));
    await signedIn(page, api, MANAGER);
    await page.goto("/review");
    const row = page
      .getByTestId("review-row")
      .filter({ has: page.getByTestId("review-escalated") });
    await row.getByTestId("decide").click();
    const dialog = page.getByTestId("decision-dialog");
    const reason = dialog.getByTestId("decision-reason");
    const record = dialog.getByTestId("record-decision");
    // Confirm is chosen: the comment is asked for all the same.
    await expect(dialog.getByRole("radio", { name: "Confirm" })).toBeChecked();
    await expect(dialog).toContainText("Comment (required)");
    await expect(dialog.getByTestId("decision-reason-hint")).toHaveText(HINT);
    await expect(record).toBeDisabled();
    await reason.fill("ok");
    await expect(record).toBeDisabled();
    await reason.fill("  ok   ");
    await expect(record).toBeDisabled();
    // Waive asks for it too.
    await dialog.getByText("Waive", { exact: true }).click();
    await expect(record).toBeDisabled();
    await reason.fill("The declaration is corrected; the sanction letter governs.");
    await expect(record).toBeEnabled();
    await dialog.getByText("Confirm", { exact: true }).click();
    await expect(record).toBeEnabled();
    expect(api.called("POST", "/api/review/r-ob1/decision")).toHaveLength(0);

    await record.click();
    await expect(dialog).toHaveCount(0);
    expect(api.called("POST", "/api/review/r-ob1/decision").map((c) => c.body)).toEqual([
      {
        decision: "confirm",
        reason: "The declaration is corrected; the sanction letter governs.",
        value: null,
      },
    ]);
    // Confirmed in the queue, it is accepted on the board.
    await page.goto(BOARD);
    const ob1 = await expand(page, "fnd-ob1");
    await expect(ob1.getByTestId("xv-recorded-decision")).toContainText("Accepted");
    await expect(ob1.getByTestId("xv-recorded-decision")).toContainText(
      "The declaration is corrected; the sanction letter governs.",
    );
  });

  test("one that was never escalated needs the comment too", async ({ page }) => {
    const api = new MockApi();
    api.review.push(structuredClone(FINDING_ITEM));
    await signedIn(page, api);
    await page.goto("/review");
    await page.getByTestId("kind-finding").click();
    await page.getByTestId("decide").click();
    const dialog = page.getByTestId("decision-dialog");
    const reason = dialog.getByTestId("decision-reason");
    const record = dialog.getByTestId("record-decision");
    await expect(dialog.getByRole("radio", { name: "Confirm" })).toBeChecked();
    await expect(dialog).toContainText("Comment (required)");
    await expect(dialog).not.toContainText("Reason (optional)");
    await expect(dialog.getByTestId("decision-reason-hint")).toHaveText(HINT);
    await expect(record).toBeDisabled();
    await reason.fill("ok");
    await expect(record).toBeDisabled();
    await dialog.getByText("Waive", { exact: true }).click();
    await expect(record).toBeDisabled();
    await dialog.getByText("Confirm", { exact: true }).click();
    await reason.fill("Equipment lease instalments, now declared.");
    await expect(record).toBeEnabled();
    expect(api.called("POST", "/api/review/r-finding/decision")).toHaveLength(0);
    await record.click();
    await expect(dialog).toHaveCount(0);
    expect(api.called("POST", "/api/review/r-finding/decision").map((c) => c.body)).toEqual([
      { decision: "confirm", reason: "Equipment lease instalments, now declared.", value: null },
    ]);
    // Confirmed in the queue, it is accepted on the board, with the comment.
    await page.goto(BOARD);
    const ob2 = await expand(page, "fnd-ob2");
    await expect(ob2.getByTestId("xv-recorded-decision")).toContainText("Accepted");
    await expect(ob2.getByTestId("xv-recorded-decision")).toContainText(
      "Equipment lease instalments, now declared.",
    );
    await expect(ob2.getByTestId("xv-no-comment")).toHaveCount(0);
  });

  test("the engine's refusal shows in the dialog", async ({ page }) => {
    const api = new MockApi();
    api.review.push(structuredClone(FINDING_ITEM));
    await signedIn(page, api);
    await page.goto("/review");
    await page.getByTestId("kind-finding").click();
    await page.getByTestId("decide").click();
    const dialog = page.getByTestId("decision-dialog");
    const error = dialog.getByTestId("decision-error");
    await dialog.getByTestId("decision-reason").fill("Equipment lease instalments, now declared.");
    // Escalated by someone else since the queue loaded: the Credit Manager decides it now.
    api.review.find((r) => r.id === "r-finding")!.escalated = true;
    await dialog.getByTestId("record-decision").click();
    await expect(error).toHaveText("an escalated discrepancy is decided by the Credit Manager");
    await expect(dialog).toBeVisible();
    // Typing clears it.
    await dialog.getByTestId("decision-reason").fill("Equipment lease instalments, declared now.");
    await expect(error).toHaveCount(0);
    // A comment the engine refuses: its words, as given.
    api.review.find((r) => r.id === "r-finding")!.escalated = false;
    api.on("POST", /^\/api\/review\/r-finding\/decision$/, () => ({
      status: 422,
      json: { detail: "a comment is required for every decision on a discrepancy" },
    }));
    await dialog.getByTestId("record-decision").click();
    await expect(error).toHaveText("a comment is required for every decision on a discrepancy");
    await expect(dialog.locator("[data-testid^='state-']")).toHaveCount(0);
    expect(api.review.find((r) => r.id === "r-finding")).toMatchObject({ status: "open" });
  });

  test("a decision recorded without a comment says so on the board", async ({ page }) => {
    // Recorded in the queue before every decision on a discrepancy needed a comment.
    const api = new MockApi();
    api.boards.set(
      KESTREL,
      boardWith((items) => {
        const ob2 = items.find((i) => i.finding.id === "fnd-ob2")!;
        ob2.adjudicated = true;
        ob2.decision = xvDecision("accept", "", XV_DECIDED_AT);
        return items;
      }),
    );
    await openBoard(page, api);
    const ob2 = await expand(page, "fnd-ob2");
    await expect(ob2.getByTestId("xv-recorded-decision")).toContainText("Accepted");
    await expect(ob2.getByTestId("xv-no-comment")).toHaveText(
      "No comment was recorded with this decision.",
    );
  });
});

test("a refusal says why on the card, and the board then shows what changed meanwhile", async ({
  page,
}) => {
  const api = await openBoard(page);
  const items = api.boards.get(KESTREL)!.items;
  const meanwhile = (id: string) => items.find((i) => i.finding.id === id)!;
  const boardReads = () => api.called("GET", `/api/cases/${KESTREL}/cross-verification`).length;
  const meta = page.getByTestId("xv-meta-line");

  // Escalated by someone else since the board loaded: only the Credit Manager may decide it.
  meanwhile("fnd-ba1").escalation = xvDecision("escalate", "For the manager.", XV_DECIDED_AT);
  let reads = boardReads();
  const ba1 = await decide(page, "fnd-ba1", "dismiss", "The account was closed in March.");
  await expect(ba1.getByTestId("xv-decision-error")).toHaveText(
    "an escalated discrepancy is decided by the Credit Manager",
  );
  await expect.poll(boardReads).toBeGreaterThan(reads);
  // The board now shows the escalation, and the card waits for the Credit Manager.
  await expect(ba1.getByTestId("xv-escalation-note")).toContainText("For the manager.");
  await expect(ba1.getByTestId("xv-card-toggle")).toContainText("Escalated");
  await expect(ba1.getByTestId("xv-waiting-manager")).toBeVisible();
  await expect(ba1.getByTestId("xv-save-decision")).toBeDisabled();
  await expect(ba1.getByTestId("xv-recorded-decision")).toHaveCount(0);
  await expect(meta).toContainText("1 of 7 adjudicated");
  await expect(areaCard(page, "accounts").getByTestId("xv-area-open")).toHaveText("1");

  // Decided by someone else since the board loaded.
  Object.assign(meanwhile("fnd-to5"), {
    adjudicated: true,
    decision: xvDecision("accept", "Exports under LUT explain it.", XV_DECIDED_AT, MANAGER),
  });
  reads = boardReads();
  const to5 = await decide(page, "fnd-to5", "accept", "GST leaves out the exports.");
  await expect(to5.getByTestId("xv-decision-error")).toHaveText(
    "this discrepancy has already been decided",
  );
  await expect.poll(boardReads).toBeGreaterThan(reads);
  // The decision made meanwhile replaces the form, the refusal still said above it; the
  // analyst's own was never recorded.
  const recorded = to5.getByTestId("xv-recorded-decision");
  await expect(recorded).toContainText("Meenal Kulkarni");
  await expect(recorded).toContainText("Exports under LUT explain it.");
  await expect(recorded).not.toContainText("GST leaves out the exports.");
  await expect(to5.getByTestId("xv-adjudication")).toHaveCount(0);
  await expect(to5).toHaveAttribute("data-adjudicated", "true");
  expect(api.called("POST", decisionPath("fnd-to5"))).toHaveLength(1);
  // The header and the area count it, as the engine does.
  await expect(meta).toContainText("2 of 7 adjudicated");
  const turnover = areaCard(page, "turnover");
  await expect(turnover).toHaveAttribute("data-status", "decided");
  await expect(turnover.getByTestId("xv-area-decided")).toHaveText("2 of 2 decided");
});

test("a request refused because its check ran meanwhile: the board shows the check as it stands", async ({
  page,
}) => {
  const api = await openBoard(page);
  const boardReads = () => api.called("GET", `/api/cases/${KESTREL}/cross-verification`).length;
  const row = page.locator('[data-testid="xv-incomplete-row"][data-rule="ID-04"]');
  await expect(row.getByTestId("xv-add-query")).toBeVisible();
  // The director KYC arrived and the check ran again since the board loaded: it passed.
  const id4 = api.boards.get(KESTREL)!.items.find((i) => i.finding.id === "fnd-id4")!;
  Object.assign(id4.finding, {
    outcome: "pass",
    explanation: "The same 2 person(s) in 3 sources.",
    missing: [],
    request: null,
  });
  const reads = boardReads();
  await row.getByTestId("xv-add-query").click();
  await expect.poll(boardReads).toBeGreaterThan(reads);
  // Nothing went on the query list; the check now sits with the passed ones.
  await expect(row).toHaveCount(0);
  await expect(section(page, "identity").getByTestId("xv-incomplete")).toHaveCount(0);
  await expect(areaCard(page, "identity").getByTestId("xv-area-others")).toHaveText(
    "0 could not be checked · 5 passed · 1 not applicable",
  );
  expect((api.queries.get(KESTREL) ?? []).some((q) => q.source_ref?.startsWith("ID-04"))).toBe(
    false,
  );
});

test("an error the engine did not word for the reader shows as the designed state", async ({
  page,
}) => {
  const api = await openBoard(page);
  // The service fails while a decision is recorded.
  api.on("POST", /\/cross-verification\/findings\/fnd-ba1\/decision$/, () => ({
    status: 500,
    json: {},
  }));
  const ba1 = await decide(page, "fnd-ba1", "dismiss", "The account was closed in March.");
  const error = ba1.getByTestId("xv-decision-error");
  await expect(error.getByTestId("state-failed")).toContainText("Something went wrong");
  await expect(error).not.toContainText("Internal Server Error");
  // Unreachable while a request goes on the query list.
  await page.route("**/cross-verification/findings/fnd-id4/query", (route) => route.abort());
  const id4 = page.locator('[data-testid="xv-incomplete-row"][data-rule="ID-04"]');
  await showArea(page, "identity");
  await id4.getByTestId("xv-add-query").click();
  const queryError = id4.getByTestId("xv-query-error");
  await expect(queryError.getByTestId("state-unreachable")).toContainText(
    "The service is not reachable",
  );
  await expect(queryError).not.toContainText("Failed to fetch");
  // A role without the permission reads as such, not as the engine's log line.
  api.on("POST", /\/cross-verification\/findings\/fnd-to1\/query$/, () => ({
    status: 403,
    json: { detail: "role 'credit_analyst' lacks 'review.decide'" },
  }));
  const to1 = page.locator('[data-testid="xv-incomplete-row"][data-rule="TO-01"]');
  await showArea(page, "turnover");
  await to1.getByTestId("xv-add-query").click();
  await expect(to1.getByTestId("xv-query-error").getByTestId("state-forbidden")).toContainText(
    "Not part of your role",
  );
  await expect(to1.getByTestId("xv-query-error")).not.toContainText("lacks");
});

test("without review.decide the decisions are read-only", async ({ page }) => {
  const reader = {
    ...ANALYST,
    permissions: ANALYST.permissions.filter((p) => p !== "review.decide"),
  };
  await openBoard(page, new MockApi(), reader);
  const ob2 = await expand(page, "fnd-ob2");
  await expect(ob2.getByTestId("xv-read-only")).toHaveText("Waiting for a reviewer's decision.");
  await expect(ob2.getByRole("radio")).toHaveCount(0);
  await expect(ob2.getByTestId("xv-save-decision")).toHaveCount(0);
  await expect(page.getByTestId("xv-add-query")).toHaveCount(0);
});

test("each area lists its checks that could not run and what would complete them", async ({
  page,
}) => {
  const api = await openBoard(page);
  const identity = section(page, "identity").getByTestId("xv-incomplete");
  const turnover = section(page, "turnover").getByTestId("xv-incomplete");
  await showArea(page, "identity");
  await expect(identity.getByRole("heading")).toHaveText("Could not be checked (1)");
  await showArea(page, "turnover");
  await expect(turnover.getByRole("heading")).toHaveText("Could not be checked (3)");
  expect(await rules(identity.getByTestId("xv-incomplete-row"))).toEqual(["ID-04"]);
  expect(await rules(turnover.getByTestId("xv-incomplete-row"))).toEqual([
    "TO-01",
    "TO-02",
    "TO-03",
  ]);
  // Hidden where every check ran.
  await expect(section(page, "accounts").getByTestId("xv-incomplete")).toHaveCount(0);
  await expect(section(page, "obligations").getByTestId("xv-incomplete")).toHaveCount(0);
  const row = (rule: string) =>
    page.locator(`[data-testid="xv-incomplete-row"][data-rule="${rule}"]`);

  // What it compares, why it could not run, and what would complete it.
  const to1 = row("TO-01");
  await expect(to1).toContainText("Audited turnover against GST outward supplies · FY 2025-26");
  await expect(to1).toContainText("GST outward supplies covers 8 of 12 months");
  await expect(to1.getByTestId("xv-request")).toHaveText(
    "To complete it, provide GSTR-3B returns for Apr 2025 to Jul 2025.",
  );
  await to1.getByTestId("xv-add-query").click();
  await expect(to1.getByTestId("xv-on-query-list")).toHaveText("On the query list");
  await expect(to1.getByTestId("xv-add-query")).toHaveCount(0);
  expect(
    api.called("POST", `/api/cases/${KESTREL}/cross-verification/findings/fnd-to1/query`),
  ).toHaveLength(1);
  await expect(row("TO-02").getByTestId("xv-on-query-list")).toBeVisible();

  // A document not on file: the request, and the way to add documents.
  await showArea(page, "identity");
  await expect(row("ID-04").getByTestId("xv-request")).toHaveText(
    "To complete it, provide the director KYC.",
  );
  await expect(row("ID-04").getByTestId("xv-add-query")).toBeVisible();
  await expect(row("ID-04").getByTestId("xv-add-documents")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/documents`,
  );

  // Waiting for a person's review: nothing to ask for; the value opens at its page.
  const to3 = row("TO-03");
  await showArea(page, "turnover");
  await expect(to3.getByTestId("xv-request")).toHaveCount(0);
  await expect(to3.getByTestId("xv-add-query")).toHaveCount(0);
  await to3.getByTestId("xv-awaiting-review").click();
  const viewer = page.getByTestId("evidence-viewer");
  await expect(viewer.getByTestId("viewer-page")).toHaveText("Page 7 · pages 3–9");
  await expect(viewer.getByTestId("viewer-value")).toHaveText("41,02,300");
  await page.keyboard.press("Escape");

  // The request is on the pre-login query list.
  await page.goto(`/appraisals/${KESTREL}/completeness#queries`);
  await expect(page.getByTestId("query-list")).toContainText(
    "Please provide GSTR-3B returns for Apr 2025 to Jul 2025, so that the check “Audited turnover against GST outward supplies” can be completed.",
  );
});

test("each area keeps its passed checks closed, with the checks that did not apply and why", async ({
  page,
}) => {
  await openBoard(page);
  const identity = section(page, "identity").getByTestId("xv-passed");
  await expect(identity).not.toHaveAttribute("open", "");
  const summary = identity.locator("summary");
  await expect(summary).toContainText("Passed (4)");
  await expect(summary).toContainText("Not applicable (1)");
  await expect(identity.getByTestId("xv-passed-row").first()).toBeHidden();
  await summary.click();
  expect(await rules(identity.getByTestId("xv-passed-row"))).toEqual([
    "ID-02",
    "ID-03",
    "ID-06",
    "ID-07",
  ]);
  await expect(identity.locator('[data-testid="xv-passed-row"][data-rule="ID-02"]')).toHaveText(
    "ID-02 · GSTIN consistent across documents · Consistent across 3 sources.",
  );
  await expect(identity.getByTestId("xv-not-applicable-row")).toHaveText([
    "ID-08 · Directors in the memorandum are accounted for · No director is named in the memorandum.",
  ]);

  // Hidden where nothing passed and everything applied.
  await expect(section(page, "turnover").getByTestId("xv-passed")).toHaveCount(0);

  const obligations = section(page, "obligations").getByTestId("xv-passed");
  await showArea(page, "obligations");
  await expect(obligations.locator("summary")).toHaveText("Passed (1)");
  await obligations.locator("summary").click();
  await expect(obligations.getByTestId("xv-passed-row")).toHaveText([
    "OB-03 · Borrowings in the books are serviced in the bank · FY 2025-26 · The borrowings in the books are serviced in the bank statements.",
  ]);
  await expect(section(page, "accounts").getByTestId("xv-passed").locator("summary")).toHaveText(
    "Passed (1)",
  );
});

test("each area's facts stay closed, load when opened, and show what that area compared", async ({
  page,
}) => {
  const api = await openBoard(page);
  const facts = (area: string) => section(page, area).getByTestId("xv-facts");
  for (const area of AREAS) await expect(facts(area)).not.toHaveAttribute("open", "");
  expect(api.called("GET", `/api/cases/${KESTREL}/facts`)).toHaveLength(0);
  const panels = (area: string) => facts(area).locator("[data-testid^='facts-']");

  await showArea(page, "identity");
  await facts("identity").locator("summary").click();
  await expect(facts("identity").getByTestId("facts-identity")).toContainText("AAACK1243K");
  await expect(facts("identity").getByTestId("facts-people")).toContainText("Leela Varghese");
  expect(await testIds(panels("identity"))).toEqual(["facts-identity", "facts-people"]);
  expect(api.called("GET", `/api/cases/${KESTREL}/facts`).length).toBeGreaterThan(0);

  await showArea(page, "turnover");
  await facts("turnover").locator("summary").click();
  await expect(facts("turnover").getByTestId("facts-turnover")).toContainText("FY 2025-26");
  expect(await testIds(panels("turnover"))).toEqual(["facts-turnover"]);

  await showArea(page, "accounts");
  await facts("accounts").locator("summary").click();
  await expect(facts("accounts").getByTestId("facts-accounts")).toContainText(
    "Lotuscrest Bank ·1234",
  );
  await expect(facts("accounts").getByTestId("facts-credits")).toContainText("Loan disbursal");
  expect(await testIds(panels("accounts"))).toEqual(["facts-accounts", "facts-credits"]);

  await showArea(page, "obligations");
  await facts("obligations").locator("summary").click();
  const obligations = facts("obligations").getByTestId("facts-obligations");
  await expect(obligations).toContainText("ASHWOOD FINSERV");
  await expect(obligations).toContainText("Tidewater Finance");
  expect(await testIds(panels("obligations"))).toEqual(["facts-obligations"]);

  // The board resolution and income tax are not compared on this screen.
  await expect(page.getByTestId("facts-authority")).toHaveCount(0);
  await expect(page.getByTestId("facts-tax")).toHaveCount(0);
});

test("a board without discrepancies says so and leaves the draft open", async ({ page }) => {
  const api = new MockApi();
  api.boards.set(
    KESTREL,
    boardWith((items) => items.filter((i) => i.finding.outcome !== "fail")),
  );
  await openBoard(page, api);
  await expect(page.getByTestId("xv-summary-line")).toHaveText(
    "Every source lined up against every other. No discrepancy found for this borrower.",
  );
  // Nothing to adjudicate: the meta line gives the run alone.
  await expect(page.getByTestId("xv-meta-line")).toHaveText(
    "XR-000021-003 · 18 rules across 9 sources · 09 Oct 2026, 14:00",
  );
  await expect(page.getByTestId("xv-banner")).toHaveCount(0);
  const statuses = {
    identity: "incomplete",
    turnover: "incomplete",
    accounts: "clear",
    obligations: "clear",
  };
  for (const [area, status] of Object.entries(statuses)) {
    await expect(areaCard(page, area)).toHaveAttribute("data-status", status);
    await expect(areaCard(page, area).getByTestId("xv-area-open")).toHaveText("0");
    await expect(areaCard(page, area).getByTestId("xv-area-top")).toHaveText("No discrepancy");
    await showArea(page, area);
    await expect(section(page, area).getByTestId("xv-area-none")).toBeVisible();
  }
  await expect(page.locator("[data-expanded]")).toHaveCount(0);
  await expect(page.getByTestId("xv-continue")).toHaveAttribute(
    "href",
    `/appraisals/${KESTREL}/outputs?view=cam`,
  );
});

test("without a run on record the meta line gives the decisions alone", async ({ page }) => {
  const api = new MockApi();
  const board = kestrelBoard();
  api.boards.set(KESTREL, { ...board, run: null });
  await openBoard(page, api);
  await expect(page.getByTestId("xv-meta-line")).toHaveText("1 of 7 adjudicated");
});

test("before any check has run, the board says so", async ({ page }) => {
  await signedIn(page, new MockApi());
  await page.goto(`/appraisals/${SAFFRON}/cross-verification`);
  await expect(page.getByTestId("xv-summary-line")).toHaveText(
    "No checks have run yet for this borrower.",
  );
  await expect(page.getByTestId("xv-board")).toContainText("No checks yet");
  await expect(page.getByTestId("xv-meta-line")).toHaveCount(0);
  await expect(page.getByTestId("xv-banner")).toHaveCount(0);
  await expect(page.getByTestId("xv-overview")).toHaveCount(0);
});

/** Every card open, with the evidence of one of its sources, the line-by-line tables, and in
 * every area the passed checks and the facts. */
async function openEverything(page: Page) {
  const evidence: [string, string][] = [
    ["fnd-ob2", "instalments"],
    ["fnd-ob1", "bureau"],
    ["fnd-id1", "group-0"],
    ["fnd-id5", "statement-1"],
    ["fnd-to5", "bank"],
    ["fnd-ba1", "declared"],
    ["fnd-to4", "audited"],
  ];
  for (const [id, column] of evidence) {
    const c = await expand(page, id);
    await c.getByTestId(`xv-column-${column}`).getByTestId("xv-open-evidence").click();
    await expect(c.getByTestId("xv-evidence-panel")).toBeVisible();
  }
  // One area's section at a time: open the rest of each in turn, the page never scrolling sideways.
  for (const area of AREAS) {
    await showArea(page, area);
    const s = section(page, area);
    for (const lines of await s.getByTestId("xv-line-by-line").all()) {
      await lines.locator("summary").click();
      await expect(lines.getByTestId("xv-detail-table")).toBeVisible();
    }
    for (const passed of await s.getByTestId("xv-passed").all())
      await passed.locator("summary").click();
    for (const facts of await s.getByTestId("xv-facts").all())
      await facts.locator("summary").click();
    expect(await scrollsSideways(page), `the ${area} section scrolls sideways`).toBe(false);
  }
  await showArea(page, "accounts");
  await expect(page.getByTestId("facts-credits")).toBeVisible();
  await showArea(page, "identity");
  await expect(page.getByTestId("facts-people")).toBeVisible();
}

type CardLayout = {
  y: number;
  height: number;
  /** Where the top finding and the key figures start (null when the card has none). */
  top: number | null;
  figures: number | null;
  /** Whether every key figure sits inside the card. */
  inside: boolean;
};

/** Each area card, in order, measured at once and only once the page has stopped moving: the
 * case header and the scroll bar arrive after the board, and both move or reflow the cards. */
async function overviewLayout(page: Page): Promise<CardLayout[]> {
  const measure = () =>
    page.getByTestId("xv-overview").evaluate((overview) =>
      Array.from(overview.querySelectorAll("[data-testid^='xv-area-card-']"), (card) => {
        const box = card.getBoundingClientRect();
        const start = (testId: string) => {
          const el = card.querySelector(`[data-testid="${testId}"]`);
          return el ? Math.round(el.getBoundingClientRect().y) : null;
        };
        const lines = Array.from(card.querySelectorAll('[data-testid="xv-area-highlight"]'));
        return {
          y: Math.round(box.y),
          height: Math.round(box.height),
          top: start("xv-area-top"),
          figures: start("xv-area-highlights"),
          inside: lines.every((line) => {
            const b = line.getBoundingClientRect();
            return (
              b.left >= box.left - 0.5 &&
              b.right <= box.right + 0.5 &&
              b.top >= box.top - 0.5 &&
              b.bottom <= box.bottom + 0.5
            );
          }),
        };
      }),
    );
  let last = "";
  await expect
    .poll(
      async () => {
        const now = JSON.stringify(await measure());
        const settled = now === last;
        last = now;
        return settled;
      },
      { intervals: [100, 200, 300, 500] },
    )
    .toBe(true);
  return JSON.parse(last) as CardLayout[];
}

/** The vertical position of each area card, in order. */
async function cardTops(page: Page): Promise<number[]> {
  return (await overviewLayout(page)).map((c) => c.y);
}

test.describe("at 1366 px, beside the side menu", () => {
  test.use({ viewport: { width: 1366, height: 768 } });

  test("the four area cards share a row, and nothing scrolls sideways", async ({ page }) => {
    await openBoard(page);
    await expect(page.getByTestId("case-nav")).toBeVisible();
    const tops = await cardTops(page);
    expect(new Set(tops).size).toBe(1);
    expect(await scrollsSideways(page)).toBe(false);
    await openEverything(page);
    expect(await scrollsSideways(page)).toBe(false);
  });

  test("the cards keep one height, their parts level, the key figures inside", async ({ page }) => {
    await openBoard(page);
    const cards = await overviewLayout(page);
    expect(new Set(cards.map((c) => c.height)).size).toBe(1);
    // The top findings and the key figures start level across the row.
    expect(new Set(cards.map((c) => c.top)).size).toBe(1);
    expect(new Set(cards.map((c) => c.figures)).size).toBe(1);
    expect(cards.map((c) => c.inside)).toEqual([true, true, true, true]);
    expect(await scrollsSideways(page)).toBe(false);
  });
});

test.describe("on a narrower screen", () => {
  test.use({ viewport: { width: 1024, height: 768 } });

  test("the area cards go two by two", async ({ page }) => {
    await openBoard(page);
    const [a, b, c, d] = await cardTops(page);
    expect(a).toBe(b);
    expect(c).toBe(d);
    expect(c!).toBeGreaterThan(a!);
    expect(await scrollsSideways(page)).toBe(false);
  });
});

test.describe("at phone width", () => {
  test.use({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });

  test("the board stacks without scrolling sideways", async ({ page }) => {
    await openBoard(page);
    // One area card under another, each with its key figures inside it.
    for (const area of AREAS) await expect(keyFigures(page, area).first()).toBeVisible();
    const cards = await overviewLayout(page);
    const tops = cards.map((c) => c.y);
    expect([...tops].sort((x, y) => x - y)).toEqual(tops);
    expect(new Set(tops).size).toBe(4);
    expect(cards.map((c) => c.inside)).toEqual([true, true, true, true]);
    expect(await scrollsSideways(page)).toBe(false);
    await openEverything(page);
    expect(await scrollsSideways(page)).toBe(false);
    // The sources stack: the second column sits below the first.
    const ob2 = card(page, "fnd-ob2");
    await showArea(page, "obligations");
    const first = await ob2.getByTestId("xv-column-instalments").boundingBox();
    const second = await ob2.getByTestId("xv-column-declaration").boundingBox();
    expect(second!.y).toBeGreaterThanOrEqual(first!.y + first!.height - 1);
  });
});

test("the turnover section opens with every compared pair of figures, coloured by the engine's outcome", async ({
  page,
}) => {
  // One turnover check of each outcome; the screen colours what the engine decided and
  // measures nothing itself.
  const turnover = (
    id: string,
    rule_id: string,
    outcome: XvItem["finding"]["outcome"],
    tolerance: string | null,
    a: number | string,
    b: number | string,
  ) =>
    xvItem(
      xvFinding({
        id,
        rule_id,
        title: `${rule_id} comparison`,
        area: "turnover",
        outcome,
        severity: "moderate",
        blocking: false,
        explanation: outcome === "incomplete" ? "GST outward supplies cover 7 of 12 months." : "",
        scope: "FY 2025-26",
        tolerance,
        sides: [
          xvSide("Audited financial statements", a, [{ document_id: "doc-bs", page: 4 }]),
          xvSide("GST outward supplies", b, []),
        ],
      }),
    );
  const api = new MockApi();
  api.boards.set(
    KESTREL,
    boardWith((items) => [
      ...items.filter((i) => i.finding.area !== "turnover"),
      turnover("t-fail", "TO-01", "fail", "1%", 118_000_000, 68_600_000),
      turnover("t-pass", "TO-02", "pass", "1%", 117_600_000, 117_000_000),
      turnover("t-incomplete", "TO-03", "incomplete", "1%", 118_000_000, 68_250_000),
      turnover("t-exact", "TO-05", "pass", null, "FY 2025-26", "FY 2025-26"),
      turnover("t-na", "TO-04", "not_applicable", null, "", ""),
    ]),
  );
  await openBoard(page, api);

  const figures = section(page, "turnover").getByTestId("xv-figures");
  await showArea(page, "turnover");
  await expect(figures).toBeVisible();
  const rows = figures.getByTestId("xv-figure-row");
  // Every check that compared two figures, discrepancy or not, in the engine's order; one that
  // did not apply is left out.
  expect(await rules(rows)).toEqual(["TO-01", "TO-03", "TO-02", "TO-05"]);
  expect(await outcomes(rows)).toEqual(["fail", "incomplete", "pass", "pass"]);

  const row = (rule: string) => figures.locator(`[data-rule="${rule}"]`);
  await expect(row("TO-01")).toContainText("Outside tolerance");
  await expect(row("TO-01").getByTestId("xv-figure-value").first()).toHaveText("INR 11.80 cr");
  await expect(row("TO-01").getByTestId("xv-figure-value").first()).toHaveClass(/text-destructive/);
  await expect(row("TO-02")).toContainText("Within tolerance");
  await expect(row("TO-02").getByTestId("xv-figure-value").nth(1)).toHaveClass(/text-positive/);
  await expect(row("TO-03")).toContainText("Not compared");
  // A rule with no tolerance compares exactly.
  await expect(row("TO-05")).toContainText("Agrees");

  // The first discrepancy is selected, its card beside the list.
  const panel = section(page, "turnover").getByTestId("xv-figure-panel");
  await expect(row("TO-01")).toHaveAttribute("data-selected", "true");
  await expect(panel.getByTestId("xv-card-t-fail")).toHaveAttribute("data-expanded", "true");
  // Selecting another comparison shows it there: a check that is not a discrepancy, read-only,
  // with why it could not be compared and its sources.
  await row("TO-03").getByTestId("xv-figure-select").click();
  await expect(row("TO-03")).toHaveAttribute("data-selected", "true");
  const check = panel.getByTestId("xv-check-panel");
  await expect(check).toHaveAttribute("data-outcome", "incomplete");
  await expect(check).toContainText("GST outward supplies cover 7 of 12 months.");
  await expect(check.getByTestId("xv-adjudication")).toHaveCount(0);
  await expect(panel.getByTestId("xv-card-t-fail")).toHaveCount(0);

  // The other areas do not carry the table.
  await expect(section(page, "identity").getByTestId("xv-figures")).toHaveCount(0);
});

test("the areas' sections sit behind tabs: one area at a time, a card choosing its tab", async ({
  page,
}) => {
  await openBoard(page);
  const tab = (area: string) => page.getByTestId(`xv-area-tab-${area}`);
  // The tabs follow the areas, each with its open discrepancies; the top discrepancy's area first.
  for (const area of AREAS) await expect(tab(area)).toBeVisible();
  await expect(tab("identity")).toHaveAttribute("data-state", "active");
  await expect(section(page, "identity")).toBeVisible();
  await expect(section(page, "turnover")).toBeHidden();
  await expect(areaCard(page, "identity")).toHaveAttribute("data-active", "true");
  // A card selects its area's tab and shows its section alone, the card marked.
  await areaCard(page, "turnover").getByTestId("xv-area-open-section").click();
  await expect(tab("turnover")).toHaveAttribute("data-state", "active");
  await expect(section(page, "turnover")).toBeVisible();
  await expect(section(page, "identity")).toBeHidden();
  await expect(areaCard(page, "turnover")).toHaveAttribute("data-active", "true");
  await expect(areaCard(page, "identity")).toHaveAttribute("data-active", "false");
  // The tab itself does the same.
  await tab("obligations").click();
  await expect(section(page, "obligations")).toBeVisible();
  await expect(section(page, "turnover")).toBeHidden();
  // A key figure in another area switches to it before opening its finding.
  await keyFigures(page, "identity").first().click();
  await expect(tab("identity")).toHaveAttribute("data-state", "active");
});
