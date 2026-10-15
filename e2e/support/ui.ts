/// <reference types="node" />
// Browser-only helpers for the integration specs: every action here is
// performed through the screens, as a user would. Nothing is set up over the
// API. Selectors are data-testid, role or label only.
//
// The engine behind these specs runs with CREDITIQ_INGEST=stub, so document
// processing replays the recorded results in tests/fixtures/ingest/ keyed by
// file hash: deterministic plumbing, NOT a test of extraction accuracy.
import { readFileSync } from "node:fs";
import { basename, resolve } from "node:path";

import { expect, type Locator, type Page } from "@playwright/test";

export const REPO_ROOT = resolve(import.meta.dirname, "..", "..");

export const PASSWORD = "CreditIQ-2026!";
export const USERS = {
  rm: {
    email: "arjun.deshpande@rblbank.com",
    name: "Arjun Deshpande",
    role: "Relationship Manager",
  },
  analyst: {
    email: "ananya.krishnan@rblbank.com",
    name: "Ananya Krishnan",
    role: "Credit Analyst",
  },
  manager: {
    email: "meenal.kulkarni@rblbank.com",
    name: "Meenal Kulkarni",
    role: "Credit Manager",
  },
} as const;
export type Role = keyof typeof USERS;

/** A sourcing message that proposes the three fields a case needs at minimum. */
export const SOURCING_MESSAGE = [
  "From: RM desk, Mumbai hub",
  "Subject: CC renewal",
  "",
  "Client Kestrel Polymers Pvt Ltd wants CC of 50L and a TL, PAN AAACK1234K.",
  "Constitution is Pvt Ltd or maybe LLP, to confirm.",
  "Turnover approx 3 cr. Directors Kabir Rao and Leela Varghese.",
].join("\n");

/** Sign in through the form and land on the workbench. */
export async function signIn(page: Page, role: Role): Promise<void> {
  await page.goto("/sign-in");
  const submit = page.getByRole("button", { name: "Sign in" });
  await expect(submit).toBeEnabled();
  await page.getByLabel("Email").fill(USERS[role].email);
  await page.getByLabel("Password").fill(PASSWORD);
  await submit.click();
  await expect(page).toHaveURL(/\/$/);
}

/** Sign out from the top bar. */
export async function signOut(page: Page): Promise<void> {
  await page.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/sign-in$/);
}

/** The side navigation's links, by their accessible names. */
export async function navLinkNames(page: Page): Promise<string[]> {
  const nav = page.getByRole("navigation").first();
  return nav.getByRole("link").allInnerTexts();
}

/**
 * Create a case through the New appraisal screen: paste, read, settle every
 * field the screen asks about, then create. Returns the new case's id, read
 * from the URL the screen lands on.
 */
export async function createCaseViaUi(
  page: Page,
  opts: { message?: string; borrower?: string; channel?: string } = {},
): Promise<string> {
  await page.goto("/appraisals/new");
  await page.getByTestId("channel").selectOption(opts.channel ?? "email");
  await page.getByTestId("message-input").fill(opts.message ?? SOURCING_MESSAGE);
  await page.getByRole("button", { name: "Read the message" }).click();
  await expect(page.getByTestId("proposed-case")).toBeVisible();

  // A unique borrower keeps specs independent of each other's data and clear of
  // the duplicate-case check (F-04.5). The default message leaves the borrower
  // unclear on purpose, so one has to be given.
  if (opts.borrower) {
    await page.getByTestId("field-borrower").getByRole("textbox").fill(opts.borrower);
  }

  await settleProposedFields(page);

  const create = page.getByTestId("create-application");
  const warning = page.getByTestId("duplicate-warning");
  // The duplicate check answers after the proposal; a borrower already on file
  // blocks creation until a reason is given (F-04.5).
  await expect(async () => {
    if ((await warning.count()) > 0 && (await page.getByTestId("override-reason").count()) === 0) {
      await warning.getByRole("button", { name: "Create anyway" }).click();
      await page.getByTestId("override-reason").fill("A separate facility for the same borrower.");
    }
    await expect(create).toBeEnabled();
  }).toPass({ timeout: 30_000, intervals: [300, 700, 1500] });

  await create.click();

  // With no attachment the screen goes straight to Files, so the next step
  // (uploading) is in front of the RM; with one, it goes to the Overview.
  await expect(page).toHaveURL(/\/appraisals\/BBG-\d{4}-\d{6}(\/documents)?$/, {
    timeout: 30_000,
  });
  return caseIdFromUrl(page);
}

