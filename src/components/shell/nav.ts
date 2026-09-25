import { t } from "@/config/terminology";

export type NavItem = { label: string; to: string; step?: boolean };
export type NavGroup = { id: string; group: string; items: NavItem[] };

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
      id: "intake",
      group: t("nav.group.intake"),
      items: [{ label: t("nav.readinessConsole"), to: "/docready" }],
    },
    {
      id: "appraisal",
      group: t("nav.group.appraisal"),
      items: [
        { label: t("nav.newApplication"), to: "/applications/new" },
        { label: t("stage.identity"), to: "identity", step: true },
        { label: t("stage.data"), to: "data", step: true },
        { label: t("stage.spread"), to: "spread", step: true },
        { label: t("stage.crossVerification"), to: "cross-verification", step: true },
        { label: t("stage.draft"), to: "draft", step: true },
        { label: t("stage.rating"), to: "rating", step: true },
        { label: t("stage.submission"), to: "submission", step: true },
      ],
    },
    {
      id: "portfolio",
      group: t("nav.group.portfolio"),
      items: [{ label: t("nav.memoLibrary"), to: "/memos" }],
    },
    {
      id: "governance",
      group: t("nav.group.governance"),
      items: [
        { label: t("nav.exceptionQueue"), to: "/exceptions" },
        { label: t("nav.auditLedger"), to: "/audit" },
      ],
    },
    {
      id: "admin",
      group: t("nav.group.admin"),
      items: [
        { label: t("nav.templateDesigner"), to: "/admin/templates" },
        { label: t("nav.policyConfigurator"), to: "/admin/policy" },
        { label: t("nav.connectorSettings"), to: "/admin/connectors" },
        { label: t("nav.usersAndRoles"), to: "/admin/users" },
      ],
    },
  ];
}
