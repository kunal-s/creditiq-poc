import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { FieldValue } from "@/api/types";
import { t } from "@/config/terminology";

export function useFields(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "fields"],
    queryFn: () => api.caseFields(caseId),
  });
}

export function useParties(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "parties"],
    queryFn: () => api.caseParties(caseId),
  });
}

/** Dictionary field names as labels: "turnover_fy25" -> "Turnover fy25";
 * table cells "gstr3b[2].outward_supplies" -> "Gstr3b 3 · outward supplies". */
export function fieldLabel(field: string): string {
  const cell = field.match(/^(\w+)\[(\d+)\]\.(\w+)$/);
  const words = (s: string) => s.replace(/_/g, " ");
  if (cell) {
    const [, table = "", row = "0", column = ""] = cell;
    return `${capitalise(words(table))} ${Number(row) + 1} · ${words(column)}`;
  }
  return capitalise(words(field));
}

function capitalise(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function formatValue(value: FieldValue["value"]): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return value.toLocaleString("en-IN");
  if (typeof value === "boolean") return value ? t("term.yes") : t("term.no");
  return value;
}

/** The value in force: a person's correction wins, the system value is kept. */
export function effectiveValue(f: FieldValue): FieldValue["value"] {
  return f.corrected_value ?? f.value;
}

export function confidencePct(c: number | null | undefined): string {
  return typeof c === "number" ? `${Math.round(c * 100)}%` : "—";
}
