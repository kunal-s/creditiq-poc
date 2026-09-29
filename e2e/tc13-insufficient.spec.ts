// TC-13 (C2): each incomplete document is identified with its specific
// deficiency, on the checklist and on the Validation tab (FRD F-13.2).
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("TC-13: insufficient items state their deficiency", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/docready/${KESTREL}/checklist`);

  const insufficient = page.locator('[data-testid="checklist-item"][data-status="insufficient"]');
  await expect(insufficient).toHaveCount(4);
  await expect(insufficient.getByTestId("deficiency")).toHaveText([
    "Unsigned: the copy provided is not signed.",
    "Incomplete: balance sheet pages absent.",
    "Period gap: April to July 2025 absent.",
    "Outdated: dated 31 Jan 2026; permitted age 60 days from 20 Sep 2026.",
  ]);

  // Expanded: why, basis and the deficiency.
  await insufficient.first().getByRole("button").first().click();
  await expect(insufficient.first()).toContainText("Why it is required");
  await expect(insufficient.first()).toContainText(
    "Insufficient — Unsigned: the copy provided is not signed.",
  );

  // The document carrying a defect fails its check on Validation.
  await page.goto(`/docready/${KESTREL}/validation`);
  const gst = page.locator('[data-testid="validation-document"][data-document-id="doc-gst"]');
  await expect(gst).toContainText("Check failed");
  await gst.getByRole("button").first().click();
  await expect(gst.getByTestId("defect")).toHaveText(
    "GST returns (12 months) — Period gap: April to July 2025 absent.",
  );
});
