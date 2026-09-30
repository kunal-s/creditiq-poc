import type { FieldValue } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t, tOr } from "@/config/terminology";
import { effectiveValue, formatValue } from "@/domain/extraction";
import { cn } from "@/lib/utils";

/** An extracted value; one click opens its source page (F-16.1). A correction
 * shows both values (F-17.5). */
export function FieldValueButton({ caseId, field }: { caseId: string; field: FieldValue }) {
  const viewer = useDocViewer();
  const corrected = field.corrected_value !== null && field.corrected_value !== undefined;
  if (field.status === "missing") {
    return (
      <span className="text-[12px] text-muted-foreground">
        {t("fieldStatus.missing")}
        {field.missing_reason &&
          `: ${tOr(`missingReason.${field.missing_reason}`, field.missing_reason)}`}
      </span>
    );
  }
  return (
    <button
      type="button"
      data-testid="field-value"
      data-field={field.field}
      onClick={() =>
        viewer.open({
          caseId,
          documentId: field.evidence?.document_id ?? field.document_id,
          ...(field.evidence
            ? { page: field.evidence.page, bbox: field.evidence.bbox ?? null }
            : {}),
          field,
        })
      }
      className={cn(
        "tabular min-w-0 break-words text-left text-[12.5px] font-medium text-foreground underline decoration-border decoration-dotted underline-offset-2 hover:text-primary hover:decoration-primary",
      )}
      title={t("data.openEvidence")}
    >
      {formatValue(effectiveValue(field))}
      {corrected && (
        <span
          className="ml-1.5 text-[11px] font-normal text-muted-foreground line-through"
          data-testid="system-value"
        >
          {formatValue(field.value)}
        </span>
      )}
    </button>
  );
}
