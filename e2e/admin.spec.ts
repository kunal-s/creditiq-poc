// Administration and the audit trail (FRD §6): read-only views of the
// published configuration, the people and roles, and the decision log.
import { expect, test } from "@playwright/test";
import { RM } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

test("Administration shows the published version and its history", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/");
  await page.getByRole("link", { name: "Configuration" }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByTestId("config-version")).toHaveCount(2);
  await expect(page.getByTestId("config-history")).toContainText("Tighten the review gate");
  // Section names read as words, not file keys.
  await expect(page.getByTestId("config-history")).toContainText("policy norms, field extraction");
  await expect(page.getByTestId("config-history")).not.toContainText("ingestion.fields");
});

test("Policy norms, checklist, document types and users are listed", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/admin/policy");
  await expect(page.getByTestId("admin-norm")).toHaveCount(2);
  await expect(page.getByTestId("admin-norms-ratios")).toContainText("at least 1.25");
  await expect(page.getByTestId("admin-norms-eligibility")).toContainText("at least 3 years");
  // A norm with no status of its own is provisional through its ratio.
  await expect(
    page.getByTestId("admin-norm").filter({ hasText: "Debt service coverage" }),
  ).toContainText("Provisional norm");
  await expect(
    page.getByTestId("admin-norm").filter({ hasText: "Business vintage" }),
  ).not.toContainText("Provisional norm");
  await page.getByTestId("admin-checklist").click();
  await expect(page.getByTestId("admin-gates")).toContainText("ready for credit review");
  await page.getByTestId("admin-documentTypes").click();
  await expect(page.getByTestId("admin-document-type").first()).toBeVisible();
  await page.getByTestId("admin-users").click();
  await expect(page.getByTestId("admin-user")).toHaveCount(2);
  await expect(page.getByTestId("admin-role").first()).toContainText("Create appraisals");
});

test("the audit trail lists activity in words", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api);
  await page.goto("/audit");
  const entries = page.getByTestId("audit-entry");
  await expect(entries).toHaveCount(2);
  await expect(entries.first()).toContainText("Decided a review item");
  await expect(entries.first()).toContainText("Ananya Krishnan");
  await expect(entries.nth(1)).toContainText("Signed in");
});

test("the cross-verification board's escalations and query additions read in words", async ({
  page,
}) => {
  const entry = (seq: number, action: string, detail: Record<string, string>) => ({
    seq,
    at: "2026-10-09T10:00:00+00:00",
    actor: "ananya-krishnan",
    actor_name: "Ananya Krishnan",
    case_id: "BBG-2026-000021",
    action,
    detail,
  });
  const api = new MockApi().on("GET", /^\/api\/audit$/, () => ({
    json: {
      entries: [
        entry(2, "finding.query_added", { rule_id: "TO-01", request: "GSTR-3B returns" }),
        entry(1, "finding.escalated", { rule_id: "OB-01", comment: "For the Credit Manager." }),
      ],
      next_before: null,
      actors: ["ananya-krishnan"],
      actions: ["finding.escalated", "finding.query_added"],
    },
  }));
  await signedIn(page, api);
  await page.goto("/audit");
  const entries = page.getByTestId("audit-entry");
  await expect(entries).toHaveCount(2);
  await expect(entries.first()).toContainText("Put a request on the query list");
  await expect(entries.nth(1)).toContainText("Escalated a discrepancy to the Credit Manager");
  await expect(page.locator("option")).toContainText([
    "Escalated a discrepancy to the Credit Manager",
    "Put a request on the query list",
  ]);
  await expect(page.getByText("finding escalated")).toHaveCount(0);
});

test("a relationship manager sees neither administration nor the audit trail", async ({ page }) => {
  const api = new MockApi();
  api.user = RM;
  await signedIn(page, api);
  await page.goto("/");
  await expect(page.getByRole("link", { name: "Audit trail" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Configuration" })).toHaveCount(0);
});