/** Confirm every field the screen still wants confirmed, until none is left. */
export async function settleProposedFields(page: Page): Promise<void> {
  const banner = page.getByTestId("needs-confirmation");
  // Each click settles one field and re-renders the list, so take them one at a
  // time and stop when the screen stops asking.
  for (let guard = 0; guard < 25; guard++) {
    if ((await banner.count()) === 0) return;
    const buttons = page.locator('[data-testid^="confirm-"]');
    if ((await buttons.count()) === 0) return;
    await buttons.first().click();
  }
  throw new Error("still asking for confirmations after 25 clicks");
}

export function caseIdFromUrl(page: Page): string {
  const match = /\/appraisals\/(BBG-\d{4}-\d{6})/.exec(page.url());
  if (!match) throw new Error(`no case id in the url: ${page.url()}`);
  return match[1]!;
}

/** A fixture document, as a Playwright file payload. */
export function fixtureFile(name: string): {
  name: string;
  mimeType: string;
  buffer: Buffer;
} {
  return {
    name: basename(name),
    mimeType: "application/pdf",
    buffer: readFileSync(resolve(REPO_ROOT, "tests", "fixtures", "files", name)),
  };
}

/** The file names of a fixture case set ("complete" = Kestrel, "partial" = Heronbay). */
export function fixtureSet(name: "complete" | "partial"): string[] {
  const path = resolve(REPO_ROOT, "tests", "fixtures", "cases.json");
  return (JSON.parse(readFileSync(path, "utf-8")) as Record<string, string[]>)[name]!;
}

/** Upload documents from the case's Documents screen, as a user does. */
export async function uploadViaUi(page: Page, caseId: string, names: string[]): Promise<void> {
  await page.goto(`/appraisals/${caseId}/documents`);
  await expect(page.getByTestId("upload-zone")).toBeVisible();
  await page.getByTestId("upload-input").setInputFiles(names.map(fixtureFile));
}

/**
 * Wait, on screen, until no stage of the case is still in progress. The stage
 * bar carries each stage's status as data-status and refreshes without a reload
 * (F-02.3, a two-second worker), so this polls the UI, never a fixed sleep.
 */
export async function waitForStagesOnScreen(page: Page, timeout = 180_000): Promise<void> {
  await expect(page.getByTestId("stage-progress")).toBeVisible();
  await expect(async () => {
    const stillRunning = await page.locator('[data-status="in_progress"]').count();
    const started = await page.locator('[data-status="done"]').count();
    expect(
      stillRunning === 0 && started > 0,
      `stages on screen: ${await stageStatuses(page)}`,
    ).toBeTruthy();
  }).toPass({ timeout, intervals: [500, 1000, 2000] });
}

/** Each stage and its status, as the stage bar shows them. */
export async function stageStatuses(page: Page): Promise<string> {
  const keys = [
    "documents",
    "extraction",
    "completeness",
    "cross_verification",
    "policy",
    "outputs",
  ];
  const out: string[] = [];
  for (const key of keys) {
    const el = page.getByTestId(`stage-${key}`).first();
    out.push(`${key}=${(await el.count()) ? await el.getAttribute("data-status") : "absent"}`);
  }
  return out.join(" ");
}

/** The case tabs visible to the signed-in role, by accessible name. */
export function caseTabs(page: Page): Locator {
  return page.getByTestId("case-nav").getByRole("link");
}

/** Delete a case from its own screen, confirming as the dialog requires. */
export async function deleteCaseViaUi(page: Page, caseId: string): Promise<void> {
  await page.goto(`/appraisals/${caseId}`);
  // Wait for the case screen before looking for the control: counting straight
  // after a goto finds nothing and would skip the deletion in silence.
  await expect(page.getByTestId("case-header")).toContainText(caseId);
  const open = page.getByTestId("delete-case");
  await expect(open).toBeVisible();
  await open.click();
  // The confirmation is an alert dialog (components/cases/DeleteCaseButton.tsx).
  const dialog = page.getByRole("alertdialog");
  await expect(dialog).toBeVisible();
  // The dialog will not submit until both a reason and the case id are typed.
  await dialog.getByLabel("Reason").fill("automated test cleanup");
  await dialog.getByLabel(`Type ${caseId} to confirm`).fill(caseId);
  const confirm = page.getByTestId("delete-case-confirm");
  await expect(confirm).toBeEnabled();
  await confirm.click();
  await expect(page).toHaveURL(/\/$/, { timeout: 30_000 });
}
