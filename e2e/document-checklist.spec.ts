// The Files step opens with the document checklist: every document the appraisal needs, what has
// come in for each, what is wrong or missing, and an upload on the row (one-stop journey).
import { expect, test } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("the Files step leads with what the appraisal needs, has and lacks", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const panel = page.getByTestId("document-checklist");
  await expect(panel).toBeVisible();
  const items = panel.getByTestId("journey-item");
  await expect(items).toHaveCount(9);
  // The compact summary counts the requirements by status. The percentage lives in the case
  // header and the Overview's readiness glance, never in the summary on the Files step.
  await expect(page.getByTestId("journey-summary")).toContainText(/Missing\s*2/);
  await expect(page.getByTestId("journey-summary")).not.toContainText("58%");
  await expect(page.getByTestId("header-readiness")).toContainText("58%");

  // What is on file for a requirement opens its page.
  const audited = items.filter({ hasText: "Audited financial statements" });
  await expect(audited.getByTestId("journey-doc")).toContainText("Balance sheet");

  // To do: the missing and the insufficient, each with an upload on its row.
  await page.getByTestId("journey-filter-todo").click();
  await expect(items).toHaveCount(6);
  for (const status of await items.evaluateAll((els) => els.map((e) => e.dataset["status"])))
    expect(["missing", "insufficient"]).toContain(status);
  await expect(items.first().getByTestId("journey-upload")).toBeVisible();

  // The files received stay below, every one with its checks.
  await expect(page.getByTestId("files-received")).toBeVisible();
});

test("a file uploaded from a requirement's row goes to the appraisal and the row says so", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const row = page.locator('[data-testid="journey-item"][data-item="valuation"]');
  await row
    .getByTestId("journey-upload-input")
    .setInputFiles([
      { name: "kyc-leela.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") },
    ]);
  await expect(row.getByTestId("journey-received")).toContainText("kyc-leela.pdf");
  await expect(row.getByTestId("journey-outcome")).toHaveAttribute("data-state", "reading");
  expect(api.called("POST", `/api/cases/${KESTREL}/files`)).toHaveLength(1);
});

test("each requirement says what to ask the customer, and flags a file whose checks want a person", async ({
  page,
}) => {
  const api = new MockApi();
  api.queries.set(KESTREL, [
    ...(api.queries.get(KESTREL) ?? []),
    {
      id: "q-kyc",
      case_id: KESTREL,
      group: "documents_needed",
      text: "KYC of Leela Varghese: PAN and address proof.",
      source_kind: "checklist",
      source_ref: "kyc_directors",
      resolved: false,
      evidence: [],
    },
    {
      id: "q-board",
      case_id: KESTREL,
      group: "documents_to_redo",
      text: "Board resolution: the copy provided is not signed.",
      source_kind: "checklist",
      source_ref: "board_resolution:unsigned",
      resolved: false,
      evidence: [],
    },
  ]);
  // A copy of the file, so the shared fixture stays as it was for the tests that follow.
  api.files.set(
    KESTREL,
    api.files.get(KESTREL)!.map((f) =>
      f.id === "f-bs"
        ? {
            ...f,
            integrity_status: {
              state: "review_recommended",
              passed: 9,
              not_applicable: 0,
            } as never,
          }
        : f,
    ),
  );
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const items = page.getByTestId("journey-item");
  await expect(items.filter({ hasText: "KYC of directors" })).toContainText(
    "Ask:KYC of Leela Varghese: PAN and address proof.",
  );
  // A request for something wrong with what came in counts under its requirement too.
  await expect(items.filter({ hasText: "Board resolution" })).toContainText(
    "Board resolution: the copy provided is not signed.",
  );
  const audited = items.filter({ hasText: "Audited financial statements" });
  await expect(audited.getByTestId("journey-doc")).toHaveAttribute("data-flagged", "true");
  // What came in that no requirement asks for is kept in view.
  await expect(page.getByTestId("journey-unmatched")).toBeVisible();
  // Why each is needed, on demand.
  await items.filter({ hasText: "KYC of directors" }).getByTestId("journey-why").click();
  await expect(items.filter({ hasText: "KYC of directors" })).toContainText(
    "is required for this constitution and facility",
  );
});

test("a provisional checklist says so above the requirements", async ({ page }) => {
  const api = new MockApi();
  const r = api.checklists.get(KESTREL)!;
  api.checklists.set(KESTREL, { ...r, provisional: true });
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await expect(page.getByTestId("journey-provisional")).toBeVisible();
});

test("a file sent from a row says where it landed once it is read", async ({ page }) => {
  const api = new MockApi();
  // Processing runs until the engine has read the file; then the stage settles.
  let read = false;
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/progress$`), () => {
    const progress = api.progress(KESTREL);
    if (!read) progress.stages[0]!.status = "in_progress";
    return { json: progress };
  });
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const row = page.locator('[data-testid="journey-item"][data-item="kyc_directors"]');
  await row
    .getByTestId("journey-upload-input")
    .setInputFiles([
      { name: "kyc-leela.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") },
    ]);
  const outcome = row.getByTestId("journey-outcome");
  await expect(outcome).toHaveAttribute("data-state", "reading");
  // The engine reads it: a document on the new file, now counted toward the requirement.
  const added = api.files.get(KESTREL)!.find((f) => f.original_name === "kyc-leela.pdf")!;
  const template = api.documents.get(KESTREL)![0]!;
  api.documents.set(KESTREL, [
    ...api.documents.get(KESTREL)!,
    { ...template, id: "doc-kyc-new", file_id: added.id },
  ]);
  const r = api.checklists.get(KESTREL)!;
  api.checklists.set(KESTREL, {
    ...r,
    items: r.items.map((i) =>
      i.item_id === "kyc_directors" ? { ...i, document_ids: ["doc-kyc-new"] } : i,
    ),
  });
  read = true;
  await expect(outcome).toHaveAttribute("data-state", "counted", { timeout: 15_000 });
  await expect(outcome).toContainText("counts toward KYC of directors");
});

test("a second file sent from the same row keeps the first one's line", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const row = page.locator('[data-testid="journey-item"][data-item="kyc_directors"]');
  const outcomes = row.getByTestId("journey-outcome");
  for (const name of ["kyc-first-director.pdf", "kyc-second-director.pdf"]) {
    await row
      .getByTestId("journey-upload-input")
      .setInputFiles([{ name, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.7") }]);
    await expect(outcomes.filter({ hasText: name })).toHaveCount(1);
  }
  await expect(outcomes).toHaveCount(2);
  await expect(outcomes.nth(0)).toContainText("kyc-first-director.pdf");
  await expect(outcomes.nth(1)).toContainText("kyc-second-director.pdf");
  expect(api.called("POST", `/api/cases/${KESTREL}/files`)).toHaveLength(2);
});

test("files dropped on a requirement's row are uploaded from it", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const row = page.locator('[data-testid="journey-item"][data-item="valuation"]');
  await expect(row).toBeVisible();
  const dataTransfer = await page.evaluateHandle(() => {
    const dt = new DataTransfer();
    dt.items.add(new File(["%PDF-1.7"], "valuation-report.pdf", { type: "application/pdf" }));
    return dt;
  });
  await row.dispatchEvent("dragover", { dataTransfer });
  await expect(row).toContainText("Drop to upload for Valuation report");
  await row.dispatchEvent("drop", { dataTransfer });
  await expect(row.getByTestId("journey-outcome")).toContainText("valuation-report.pdf");
  expect(api.called("POST", `/api/cases/${KESTREL}/files`)).toHaveLength(1);
});
