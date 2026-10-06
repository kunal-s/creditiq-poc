import type { StageKey } from "@/api/types";
import { t } from "@/config/terminology";

// Navigation (docs/functional-requirements.md §6). The side menu holds the
// screens outside a case, gated per role by config/roles.yaml `navByRole`
// and per item by permission. A case's tabs appear only inside the case.

export type NavItem = { label: string; to: string; permission?: string };
export type NavGroup = { id: string; group: string; items: NavItem[] };

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
  { to: "comparison", key: "comparison", permission: "comparison.adjudicate" },
];

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

export function buildNav(): NavGroup[] {
  return [
    {
      id: "workbench",
      group: t("nav.group.workbench"),
      items: [
        { label: t("nav.cases"), to: "/" },
        { label: t("nav.newCase"), to: "/appraisals/new", permission: "case.create" },
      ],
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
        { label: t("nav.admin.policy"), to: "/admin/policy", permission: "config.read" },
        { label: t("nav.admin.checklist"), to: "/admin/checklist", permission: "config.read" },
        {
          label: t("nav.admin.documentTypes"),
          to: "/admin/document-types",
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
