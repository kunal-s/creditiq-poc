// The assistant on the open appraisal: a launcher, a side panel, and answers from the assistant service,
// which is answered in the browser here (no service, no model). The panel is the reusable one in
// services/copilot/ui; these tests cover how the case screen mounts it.
import { expect, test, type Page, type Route } from "@playwright/test";
import { KESTREL } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

const SERVICE = "http://localhost:8202";
const CORS = {
  "access-control-allow-origin": "*",
  "access-control-allow-headers": "authorization,content-type",
  "access-control-allow-methods": "GET,POST",
};

const RESULT = {
  session_id: "s_1",
  turn_id: "t_1",
  terminal: "answer",
  text: "One document was rejected.",
  use_case: "explain_rejections",
  columns: ["document", "status", "reason", "rule"],
  rows: [
    {
      document: "bank_statement_apr.pdf",
      status: "exception",
      reason: "The file is password-protected.",
      rule: "encrypted",
    },
  ],
  sources: [{ tool: "get_rejection_reasons", fetched_at: "2026-10-28T10:00:00" }],
};

const sse = (events: [string, unknown][]) =>
  events.map(([e, d]) => `event: ${e}\ndata: ${JSON.stringify(d)}\n\n`).join("");

/** Answer the service: remember what the page sent, reply with the given events or status. */
async function service(
  page: Page,
  reply: { status?: number; events?: [string, unknown][]; refuse?: string },
  actions: { url: string; auth: string | undefined; body: Record<string, unknown> }[] = [],
) {
  const sent: { auth: string | undefined; body: Record<string, unknown> }[] = [];
  await page.route(`${SERVICE}/**`, async (route: Route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    if (request.url().includes("/actions/")) {
      actions.push({
        url: request.url(),
        auth: request.headers()["authorization"],
        body: request.postDataJSON() as Record<string, unknown>,
      });
      const refuse = request.url().endsWith("/confirm") ? reply.refuse : undefined;
      return route.fulfill({
        status: refuse ? 422 : 200,
        headers: { ...CORS, "content-type": "application/json" },
        body: JSON.stringify(
          refuse
            ? { detail: refuse }
            : {
                session_id: "s_1",
                terminal: "answer",
                done: true,
                text: "The email to asha@example.com has been recorded for sending.",
                sources: [],
              },
        ),
      });
    }
    if (request.url().endsWith("/chat")) {
      sent.push({
        auth: request.headers()["authorization"],
        body: request.postDataJSON() as Record<string, unknown>,
      });
      return route.fulfill({
        status: reply.status ?? 200,
        headers: { ...CORS, "content-type": "text/event-stream" },
        body: sse(reply.events ?? []),
      });
    }
    return route.fulfill({ status: 404, headers: CORS, body: "{}" });
  });
  return sent;
}

async function openPanel(page: Page) {
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  await page.getByTestId("assistant-launcher").click();
  await expect(page.getByTestId("copilot-panel")).toBeVisible();
}

test("the launcher opens the panel with the intro and the suggested questions", async ({
  page,
}) => {
  await signedIn(page, new MockApi());
  await service(page, {});
  await openPanel(page);
  const panel = page.getByTestId("copilot-panel");
  await expect(panel.getByRole("heading", { name: "Appraisal assistant" })).toBeVisible();
  await expect(panel).toContainText(
    "Ask why a document on this appraisal was rejected or held for review, ask for a draft email to the customer, or send that email once you have checked it.",
  );
  await expect(panel.getByRole("button", { name: "Why was a document rejected?" })).toBeVisible();
  await expect(
    panel.getByRole("button", { name: "Draft an email to the customer about them" }),
  ).toBeVisible();
  await expect(panel.getByRole("button", { name: "Send" })).toBeDisabled();
});

test("a question goes to the service with the open appraisal and the user's token; the answer is a table", async ({
  page,
}) => {
  await signedIn(page, new MockApi());
  const sent = await service(page, {
    events: [
      ["session", { session_id: "s_1" }],
      ["result", RESULT],
    ],
  });
  await openPanel(page);
  const panel = page.getByTestId("copilot-panel");
  await panel
    .getByRole("textbox", { name: "Ask about this appraisal" })
    .fill("Why was the bank statement rejected?");
  await panel.getByRole("textbox").press("Enter");

  await expect(panel).toContainText("One document was rejected.");
  const row = panel.getByTestId("copilot-row");
  await expect(row).toHaveCount(1);
  await expect(row.getByRole("term")).toHaveText(["Status", "Reason", "Rule"]);
  await expect(row.getByRole("definition")).toHaveText([
    "exception",
    "The file is password-protected.",
    "encrypted",
  ]);
  await expect(row).toContainText("bank_statement_apr.pdf");
  await expect(panel).toContainText("Sources: get_rejection_reasons");
  expect(sent).toHaveLength(1);
  expect(sent[0]?.auth).toBe("Bearer session-token");
  expect(sent[0]?.body).toMatchObject({
    message: "Why was the bank statement rejected?",
    context: { case_id: KESTREL },
  });
});

