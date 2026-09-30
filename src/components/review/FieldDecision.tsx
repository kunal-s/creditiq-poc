import type { FieldValue, ReviewItem } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useConfirmField, useFieldItem } from "@/domain/review";
import { useCan } from "@/domain/session";
import { decisionButton } from "./styles";

// Confirm or correct an extracted value where it is read (FRD §6, F-17.5):
// on its row, and beside its source page in the evidence viewer. A correction
// is always made with the page in view, so the row's Correct opens the viewer.

/** On a field's row: confirm in one click, or correct beside the evidence. */
export function FieldRowDecision({ field }: { field: FieldValue }) {
  const item = useFieldItem(field);
  const canDecide = useCan("review.decide");
  const viewer = useDocViewer();
  if (!item || !canDecide) return null;
  return <RowButtons item={item} field={field} onCorrect={() => openEvidence(viewer, field)} />;
}

function RowButtons({
  item,
  field,
  onCorrect,
}: {
  item: ReviewItem;
  field: FieldValue;
  onCorrect: () => void;
}) {
  const { confirm, pending } = useConfirmField(item);
  return (
    <span
      className="mt-1 flex flex-wrap gap-1"
      data-testid="field-decision"
      data-field={field.field}
    >
      <button
        type="button"
        disabled={pending}
        onClick={confirm}
        className={`${decisionButton} border-positive/40 bg-surface text-positive hover:bg-positive-soft`}
        data-testid="field-confirm"
      >
        {t("fieldDecision.confirm")}
      </button>
      <button
        type="button"
        onClick={onCorrect}
        className={`${decisionButton} border-border bg-surface text-foreground hover:bg-muted`}
        data-testid="field-correct"
      >
        {t("fieldDecision.correct")}
      </button>
    </span>
  );
}

function openEvidence(viewer: ReturnType<typeof useDocViewer>, field: FieldValue) {
  viewer.open({
    caseId: field.case_id,
    documentId: field.evidence?.document_id ?? field.document_id,
    ...(field.evidence ? { page: field.evidence.page, bbox: field.evidence.bbox ?? null } : {}),
    field,
    correct: true,
  });
}
