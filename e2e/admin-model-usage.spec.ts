// Administration > Model usage: an Administrator sees every request the system made to a language
// model in the range, by day, service and task, with its tokens, its cost at the configured prices
// and what failed; a price that is not set reads "Price not set", never 0. Only a role with
// model_usage.read sees it, and only where the deployment has it on (features.model_usage).
import { expect, test } from "@playwright/test";
import { ADMIN, ANALYST, META } from "./fixtures/data";
import { USAGE_ROWS, usageSummary } from "./fixtures/modelUsage";
import { MockApi, scrollsSideways, signedIn } from "./support/api";

test.use({ viewport: { width: 1440, height: 900 } });

async function open(page: import("@playwright/test").Page, api = new MockApi()) {
  await signedIn(page, api, ADMIN);
  await page.goto("/admin/model-usage");
  await expect(page.getByTestId("usage-kpi-calls")).toBeVisible();
  return api;
}

test("the Administrator sees the calls, tokens, cost and failures of the range", async ({
  page,
}) => {
  await open(page);
  await expect(page.getByTestId("admin-modelUsage")).toBeVisible();
  // In the side menu and among the Administration sections.
  await expect(page.getByRole("link", { name: "Model Usage", exact: true })).toHaveCount(2);
  // 6 + 14 + 3 + 4 + 12 calls; 33,300 tokens in and 6,200 out.
  await expect(page.getByTestId("usage-kpi-calls")).toContainText("39");
  await expect(page.getByTestId("usage-kpi-calls")).toContainText("23 answered, 16 failed");
  await expect(page.getByTestId("usage-kpi-tokens")).toContainText("39,500");
  await expect(page.getByTestId("usage-kpi-tokens")).toContainText("33,300 in, 6,200 out");
  // The case assistant's model has no price: the cost leaves it out and says so.
  await expect(page.getByTestId("usage-kpi-cost")).toContainText("USD 0.0099");
  await expect(page.getByTestId("usage-kpi-cost")).toContainText(
    "Leaves out models whose price is not set",
  );
  await expect(page.getByTestId("usage-sources")).toContainText("No recorded answer: 12");

  // One bar a day of the range, in both charts.
  await expect(page.getByTestId("usage-tokens-chart-bar")).toHaveCount(7);
  await expect(page.getByTestId("usage-cost-chart-bar")).toHaveCount(7);
  await page.locator('[data-testid="usage-tokens-chart-bar"][data-day="2026-11-10"]').hover();
  await expect(page.getByTestId("usage-tokens-chart-readout")).toContainText("21,000");

  const groups = page.getByTestId("usage-group");
  await expect(groups).toHaveCount(USAGE_ROWS.length - 1); // the two extract days are one row
  const assistant = groups.filter({ hasText: "Case assistant" });
  await expect(assistant).toContainText("Price not set");
  await expect(assistant).not.toContainText("USD 0");

  const kinds = page.getByTestId("usage-kind");
  await expect(kinds.first()).toContainText("No recorded answer");
  await expect(page.getByTestId("usage-by-kind")).toContainText("Per-minute limit");
  await expect(page.getByTestId("usage-by-kind")).toContainText("Quota used up");

  // A model is named by its configured label, never by the provider's id.
  await expect(page.getByTestId("model-usage")).not.toContainText("gpt-");
  await expect(page.getByTestId("usage-by-service")).toContainText("Compact model");
});

