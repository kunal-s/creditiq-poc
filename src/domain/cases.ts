import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api, ApiError } from "@/api/client";
import type {
  CaseCreate,
  ChecklistPreviewRequest,
  IntakeCreated,
  ProposalRequest,
  Stage,
  StageKey,
} from "@/api/types";
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

/** What the proposed application will need (F-12), refreshed as its values change. */
export function useChecklistPreview(body: ChecklistPreviewRequest | null) {
  return useQuery({
    queryKey: ["checklist-preview", body],
    queryFn: () => api.checklistPreview(body!),
    enabled: body !== null,
    placeholderData: (previous) => previous,
    staleTime: 60_000,
  });
}

/** F-04: parse a pasted message into a proposed case. Stores nothing. */
export function useProposeCase() {
  return useMutation({ mutationFn: (body: ProposalRequest) => api.proposeCase(body) });
}

/** The review of a new application as it stands (F-04.5, F-04.6): the engine's duplicate check
 * and identifier checks for the values on screen, with or without a message. Stores nothing;
 * refreshed as the values change (the caller debounces the request). */
export function useIntakeReview(body: ProposalRequest | null) {
  return useQuery({
    queryKey: ["intake-review", body],
    queryFn: () => api.proposeCase(body!),
    enabled: body !== null,
    placeholderData: (previous) => previous,
    staleTime: 30_000,
    retry: false,
  });
}

/** F-13: create the case, opening cross-verification, the policy checks and the outputs.
 * Everything shown for the case is stale afterwards, so the whole case is refreshed. */
export function useOpenAssessment(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    /** With a reason, the case is created with conditions not met and the reason is recorded (F-04.10). */
    mutationFn: (reason?: string) => api.openAssessment(caseId, reason),
    onSuccess: () =>
      client.invalidateQueries({
        predicate: (q) =>
          q.queryKey[0] === "cases" && (q.queryKey.length === 1 || q.queryKey[1] === caseId),
      }),
  });
}

/** F-04.7: create the case once the RM has confirmed it. */
export function useCreateCase() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: CaseCreate) => api.createCase(body),
    onSuccess: () => client.invalidateQueries({ queryKey: ["cases"] }),
  });
}

/** F-04.7: create the case with its files in one request (POST /api/cases/intake). Nothing is
 * created when it fails, so the files stay on screen to try again. */
export function useCreateCaseWithFiles() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: async ({
      body,
      files,
    }: {
      body: CaseCreate;
      files: File[];
    }): Promise<IntakeCreated & { uploadFailed?: boolean }> => {
      try {
        return await api.createCaseWithFiles(body, files);
      } catch (error) {
        // An engine without the one-request create: the case, then its files, as before.
        if (!(error instanceof ApiError) || (error.status !== 404 && error.status !== 405))
          throw error;
        const created = await api.createCase(body);
        try {
          return { case: created, upload: await api.uploadFiles(created.id, files) };
        } catch {
          // The case exists: never offer a retry that would create it twice.
          return { case: created, upload: { files: [], job_id: null }, uploadFailed: true };
        }
      }
    },
    onSuccess: (created) => {
      client.setQueryData(["cases", created.case.id], created.case);
      void client.invalidateQueries({ queryKey: ["cases"], exact: true });
    },
  });
}

/** F-01.5: delete a case and everything it owns (a log record remains). */
export function useDeleteCase() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => api.deleteCase(id, reason),
    onSuccess: (_data, { id }) => {
      client.removeQueries({ queryKey: ["cases", id] });
      void client.invalidateQueries({ queryKey: ["cases"] });
      void client.invalidateQueries({ queryKey: ["review"] });
    },
  });
}

type OptionList = { id: string; label: string }[] | undefined;

/** A case field's label (T2.1). A case created before the field was recorded has none
 * ("Not recorded"); "unknown" is "Not yet confirmed". */
function recorded(list: OptionList, id: string | null | undefined): string {
  if (!id) return t("term.notRecorded");
  if (id === "unknown") return t("term.notConfirmed");
  return list?.find((o) => o.id === id)?.label ?? id.replace(/_/g, " ");
}

/** Labels for configured ids (constitutions, facilities, channels, case fields) from /api/meta. */
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
  const product = useCallback((id?: string | null) => recorded(meta?.products, id), [meta]);
  const caseType = useCallback((id?: string | null) => recorded(meta?.case_types, id), [meta]);
  const branch = useCallback((id?: string | null) => recorded(meta?.branches, id), [meta]);
  const bankStage = useCallback((id?: string | null) => recorded(meta?.bank_stages, id), [meta]);
  // Product and case type in one line; a case from before case types were recorded shows its
  // product only.
  const caseKind = useCallback(
    (c: { product?: string | null; case_type?: string | null }) =>
      c.case_type ? `${product(c.product)} · ${caseType(c.case_type)}` : product(c.product),
    [product, caseType],
  );
  // A customer type's label (salaried, self-employed, ...), from the product that offers it.
  const customerType = useCallback(
    (id: string) =>
      find(
        meta?.products?.flatMap((p) => p.customer_types ?? []),
        id,
      ),
    [meta],
  );
  // Who the borrower is, in the product's own terms: a loan against property's customer type
  // when the case was opened with one, otherwise the constitution (business banking).
  const borrowerKind = useCallback(
    (c: { constitution: string; customer_type?: string | null }) =>
      c.customer_type ? customerType(c.customer_type) : constitution(c.constitution),
    [customerType, constitution],
  );
  return {
    constitution,
    customerType,
    borrowerKind,
    facility,
    facilities,
    channel,
    product,
    caseType,
    caseKind,
    branch,
    bankStage,
  };
}

export function stageLabel(stage: Stage): string {
  return t(`stage.${stage.toLowerCase()}`);
}

/** The processing stage a case stage names; none for Intake and Completed. */
export function stageKey(stage: Stage): StageKey | undefined {
  const keys: Partial<Record<Stage, StageKey>> = {
    Documents: "documents",
    Extraction: "extraction",
    Completeness: "completeness",
    CrossVerification: "cross_verification",
    Policy: "policy",
    Outputs: "outputs",
  };
  return keys[stage];
}

/** INR amount in the Indian convention: crore above 1 crore, lakh above 1 lakh.
 * A negative amount (a net loss, negative net worth) keeps its sign. */
export function formatInr(amount: number): string {
  const size = Math.abs(amount);
  if (size >= 1e7) return `INR ${(amount / 1e7).toFixed(2)} cr`;
  if (size >= 1e5) return `INR ${(amount / 1e5).toFixed(2)} lakh`;
  return `INR ${amount.toLocaleString("en-IN")}`;
}

/** A date-time from the engine, shown as a date. */
export function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}
