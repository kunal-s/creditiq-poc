/// <reference types="node" />
// Helpers shared by the integration specs. Every user-visible action goes
// through the screens; the only thing done behind the UI is pinning a case's
// `as_of`, for which no endpoint exists (it mirrors tests/conftest.py::set_as_of).
//
// The engine behind these specs runs with CREDITIQ_INGEST=stub, so document
// processing replays the recorded results in tests/fixtures/ingest/ keyed by
// file hash: deterministic plumbing, NOT a test of extraction accuracy.
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";

import { expect, type Page } from "@playwright/test";

import { REPO_ROOT, caseIdFromUrl, settleProposedFields } from "./ui";

/** The frozen date every age and window rule in these specs reads (principle 5). */
export const AS_OF = "2026-09-29";

const DATA_ROOT = process.env["E2E_DATA_ROOT"] ?? "workflow/data-e2e";
const DB = resolve(REPO_ROOT, DATA_ROOT, "creditiq.sqlite3");
const PYTHON = resolve(REPO_ROOT, ".venv", "bin", "python");

/** The borrower names the recorded fixture sets belong to. */
export const KESTREL = "Kestrel Polymers Pvt Ltd";
export const HERONBAY = "Heronbay Polymers Pvt Ltd";

/**
 * A sourcing message the engine reads without ambiguity: one business name,
 * one constitution word, an amount and the products. Used where the subject of
 * a spec is a later screen, not the reading of the message itself.
 */
export function sourcingMessage(borrower: string): string {
  return [
    "Subject: Working capital request",
    "",
    `Client ${borrower}, a private limited company, is asking for a cash credit limit of 50L and a term loan.`,
    "Turnover approx 3 cr.",
  ].join("\n");
}

/**
 * Create a case through the New appraisal screen and return its id. A borrower
 * already on file blocks creation until a reason is given (F-04.5); this gives
 * one, so a spec is not held hostage by a case an earlier run left behind.
 */
export async function createCase(page: Page, borrower: string): Promise<string> {
  await page.goto("/appraisals/new");
  await page.getByTestId("channel").selectOption("email");
  await page.getByTestId("message-input").fill(sourcingMessage(borrower));
  const read = page.getByRole("button", { name: "Read the message" });
  await expect(read).toBeEnabled();
  await read.click();
  await expect(page.getByTestId("proposed-case")).toBeVisible();

  // The RM confirms the borrower on the proposal. It is typed rather than taken
  // from what the message pass read, because these names carry a unique number
  // to keep one spec's data clear of another's, and a run of digits inside a
  // name is not read as part of it.
  await page.getByTestId("field-borrower").getByRole("textbox").fill(borrower);
  await settleProposedFields(page);

  const create = page.getByTestId("create-application");
  const warning = page.getByTestId("duplicate-warning");
  // The duplicate check answers after the proposal, so poll the screen rather
  // than assume which of the two states it settles into.
  await expect(async () => {
    if ((await warning.count()) > 0 && (await page.getByTestId("override-reason").count()) === 0) {
      await warning.getByRole("button", { name: "Create anyway" }).click();
      await page.getByTestId("override-reason").fill("A separate facility for the same borrower.");
    }
    await expect(create).toBeEnabled();
  }).toPass({ timeout: 30_000, intervals: [300, 700, 1500] });

  await create.click();
  // With no attachment the screen goes straight to Files (appraisals.new.tsx).
  await expect(page).toHaveURL(/\/appraisals\/BBG-\d{4}-\d{6}(\/documents)?$/, {
    timeout: 30_000,
  });
  return caseIdFromUrl(page);
}

/** Fix a case's as_of, so age and window rules are reproducible (principle 5). */
export function pinAsOf(caseId: string, asOf: string = AS_OF): void {
  const out = execFileSync(
    PYTHON,
    [
      "-I",
      "-c",
      [
        "import sqlite3,sys",
        "c=sqlite3.connect(sys.argv[1])",
        "n=c.execute('UPDATE cases SET as_of=? WHERE id=?',(sys.argv[3],sys.argv[2])).rowcount",
        "c.commit();c.close();print(n)",
      ].join("\n"),
      DB,
      caseId,
      asOf,
    ],
    { encoding: "utf-8" },
  );
  expect(out.trim(), `as_of pinned on exactly one case (${caseId})`).toBe("1");
}

/** A case's stored as_of, to show that nothing downstream has moved it. */
export function readAsOf(caseId: string): string {
  return execFileSync(
    PYTHON,
    [
      "-I",
      "-c",
      [
        "import sqlite3,sys",
        "c=sqlite3.connect(sys.argv[1])",
        "print(c.execute('SELECT as_of FROM cases WHERE id=?',(sys.argv[2],)).fetchone()[0])",
      ].join("\n"),
      DB,
      caseId,
    ],
    { encoding: "utf-8" },
  ).trim();
}

/** The published configuration version, as the Administration screen prints it. */
export async function publishedConfigVersion(page: Page): Promise<string> {
  await page.goto("/admin");
  const version = page.getByTestId("config-version").first();
  await expect(version).toBeVisible();
  return (await version.innerText()).trim();
}

/** Every stage key the stage bar carries, with the status shown for it. */
export async function stageStatusMap(page: Page): Promise<Record<string, string | null>> {
  const keys = [
    "documents",
    "extraction",
    "completeness",
    "cross_verification",
    "policy",
    "outputs",
  ];
  // The bar is drawn once the case's progress has been fetched, so wait for it
  // rather than reading an empty screen.
  await expect(page.getByTestId("stage-progress")).toBeVisible();
  await expect(page.getByTestId("stage-documents").first()).toBeAttached();

  const out: Record<string, string | null> = {};
  for (const key of keys) {
    const el = page.getByTestId(`stage-${key}`).first();
    out[key] = (await el.count()) > 0 ? await el.getAttribute("data-status") : null;
  }
  return out;
}

/** The statuses of the checklist items on screen, once the panel has drawn. */
export async function checklistStatuses(page: Page): Promise<string[]> {
  await expect(page.getByTestId("checklist")).toBeVisible();
  return (
    await page
      .getByTestId("checklist-item")
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-status")))
  ).map((s) => s ?? "");
}
