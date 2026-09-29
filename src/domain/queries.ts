import type { CaseDetail, QueryGroup, QueryItem } from "@/api/types";
import { t } from "@/config/terminology";

export const QUERY_GROUPS: QueryGroup[] = [
  "documents_needed",
  "documents_to_redo",
  "clarifications",
];

/** Items grouped (F-14.2); open items numbered continuously, resolved last. */
export function numbered(
  items: QueryItem[],
): { group: QueryGroup; items: { n: number; item: QueryItem }[] }[] {
  let n = 0;
  return QUERY_GROUPS.map((group) => ({
    group,
    items: items
      .filter((i) => i.group === group)
      .sort((a, b) => Number(a.resolved) - Number(b.resolved))
      .map((item) => ({ n: item.resolved ? 0 : ++n, item })),
  })).filter((g) => g.items.length > 0);
}

/** The list as plain text: open items only, grouped and numbered (F-14.3). */
export function queryListText(items: QueryItem[]): string {
  const lines: string[] = [];
  for (const g of numbered(items.filter((i) => !i.resolved))) {
    lines.push(t(`queryGroup.${g.group}`));
    for (const { n, item } of g.items) lines.push(`${n}. ${item.text}`);
    lines.push("");
  }
  return lines.join("\n").trim();
}

/** The list as an email for the RM to send; nothing is sent from the system. */
export function queryListEmail(c: Pick<CaseDetail, "borrower" | "id">, items: QueryItem[]): string {
  return [
    t("queries.email.subject", { borrower: c.borrower, id: c.id }),
    "",
    t("queries.email.opening"),
    "",
    t("queries.email.intro", { borrower: c.borrower }),
    "",
    queryListText(items),
    "",
    t("queries.email.closing"),
  ].join("\n");
}
