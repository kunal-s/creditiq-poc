// CAM templates (FRD F-23; decision C.4-12): the memo follows the default template until another is
// chosen for the appraisal; an analyst makes a new one from the draft screen, its sections drawing
// on parts of the file (each part in one section) or left blank for the analyst to write.
import { expect, test, type Page } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

async function openReview(page: Page, api = new MockApi()) {
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/outputs?view=cam`);
  await expect(page.getByTestId("cam-review")).toBeVisible();
  return api;
}

test("the memo follows the default template, the eight sections, until another is chosen", async ({
  page,
}) => {
  await openReview(page);
  const select = page.getByTestId("cam-template-select");
  await expect(select).toHaveValue("default");
  await expect(select.locator("option")).toHaveText(["Default template · 8 sections"]);
  await expect(page.getByTestId("cam-review-nav-item")).toHaveCount(8);
});

test("a new template is built from the default: sections renamed, parts moved, a blank one added", async ({
  page,
}) => {
  const api = await openReview(page);
  await page.getByTestId("cam-template-new").click();
  const dialog = page.getByTestId("cam-template-dialog");
  await expect(dialog).toBeVisible();
  const sections = dialog.getByTestId("cam-template-section");
  // It starts from the template the memo follows, its parts chosen.
  await expect(sections).toHaveCount(6);
  await expect(
    sections.first().locator('[data-testid="cam-template-part"][aria-pressed="true"]'),
  ).toHaveText(["Borrower profile", "Promoters and management"]);
  // A part drafted in one section cannot be chosen in another.
  await expect(sections.nth(1).locator('[data-part="borrower_profile"]')).toBeDisabled();
  await expect(dialog.getByTestId("cam-template-save")).toBeDisabled();

  await dialog.getByTestId("cam-template-name").fill("Renewal memo");
  // Keep two sections: remove the rest from the end.
  for (let i = 0; i < 4; i++) await sections.last().getByTestId("cam-template-remove").click();
  await sections.first().getByTestId("cam-template-section-title").fill("The borrower");
  // Add a blank section for the analyst.
  await dialog.getByTestId("cam-template-add").click();
  await sections.last().getByTestId("cam-template-section-title").fill("Analyst's note");
  await expect(sections.last()).toContainText("left for the analyst to write");
  await expect(dialog.getByTestId("cam-template-closing")).toContainText(
    "Risk Assessment and Rating and Recommendation (sections 4 onwards)",
  );
  // Move the blank section first.
  await sections.last().getByTestId("cam-template-up").click();
  await sections.nth(1).getByTestId("cam-template-up").click();
  await expect(sections.first().getByTestId("cam-template-section-title")).toHaveValue(
    "Analyst's note",
  );

  await dialog.getByTestId("cam-template-save").click();
  await expect(dialog).toHaveCount(0);
  const made = api.camCalls.find((c) => c.kind === "template")!.body as {
    name: string;
    sections: { title: string; parts: string[] }[];
  };
  expect(made.name).toBe("Renewal memo");
  expect(made.sections.map((s) => [s.title, s.parts])).toEqual([
    ["Analyst's note", []],
    ["The borrower", ["borrower_profile", "promoters"]],
    ["Facility Requested and Purpose", ["snapshot", "proposal", "working_capital"]],
  ]);
  // Used for this appraisal straight away: the memo now has its sections, then the closing two.
  expect(api.camCalls.at(-1)).toEqual({
    kind: "choose",
    section: "",
    body: { template_id: "tpl-1" },
  });
  await expect(page.getByTestId("cam-template-select")).toHaveValue("tpl-1");
  await expect(page.getByTestId("cam-review-nav-item")).toHaveCount(5);
  await expect(page.getByTestId("cam-review-section").getByTestId("cam-section-empty")).toHaveText(
    "For the analyst to write.",
  );
});

test("choosing another template, and back to the default", async ({ page }) => {
  const api = new MockApi();
  api.camTemplates.push({
    id: "tpl-9",
    name: "Short memo",
    description: null,
    default: false,
    sections: [
      { id: "numbers", title: "Numbers", purpose: null, parts: ["financial_performance"] },
    ],
  });
  await openReview(page, api);
  const select = page.getByTestId("cam-template-select");
  await expect(select.locator("option")).toHaveText([
    "Default template · 8 sections",
    "Short memo · 3 sections",
  ]);
  await select.selectOption("tpl-9");
  await expect(page.getByTestId("cam-review-nav-item")).toHaveCount(3);
  await expect(page.getByTestId("cam-review-nav-item").first()).toContainText("Numbers");
  await select.selectOption("default");
  await expect
    .poll(() => api.camCalls.at(-1))
    .toEqual({ kind: "choose", section: "", body: { template_id: "default" } });
});

test("a name already used is refused with why", async ({ page }) => {
  const api = new MockApi();
  api.camTemplates.push({
    id: "tpl-9",
    name: "Short memo",
    description: null,
    default: false,
    sections: [],
  });
  await openReview(page, api);
  await page.getByTestId("cam-template-new").click();
  const dialog = page.getByTestId("cam-template-dialog");
  await dialog.getByTestId("cam-template-name").fill("short memo");
  await dialog.getByTestId("cam-template-save").click();
  await expect(dialog.getByTestId("cam-template-error")).toContainText("already exists");
});
