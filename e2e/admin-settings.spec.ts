// Settings (F-00.6): an Administrator edits the tolerances, policy norms, cross-check rules and
// approval matrix, reviews the changes with the engine and publishes them, with a note, as a new
// configuration version. Other readers of administration see the same values read-only.
import { expect, test, type Page } from "@playwright/test";
import { ADMIN, ANALYST } from "./fixtures/data";
import { MockApi, signedIn } from "./support/api";

const NOTHING_ELSE = { ratios: {}, norms: {}, rules: {}, bands: {}, deviations: {} };

async function openSettings(page: Page, api = new MockApi()) {
  await signedIn(page, api, ADMIN);
  await page.goto("/admin/settings");
  await expect(page.getByTestId("settings-tolerances")).toBeVisible();
  return api;
}

const setting = (page: Page, key: string) => page.getByTestId(`setting-${key}`);

test("the Administrator lands on Settings after signing in and sees only administration", async ({
  page,
}) => {
  const api = new MockApi();
  api.user = ADMIN;
  await api.install(page);
  await page.goto("/sign-in");
  await expect(page.getByRole("button", { name: "Sign in" })).toBeEnabled();
  await page.getByLabel("Email").fill(ADMIN.email);
  await page.getByLabel("Password").fill("local-test-only");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin\/settings$/);
  await expect(page.getByTestId("settings-header")).toContainText("Version 2 in force");
  await expect(page.getByTestId("settings-header")).toContainText("Config Admin");
  await expect(page.getByTestId("admin-settings")).toHaveClass(/bg-primary/);

  const menu = page.getByRole("navigation").first();
  await expect(menu.getByRole("link", { name: "Settings" })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Configuration" })).toBeVisible();
  await expect(menu.getByRole("link", { name: "Appraisals" })).toHaveCount(0);
  await expect(menu.getByRole("link", { name: "New appraisal" })).toHaveCount(0);
  await expect(menu.getByRole("link", { name: "Review queue" })).toHaveCount(0);
  await expect(menu.getByRole("link", { name: "Audit trail" })).toHaveCount(0);
  // The workbench never loaded: an Administrator has no case access.
  expect(api.called("GET", "/api/cases")).toHaveLength(0);

  // The product name, which leads to the workbench, brings them back to Settings.
  await page.getByRole("link", { name: "Configuration" }).first().click();
  await expect(page).toHaveURL(/\/admin$/);
  await page.getByRole("link", { name: "CreditIQ" }).click();
  await expect(page).toHaveURL(/\/admin\/settings$/);
});

test("an edited tolerance is marked with the value in force and counted", async ({ page }) => {
  await openSettings(page);
  await expect(page.getByTestId("settings-bar")).toHaveCount(0);
  const tolerance = setting(page, "tolerances:turnover_variance");
  await expect(tolerance).toHaveAttribute("data-changed", "false");
  await tolerance.getByRole("textbox").fill("2");
  await expect(tolerance).toHaveAttribute("data-changed", "true");
  await expect(tolerance.getByTestId("setting-was")).toHaveText("was 1%");
  await expect(page.getByTestId("settings-count")).toHaveText("1 change");

  const acceptable = setting(page, "ratios:current-ratio:acceptable");
  await acceptable.getByRole("textbox").fill("1.3");
  await expect(acceptable.getByTestId("setting-was")).toHaveText("was 1.2 times");
  await expect(page.getByTestId("settings-count")).toHaveText("2 changes");

  // Typing the value in force back is no change; a value that is not a number is marked.
  await acceptable.getByRole("textbox").fill("1.2");
  await expect(acceptable).toHaveAttribute("data-changed", "false");
  await expect(page.getByTestId("settings-count")).toHaveText("1 change");
  await tolerance.getByRole("textbox").fill("two");
  await expect(tolerance).toContainText("Enter a number");
  await expect(page.getByTestId("settings-review")).toBeDisabled();
});

