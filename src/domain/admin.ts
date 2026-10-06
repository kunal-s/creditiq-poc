import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { t, tOr } from "@/config/terminology";

export function useConfigVersions() {
  return useQuery({ queryKey: ["admin", "versions"], queryFn: api.configVersions });
}

export function useUsers() {
  return useQuery({ queryKey: ["admin", "users"], queryFn: api.users });
}

export function usePolicyConfig() {
  return useQuery({ queryKey: ["config", "policy"], queryFn: api.policyConfig });
}

export function useAudit(filters: { caseId?: string; actor?: string; action?: string }) {
  return useQuery({
    queryKey: ["admin", "audit", filters],
    queryFn: () => api.audit(filters),
  });
}

/** A published configuration section as a person names it. */
export function sectionLabel(key: string): string {
  return tOr(`admin.section.${key.replace(/\./g, "_")}`, key.replace(/[._]/g, " "));
}

/** A permission in plain words. */
export function permissionLabel(id: string): string {
  return tOr(`admin.permission.${id.replace(/\./g, "_")}`, id.replace(/[._]/g, " "));
}

/** An audit action in plain words. */
export function actionLabel(action: string): string {
  return tOr(`audit.action.${action.replace(/\./g, "_")}`, action.replace(/[._]/g, " "));
}

export function formatWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function requirementText(
  kind: "min" | "max" | null | undefined,
  threshold: number | null | undefined,
  unit: string | null | undefined,
): string {
  if (threshold === null || threshold === undefined || !kind) return t("admin.policy.byRule");
  const value = `${threshold.toLocaleString("en-IN")}${unit && unit !== "inr" && unit !== "count" ? ` ${tOr(`admin.unit.${unit}`, unit)}` : ""}`;
  return t(`admin.policy.${kind}`, { value });
}
