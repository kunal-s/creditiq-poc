import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api } from "@/api/client";
import type { CaseCreate, ProposalRequest, Stage } from "@/api/types";
import { t } from "@/config/terminology";

export function useCases() {
  return useQuery({ queryKey: ["cases"], queryFn: api.listCases });
}

export function useCase(id: string | undefined) {
  return useQuery({
    queryKey: ["cases", id],
    queryFn: () => api.getCase(id as string),
    enabled: Boolean(id),
    retry: false,
  });
}

export function useMeta() {
  return useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
}

/** F-04: parse a pasted message into a proposed case. Stores nothing. */
export function useProposeCase() {
  return useMutation({ mutationFn: (body: ProposalRequest) => api.proposeCase(body) });
}

/** F-04.7: create the case once the RM has confirmed it. */
export function useCreateCase() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CaseCreate) => api.createCase(body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["cases"] }),
  });
}

/** Labels for configured ids (constitutions, facilities, channels) from /api/meta. */
export function useLabels() {
  const { data: meta } = useMeta();
  const find = (list: { id: string; label: string }[] | undefined, id: string) =>
    list?.find((o) => o.id === id)?.label ?? id.replace(/_/g, " ");
  const constitution = useCallback(
    (id: string) => (id === "unknown" ? t("term.notConfirmed") : find(meta?.constitutions, id)),
    [meta],
  );
  const facility = useCallback((id: string) => find(meta?.facilities, id), [meta]);
  const facilities = useCallback((ids: string[]) => ids.map(facility).join(", "), [facility]);
  const channel = useCallback((id: string) => find(meta?.channels, id), [meta]);
  return { constitution, facility, facilities, channel };
}

export function stageLabel(stage: Stage): string {
  return t(`stage.${stage.toLowerCase()}`);
}

/** Where a case's stage is worked on. */
export function stageRoute(stage: Stage): { to: string; docready: boolean } {
  if (stage === "Intake") return { to: "upload", docready: false };
  if (stage === "Readiness") return { to: "checklist", docready: true };
  return { to: "data", docready: false };
}

/** INR amount in the Indian convention: crore above 1 crore, lakh above 1 lakh. */
export function formatInr(amount: number): string {
  if (amount >= 1e7) return `INR ${(amount / 1e7).toFixed(2)} cr`;
  if (amount >= 1e5) return `INR ${(amount / 1e5).toFixed(2)} lakh`;
  return `INR ${amount.toLocaleString("en-IN")}`;
}

/** A date-time from the engine, shown as a date. */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}
