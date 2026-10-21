import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { Cam, CamTemplateCreate, Finding, FindingOutcome } from "@/api/types";

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

/** The spread, interim layout (F-22). */
export function useSpread(caseId: string) {
  return useQuery({ queryKey: ["cases", caseId, "spread"], queryFn: () => api.caseSpread(caseId) });
}

/** The draft CAM (F-23). */
export function useCam(caseId: string) {
  return useQuery({ queryKey: ["cases", caseId, "cam"], queryFn: () => api.caseCam(caseId) });
}

/** A change to the draft CAM's review (F-23): the memo as it now reads replaces the one on
 * screen; a data request also changes the query list. */
export function useCamChange<V>(caseId: string, send: (v: V) => Promise<Cam>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: send,
    onSuccess: (cam) => {
      client.setQueryData(["cases", caseId, "cam"], cam);
      void client.invalidateQueries({ queryKey: ["cases", caseId, "queries"] });
      void client.invalidateQueries({ queryKey: ["cases", caseId, "pd-note"] });
    },
  });
}

/** The CAM templates (FRD decision C.4-12). */
export function useCamTemplates() {
  return useQuery({ queryKey: ["cam-templates"], queryFn: () => api.camTemplates() });
}

/** Make a template; the list is read again. */
export function useCreateCamTemplate() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CamTemplateCreate) => api.createCamTemplate(body),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["cam-templates"] }),
  });
}

/** The copilot's redraft of a section, for a person to keep or discard. */
export function useCamRegenerate(caseId: string) {
  return useMutation({
    mutationFn: ({ sectionId, instruction }: { sectionId: string; instruction: string }) =>
      api.camRegenerate(caseId, sectionId, { instruction }),
  });
}

/** The PD question note (F-24). */
export function usePdNote(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "pd-note"],
    queryFn: () => api.casePdNote(caseId),
  });
}
