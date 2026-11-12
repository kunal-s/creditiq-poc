import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/api/client";
import type { FieldValue, ReviewItem } from "@/api/types";
import { t } from "@/config/terminology";
import { save } from "./outputs";
import { useReviewQueue } from "./review";
import { useCan } from "./session";

// A figure a person changes on Extracted data (engine/figure_edits.py): the maker (manual.make)
// proposes the new value with a reason and, optionally, the paper it rests on; it waits on a
// manual-entry review item until a checker (manual.check, never the maker) approves it or sends it
// back. Nothing reads the new figure until it is approved.

/** The engine's shortest reason for a change (engine/figure_edits.py REASON_MIN). */
export const CHANGE_REASON_MIN = 10;

/** The kinds of paper a change may rest on, as the engine accepts them. */
export const ATTACHMENT_ACCEPT = ".pdf,.png,.jpg,.jpeg,.xlsx,.docx";

/** A changed figure waiting for its check. */
export type PendingChange = ReviewItem & { edit: NonNullable<ReviewItem["edit"]> };

function isPendingChange(i: ReviewItem): i is PendingChange {
  return i.status === "open" && i.kind === "manual_entry" && !!i.edit;
}

/** The case's changes still waiting for a check, by field id. */
export function usePendingChanges(caseId: string): Map<string, PendingChange> {
  const canRead = useCan("review.read");
  const queue = useReviewQueue({ caseId });
  const byField = new Map<string, PendingChange>();
  if (!canRead) return byField;
  for (const i of queue.data ?? []) {
    if (isPendingChange(i)) byField.set(i.edit.field_value_id, i);
  }
  return byField;
}

/** The change to this figure still waiting for a check, if the user may see it. */
export function usePendingChange(field: FieldValue): PendingChange | undefined {
  return usePendingChanges(field.case_id).get(field.id);
}

/** Propose a new figure; the queue and the case refresh so the change shows where it was made. */
export function useChangeFigure(field: FieldValue) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { value: string; reason: string; file: File | null }) =>
      api.editField(field.case_id, field.id, body),
    onSuccess: () => {
      toast.success(t("figureEdit.sent"));
      void client.invalidateQueries({ queryKey: ["review"] });
      void client.invalidateQueries({ queryKey: ["cases", field.case_id] });
    },
  });
}

/** Save the paper a change rests on, under the name it was attached with. */
export async function saveAttachment(item: PendingChange) {
  try {
    const file = await api.editAttachment(item.id);
    save(file.blob, item.edit.attachment?.name ?? file.filename ?? "attachment");
  } catch (error) {
    toast.error(error instanceof Error ? error.message : String(error));
  }
}
