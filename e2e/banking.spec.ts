// The Banking view of the Financials section: the case's statement transactions each filed under a category, how
// each was read (a rule, the model, a person), and what the accounts show. The screen arranges; the engine decides
// nothing here, and a person's filing goes to the engine with its reason.
import { expect, test, type Page } from "@playwright/test";
import type { BankConduct, TxnRow } from "../src/api/types";
import { ANALYST, KESTREL } from "./fixtures/data";
import { MockApi, emptyConduct, scrollsSideways, signedIn } from "./support/api";

const POLICY_PATH = `/appraisals/${KESTREL}/policy`;
const ACCOUNT = "Lotuscrest Bank ·1234";
const page7 = [{ document_id: "doc-bank", page: 7 }];

const row = (
  n: number,
  date: string,
  narration: string,
  side: { credit?: number; debit?: number },
  category: string,
  label: string,
  over: Partial<TxnRow> = {},
): TxnRow => ({
  txn_id: `FV-${n}`,
  document_id: "doc-bank",
  account: ACCOUNT,
  seq: n,
  date,
  narration,
  debit: side.debit ?? 0,
  credit: side.credit ?? 0,
  category,
  category_label: label,
  direction: side.credit ? "credit" : "debit",
  status: "matched",
  method: "rule",
  rule_id: "r",
  confidence: 0.9,
  channel: null,
  counterparty: null,
  candidates: [],
  flags: [],
  paired_with: null,
  needs_review: false,
  reason: null,
  evidence: page7,
  ...over,
});

const ROWS: TxnRow[] = [
  row(
    1,
    "2025-04-03",
    "NEFT CR ORCHID TRADERS",
    { credit: 700_000 },
    "customer_receipt",
    "Receipt from a customer",
    {
      counterparty: "ORCHID TRADERS",
    },
  ),
  row(
    2,
    "2025-04-05",
    "CASH DEPOSIT CDM TALOJA",
    { credit: 400_000 },
    "cash_deposit",
    "Cash deposit",
  ),
  row(3, "2025-04-28", "NEFT DR SALARY", { debit: 120_000 }, "salary", "Salary and wages"),
  row(
    4,
    "2025-05-02",
    "BY TRANSFER 402211009988 ORCHID MART PAYMENT",
    { credit: 7_200 },
    "customer_receipt",
    "Receipt from a customer",
    {
      method: "model",
      rule_id: null,
      confidence: 0.75,
      reason: "“ORCHID MART PAYMENT” indicates customer payment",
    },
  ),
  row(5, "2025-05-09", "ZZ-SETTLEMENT 77/ADJ", { debit: 1_250 }, "other_debit", "Other debit", {
    status: "unmatched",
    rule_id: null,
    confidence: 0,
    needs_review: true,
    reason: "narration unclear",
  }),
  row(
    6,
    "2025-05-12",
    "BY 004419 AMBER OILS",
    { credit: 310_000 },
    "other_credit",
    "Other credit",
    {
      status: "unmatched",
      rule_id: null,
      confidence: 0,
      needs_review: true,
      candidates: ["customer_receipt"],
    },
  ),
];

const CONDUCT: BankConduct = {
  ...emptyConduct(KESTREL),
  accounts: [ACCOUNT],
  months: [
    {
      month: "2025-04",
      credits: 1_100_000,
      business_credits: 1_100_000,
      customer_receipts: 700_000,
      cash_deposits: 400_000,
      cash_share_pct: 36.4,
      returns_count: 1,
      returns_amount: 25_000,
      failed_debits_reversed: 0,
      salary: 120_000,
      salary_day: 28,
      statutory: {},
      promoter_in: 0,
      promoter_out: 0,
    },
    {
      month: "2025-05",
      credits: 317_200,
      business_credits: 317_200,
      customer_receipts: 7_200,
      cash_deposits: 0,
      cash_share_pct: 0,
      returns_count: 0,
      returns_amount: 0,
      failed_debits_reversed: 0,
      salary: 0,
      salary_day: null,
      statutory: {},
      promoter_in: 0,
      promoter_out: 0,
    },
  ],
  customers: [{ party: "ORCHID TRADERS", amount: 700_000, count: 1, share_pct: 100 }],
  customer_top1_pct: 100,
  customer_top5_pct: 100,
  flags: [
    {
      kind: "unsettled",
      severity: "info",
      message: "2 transactions pending classification; included in the figures as they stand",
      evidence: page7,
    },
    {
      kind: "cash",
      severity: "watch",
      message: "Apr 2025: cash deposits are 36% of credits",
      month: "2025-04",
      evidence: page7,
    },
    {
      kind: "returns",
      severity: "concern",
      message: "Apr 2025: 1 cheque return (dishonoured)",
      month: "2025-04",
      evidence: page7,
    },
  ],
  round_trips: [
    {
      party: "ACME TRADERS",
      out_date: "2025-04-03",
      out_amount: 500_000,
      in_date: "2025-04-09",
      in_amount: 490_000,
      evidence: page7,
    },
  ],
  unsettled_count: 2,
};