test("a field's change is undone, and Discard drops every change", async ({ page }) => {
  await openSettings(page);
  const tolerance = setting(page, "tolerances:turnover_variance");
  const vintage = setting(page, "norms:EL-01");
  await tolerance.getByRole("textbox").fill("2");
  await vintage.getByRole("textbox").fill("2");
  await expect(vintage.getByTestId("setting-was")).toHaveText("was 3 years");
  await expect(page.getByTestId("settings-count")).toHaveText("2 changes");

  await tolerance.getByTestId("setting-undo").click();
  await expect(tolerance).toHaveAttribute("data-changed", "false");
  await expect(tolerance.getByRole("textbox")).toHaveValue("1");
  await expect(page.getByTestId("settings-count")).toHaveText("1 change");

  await page.getByTestId("settings-discard").click();
  await expect(page.getByTestId("settings-bar")).toHaveCount(0);
  await expect(vintage.getByRole("textbox")).toHaveValue("3");
  await expect(vintage).toHaveAttribute("data-changed", "false");
});

test("the review lists each change in words and needs a note", async ({ page }) => {
  const api = await openSettings(page);
  await setting(page, "tolerances:turnover_variance").getByRole("textbox").fill("2");
  await setting(page, "norms:EL-05").getByRole("textbox").fill("25");
  await page.getByTestId("settings-review").click();

  const dialog = page.getByTestId("settings-review-dialog");
  const changes = dialog.getByTestId("settings-change");
  await expect(changes).toHaveText([
    "Turnover variance between sources · Value: 1% → 2%",
    "EL-05 Total request against turnover · Threshold: 20% → 25%",
    // The engine adds what follows from a change; it is listed as given.
    "Turnover method: working-capital requirement · Requirement: 25% → 30%",
  ]);
  expect(api.called("POST", "/api/admin/settings/preview")[0]!.body).toEqual({
    ...NOTHING_ELSE,
    tolerances: { turnover_variance: 2 },
    norms: { "EL-05": 25 },
  });
  // Nothing is published by a review.
  expect(api.called("POST", "/api/admin/settings/publish")).toHaveLength(0);

  const publish = dialog.getByTestId("settings-publish");
  await expect(publish).toBeDisabled();
  await dialog.getByTestId("settings-note").fill("ok");
  await expect(publish).toBeDisabled();
  await dialog.getByTestId("settings-note").fill("Tolerance for the pilot");
  await expect(publish).toBeEnabled();

  // Cancelling keeps the draft.
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("settings-count")).toHaveText("2 changes");
});

test("publishing reports the cases re-checked, and the history shows the version edited on screen", async ({
  page,
}) => {
  const api = new MockApi();
  api.casesFailed = ["BBG-2026-000022"];
  await openSettings(page, api);
  const tolerance = setting(page, "tolerances:turnover_variance");
  await tolerance.getByRole("textbox").fill("2");
  await page.getByTestId("settings-review").click();
  const dialog = page.getByTestId("settings-review-dialog");
  await expect(dialog.getByTestId("settings-change")).toHaveCount(1);
  await dialog.getByTestId("settings-note").fill("  Tolerance for the pilot  ");
  await dialog.getByTestId("settings-publish").click();

  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("settings-published")).toContainText(
    "Version published · 3 cases re-checked",
  );
  await expect(page.getByTestId("settings-failed")).toHaveText(
    "Could not be re-checked: BBG-2026-000022",
  );
  expect(api.called("POST", "/api/admin/settings/publish")[0]!.body).toEqual({
    note: "Tolerance for the pilot",
    changes: { ...NOTHING_ELSE, tolerances: { turnover_variance: 2 } },
  });
  // The draft is cleared and the settings read again: 2% is now the value in force.
  await expect(page.getByTestId("settings-bar")).toHaveCount(0);
  await expect(tolerance.getByRole("textbox")).toHaveValue("2");
  await expect(tolerance).toHaveAttribute("data-changed", "false");
  await expect(page.getByTestId("settings-header")).toContainText("Version 3 in force");
  await expect(page.getByTestId("settings-header")).toContainText("Nikhil Sawant");
  await expect(page.getByTestId("settings-header")).toContainText("Edited on screen");

  await page.getByTestId("admin-configuration").click();
  const versions = page.getByTestId("config-version");
  await expect(versions).toHaveCount(3);
  await expect(versions.first()).toContainText("Version 3");
  await expect(versions.first()).toContainText("In force");
  await expect(versions.first()).toContainText("Edited on screen");
  await expect(versions.first()).toContainText("Tolerance for the pilot");
  await expect(versions.first()).toContainText("1 section(s) changed: tolerances");
  await expect(versions.nth(1)).not.toContainText("Edited on screen");
  await expect(page.getByTestId("config-current")).toContainText(
    "changed under Settings by an Administrator",
  );
});

