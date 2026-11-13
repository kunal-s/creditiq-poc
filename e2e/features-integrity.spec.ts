// The integrity checks are a feature a deployment switches on or off (config/app.yaml
// `features.integrity_checks`, reported in /api/meta). On, the Files register shows the Integrity
// check column and a file whose checks found something waits under "Needs attention"; off, the
// screens show nothing of them: no column, no chip, no section, no review items, no evidence page.
import { expect, test, type Page } from "@playwright/test";
import type { FileRecord, ReviewItem } from "@/api/types";
import { KESTREL, META } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test.use({ viewport: { width: 1440, height: 900 } });

/** The PAN image's checks found something a person should look at. */
function withFinding(api: MockApi, on: boolean): MockApi {
  const files = api.files.get(KESTREL)!;
  api.files.set(
    KESTREL,
    files.map((f): FileRecord =>
      f.id === "f-pan"
        ? {
            ...f,
            integrity_status: {
              state: "suspicious",
              passed: 7,
              not_applicable: 23,
              stopped: false,
              suspicious: ["PDF_COVERED_TEXT"],
            },
          }
        : f,
    ),
  );
  const item: ReviewItem = {
    id: "r-integrity",
    case_id: KESTREL,
    kind: "integrity",
    ref: "file:f-pan",
    summary: "director1_pan.jpg: block over what is printed",
    status: "open",
    escalated: false,
    created_at: "2026-11-12T10:00:00Z",
  };
  api.review.push(item);
  api.on("GET", /^\/api\/meta$/, () => ({
    json: { ...META, features: { integrity_checks: on } },
  }));
  return api;
}

const panRow = (page: Page) =>
  page.locator('[data-testid="tree-document"][data-document-id="doc-pan"]').first();

test("switched on, the register shows the integrity check and the file waits for a person", async ({
  page,
}) => {
  const api = withFinding(new MockApi(), true);
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("register-head")).toContainText("Integrity check");
  await expect(
    page.getByTestId("section-attention").locator('[data-document-id="doc-pan"]'),
  ).toBeVisible();
  await expect(panRow(page).getByTestId("integrity-chip")).toBeVisible();

  await page.goto("/review");
  await expect(page.getByTestId("kind-integrity")).toBeVisible();
});

test("switched off, the screens show nothing of the integrity checks", async ({ page }) => {
  const api = withFinding(new MockApi(), false);
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("register-head")).toBeVisible();
  await expect(page.getByTestId("register-head")).not.toContainText("Integrity check");
  await expect(page.getByTestId("integrity-chip")).toHaveCount(0);
  // Its findings no longer put the file under "Needs attention".
  await expect(
    page.getByTestId("section-attention").locator('[data-document-id="doc-pan"]'),
  ).toHaveCount(0);

  // Nor in the review lists.
  await page.goto("/review");
  await expect(page.getByTestId("review-row").first()).toBeVisible();
  await expect(page.getByTestId("kind-integrity")).toHaveCount(0);
  await expect(page.getByText("block over what is printed")).toHaveCount(0);

  // The evidence page leads back to the case's files.
  await page.goto(`/appraisals/${KESTREL}/files/f-pan/integrity`);
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/documents$`));
});

test("switched off, the register still fits a phone", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  const api = withFinding(new MockApi(), false);
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("file-tree").first()).toBeVisible();
  await expect(page.getByTestId("integrity-chip")).toHaveCount(0);
  const wide = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(wide).toBeLessThanOrEqual(375);
});
