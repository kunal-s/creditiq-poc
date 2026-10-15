// Earlier addresses still work: each lands on its place in the case workspace
// (src/domain/legacyRoutes.ts), so a saved link is never broken.
import { expect, test, type Page } from "@playwright/test";

import { createCase, pinAsOf } from "../support/integration";
import { deleteCaseViaUi, signIn } from "../support/ui";

test.describe.configure({ mode: "serial" });

let page: Page;
let caseId: string;

test.beforeAll(async ({ browser }) => {
  page = await browser.newPage();
  await signIn(page, "analyst");
  caseId = await createCase(page, `Legacy Links ${Date.now()} Pvt Ltd`);
  pinAsOf(caseId);
});

test.afterAll(async () => {
  if (caseId) await deleteCaseViaUi(page, caseId);
  await page.close();
});

test("every earlier address lands on its place in the workspace", async () => {
  const here = () => {
    const url = new URL(page.url());
    return `${url.pathname}${url.search}${url.hash}`;
  };
  const base = `/appraisals/${caseId}`;
  const redirects: [string, string][] = [
    ["/appraisals", "/"],
    ["/docready", "/"],
    ["/exceptions", "/review"],
    [`/docready/${caseId}`, base],
    [`${base}/upload`, `${base}/documents`],
    [`/docready/${caseId}/validation`, `${base}/documents`],
    [`${base}/identity`, `${base}/extraction#identity`],
    [`${base}/data`, `${base}/extraction#fields`],
    [`/docready/${caseId}/checklist`, `${base}/completeness#checklist`],
    [`/docready/${caseId}/readiness`, `${base}/completeness#readiness`],
    [`/docready/${caseId}/collection`, `${base}/completeness#queries`],
    [`${base}/spread`, `${base}/outputs?view=spread`],
    [`${base}/draft`, `${base}/outputs?view=cam`],
  ];
  for (const [from, to] of redirects) {
    await page.goto(from);
    await expect.poll(here, { message: from }).toBe(to);
  }
});

test("the New appraisal address is not swallowed by the case routes", async () => {
  await page.goto("/appraisals/new");
  await expect(page).toHaveURL(/\/appraisals\/new$/);
  await expect(page.getByTestId("message-input")).toBeVisible();
});
