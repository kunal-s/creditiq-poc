// The invariants the service is built on, shown through the screens.
import { expect, test, type Page } from "@playwright/test";

import { checklistStatuses, createCase, pinAsOf, readAsOf } from "../support/integration";
import {
  deleteCaseViaUi,
  fixtureSet,
  signIn,
  uploadViaUi,
  waitForStagesOnScreen,
} from "../support/ui";

test.describe.configure({ mode: "serial" });

// The same recorded documents, read against two different frozen dates.
const BASELINE = "2026-09-29";
const SHIFTED = "2027-09-29";

let page: Page;
const cases: Record<string, string> = {};

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await signIn(page, "analyst");
  for (const [key, asOf] of [
    ["baseline", BASELINE],
    ["shifted", SHIFTED],
  ] as const) {
    const caseId = await createCase(page, `As Of ${key} ${Date.now()} Pvt Ltd`);
    pinAsOf(caseId, asOf);
    await uploadViaUi(page, caseId, fixtureSet("complete"));
    await waitForStagesOnScreen(page);
    cases[key] = caseId;
  }
});

test.afterAll(async () => {
  for (const caseId of Object.values(cases)) await deleteCaseViaUi(page, caseId);
  await page.close();
});

test("age rules read the case's own frozen date, so the same file reads differently", async () => {
  await page.goto(`/appraisals/${cases["baseline"]}/completeness`);
  const baseline = await checklistStatuses(page);
  expect(new Set(baseline)).toEqual(new Set(["satisfied"]));
  await expect(page.getByTestId("gate-banner")).toHaveAttribute("data-ready", "true");

  await page.goto(`/appraisals/${cases["shifted"]}/completeness`);
  const shifted = await checklistStatuses(page);
  expect(shifted).toHaveLength(baseline.length);
  // A year later, the same documents are out of their permitted age and their
  // periods no longer cover what the policy asks for.
  expect(new Set(shifted)).not.toEqual(new Set(["satisfied"]));
  await expect(page.getByTestId("gate-banner")).toHaveAttribute("data-ready", "false");
});

test("an age deficiency is measured from the case's date, never from today", async () => {
  await page.goto(`/appraisals/${cases["shifted"]}/completeness`);
  const br = page.locator('[data-testid="checklist-item"][data-item="board_resolution"]');
  await expect(br).toHaveAttribute("data-status", "insufficient");
  // The frozen date is 29 Sep 2027; the wall clock is years before it.
  await expect(br.getByTestId("deficiency")).toContainText("29 Sep 2027");
  // Today's date appears nowhere in it.
  const today = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date());
  await expect(br.getByTestId("deficiency")).not.toContainText(today);
});

test("nothing downstream of the pipeline moves a case's frozen date", async () => {
  expect(readAsOf(cases["baseline"]!)).toBe(BASELINE);
  expect(readAsOf(cases["shifted"]!)).toBe(SHIFTED);
});
