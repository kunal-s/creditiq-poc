// The case pipeline says one thing everywhere and can be finished: the borrower's identifiers come
// from the documents, the recommendation is written where Submission sends you, and Submission
// counts what Cross-verification and Outputs count.
import { expect, test } from "@playwright/test";
import { KESTREL, RM } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test.use({ viewport: { width: 1440, height: 900 } });

test("Identity shows the PAN the documents agree on, and a person takes it onto the case", async ({
  page,
}) => {
  const api = new MockApi();
  // No PAN typed at intake; every document carries the same one.
  const detail = api.details.get(KESTREL)!;
  api.details.set(KESTREL, { ...detail, pan: null });
  const board = api.boards.get(KESTREL)!;
  const id1 = board.items.find((i) => i.finding.rule_id === "ID-01")!;
  id1.finding = {
    ...id1.finding,
    outcome: "pass",
    sides: [{ ...id1.finding.sides[0]!, value: "AAACK1234K" }],
  };
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/identity`);

  const pan = page.locator('[data-testid="identifier"][data-field="pan"]');
  await expect(pan.getByTestId("identifier-from-documents")).toContainText("AAACK1234K");
  await expect(pan.getByTestId("identifier-from-documents")).toContainText("same on");
  // The CIN differs between documents in this case: it says so, and where to look.
  const cin = page.locator('[data-testid="identifier"][data-field="cin"]');
  await expect(cin).not.toContainText("Not on record");
  await expect(cin).not.toContainText("Not on any document");

  await pan.getByTestId("identifier-use").click();
  await expect(pan).toContainText("AAACK1234K");
  await expect(pan.getByTestId("identifier-use")).toHaveCount(0);
  expect(api.identifierRecords).toEqual([{ caseId: KESTREL, field: "pan", value: "AAACK1234K" }]);
});

test("a role that cannot read the cross-checks sees the case record, without the button", async ({
  page,
}) => {
  const api = new MockApi();
  const detail = api.details.get(KESTREL)!;
  api.details.set(KESTREL, { ...detail, pan: null });
  await signedIn(page, api, RM);
  await page.goto(`/appraisals/${KESTREL}/identity`);
  const pan = page.locator('[data-testid="identifier"][data-field="pan"]');
  await expect(pan).toContainText("Not on record");
  await expect(pan.getByTestId("identifier-use")).toHaveCount(0);
});

test("the recommendation is written on Rating, saved into the memo, and opens Submission's check", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/submission`);
  const check = page.locator('[data-testid="submission-check"]').nth(3);
  await expect(check).toHaveAttribute("data-met", "false");

  // The link lands with the cursor in the first box.
  await check.getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`/appraisals/${KESTREL}/rating#recommendation$`));
  const editor = page.getByTestId("recommendation-editor");
  const first = editor.getByTestId("recommendation-answer").first().locator("textarea");
  await expect(first).toBeFocused();
  await expect(editor.getByTestId("recommendation-save")).toBeDisabled();

  await first.fill("Recommend the cash credit of INR 3.00 crore for working capital.");
  await editor
    .locator('[data-testid="recommendation-answer"][data-prompt="Terms and conditions"] textarea')
    .fill("Stock statement monthly.");
  await expect(editor.getByTestId("recommendation-saved")).toHaveText("Not saved yet");
  await editor.getByTestId("recommendation-save").click();

  const call = api.camCalls.find((c) => c.kind === "words" && c.section === "recommendation")!;
  expect(call.body).toMatchObject({
    paragraphs: [
      "Recommendation\nRecommend the cash credit of INR 3.00 crore for working capital.",
      "Terms and conditions\nStock statement monthly.",
    ],
  });
  await expect(editor.getByTestId("recommendation-saved")).toContainText(
    "Saved by Ananya Krishnan",
  );
  await expect(editor.getByTestId("recommendation-sign-off")).toContainText("Ananya Krishnan");
  // The boxes start again from what the memo now holds.
  await expect(first).toHaveValue(
    "Recommend the cash credit of INR 3.00 crore for working capital.",
  );

  await page.goto(`/appraisals/${KESTREL}/submission`);
  await expect(page.locator('[data-testid="submission-check"]').nth(3)).toHaveAttribute(
    "data-met",
    "true",
  );
});

test("Submission counts open discrepancies, not checks that passed, and every memo section", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}/submission`);
  const items = api.boards.get(KESTREL)!.items;
  const open = items.filter(
    (i) => i.finding.outcome === "fail" && !i.adjudicated && !i.finding.blocking,
  ).length;
  const advisory = page.locator('[data-testid="submission-check"]').nth(1);
  if (open > 0) await expect(advisory).toContainText(`${open} discrepancy(ies) still open`);
  else await expect(advisory).not.toContainText("still open");
  const sections = api.cam.sections.length + 2;
  await expect(page.getByTestId("submission-travels")).toContainText(`${sections} sections`);
  // The state is a line at the head of the checklist, not a coloured banner.
  await expect(page.getByTestId("submission-state")).toHaveText(/\d of \d met|Every item/);
});

test("once the case is created, the Overview shows its progress through every step and what is next", async ({
  page,
}) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  const card = page.getByTestId("case-progress");
  const rows = card.getByTestId("case-progress-row");
  await expect(rows).toHaveCount(6);
  expect(await rows.evaluateAll((els) => els.map((e) => e.getAttribute("data-row")))).toEqual([
    "completeness",
    "crossVerification",
    "policy",
    "outputs",
    "rating",
    "submission",
  ]);
  // The recommendation is not written in this case: the row says so, and Submission waits.
  await expect(card.locator('[data-row="rating"]')).toContainText("Not written");
  await expect(card.locator('[data-row="submission"]')).toHaveAttribute("data-state", "waiting");
  // Next is the first row that needs a person.
  const next = card.getByTestId("case-progress-next");
  const first = await rows.evaluateAll((els) =>
    els.find((e) => e.getAttribute("data-state") === "open")?.getAttribute("data-row"),
  );
  await expect(next).toHaveAttribute("data-to", first!);
  // A blocking requirement still open is what the header says first.
  await expect(page.getByTestId("header-blocking")).toBeVisible();
});

test("with nothing blocking, the header names where the created case stands", async ({ page }) => {
  const api = new MockApi();
  const r = api.checklists.get(KESTREL)!;
  api.checklists.set(KESTREL, { ...r, blocking_open: 0 });
  await signedIn(page, api);
  await page.goto(`/appraisals/${KESTREL}`);
  await expect(page.getByTestId("header-stage")).toHaveText(/^(In assessment|Memo in draft)$/);
  await expect(page.getByTestId("header-ready")).toHaveCount(0);
});
