// The appraisal workspace (FRD §6): the Overview says what is still needed
// and what waits for a decision; Completeness filters its checklist; links
// to a part of a tab land on it.
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
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
