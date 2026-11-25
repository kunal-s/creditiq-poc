// The Files tab: a person's corrections on a document. Its period, as read or as a person set it, and setting it
// where none was found; each page with the other documents of the file that hold it; and reading one page as
// another type, in a document of its own. Every change goes to the engine with its reason.
import { expect, test, type Page } from "@playwright/test";
import { DOCUMENTS, KESTREL, RM } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

function withCorrections(api: MockApi) {
  const docs = DOCUMENTS.map((d) => {
    if (d.id === "doc-bank")
      return {
        ...d,
        period: { start: null, end: null, status: "not_found" as const, source: null, note: null },
      };
    // The registration page is also read as the first page of the bank statement's file part.
    if (d.id === "doc-gst") return { ...d, pages: [...d.pages, { ...d.pages[0]!, n: 3 }] };
    return d;
  });
  api.documents.set(KESTREL, docs);
  const sent: { url: string; body: unknown }[] = [];
  api.on(
    "POST",
    new RegExp(`^/api/cases/${KESTREL}/documents/doc-bank/pages/(\\d+)/type$`),
    (req) => {
      sent.push({ url: req.url(), body: req.postDataJSON() });
      return { json: { job_id: "job-1" } };
    },
  );
  api.on("PUT", new RegExp(`^/api/cases/${KESTREL}/documents/doc-bank/period$`), (req) => {
    sent.push({ url: req.url(), body: req.postDataJSON() });
    return { json: { job_id: null } };
  });
  return { api, sent };
}

async function openBank(page: Page, api: MockApi, user = api.user) {
  await signedIn(page, api, user);
  await page.goto(`/appraisals/${KESTREL}/documents`);
  const row = page.locator("[data-testid='tree-document'][data-document-id='doc-bank']");
  await row.getByTestId("document-toggle").click();
  return row;
}

test("a period not found is said so and a person sets it with a reason", async ({ page }) => {
  const { api, sent } = withCorrections(new MockApi());
  const row = await openBank(page, api);
  const period = row.getByTestId("document-period");
  await expect(period).toHaveAttribute("data-status", "not_found");
  await expect(period).toContainText("Not found on the document");
  await row.getByTestId("period-set-open").click();
  await expect(row.getByTestId("period-save")).toBeDisabled();
  await row.getByTestId("period-start").fill("2025-04-01");
  await row.getByTestId("period-end").fill("2026-03-31");
  await row.getByTestId("period-reason").fill("Printed in the statement's header.");
  await row.getByTestId("period-save").click();
  await expect
    .poll(() => sent.map((s) => s.body))
    .toEqual([
      { start: "2025-04-01", end: "2026-03-31", reason: "Printed in the statement's header." },
    ]);
});

test("a page another document of the file also holds says so, and one page is read as another type", async ({
  page,
}) => {
  const { api, sent } = withCorrections(new MockApi());
  const row = await openBank(page, api);
  const third = row.locator("[data-testid='document-page'][data-page='3']");
  await expect(third.getByTestId("page-also-in")).toContainText("Also in:");
  await expect(
    row.locator("[data-testid='document-page'][data-page='4']").getByTestId("page-also-in"),
  ).toHaveCount(0);
  await third.getByTestId("page-type-open").click();
  await expect(third.getByTestId("page-type-save")).toBeDisabled();
  await third.getByTestId("page-type-select").selectOption({ index: 1 });
  await third.getByTestId("page-type-reason").fill("This page is the registration certificate.");
  await third.getByTestId("page-type-save").click();
  await expect(third.getByTestId("page-type-queued")).toBeVisible();
  expect(sent[0]!.url).toMatch(/\/pages\/3\/type$/);
  expect((sent[0]!.body as { reason: string }).reason).toBe(
    "This page is the registration certificate.",
  );
});

test("a role that cannot decide sees the period and the pages without the actions", async ({
  page,
}) => {
  const { api } = withCorrections(new MockApi());
  const row = await openBank(page, api, RM);
  await expect(row.getByTestId("document-period")).toBeVisible();
  await expect(row.getByTestId("document-page")).toHaveCount(7);
  await expect(row.getByTestId("period-set-open")).toHaveCount(0);
  await expect(row.getByTestId("page-type-open")).toHaveCount(0);
});
