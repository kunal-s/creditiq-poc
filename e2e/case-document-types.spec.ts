// F-09.7 to F-09.10, F-15.8 (FRD decision 13): an unclassified document is
// assigned any published type from its row, or a type made for the appraisal
// when none fits; the new type may count toward a checklist item, a mandatory
// one waiting for a checker; a field proposed from the document reads by its
// own label, marked as proposed; the Administrator sees the types made.
import { expect, test, type Page } from "@playwright/test";
import { ADMIN, FIELDS, KESTREL, TAXONOMY } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

const unclassified = (page: Page) =>
  page.getByTestId("section-files").locator('[data-document-id="doc-unc"]');

/** The taxonomy with two items one document satisfies: the valuation report (not mandatory on
 * this case's checklist) and the certificate of incorporation (mandatory). */
async function withSingleDocumentItems(page: Page) {
  await page.route("**/api/config/checklist-taxonomy", (route) =>
    route.fulfill({
      json: {
        ...TAXONOMY,
        items: [
          ...TAXONOMY.items,
          { ...TAXONOMY.items[0]!, id: "valuation", name: "Valuation report", coverage: null },
          {
            ...TAXONOMY.items[0]!,
            id: "coi",
            name: "Certificate of incorporation",
            coverage: null,
          },
        ],
      },
    }),
  );
}

test("any published type is chosen from the row, then assigned", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const row = unclassified(page);
  await expect(row.getByTestId("assign-chosen")).toHaveCount(0);
  await row.getByTestId("assign-choose").selectOption("bank_statement");
  await row.getByTestId("assign-chosen").click();
  await expect(page.getByText("Assigned as Bank statement")).toBeVisible();
  const [call] = api.called("POST", "/api/review/r-type/decision");
  expect(call?.body).toEqual({ decision: "assign", value: "bank_statement", reason: null });
});

test("a new type with named fields is made, assigned and counted toward an item", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await withSingleDocumentItems(page);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await unclassified(page).getByTestId("assign-new").click();
  const dialog = page.getByTestId("new-type-dialog");
  await expect(dialog.getByTestId("new-type-fields-none")).toBeVisible();
  await expect(dialog.getByTestId("new-type-create")).toBeDisabled();

  await dialog.getByTestId("new-type-name").fill("Shop and establishment certificate");
  await dialog.getByTestId("new-type-add-field").click();
  await dialog.getByTestId("new-type-field").fill("Registration number");
  await dialog.getByTestId("new-type-hint").fill("printed after Registration");
  await expect(dialog.getByTestId("new-type-fields-none")).toHaveCount(0);
  // Only the items one document satisfies, and not yet satisfied, are offered.
  const offered = await dialog.getByTestId("new-type-counts").locator("option").allTextContents();
  expect(offered).toEqual(["No checklist item", "Valuation report"]);
  await dialog.getByTestId("new-type-counts").selectOption("valuation");
  await expect(dialog.getByTestId("new-type-reason")).toHaveCount(0); // not mandatory
  await dialog.getByTestId("new-type-create").click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("Assigned as Shop and establishment certificate")).toBeVisible();
  await expect(page.getByText("Counts toward Valuation report")).toBeVisible();

  const [made] = api.called("POST", `/api/cases/${KESTREL}/document-types`);
  expect(made?.body).toEqual({
    name: "Shop and establishment certificate",
    description: null,
    fields: [{ name: "Registration number", hint: "printed after Registration" }],
  });
  const [assigned] = api.called("POST", "/api/review/r-type/decision");
  expect(assigned?.body).toEqual({ decision: "assign", value: "CDT-1", reason: null });
  const [mapped] = api.called("POST", `/api/cases/${KESTREL}/document-types/CDT-1/mappings`);
  expect(mapped?.body).toEqual({ item_id: "valuation", reason: null });
  // The type is offered for the appraisal's other documents.
  expect(api.caseTypes.get(KESTREL)?.[0]?.mappings?.[0]?.status).toBe("confirmed");
});

test("a mandatory item needs a reason for the checker", async ({ page }) => {
  const api = new MockApi();
  const checklist = api.checklists.get(KESTREL)!;
  api.checklists.set(KESTREL, {
    ...checklist,
    items: checklist.items.map((i) => (i.item_id === "valuation" ? { ...i, blocking: true } : i)),
  });
  await signedIn(page, api);
  await withSingleDocumentItems(page);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  await unclassified(page).getByTestId("assign-new").click();
  const dialog = page.getByTestId("new-type-dialog");
  await dialog.getByTestId("new-type-name").fill("Valuer's certificate");
  await dialog.getByTestId("new-type-counts").selectOption("valuation");
  await expect(dialog).toContainText(
    "Valuation report is mandatory: a Credit Manager confirms the mapping before it counts.",
  );
  await expect(dialog.getByTestId("new-type-create")).toBeDisabled();
  await dialog.getByTestId("new-type-reason").fill("Issued by the panel valuer for the property");
  await dialog.getByTestId("new-type-create").click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByText("Proposed for Valuation report, awaiting a checker")).toBeVisible();
  expect(api.caseTypes.get(KESTREL)?.[0]?.mappings?.[0]?.status).toBe("proposed");
});

test("a type made earlier is offered on the row under this appraisal", async ({ page }) => {
  const api = new MockApi();
  api.caseTypes.set(KESTREL, [
    {
      id: "CDT-9",
      case_id: KESTREL,
      name: "Rent agreement",
      description: null,
      fields: [],
      replaces: null,
      made_by: "u",
      made_at: "2026-09-29T10:00:00Z",
      mappings: [],
    },
  ]);
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const choose = unclassified(page).getByTestId("assign-choose");
  await expect(choose.locator('optgroup[label="Made for this appraisal"] option')).toHaveText([
    "Rent agreement",
  ]);
  await choose.selectOption("CDT-9");
  await unclassified(page).getByTestId("assign-chosen").click();
  await expect(page.getByText("Assigned as Rent agreement")).toBeVisible();
});

test("a field proposed from the document reads by its own label, marked proposed", async ({
  page,
}) => {
  const api = new MockApi();
  const base = FIELDS[0]!;
  api.fields.set(KESTREL, [
    ...FIELDS,
    {
      ...base,
      id: "fv-proposed",
      field: "registration_no",
      label: "Registration No.",
      origin: "discovered",
      method: "model",
      status: "in_review",
    },
  ]);
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/extraction`);
  await page.getByRole("button", { name: "All fields" }).click();
  const row = page.getByTestId("field-row").filter({ hasText: "Registration No." });
  await expect(row.getByTestId("field-proposed")).toHaveText("Proposed");
});

test("the Administrator sees the types made on appraisals", async ({ page }) => {
  const api = new MockApi();
  api.caseTypes.set(KESTREL, [
    {
      id: "CDT-1",
      case_id: KESTREL,
      name: "Rent agreement",
      description: "Lease of the factory premises",
      fields: [{ name: "monthly_rent", hint: null }],
      replaces: null,
      made_by: "u",
      made_at: "2026-09-29T10:00:00Z",
      mappings: [],
    },
  ]);
  await signedIn(page, api, ADMIN);
  await page.goto("/admin/document-types");
  const panel = page.getByTestId("admin-case-type-proposals");
  await expect(panel.getByTestId("admin-case-type")).toHaveCount(1);
  await expect(panel).toContainText("Rent agreement");
  await expect(panel).toContainText("Fields: monthly rent");
  await expect(panel).toContainText("Appraisals: 1 · Documents: 1");
});
