// A figure on a financial statement changed by the Credit Analyst (maker) with a reason and the
// paper it rests on, and checked by the Credit Manager (checker, never the maker): the row reads
// "Awaiting check" until then, and the figure on record stands.
import { expect, test, type Page } from "@playwright/test";
import type { ReviewItem } from "@/api/types";
import { KESTREL, MANAGER } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test.use({ viewport: { width: 1440, height: 900 } });

const REASON = "Revised per the auditor's letter dated 14 Oct 2026";

/** A change to the balance sheet's net worth, made by the Credit Analyst, waiting for a check. */
function pending(): ReviewItem {
  return {
    id: "r-edit-fv-networth",
    case_id: KESTREL,
    kind: "manual_entry",
    ref: "field:fv-networth",
    summary:
      "Ananya Krishnan changed net worth from 4,25,00,000 to 4,40,00,000; awaiting the Credit Manager's check",
    status: "open",
    escalated: false,
    created_at: "2026-11-12T10:00:00Z",
    maker: "ananya-krishnan",
    edit: {
      field_value_id: "fv-networth",
      document_id: "doc-bs",
      field: "net_worth",
      from_value: 42_500_000,
      to_value: 44_000_000,
      reason: REASON,
      maker_name: "Ananya Krishnan",
      at: "2026-11-12T10:00:00Z",
      attachment: { name: "auditor-letter.pdf", size: 24_576, content_type: "application/pdf" },
    },
  };
}

const netWorth = (page: Page) =>
  page.locator('[data-testid="field-row"]', {
    has: page.locator('[data-testid="field-value"][data-field="net_worth"]'),
  });

test("the Credit Analyst changes a balance-sheet figure with a reason and a paper; it waits for the Credit Manager", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  await page.getByTestId("data-filter-all").click();
  // Only a financial statement's figures are changed this way.
  await expect(
    page.locator('[data-testid="figure-edit-open"][data-field="net_worth"]'),
  ).toBeVisible();
  await expect(page.locator('[data-testid="figure-edit-open"][data-field="pan"]')).toHaveCount(0);

  await netWorth(page).getByTestId("figure-edit-open").click();
  const dialog = page.getByTestId("figure-edit-dialog");
  await expect(dialog).toContainText("4,25,00,000");
  await dialog.getByTestId("figure-edit-value").fill("4,40,00,000");
  await dialog.getByTestId("figure-edit-reason-input").fill("Too short");
  await expect(dialog.getByTestId("figure-edit-send")).toBeDisabled();
  await dialog.getByTestId("figure-edit-reason-input").fill(REASON);
  await dialog.getByTestId("figure-edit-file").setInputFiles({
    name: "auditor-letter.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("%PDF-1.7\n"),
  });
  await dialog.getByTestId("figure-edit-send").click();
  await expect(dialog).toBeHidden();
  expect(api.figureEdits).toEqual([
    {
      caseId: KESTREL,
      fieldId: "fv-networth",
      value: "4,40,00,000",
      reason: REASON,
      file: "auditor-letter.pdf",
    },
  ]);

  // The row says what waits, and for whom; the maker cannot approve their own change.
  const note = page.locator('[data-testid="figure-edit-pending"][data-field="net_worth"]');
  // The yellow tag is on the figure's row; the change itself reads across the row below.
  await expect(netWorth(page).getByText("Awaiting check")).toBeVisible();
  await expect(note.getByTestId("figure-edit-change")).toContainText("4,25,00,000");
  await expect(note.getByTestId("figure-edit-change")).toContainText("4,40,00,000");
  await expect(note.getByTestId("figure-edit-reason")).toHaveText(REASON);
  await expect(note.getByTestId("figure-edit-attachment")).toContainText("auditor-letter.pdf");
  await expect(note.getByTestId("figure-edit-by")).toContainText("Ananya Krishnan");
  await expect(note.getByTestId("figure-edit-waiting")).toHaveText(
    "Waiting for the Credit Manager's check",
  );
  await expect(note.getByTestId("figure-edit-approve")).toHaveCount(0);
  // The figure on record stands until the check.
  await expect(netWorth(page).getByTestId("field-value")).toHaveText("4,25,00,000");
  await expect(page.getByTestId("data-awaiting")).toContainText("1");
});

test("the Credit Manager opens on the changes awaiting check and approves one", async ({
  page,
}) => {
  const api = new MockApi();
  api.review.push(pending());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  await expect(page.getByTestId("data-filter-awaiting")).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("field-row")).toHaveCount(1);
  // The checker changes no figures.
  await expect(page.getByTestId("figure-edit-open")).toHaveCount(0);

  const note = page.locator('[data-testid="figure-edit-pending"][data-field="net_worth"]');
  const download = page.waitForEvent("download");
  await note.getByTestId("figure-edit-attachment").click();
  expect((await download).suggestedFilename()).toBe("auditor-letter.pdf");

  await note.getByTestId("figure-edit-approve").click();
  await page.getByTestId("data-filter-all").click();
  await expect(netWorth(page).getByTestId("field-value")).toContainText("4,40,00,000");
  await expect(netWorth(page).getByTestId("system-value")).toHaveText("4,25,00,000");
  await expect(netWorth(page)).toContainText("Corrected");
  const item = api.review.find((r) => r.id === "r-edit-fv-networth")!;
  expect(item).toMatchObject({ status: "decided", decision: "confirm" });
});

test("the Credit Manager sends a change back with a reason; the figure stays as it was", async ({
  page,
}) => {
  const api = new MockApi();
  api.review.push(pending());
  await signedIn(page, api, MANAGER);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  const note = page.locator('[data-testid="figure-edit-pending"][data-field="net_worth"]');
  await note.getByTestId("figure-edit-send-back").click();
  await expect(note.getByTestId("figure-edit-back-confirm")).toBeDisabled();
  await note.getByTestId("figure-edit-back-reason").fill("The letter covers FY 2023-24");
  await note.getByTestId("figure-edit-back-confirm").click();
  const item = api.review.find((r) => r.id === "r-edit-fv-networth")!;
  await expect.poll(() => item.status).toBe("decided");
  expect(item).toMatchObject({ decision: "waive", reason: "The letter covers FY 2023-24" });
  await page.getByTestId("data-filter-all").click();
  await expect(netWorth(page).getByTestId("field-value")).toHaveText("4,25,00,000");
  await expect(page.getByTestId("figure-edit-pending")).toHaveCount(0);
});

test("in the review queue a changed figure is opened where it is checked, not decided there", async ({
  page,
}) => {
  const api = new MockApi();
  api.review.push(pending());
  await signedIn(page, api, MANAGER);
  await page.goto("/review");
  const row = page.locator("tr", { hasText: "awaiting the Credit Manager's check" });
  await expect(row.getByTestId("decide")).toHaveCount(0);
  await row.getByRole("link", { name: "View", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/extraction`));
  await expect(page.getByTestId("figure-edit-pending")).toBeVisible();
});
