import { t } from "@/config/terminology";

// The prototype's navigation, reduced to the PoC screens
// (docs/functional-requirements.md §6). Groups are gated per role by
// config/roles.yaml `navByRole`.

export type NavItem = { label: string; to: string; step?: "appraisal" | "docready" };
export type NavGroup = { id: string; group: string; items: NavItem[] };

/** Appraisal steps, in order; also the context strip's step pills. */
export const APPRAISAL_STEPS = [
  { to: "identity", key: "identity" },
  { to: "upload", key: "documents" },
  { to: "data", key: "data" },
  { to: "spread", key: "spread" },
  { to: "cross-verification", key: "crossVerification" },
  { to: "policy", key: "policy" },
  { to: "draft", key: "draft" },
  { to: "comparison", key: "comparison" },
] as const;

/** DocReady case tabs, in order. */
export const DOCREADY_TABS = [
  { to: "checklist", key: "checklist" },
  { to: "validation", key: "validation" },
  { to: "readiness", key: "readiness" },
  { to: "collection", key: "queries" },
] as const;

export function buildNav(): NavGroup[] {
  return [
    {
      id: "workbench",
      group: t("nav.group.workbench"),
      items: [
        { label: t("nav.home"), to: "/" },
        { label: t("nav.myAppraisals"), to: "/appraisals" },
      ],
    },
    {
      id: "docready",
      group: t("nav.group.docready"),
      items: [
        { label: t("nav.readinessConsole"), to: "/docready" },
        ...DOCREADY_TABS.map((tab) => ({
          label: t(`docreadyTab.${tab.key}`),
          to: tab.to,
          step: "docready" as const,
        })),
      ],
    },
    {
      id: "appraisal",
      group: t("nav.group.appraisal"),
      items: [
        { label: t("nav.newApplication"), to: "/appraisals/new" },
        ...APPRAISAL_STEPS.map((step) => ({
          label: t(`step.${step.key}`),
          to: step.to,
          step: "appraisal" as const,
        })),
      ],
    },
    {
      id: "governance",
      group: t("nav.group.governance"),
      items: [
        { label: t("nav.exceptionQueue"), to: "/exceptions" },
        { label: t("nav.scorecard"), to: "/scorecard" },
      ],
    },
  ];
}
