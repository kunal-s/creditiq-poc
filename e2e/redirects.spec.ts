// Earlier routes redirect to their place in the case workspace (FRD §6),
// so saved links keep working.
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

const C = `/appraisals/${KESTREL}`;

const REDIRECTS: [string, string][] = [
  ["/appraisals", "/"],
  ["/docready", "/"],
  ["/exceptions", "/review"],
  ["/appraisals/new", "/appraisals/new"],
  [`/appraisals/${KESTREL}`, C],
  [`/docready/${KESTREL}`, C],
  [`/appraisals/${KESTREL}/upload`, `${C}/documents`],
  [`/docready/${KESTREL}/validation`, `${C}/documents`],
  [`/appraisals/${KESTREL}/identity`, `${C}/extraction#identity`],
  [`/appraisals/${KESTREL}/data`, `${C}/extraction#fields`],
  [`/docready/${KESTREL}/checklist`, `${C}/completeness#checklist`],
  [`/docready/${KESTREL}/readiness`, `${C}/completeness#readiness`],
  [`/docready/${KESTREL}/collection`, `${C}/completeness#queries`],
  [`/appraisals/${KESTREL}/spread`, `${C}/outputs?view=spread`],
  [`/appraisals/${KESTREL}/draft`, `${C}/outputs?view=cam`],
  [`/appraisals/${KESTREL}/cross-verification`, `${C}/cross-verification`],
  [`/appraisals/${KESTREL}/policy`, `${C}/policy`],
  [`/appraisals/${KESTREL}/comparison`, `${C}/comparison`],
];

test("every earlier route redirects to its new place", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  for (const [from, to] of REDIRECTS) {
    await page.goto(from);
    await expect
      .poll(() => {
        const url = new URL(page.url());
        return `${url.pathname}${url.search}${url.hash}`;
      }, from)
      .toBe(to);
  }
});
