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
      ],
    },
  ];
}
