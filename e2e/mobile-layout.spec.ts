// Every screen at phone width (375 px): nothing makes the page scroll sideways. Wide content
// (tables, page images) may scroll inside its own box; the page itself must fit the screen.
import { expect, test, type Page } from "@playwright/test";
import type { SessionUser } from "@/api/types";
import { ADMIN, ANALYST, KESTREL, MANAGER, MESSAGE, RM } from "./fixtures/data";
import { MockApi, showArea, signedIn } from "./support/api";
import { dialogsCut, overflow, unroll } from "./support/layout";

const WIDTH = Number(process.env["MOBILE_WIDTH"] ?? 375);
const HEIGHT = Number(process.env["MOBILE_HEIGHT"] ?? (WIDTH >= 768 ? 1024 : 812));
test.use({
  viewport: { width: WIDTH, height: HEIGHT },
  isMobile: WIDTH < 768,
  hasTouch: true,
});

const SHOTS = process.env["MOBILE_SHOTS"];

type Screen = {
  name: string;
  path: string;
  user?: SessionUser | null;
  open?: (page: Page) => Promise<void>;
};

const CASE = `/appraisals/${KESTREL}`;
export const SCREENS: Screen[] = [
  { name: "sign-in", path: "/sign-in", user: null },
  { name: "home", path: "/" },
  { name: "appraisals", path: "/appraisals" },
  { name: "new-appraisal", path: "/appraisals/new" },
  { name: "case-overview", path: CASE },
  { name: "case-files", path: `${CASE}/documents` },
  { name: "case-file-integrity", path: `${CASE}/files/f-merged/integrity` },
  { name: "case-extraction", path: `${CASE}/extraction` },
  { name: "case-completeness", path: `${CASE}/completeness` },
  { name: "case-cross-verification", path: `${CASE}/cross-verification` },
  { name: "case-policy", path: `${CASE}/policy` },
  { name: "case-outputs", path: `${CASE}/outputs` },
  { name: "case-comparison", path: `${CASE}/comparison`, user: MANAGER },
  { name: "review-queue", path: "/review" },
  { name: "exceptions", path: "/exceptions" },
  { name: "audit-trail", path: "/audit" },
  { name: "scorecard", path: "/scorecard" },
  { name: "help", path: "/help" },
  { name: "docready", path: "/docready" },
  { name: "admin", path: "/admin", user: ADMIN },
  { name: "admin-checklist", path: "/admin/checklist", user: ADMIN },
  { name: "admin-document-types", path: "/admin/document-types", user: ADMIN },
  { name: "admin-policy", path: "/admin/policy", user: ADMIN },
  { name: "admin-settings", path: "/admin/settings", user: ADMIN },
  { name: "admin-users", path: "/admin/users", user: ADMIN },
  { name: "admin-templates", path: "/admin/templates", user: ADMIN },
  { name: "case-identity", path: `${CASE}/identity` },
  { name: "case-rating", path: `${CASE}/rating` },
  { name: "case-submission", path: `${CASE}/submission` },
  { name: "readiness-console", path: "/docready" },
  { name: "memo-library", path: "/memos" },
  // Each screen as it is used: what opens on a click must fit a phone too.
  {
    name: "case-files-document-detail",
    path: `${CASE}/documents`,
    open: async (page) => page.getByTestId("document-toggle").first().click(),
  },
  {
    name: "case-completeness-item-open",
    path: `${CASE}/completeness`,
    open: async (page) => page.locator("[data-item] button").first().click(),
  },
  { name: "case-outputs-cam", path: `${CASE}/outputs?view=cam` },
  { name: "case-outputs-pd-note", path: `${CASE}/outputs?view=pd` },
  {
    name: "case-cross-verification-area",
    path: `${CASE}/cross-verification`,
    open: async (page) => showArea(page, "turnover"),
  },
  {
    name: "case-policy-balance-sheet",
    path: `${CASE}/policy`,
    open: async (page) =>
      page.getByRole("tab", { name: "Balance sheet", exact: true }).first().click(),
  },
  {
    name: "new-appraisal-proposed",
    path: "/appraisals/new",
    user: RM,
    open: async (page) => {
      await page.getByTestId("message-input").fill(MESSAGE);
      await page.getByRole("button", { name: "Read the message" }).click();
    },
  },
  {
    name: "review-deciding",
    path: "/review",
    open: async (page) => page.getByTestId("decide").first().click(),
  },
  {
    name: "overlay-menu",
    path: "/appraisals",
    open: async (page) =>
      page
        .getByRole("button", { name: /menu|navigation/i })
        .first()
        .click(),
  },
  {
    name: "overlay-document-viewer",
    path: `${CASE}/documents`,
    open: async (page) => page.getByTestId("document-type").first().click(),
  },
  {
    name: "overlay-assistant",
    path: CASE,
    open: async (page) =>
      page
        .getByRole("button", { name: /ask about this appraisal/i })
        .first()
        .click(),
  },
];

for (const s of SCREENS) {
  test(`fits a phone: ${s.name}`, async ({ page }) => {
    const api = new MockApi();
    if (s.user !== null) await signedIn(page, api, s.user ?? ANALYST);
    else await api.install(page);
    await page.goto(s.path);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(600);
    if (s.open) {
      // The menu button is a phone's; a tablet shows the side menu instead.
      if (s.name === "overlay-menu" && WIDTH >= 768) test.skip();
      await s.open(page);
      await page.waitForTimeout(600);
    }
    const found = await overflow(page);
    expect(await dialogsCut(page), "a dialog runs past the bottom of the screen").toEqual([]);
    if (SHOTS) {
      await unroll(page);
      await page.screenshot({ path: `${SHOTS}/${s.name}.png`, fullPage: true });
    }
    expect(found.offenders, JSON.stringify(found)).toEqual([]);
    expect(found.page).toBeLessThanOrEqual(0);
  });
}
