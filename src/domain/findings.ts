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