async function openBanking(page: Page, opts: { rows?: TxnRow[]; user?: typeof ANALYST } = {}) {
  const api = new MockApi();
  const rows = opts.rows ?? structuredClone(ROWS);
  api.transactions.set(KESTREL, rows);
  if (rows.length > 0) api.conducts.set(KESTREL, CONDUCT);
  await signedIn(page, api, opts.user ?? ANALYST);
  await page.goto(POLICY_PATH);
  await page.getByTestId("financials-tab-banking").click();
  return api;
}

const txn = (page: Page) => page.getByTestId("banking-txn");

test("the Banking tab sits with the statements and is badged with what is unclassified", async ({
  page,
}) => {
  await openBanking(page);
  await expect(page.getByTestId("financials-tab-banking")).toContainText("Banking");
  await expect(
    page.getByTestId("financials-tab-banking").getByTestId("financials-tab-count"),
  ).toHaveText(/2/);
  await expect(page.getByTestId("banking")).toBeVisible();
});

test("the counts say how many were read by the rules, the model and a person, and how many are open", async ({
  page,
}) => {
  await openBanking(page);
  await expect(page.getByTestId("banking-count-total")).toContainText("6");
  await expect(page.getByTestId("banking-count-rule")).toContainText("3");
  await expect(page.getByTestId("banking-count-model")).toContainText("1");
  await expect(page.getByTestId("banking-count-person")).toContainText("0");
  await expect(page.getByTestId("banking-count-open")).toContainText("2");
  await expect(page.getByTestId("banking-counts")).toContainText("included in business inflow");
});

test("the flags are questions for a person, concerns first, each with its page", async ({
  page,
}) => {
  await openBanking(page);
  const flags = page.getByTestId("banking-flag");
  await expect(flags).toHaveCount(3);
  expect(await flags.evaluateAll((els) => els.map((e) => e.getAttribute("data-severity")))).toEqual(
    ["info", "watch", "concern"],
  );
  await expect(flags.nth(2)).toContainText("1 cheque return (dishonoured)");
  await flags.nth(2).getByTestId("banking-flag-page").click();
  await expect(page.getByTestId("evidence-viewer")).toBeVisible();
});

test("the months, the categories, the customers and the money out and back are laid out", async ({
  page,
}) => {
  await openBanking(page);
  await expect(page.getByTestId("banking-month")).toHaveCount(2);
  await expect(page.getByTestId("banking-month").first()).toContainText("11.00");
  await expect(page.getByTestId("banking-month").first()).toContainText("36%");
  const category = page.locator(
    '[data-testid="banking-category"][data-category="customer_receipt"]',
  );
  await expect(category).toContainText("7.07");
  await expect(page.getByTestId("banking-customer")).toContainText("ORCHID TRADERS");
  const trip = page.getByTestId("banking-trip");
  await expect(trip).toContainText("ACME TRADERS");
  await expect(trip).toContainText("5,00,000");
  await expect(trip).toContainText("03 Apr 2025");
  await expect(trip).toContainText("4,90,000");
  await expect(trip).toContainText("09 Apr 2025");
});

test("each row says how it was read, a row nothing settled is open with a suggestion, and the model's reason is kept", async ({
  page,
}) => {
  await openBanking(page);
  const by = (narration: string) => txn(page).filter({ hasText: narration });
  await expect(by("ORCHID TRADERS").first()).toHaveAttribute("data-method", "rule");
  await expect(by("ORCHID MART")).toHaveAttribute("data-method", "model");
  await expect(by("ORCHID MART")).toContainText("Model");
  await expect(by("ORCHID MART")).toContainText(
    "Basis: “ORCHID MART PAYMENT” indicates customer payment",
  );
  await expect(by("AMBER OILS")).toHaveAttribute("data-open", "true");
  await expect(by("AMBER OILS")).toContainText("Unclassified");
  await expect(by("AMBER OILS")).toContainText("Suggested category: Receipt from a customer");
});

test("the list narrows by category, by what is open, and by what is typed", async ({ page }) => {
  await openBanking(page);
  await expect(txn(page)).toHaveCount(6);
  await page.getByTestId("banking-filter-category").selectOption("salary");
  await expect(txn(page)).toHaveCount(1);
  await page.getByTestId("banking-filter-category").selectOption("");
  await page.getByTestId("banking-filter-status").selectOption("open");
  await expect(txn(page)).toHaveCount(2);
  await page.getByTestId("banking-filter-status").selectOption("all");
  await page.getByTestId("banking-filter-search").fill("orchid");
  await expect(txn(page)).toHaveCount(2);
  await page.getByTestId("banking-filter-search").fill("nothing like this");
  await expect(page.getByTestId("banking-empty-list")).toBeVisible();
});

