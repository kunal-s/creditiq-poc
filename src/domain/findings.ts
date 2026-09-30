import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Finding, FindingOutcome } from "@/api/types";

/** The case's cross-check outcomes (F-19), fails first. */
export function useFindings(caseId: string, enabled = true) {
  return useQuery({
    queryKey: ["cases", caseId, "findings"],
    queryFn: () => api.caseFindings(caseId),
    enabled,
  });
}

/** The aligned facts behind the checks (F-18). */
export function useFacts(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "facts"],
    queryFn: () => api.caseFacts(caseId),
  });
}

export const OUTCOMES: FindingOutcome[] = ["fail", "incomplete", "pass", "not_applicable"];

export function countOutcomes(findings: Finding[]): Record<FindingOutcome, number> {
  const counts: Record<FindingOutcome, number> = {
    fail: 0,
    incomplete: 0,
    pass: 0,
    not_applicable: 0,
  };
  for (const f of findings) counts[f.outcome] += 1;
  return counts;
}

/** Every policy norm for the case, with its outcome (F-20). */
export function usePolicy(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "policy"],
    queryFn: () => api.casePolicy(caseId),
  });
}

/** The spread, interim layout (F-22). */
export function useSpread(caseId: string) {
  return useQuery({ queryKey: ["cases", caseId, "spread"], queryFn: () => api.caseSpread(caseId) });
}

/** The draft CAM (F-23). */
export function useCam(caseId: string) {
  return useQuery({ queryKey: ["cases", caseId, "cam"], queryFn: () => api.caseCam(caseId) });
}

/** The PD question note (F-24). */
export function usePdNote(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "pd-note"],
    queryFn: () => api.casePdNote(caseId),
  });
}
