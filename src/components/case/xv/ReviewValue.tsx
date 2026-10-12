import { Eye } from "lucide-react";
import type { Evidence } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useFields } from "@/domain/extraction";

/** A value the check waits on until a person reviews it (F-17.2): opens it at its page, where
 * a reviewer confirms or corrects it. */
export function ReviewValue({
  caseId,
  fieldIds,
  evidence,
}: {
  caseId: string;
  fieldIds: string[];
  evidence: Evidence | undefined;
}) {
  const viewer = useDocViewer();
  const fields = useFields(caseId);
  const field = fields.data?.find((f) => fieldIds.includes(f.id));
  const page = evidence ?? field?.evidence ?? undefined;
  const documentId = field?.document_id ?? page?.document_id;
  return (
    <button
      type="button"
      disabled={!documentId}
      onClick={() =>
        documentId &&
        viewer.open({
          caseId,
          documentId,
          ...(page ? { page: page.page, bbox: page.bbox ?? null } : {}),
          ...(field ? { field } : {}),
        })
      }
      title={t("crossVerification.column.reviewHint")}
      className="inline-flex items-center gap-1 rounded border border-flag/35 bg-flag-soft px-1.5 py-0.5 text-[10.5px] font-medium text-flag-foreground hover:bg-flag/20 disabled:cursor-default disabled:hover:bg-flag-soft"
      data-testid="xv-awaiting-review"
    >
      <Eye className="h-3 w-3" aria-hidden /> {t("crossVerification.column.awaitingReview")}
    </button>
  );
}
