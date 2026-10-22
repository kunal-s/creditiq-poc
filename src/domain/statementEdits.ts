import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/api/client";
import type { StatementEditRequest } from "@/api/types";

/** An edit changes the statement lines every figure is worked from, so everything the case shows is read again. */
function useAfterEdit(caseId: string) {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: ["cases", caseId] });
    void client.invalidateQueries({ queryKey: ["review"] });
  };
}

export function useEditStatementLine(caseId: string) {
  const after = useAfterEdit(caseId);
  return useMutation({
    mutationFn: (body: StatementEditRequest) => api.editStatementLine(caseId, body),
    onSuccess: after,
  });
}

export function useRevertStatementEdit(caseId: string) {
  const after = useAfterEdit(caseId);
  return useMutation({
    mutationFn: ({ edit, reason }: { edit: string; reason: string }) =>
      api.revertStatementEdit(caseId, edit, reason),
    onSuccess: after,
  });
}

/** An amount in the statement's own unit, as the statement prints it. */
export function printedAmount(value: number): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

/** The amount in whole rupees, Indian grouping. */
export function inRupees(value: number): string {
  return Math.round(value).toLocaleString("en-IN");
}
