// The assistant on a real appraisal: the real engine, the real assistant service, and recorded model answers
// (services/copilot/tests/fixtures/e2e_recordings.json, replayed; no key, no network). An RM uploads two files the
// engine turns away, opens the assistant and asks why; the table is the engine's own account of each file.
// If the engine's wording for these two files changes, the recordings no longer match and the service answers that
// it is unavailable: re-record with services/copilot/scripts/record_golden.py --write.
// The second test goes on to draft and send the email: the message must end up in the engine's outbox.
import { expect, test } from "@playwright/test";
import { asRole, createCase, deleteCase, signedInAs, waitForProcessing } from "../support/engine";

const OLD_EXCEL = Buffer.concat([Buffer.from("d0cf11e0a1b11ae1", "hex"), Buffer.alloc(600)]);
const BROKEN_PDF = Buffer.from("%PDF-1.4\n this is not really a pdf");

test("an RM asks why two uploaded files were turned away and gets the engine's reasons", async ({
  page,
}) => {
  const api = await asRole("rm");
  const { id } = await createCase(api);
  try {
    const form = new FormData();
    form.append("files", new Blob([OLD_EXCEL]), "old.xls");
    form.append("files", new Blob([BROKEN_PDF]), "broken.pdf");
    const upload = await api.post(`/api/cases/${encodeURIComponent(id)}/files`, {
      multipart: form,
    });
    expect(upload.status()).toBe(202);
    await waitForProcessing(api, id);

    await signedInAs(page, "rm");
    await page.goto(`/appraisals/${id}/completeness`);
    await page.getByTestId("assistant-launcher").click();
    const panel = page.getByTestId("copilot-panel");
    await panel.getByRole("button", { name: "Why was a document rejected?" }).click();

    await expect(panel.getByTestId("copilot-row")).toHaveCount(2, { timeout: 30_000 }); // one per file
    await expect(panel).toContainText("old.xls");
    await expect(panel).toContainText("broken.pdf");
    await expect(panel.getByRole("alert")).toHaveCount(0);
    await expect(panel).toContainText("Sources: get_rejection_reasons");
  } finally {
    await deleteCase(api, id);
    await api.dispose();
  }
});

test("an RM drafts the follow-up email, completes it on the card and sends it: the engine records it", async ({
  page,
}) => {
  const api = await asRole("rm");
  const { id } = await createCase(api);
  try {
    const form = new FormData();
    form.append("files", new Blob([OLD_EXCEL]), "old.xls");
    form.append("files", new Blob([BROKEN_PDF]), "broken.pdf");
    expect(
      (await api.post(`/api/cases/${encodeURIComponent(id)}/files`, { multipart: form })).status(),
    ).toBe(202);
    await waitForProcessing(api, id);

    await signedInAs(page, "rm");
    await page.goto(`/appraisals/${id}/completeness`);
    await page.getByTestId("assistant-launcher").click();
    const panel = page.getByTestId("copilot-panel");
    const ask = panel.getByRole("textbox", { name: "Ask about this appraisal" });

    await panel.getByRole("button", { name: "Draft an email to the customer about them" }).click();
    await expect(panel).toContainText("Draft - not sent", { timeout: 30_000 });
    expect(
      await api.get(`/api/cases/${encodeURIComponent(id)}/messages`).then((r) => r.json()),
    ).toEqual([]);

    await ask.fill("Send it");
    await ask.press("Enter");
    const card = panel.getByTestId("copilot-action");
    await expect(card).toBeVisible({ timeout: 30_000 });
    await expect(card.getByLabel("To")).toHaveValue("");

    // A draft that still has [Name] in it cannot be sent; the user fills it in.
    await card.getByLabel("To").fill("asha@example.com");
    await card.getByRole("button", { name: "Send" }).click();
    await expect(card.getByRole("alert")).toContainText("square brackets");
    await card
      .getByLabel("Message")
      .fill("Hello Asha,\n\nPlease send old.xls and broken.pdf again as PDF or XLSX.");
    await card.getByRole("button", { name: "Send" }).click();

    await expect(panel).toContainText(
      "The email to asha@example.com has been recorded for sending.",
    );
    await expect(card).toHaveCount(0);
    const sent = (await (
      await api.get(`/api/cases/${encodeURIComponent(id)}/messages`)
    ).json()) as {
      to: string;
      subject: string;
      status: string;
    }[];
    expect(sent).toHaveLength(1);
    expect(sent[0]).toMatchObject({ to: "asha@example.com", status: "recorded" });
    expect(sent[0]?.subject.length).toBeGreaterThan(0);
  } finally {
    await deleteCase(api, id);
    await api.dispose();
  }
});
