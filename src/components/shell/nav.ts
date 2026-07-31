export type NavItem = { label: string; to: string; step?: boolean };
export type NavGroup = { group: string; items: NavItem[] };

export const NAV: NavGroup[] = [
  {
    group: "Workbench",
    items: [
      { label: "Home", to: "/" },
      { label: "My Appraisals", to: "/appraisals" },
    ],
  },
  {
    group: "Appraisal",
    items: [
      { label: "New Appraisal", to: "/appraisals/new" },
      { label: "Identity", to: "identity", step: true },
      { label: "Data", to: "data", step: true },
      { label: "Spread", to: "spread", step: true },
      { label: "Cross-Verification", to: "cross-verification", step: true },
      { label: "Draft and Review", to: "draft", step: true },
      { label: "Submission", to: "submission", step: true },
    ],
  },
  {
    group: "Portfolio",
    items: [{ label: "Memo Library", to: "/memos" }],
  },
  {
    group: "Governance",
    items: [{ label: "Audit and Examiner Walk-through", to: "/audit" }],
  },
  {
    group: "Admin",
    items: [
      { label: "Template Designer", to: "/admin/templates" },
      { label: "Ratio and Policy", to: "/admin/policy" },
      { label: "Connectors and Consent", to: "/admin/connectors" },
      { label: "Users and Roles", to: "/admin/users" },
    ],
  },
];