import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { FieldValue } from "@/api/types";
import { t, tOr } from "@/config/terminology";

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

const ACRONYMS = new Set([
  "cin",
  "pan",
  "gst",
  "gstin",
  "din",
  "roc",
  "itr",
  "gstr",
  "emi",
  "cc",
  "tl",
  "ebitda",
  "moa",
  "aoa",
  "kyc",
  "ocr",
  "npa",
  "dscr",
  "tnw",
  "od",
]);

/** One word of a field name as a person writes it: acronyms in capitals,
 * financial years as FY25, GSTR-3B style return names as GSTR-3B. */
function word(w: string): string {
  if (ACRONYMS.has(w)) return w.toUpperCase();
  if (/^fy\d+$/.test(w)) return w.toUpperCase();
  const ret = w.match(/^(gstr)(\d+[a-z]?)$/);
  if (ret) return `${ret[1]!.toUpperCase()}-${ret[2]!.toUpperCase()}`;
  return w;
}

function words(s: string): string {
  const out = s.split("_").map(word).join(" ");
  return out.charAt(0).toUpperCase() + out.slice(1);
}

/** A person-readable name for a dictionary field. An entry in the
 * terminology file (`fieldLabels.<field>`) wins; otherwise the field name is
 * spelled out: "turnover_fy25" -> "Turnover FY25"; a table cell
 * "gstr3b[2].outward_supplies" -> "GSTR-3B, row 3 · Outward supplies". */
export function fieldLabel(field: string): string {
  const named = tOr(`fieldLabels.${field}`, "");
  if (named) return named;
  const cell = field.match(/^(\w+)\[(\d+)\]\.(\w+)$/);
  if (cell) {
    const [, table = "", row = "0", column = ""] = cell;
    return t("data.cell", { table: words(table), row: Number(row) + 1, column: words(column) });
  }
  return words(field);
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