test("a refused session and an unavailable service each show their own message", async ({
  page,
}) => {
  await signedIn(page, new MockApi());
  await service(page, { status: 401 });
  await openPanel(page);
  const panel = page.getByTestId("copilot-panel");
  await panel.getByRole("button", { name: "Why was a document rejected?" }).click();
  await expect(panel.getByRole("alert")).toHaveText("Sign in again to use the assistant.");

  await page.unroute(`${SERVICE}/**`);
  await service(page, {
    events: [
      ["session", { session_id: "s_2" }],
      ["error", { code: "model_unavailable" }],
    ],
  });
  await panel.getByRole("button", { name: "New conversation" }).click();
  await panel.getByRole("button", { name: "Which documents have a problem?" }).click();
  await expect(panel.getByRole("alert")).toHaveText(
    "The assistant is not available right now. Try again in a moment.",
  );
});

test("a user without access to appraisals is not offered the assistant", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, { ...api.user, permissions: [] });
  await service(page, {});
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  await expect(page.getByTestId("assistant-launcher")).toHaveCount(0);
});

const CARD = {
  session_id: "s_1",
  turn_id: "t_2",
  terminal: "confirm",
  text: "Check the message and add the customer's email address. Nothing is sent until you press Send.",
  use_case: "send_followup_email",
  columns: [],
  rows: [],
  sources: [],
  action: {
    id: "p_1",
    fields: {
      to: "",
      subject: "Please resend corrected documents",
      body: "Hello [Name],\n\nPlease resend the bank statement.",
    },
  },
};

async function askToSend(page: Page, reply: { refuse?: string } = {}) {
  const actions: { url: string; auth: string | undefined; body: Record<string, unknown> }[] = [];
  await signedIn(page, new MockApi());
  await service(
    page,
    {
      events: [
        ["session", { session_id: "s_1" }],
        ["result", CARD],
      ],
      ...reply,
    },
    actions,
  );
  await openPanel(page);
  const panel = page.getByTestId("copilot-panel");
  await panel.getByRole("textbox", { name: "Ask about this appraisal" }).fill("Send it");
  await panel.getByRole("textbox", { name: "Ask about this appraisal" }).press("Enter");
  await expect(panel.getByTestId("copilot-action")).toBeVisible();
  return { panel, actions, card: panel.getByTestId("copilot-action") };
}

test("sending: the card holds the draft, the user completes it, and Send confirms exactly those values", async ({
  page,
}) => {
  const { panel, actions, card } = await askToSend(page);
  await expect(card.getByLabel("Subject")).toHaveValue("Please resend corrected documents");
  await expect(card.getByLabel("Message")).toHaveValue(/Hello \[Name\]/);
  await expect(card.getByLabel("To")).toHaveValue("");
  expect(actions).toHaveLength(0); // nothing runs until the user presses Send

  await card.getByLabel("To").fill("asha@example.com");
  await card.getByLabel("Message").fill("Hello Asha,\n\nPlease resend the bank statement.");
  await card.getByRole("button", { name: "Send" }).click();

  await expect(panel).toContainText("The email to asha@example.com has been recorded for sending.");
  await expect(card).toHaveCount(0);
  expect(actions).toHaveLength(1);
  expect(actions[0]?.url).toContain("/actions/p_1/confirm");
  expect(actions[0]?.auth).toBe("Bearer session-token");
  expect(actions[0]?.body).toMatchObject({
    session_id: "s_1",
    context: { case_id: KESTREL },
    values: {
      to: "asha@example.com",
      subject: "Please resend corrected documents",
      body: "Hello Asha,\n\nPlease resend the bank statement.",
    },
  });
});

