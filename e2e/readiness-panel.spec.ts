// The Document readiness step opens with where the case stands: the verdict; the gate's four
// conditions, each drawn (the weighted score against the review gate, no blocking requirement
// open, every file read, every required field found) and how many are met; the counts by status and each gate; and the one
// action that creates the case, for a role that may. The required document set and the query
// list follow.
import { expect, test, type Page } from "@playwright/test";
import { KESTREL, RM } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

/** The case-creation gate as the engine works it out: the review gate unmet, two blocking
 * requirements open, every file read. */
function withGate(api: MockApi) {
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/progress$`), () => ({
    json: {
      ...api.progress(KESTREL),
      gate: {
        open: false,
        can_open: false,
        open_exceptions: 0,
        blocking_open: 2,
        score_pct: 58,
        gate_pct: 85,
        blockers: ["review_gate", "blocking_items"],
      },
    },
  }));
  return api;
}

async function step(page: Page, api = withGate(new MockApi()), user = api.user) {
  await signedIn(page, api, user);
  await page.goto(`/appraisals/${KESTREL}/completeness`);
  await expect(page.getByTestId("create-case-panel")).toBeVisible();
  return api;
}

test("the panel heads the step: the verdict, the four conditions, the counts and each gate", async ({
  page,
}) => {
  await step(page);
  const panel = page.getByTestId("create-case-panel");
  await expect(panel.getByTestId("gate-banner")).toContainText("Not ready to create the case yet");
  await expect(panel.getByTestId("blocking-gaps")).toHaveText(
    "2 blocking requirement(s) not satisfied. Each one stops the case reaching credit review.",
  );
  const tiles = panel.getByTestId("gate-condition");
  expect(
    await tiles.evaluateAll((els) => els.map((e) => e.getAttribute("data-condition"))),
  ).toEqual(["review_gate", "blocking_items", "open_exceptions", "required_fields"]);
  await expect(tiles.nth(0)).toContainText("Review gate");
  await expect(tiles.nth(0)).toContainText("Weighted score");
  await expect(tiles.nth(1)).toContainText("Blocking requirements");
  await expect(tiles.nth(1)).toContainText(/2\s*not satisfied/);
  await expect(tiles.nth(2)).toContainText("Files read");
  await expect(tiles.nth(2)).toContainText("Every file was read");
  await expect(tiles.nth(3)).toContainText("Required fields");
  await expect(tiles.nth(3)).toContainText("Every required field was found");
  // The counts by status and each gate.
  await expect(panel.getByTestId("checklist-summary")).toContainText("Missing2");
  await expect(panel.getByTestId("gate")).toHaveCount(2);
  // Below it, the required document set and the query list.
  await expect(page.getByTestId("checklist")).toBeVisible();
});

test("two of four conditions met, said plainly, and the one Create case shut until all are", async ({
  page,
}) => {
  await step(page);
  const progress = page.getByTestId("gate-progress");
  await expect(progress).toContainText("2 of 4 conditions met");
  await expect(progress).toHaveAttribute(
    "title",
    /no blocking requirement is open, every file has been read, and every required figure and identifier is found/,
  );
  const create = page.getByTestId("create-case");
  await expect(create).toHaveCount(1);
  await expect(create).toBeDisabled();
  // Its hover names what stands in the way.
  await expect(create).toHaveAttribute(
    "title",
    /Every condition must be met first: Review gate not met/,
  );
  await expect(create).toHaveAttribute("title", /2 blocking requirement\(s\) not satisfied/);
  // The required document set has no Create case of its own.
  await expect(page.getByTestId("checklist").getByTestId("create-case")).toHaveCount(0);
});

test("a role that cannot create the case sees where it stands, without the action", async ({
  page,
}) => {
  await step(page, withGate(new MockApi()), RM);
  await expect(page.getByTestId("gate-progress")).toContainText("2 of 4 conditions met");
  await expect(page.getByTestId("create-case")).toHaveCount(0);
  await expect(page.getByTestId("create-anyway")).toHaveCount(0);
});

test("a provisional checklist says so once, in the panel", async ({ page }) => {
  const api = withGate(new MockApi());
  api.checklists.set(KESTREL, { ...api.checklists.get(KESTREL)!, provisional: true });
  await step(page, api);
  await expect(page.getByTestId("provisional")).toHaveCount(1);
  await expect(page.getByTestId("create-case-panel").getByTestId("provisional")).toBeVisible();
});

test("a required field not found names what it stops, and the case can be created anyway with a reason", async ({
  page,
}) => {
  const api = new MockApi();
  let sent: unknown = null;
  api.on("GET", new RegExp(`^/api/cases/${KESTREL}/progress$`), () => ({
    json: {
      ...api.progress(KESTREL),
      gate: {
        open: false,
        can_open: false,
        open_exceptions: 0,
        blocking_open: 0,
        score_pct: 90,
        gate_pct: 85,
        blockers: ["required_fields"],
        required_fields: [
          {
            field: "depreciation@2025-03-31",
            label: "Depreciation, FY 2024-25",
            stops: ["EBITDA", "DSCR"],
          },
        ],
      },
    },
  }));
  api.on("POST", new RegExp(`^/api/cases/${KESTREL}/assessment$`), (req) => {
    sent = req.postDataJSON();
    return { json: api.cases.find((c) => c.id === KESTREL) };
  });
  await step(page, api);
  const tile = page.locator('[data-condition="required_fields"]');
  await expect(tile).toHaveAttribute("data-met", "false");
  await expect(tile.getByTestId("required-field-gap")).toHaveText(
    "Depreciation, FY 2024-25Needed for EBITDA, DSCR",
  );
  await expect(page.getByTestId("create-case")).toBeDisabled();
  await page.getByTestId("create-anyway-open").click();
  const submit = page.getByTestId("create-anyway-submit");
  await expect(submit).toBeDisabled();
  await page
    .getByTestId("create-anyway-reason")
    .fill("Depreciation follows with the revised statements.");
  await submit.click();
  await expect
    .poll(() => sent)
    .toEqual({ reason: "Depreciation follows with the revised statements." });
});