test("the engine's problems are shown as given and stop the publish", async ({ page }) => {
  const api = new MockApi();
  api.settingsProblems = [
    "Turnover variance between sources: give a percentage between 0 and 100.",
  ];
  await openSettings(page, api);
  await setting(page, "tolerances:turnover_variance").getByRole("textbox").fill("150");
  await page.getByTestId("settings-review").click();
  const dialog = page.getByTestId("settings-review-dialog");
  await expect(dialog.getByTestId("settings-problems")).toContainText(
    "Turnover variance between sources: give a percentage between 0 and 100.",
  );
  await dialog.getByTestId("settings-note").fill("Tolerance for the pilot");
  await expect(dialog.getByTestId("settings-publish")).toBeDisabled();
  await dialog.getByRole("button", { name: "Cancel" }).click();

  // A refusal at publish (the configuration changed meanwhile) is shown the same way.
  api.settingsProblems = [];
  api.on("POST", /^\/api\/admin\/settings\/publish$/, () => ({
    status: 422,
    json: { detail: { problems: ["Turnover variance between sources: already 150% in force."] } },
  }));
  await page.getByTestId("settings-review").click();
  await expect(dialog.getByTestId("settings-problems")).toHaveCount(0);
  await dialog.getByTestId("settings-note").fill("Tolerance for the pilot");
  await dialog.getByTestId("settings-publish").click();
  await expect(dialog.getByTestId("settings-problems")).toContainText("already 150% in force");
  await expect(dialog.getByTestId("settings-publish")).toBeDisabled();
  await expect(page.getByTestId("settings-published")).toHaveCount(0);
});

test("a rule switched off and a severity changed appear in the review", async ({ page }) => {
  const api = await openSettings(page);
  const rule = page.getByTestId("rule-TO-04");
  await expect(rule).toContainText("RM-declared turnover against evidenced turnover");
  await rule.getByRole("switch").click();
  await expect(setting(page, "rules:TO-04:enabled")).toContainText("Off");
  await expect(setting(page, "rules:TO-04:enabled").getByTestId("setting-was")).toHaveText(
    "was Runs",
  );
  await rule.getByRole("combobox").selectOption("moderate");
  await expect(setting(page, "rules:TO-04:severity").getByTestId("setting-was")).toHaveText(
    "was Mild",
  );
  await page.getByTestId("rule-ID-01").getByRole("checkbox").uncheck();
  await expect(page.getByTestId("settings-count")).toHaveText("3 changes");

  await page.getByTestId("settings-review").click();
  await expect(page.getByTestId("settings-change")).toHaveText([
    "ID-01 Entity PAN consistent across documents · Blocks submission: yes → no",
    "TO-04 RM-declared turnover against evidenced turnover · Runs: on → off",
    "TO-04 RM-declared turnover against evidenced turnover · Severity: Mild → Moderate",
  ]);
  expect(api.called("POST", "/api/admin/settings/preview")[0]!.body).toEqual({
    ...NOTHING_ELSE,
    tolerances: {},
    rules: { "ID-01": { blocking: false }, "TO-04": { enabled: false, severity: "moderate" } },
  });
});