test("sending: a refusal is shown on the card, which stays open for the user to fix; Cancel drops it", async ({
  page,
}) => {
  const { panel, actions, card } = await askToSend(page, {
    refuse: "The recipient address is not valid.",
  });
  await card.getByLabel("To").fill("nope");
  await card.getByRole("button", { name: "Send" }).click();
  await expect(card.getByRole("alert")).toHaveText("The recipient address is not valid.");
  await expect(card.getByLabel("To")).toHaveValue("nope");
  await card.getByRole("button", { name: "Cancel" }).click();
  await expect(card).toHaveCount(0);
  expect(actions.map((a) => a.url.split("/").pop())).toEqual(["confirm", "cancel"]);
  await expect(panel.getByRole("alert")).toHaveCount(0);
});

test("the panel docks beside the page: the page stays visible and usable, and closing gives the room back", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await signedIn(page, new MockApi());
  await service(page, {});
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  const header = page.getByTestId("case-header");
  const before = await header.boundingBox();

  await page.getByTestId("assistant-launcher").click();
  const panel = page.getByTestId("copilot-panel");
  await expect(panel).toBeVisible();
  await expect(page.getByTestId("assistant-launcher")).toHaveCount(0);

  // Side by side: the page is narrower, not covered, and the panel starts where the page ends.
  const during = await header.boundingBox();
  const dock = await page.getByTestId("assistant-dock").boundingBox();
  expect(during && before && during.width < before.width).toBe(true);
  expect(during && dock && during.x + during.width <= dock.x).toBe(true);
  await expect(header).toBeVisible();

  // The page can still be used while the panel is open, and the conversation stays.
  await panel.getByRole("button", { name: "Why was a document rejected?" }).click();
  await page.getByRole("link", { name: "Files", exact: true }).first().click();
  await expect(page).toHaveURL(/\/documents$/);
  await expect(panel).toBeVisible();

  await panel.getByRole("button", { name: "Close the assistant" }).click();
  await expect(panel).toBeHidden();
  const after = await header.boundingBox();
  expect(after && before && Math.abs(after.width - before.width) < 2).toBe(true);
  await page.getByTestId("assistant-launcher").click();
  await expect(panel).toBeVisible();
});

test("the next step is offered as a button; a draft is shown as a message preview with its header", async ({
  page,
}) => {
  await signedIn(page, new MockApi());
  const replies = [
    { ...RESULT, format: "table", follow_ups: ["Draft an email to the customer about them"] },
    {
      ...RESULT,
      use_case: "draft_followup_email",
      columns: [],
      rows: [],
      format: "draft",
      text: "Draft - not sent\nSubject: Please resend corrected documents\n\nHello [Name],\n\nPlease resend the bank statement.",
      follow_ups: ["Send it"],
    },
  ];
  const asked: string[] = [];
  await page.route(`${SERVICE}/**`, async (route: Route) => {
    const request = route.request();
    if (request.method() === "OPTIONS") return route.fulfill({ status: 204, headers: CORS });
    asked.push((request.postDataJSON() as { message: string }).message);
    return route.fulfill({
      status: 200,
      headers: { ...CORS, "content-type": "text/event-stream" },
      body: sse([
        ["session", { session_id: "s_1" }],
        ["result", replies[asked.length - 1] ?? replies[1]],
      ]),
    });
  });
  await openPanel(page);
  const panel = page.getByTestId("copilot-panel");
  await expect(panel).toContainText("Kestrel Polymers Pvt Ltd · " + KESTREL); // what the assistant is talking about

  await panel.getByRole("button", { name: "Why was a document rejected?" }).click();
  const chip = panel.getByRole("button", { name: "Draft an email to the customer about them" });
  await expect(chip).toBeVisible();
  await chip.click();

  const draft = panel.getByTestId("copilot-draft");
  await expect(draft).toContainText("Draft - not sent");
  await expect(draft).toContainText("Subject: Please resend corrected documents");
  await expect(draft.getByRole("button", { name: "Copy" })).toBeVisible();
  await expect(panel.getByRole("button", { name: "Send it" })).toBeVisible();
  await expect(chip).toHaveCount(0); // only the latest answer offers a next step
  expect(asked).toEqual([
    "Why was a document rejected?",
    "Draft an email to the customer about them",
  ]);
});

test("a sent email is shown as completed", async ({ page }) => {
  const { panel, card } = await askToSend(page);
  await card.getByLabel("To").fill("asha@example.com");
  await card.getByLabel("Message").fill("Hello Asha,\n\nPlease resend.");
  await card.getByRole("button", { name: "Send" }).click();
  await expect(panel.getByTestId("copilot-done")).toHaveText(
    "The email to asha@example.com has been recorded for sending.",
  );
});