test("a row opens its page", async ({ page }) => {
  await openBanking(page);
  await txn(page).first().getByTestId("banking-txn-page").click();
  await expect(page.getByTestId("evidence-viewer")).toBeVisible();
});

test("a person files an open row under a category with a reason; it counts as theirs and is no longer open", async ({
  page,
}) => {
  await openBanking(page);
  const open = txn(page).filter({ hasText: "ZZ-SETTLEMENT" });
  await open.getByTestId("banking-file").click();
  const dialog = page.getByTestId("banking-file-dialog");
  await expect(dialog).toContainText("ZZ-SETTLEMENT 77/ADJ");
  // Only the categories of a debit are offered for a debit.
  const offered = await dialog
    .getByTestId("banking-file-category")
    .locator("option")
    .allTextContents();
  expect(offered).toContain("Bank charges and penalties");
  expect(offered).not.toContain("Cash deposit");
  await dialog.getByTestId("banking-file-category").selectOption("bank_charges");
  await expect(dialog.getByTestId("banking-file-save")).toBeDisabled();
  await dialog.getByTestId("banking-file-reason").fill("ab");
  await expect(dialog.getByTestId("banking-file-save")).toBeDisabled();
  await dialog.getByTestId("banking-file-reason").fill("Quarterly service fee on the passbook");
  await dialog.getByTestId("banking-file-save").click();
  await expect(dialog).toBeHidden();
  const filed = txn(page).filter({ hasText: "ZZ-SETTLEMENT" });
  await expect(filed).toHaveAttribute("data-method", "manual");
  await expect(filed).toHaveAttribute("data-open", "false");
  await expect(filed).toContainText("Bank charges and penalties");
  await expect(page.getByTestId("banking-count-person")).toContainText("1");
  await expect(page.getByTestId("banking-count-open")).toContainText("1");
});

test("a person's decision can be taken off again", async ({ page }) => {
  await openBanking(page);
  const open = txn(page).filter({ hasText: "ZZ-SETTLEMENT" });
  await open.getByTestId("banking-file").click();
  await page.getByTestId("banking-file-category").selectOption("bank_charges");
  await page.getByTestId("banking-file-reason").fill("Quarterly service fee");
  await page.getByTestId("banking-file-save").click();
  await expect(open).toHaveAttribute("data-method", "manual");
  await open.getByTestId("banking-file").click();
  await page.getByTestId("banking-file-remove").click();
  await expect(open).toHaveAttribute("data-open", "true");
  await expect(page.getByTestId("banking-count-person")).toContainText("0");
});

test("someone who may not decide sees the rows and their pages but no way to file them", async ({
  page,
}) => {
  await openBanking(page, {
    user: { ...ANALYST, permissions: ANALYST.permissions.filter((p) => p !== "review.decide") },
  });
  await expect(txn(page)).toHaveCount(6);
  await expect(page.getByTestId("banking-file")).toHaveCount(0);
  await expect(page.getByTestId("banking-txn-page").first()).toBeVisible();
});

test("a case with no bank transactions says so", async ({ page }) => {
  await openBanking(page, { rows: [] });
  await expect(page.getByTestId("banking-none")).toContainText("No bank statement transactions");
  await expect(
    page.getByTestId("financials-tab-banking").getByTestId("financials-tab-count"),
  ).toHaveCount(0);
});

test("on a phone the tab reads without scrolling the page sideways", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await openBanking(page);
  await expect(page.getByTestId("banking")).toBeVisible();
  expect(await scrollsSideways(page)).toBe(false);
});

test("the register shows a page at a time and offers more", async ({ page }) => {
  const many = Array.from({ length: 30 }, (_, i) =>
    row(
      100 + i,
      "2025-04-03",
      `NEFT CR CUSTOMER ${i}`,
      { credit: 1_000 + i },
      "customer_receipt",
      "Receipt from a customer",
    ),
  );
  await openBanking(page, { rows: many });
  await expect(txn(page)).toHaveCount(25);
  await expect(page.getByTestId("banking-transactions")).toContainText("25 of 30");
  await page.getByTestId("banking-more").click();
  await expect(txn(page)).toHaveCount(30);
  await expect(page.getByTestId("banking-more")).toHaveCount(0);
});

test("dates read as elsewhere in the appraisal, and months are written Sep, not Sept", async ({
  page,
}) => {
  await openBanking(page, {
    rows: [
      row(
        1,
        "2025-04-03",
        "NEFT CR ORCHID TRADERS",
        { credit: 700_000 },
        "customer_receipt",
        "Receipt from a customer",
      ),
      row(
        2,
        "2025-09-03",
        "NEFT CR BHARAT PUMPS",
        { credit: 100_000 },
        "customer_receipt",
        "Receipt from a customer",
      ),
    ],
  });
  await expect(txn(page).first()).toContainText("03 Apr 2025");
  await expect(page.getByTestId("banking-categories")).toContainText("Sep 2025");
  await expect(page.getByTestId("banking-categories")).not.toContainText("Sept");
});