test("a band amount entered in crore is sent in rupees", async ({ page }) => {
  const api = await openSettings(page);
  const product = page.getByTestId("matrix-working_capital");
  await expect(page.getByTestId("band-working_capital-2")).toContainText("Above INR 5.00 cr");
  const first = setting(page, "bands:working_capital:0:up_to_inr");
  await first.getByRole("textbox").fill("0");
  await expect(first).toContainText("Enter an amount above 0");
  await expect(page.getByTestId("settings-review")).toBeDisabled();
  await first.getByRole("textbox").fill("2.5");
  await expect(
    setting(page, "bands:working_capital:0:up_to_inr").getByTestId("setting-was"),
  ).toHaveText("was INR 2.00 cr");
  // The open band above follows the amount below it.
  await setting(page, "bands:working_capital:1:up_to_inr").getByRole("textbox").fill("6");
  await expect(page.getByTestId("band-working_capital-2")).toContainText("Above INR 6.00 cr");
  await product
    .getByTestId("setting-bands:working_capital:2:authority")
    .getByRole("combobox")
    .selectOption({ label: "Regional Credit Head" });
  // No minimum authority for an eligibility deviation.
  await setting(page, "deviations:eligibility:at_least")
    .getByRole("combobox")
    .selectOption({ label: "None" });

  await page.getByTestId("settings-review").click();
  await expect(page.getByTestId("settings-change")).toHaveText([
    "Working capital, band 1 · Up to: INR 2.00 cr → INR 2.50 cr",
    "Working capital, band 2 · Up to: INR 5.00 cr → INR 6.00 cr",
    "Working capital, band 3 · Authority: Zonal Credit Committee → Regional Credit Head",
    "Eligibility · At least: Regional Credit Head → none",
  ]);
  expect(api.called("POST", "/api/admin/settings/preview")[0]!.body).toEqual({
    ...NOTHING_ELSE,
    tolerances: {},
    bands: {
      working_capital: [
        { up_to_inr: 25_000_000, authority: "credit_officer" },
        { up_to_inr: 60_000_000, authority: "regional_credit_head" },
        { up_to_inr: null, authority: "regional_credit_head" },
      ],
    },
    deviations: { eligibility: { at_least: "" } },
  });
});

test("an analyst sees the settings read-only, with nothing to edit", async ({ page }) => {
  const api = new MockApi();
  await signedIn(page, api, ANALYST);
  await page.goto("/admin");
  await page.getByTestId("admin-settings").click();
  await expect(page).toHaveURL(/\/admin\/settings$/);
  await expect(page.getByTestId("settings-mode")).toHaveText(
    "These settings are read-only for your role. An Administrator changes them and publishes them as a new version.",
  );
  await expect(setting(page, "tolerances:turnover_variance")).toHaveText("1%");
  await expect(setting(page, "ratios:tol-tnw:acceptable")).toHaveText("at most 3 times");
  await expect(setting(page, "rules:BR-01:enabled")).toHaveText("Off");
  await expect(setting(page, "bands:working_capital:0:up_to_inr")).toHaveText("INR 2.00 cr");
  await expect(setting(page, "deviations:financial:at_least")).toHaveText("None");
  const main = page.getByRole("main");
  await expect(main.locator("input, select, textarea, [role=switch]")).toHaveCount(0);
  await expect(page.getByTestId("setting-undo")).toHaveCount(0);
  await expect(page.getByTestId("settings-bar")).toHaveCount(0);
});

test("the unit for financial figures is chosen, reviewed and published like any setting", async ({
  page,
}) => {
  const api = await openSettings(page);
  const unit = setting(page, "display:unit");
  await expect(page.getByTestId("settings-display")).toContainText("Financial figures");
  await expect(unit.getByRole("combobox")).toHaveValue("crore");
  await expect(page.getByTestId("display-unit")).toContainText("INR 4.20 cr");

  await unit.getByRole("combobox").selectOption("lakh");
  await expect(unit).toHaveAttribute("data-changed", "true");
  await expect(unit.getByTestId("setting-was")).toHaveText("was Crore");
  await expect(page.getByTestId("display-unit")).toContainText("INR 420.00 lakh");

  await page.getByTestId("settings-review").click();
  const dialog = page.getByTestId("settings-review-dialog");
  await expect(dialog.getByTestId("settings-change")).toHaveText([
    "Unit for financial figures · Unit: Crore → Lakh",
  ]);
  expect(api.called("POST", "/api/admin/settings/preview")[0]!.body).toEqual({
    ...NOTHING_ELSE,
    tolerances: {},
    display_unit: "lakh",
  });
  await dialog.getByTestId("settings-note").fill("Credit prefers lakh for small borrowers");
  await dialog.getByTestId("settings-publish").click();
  await expect(page.getByTestId("settings-published")).toBeVisible();
  await expect(unit.getByRole("combobox")).toHaveValue("lakh");
});