test("the call list pages, and narrows by outcome, failure and appraisal", async ({ page }) => {
  await open(page);
  const calls = page.getByTestId("usage-call");
  await expect(calls).toHaveCount(25);
  await expect(page.getByTestId("usage-page")).toHaveText("1–25 of 39");
  await page.getByTestId("usage-page-next").click();
  await expect(page.getByTestId("usage-page")).toHaveText("26–39 of 39");
  await expect(page.getByTestId("usage-page-next")).toBeDisabled();

  await page.getByTestId("usage-status").selectOption("error");
  await expect(page.getByTestId("usage-page")).toHaveText("1–16 of 16");
  await expect(calls.first()).toHaveAttribute("data-status", "error");

  await page.getByTestId("usage-kind-filter").selectOption("quota");
  await expect(calls).toHaveCount(1);
  await expect(calls.first()).toContainText("Quota used up");

  await page.getByTestId("usage-kind-filter").selectOption("");
  await page.getByTestId("usage-status").selectOption("");
  await page.getByTestId("usage-case").fill("BBG-2026-000021");
  await expect(page.getByTestId("usage-page")).toHaveText("1–25 of 35");
  await expect(calls.first().getByRole("link", { name: "BBG-2026-000021" })).toBeVisible();
});

test("with no price set for any model, the cost reads Price not set, never 0", async ({ page }) => {
  const api = new MockApi();
  api.modelUsage = usageSummary(USAGE_ROWS.map((r) => ({ ...r, cost: null, price_set: false })));
  await open(page, api);
  await expect(page.getByTestId("usage-kpi-cost")).toContainText("Price not set");
  await expect(page.getByTestId("usage-kpi-cost")).not.toContainText("0.00");
  await expect(page.getByTestId("usage-cost-chart-empty")).toBeVisible();
  await expect(page.getByTestId("usage-cost-chart")).toHaveCount(0);
});

test("a source that cannot be read is named; the figures hold the others", async ({ page }) => {
  const api = new MockApi();
  api.modelUsage = usageSummary(
    USAGE_ROWS.filter((r) => r.service !== "copilot"),
    ["copilot"],
  );
  await open(page, api);
  await expect(page.getByTestId("usage-unavailable")).toContainText("Case assistant");
  await expect(page.getByTestId("usage-kpi-calls")).toContainText("35");
});

test("a range with no calls says so", async ({ page }) => {
  const api = new MockApi();
  api.modelUsage = usageSummary([]);
  await signedIn(page, api, ADMIN);
  await page.goto("/admin/model-usage");
  await expect(page.getByTestId("usage-empty")).toContainText("No model calls in this range");
  await expect(page.getByTestId("usage-calls")).toHaveCount(0);
});

test("the range and service are sent to the engine", async ({ page }) => {
  const api = await open(page);
  await page.getByTestId("usage-from").fill("2026-11-10");
  await page.getByTestId("usage-service").selectOption("cam");
  await expect
    .poll(() => api.calls.some((c) => c.key === "GET /api/admin/model-usage/summary"))
    .toBe(true);
  await expect(page.getByTestId("usage-task").locator("option")).toHaveText([
    "All tasks",
    "Memo section redraft",
  ]);
});

test("a role without model_usage.read has no Model usage", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, ANALYST);
  await page.goto("/admin");
  await expect(page.getByTestId("admin-configuration")).toBeVisible();
  await expect(page.getByTestId("admin-modelUsage")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Model Usage", exact: true })).toHaveCount(0);
  await page.goto("/admin/model-usage");
  await expect(page).toHaveURL(/\/admin$/);
  expect(api.called("GET", "/api/admin/model-usage/summary")).toHaveLength(0);
});

test("switched off, Administration shows nothing of model usage", async ({ page }) => {
  const api = new MockApi();
  api.on("GET", /^\/api\/meta$/, () => ({ json: { ...META, features: { model_usage: false } } }));
  await signedIn(page, api, ADMIN);
  await page.goto("/admin");
  await expect(page.getByTestId("admin-configuration")).toBeVisible();
  await expect(page.getByTestId("admin-modelUsage")).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Model Usage", exact: true })).toHaveCount(0);
  await page.goto("/admin/model-usage");
  await expect(page).toHaveURL(/\/admin$/);
  expect(api.called("GET", "/api/admin/model-usage/summary")).toHaveLength(0);
});

test("at phone width the page does not scroll sideways", async ({ page }) => {
  await page.setViewportSize({ width: 400, height: 860 });
  await open(page);
  expect(await scrollsSideways(page)).toBe(false);
  await expect(page.getByTestId("usage-tokens-chart")).toBeVisible();
});
