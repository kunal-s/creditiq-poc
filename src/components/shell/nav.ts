import type { SessionUser, StageKey } from "@/api/types";
import { t } from "@/config/terminology";

// Navigation (docs/functional-requirements.md §6). The side menu holds the
// screens outside a case, gated per role by config/roles.yaml `navByRole`
// and per item by permission. A case's tabs appear only inside the case.

export type NavItem = { label: string; to: string; permission?: string };
/** A group of the side menu; `gate` is the role's menu group it shows under (its own id when absent). */
export type NavGroup = { id: string; group: string; items: NavItem[]; gate?: string };

export type CaseTab = {
  /** Path under /appraisals/$caseId; "" is the Overview. */
  to: string;
  key: string;
  /** The processing stage this tab shows (FRD §5), numbered 1 to 6. */
  stage?: StageKey;
  permission: string;
};

/** The case workspace's tabs, in processing order (FRD §6). */
export const CASE_TABS: CaseTab[] = [
  { to: "", key: "overview", permission: "case.read" },
  { to: "identity", key: "identity", permission: "data.read" },
  { to: "documents", key: "documents", stage: "documents", permission: "case.read" },
  { to: "extraction", key: "extraction", stage: "extraction", permission: "data.read" },
  { to: "completeness", key: "completeness", stage: "completeness", permission: "checklist.read" },
  {
    to: "cross-verification",
    key: "crossVerification",
    stage: "cross_verification",
    permission: "finding.read",
  },
  { to: "policy", key: "policy", stage: "policy", permission: "finding.read" },
  { to: "outputs", key: "outputs", stage: "outputs", permission: "output.read" },
  { to: "rating", key: "rating", permission: "output.read" },
  { to: "submission", key: "submission", permission: "output.read" },
  { to: "comparison", key: "comparison", permission: "comparison.adjudicate" },
];

/** The case's steps as the tab strip shows them: the Overview, then three groups in the order a
 * case moves through them. Comparison stays reachable for the role that adjudicates it, after the
 * memo's steps. */
export const STEP_GROUPS: { id: "start" | "documents" | "assessment" | "memo"; keys: string[] }[] =
  [
    { id: "start", keys: ["overview"] },
    { id: "documents", keys: ["documents", "extraction", "identity", "completeness"] },
    { id: "assessment", keys: ["crossVerification", "policy"] },
    { id: "memo", keys: ["outputs", "rating", "submission", "comparison"] },
  ];

/** Every step in order, as one list. */
export const STEP_ORDER: CaseTab[] = STEP_GROUPS.flatMap((g) =>
  g.keys.map((k) => CASE_TABS.find((tab) => tab.key === k)!),
);

/** The step after this one in the case's order (Comparison is never "next"), if any. */
export function nextStepOf(key: string): CaseTab | undefined {
  const steps = STEP_ORDER.filter((tab) => tab.key !== "comparison");
  const i = steps.findIndex((tab) => tab.key === key);
  return i >= 0 ? steps[i + 1] : undefined;
}

/** The tab that shows a processing stage. */
export function tabForStage(stage: StageKey): CaseTab {
  return CASE_TABS.find((tab) => tab.stage === stage)!;
}

export type CaseFlow = {
  id: "ingestion" | "verification";
  /** Keys of the CASE_TABS entries shown as sub-tabs, in order. */
  tabs: string[];
};

/** The two processing flows; their tabs show as sub-tabs under one top-level tab. */
export const CASE_FLOWS: CaseFlow[] = [
  { id: "ingestion", tabs: ["documents", "extraction", "completeness"] },
  { id: "verification", tabs: ["crossVerification", "policy"] },
];

/** A top-level tab: a single case tab, or a flow standing for its sub-tabs. */
export type CaseTopTab =
  { kind: "tab"; tab: CaseTab } | { kind: "flow"; flow: CaseFlow; tabs: CaseTab[] };

/** The top-level tabs the permissions allow, in processing order. A flow
 *  appears at the position of its first tab and opens on its first allowed one. */
export function topTabs(permissions: string[]): CaseTopTab[] {
  const out: CaseTopTab[] = [];
  for (const tab of CASE_TABS) {
    if (!permissions.includes(tab.permission)) continue;
    const flow = CASE_FLOWS.find((f) => f.tabs.includes(tab.key));
    if (!flow) {
      out.push({ kind: "tab", tab });
    } else if (!out.some((o) => o.kind === "flow" && o.flow === flow)) {
      const tabs = flow.tabs
        .map((k) => CASE_TABS.find((x) => x.key === k)!)
        .filter((x) => permissions.includes(x.permission));
      out.push({ kind: "flow", flow, tabs });
    }
  }
  return out;
}

export function caseTabPath(caseId: string, tab: CaseTab): string {
  const base = `/appraisals/${encodeURIComponent(caseId)}`;
  return tab.to ? `${base}/${tab.to}` : base;
}

/** Where a user starts after signing in: the workbench, or for a role without one (the
 * Administrator), the Settings screen. */
export function homePath(user: Pick<SessionUser, "navGroups" | "permissions">): string {
  if (user.navGroups.includes("workbench")) return "/";
  return user.permissions.includes("config.read") ? "/admin/settings" : "/help";
}

export function buildNav(): NavGroup[] {
  return [
    {
      id: "workbench",
      group: t("nav.group.workbench"),
      items: [
        { label: t("nav.home"), to: "/" },
        { label: t("nav.myAppraisals"), to: "/appraisals", permission: "case.read" },
      ],
    },
    {
      id: "docready",
      gate: "workbench",
      group: t("nav.group.docready"),
      items: [{ label: t("nav.readinessConsole"), to: "/docready", permission: "checklist.read" }],
    },
    {
      // The open appraisal's steps follow New appraisal (AppShell).
      id: "appraisal",
      gate: "workbench",
      group: t("nav.group.appraisal"),
      items: [{ label: t("nav.newCase"), to: "/appraisals/new", permission: "case.create" }],
    },
    {
      id: "portfolio",
      gate: "workbench",
      group: t("nav.group.portfolio"),
      items: [{ label: t("nav.memoLibrary"), to: "/memos", permission: "output.read" }],
    },
    {
      id: "governance",
      group: t("nav.group.governance"),
      items: [
        { label: t("nav.reviewQueue"), to: "/review", permission: "review.read" },
        { label: t("nav.scorecard"), to: "/scorecard", permission: "scorecard.read" },
        { label: t("nav.audit"), to: "/audit", permission: "audit.read" },
      ],
    },
    {
      id: "administration",
      group: t("nav.group.administration"),
      items: [
        { label: t("nav.admin.configuration"), to: "/admin", permission: "config.read" },
        { label: t("nav.admin.settings"), to: "/admin/settings", permission: "config.read" },
        { label: t("nav.admin.policy"), to: "/admin/policy", permission: "config.read" },
        { label: t("nav.admin.checklist"), to: "/admin/checklist", permission: "config.read" },
        {
          label: t("nav.admin.documentTypes"),
          to: "/admin/document-types",
          permission: "config.read",
        },
        {
          label: t("nav.admin.templates"),
          to: "/admin/templates",
          permission: "config.read",
        },
        { label: t("nav.admin.users"), to: "/admin/users", permission: "config.read" },
      ],
    },
    {
      id: "help",
      group: t("nav.group.help"),
      items: [{ label: t("nav.help"), to: "/help" }],
    },
  ];
}
