import { t } from "@/config/terminology";

export type NavItem = { label: string; to: string };
export type NavGroup = { id: string; group: string; items: NavItem[] };

// Groups are gated per role by config/roles.yaml `navByRole`. Screens are
// added here as their features land (docs/functional-requirements.md §6).
export function buildNav(): NavGroup[] {
  return [
    {
      id: "workbench",
      group: t("nav.group.workbench"),
      items: [{ label: t("nav.home"), to: "/" }],
    },
  ];
}
