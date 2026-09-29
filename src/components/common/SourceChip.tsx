import { FileText } from "lucide-react";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";

/** A provenance tag: "message:<start>-<end>", "document:<id>:p<n>" or "person" (F-01.2, F-10.2). */
export function SourceChip({
  caseId,
  source,
}: {
  caseId: string;
  source: string | null | undefined;
}) {
  const viewer = useDocViewer();
  if (!source) return null;
  const doc = source.match(/^document:([^:]+):p(\d+)$/);
  if (doc) {
    const [, documentId = "", page = "1"] = doc;
    return (
      <button
        type="button"
        onClick={() => viewer.open({ caseId, documentId, page: Number(page) })}
        className="inline-flex items-center gap-1 rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10.5px] font-medium text-primary hover:bg-muted"
        data-testid="source-document"
      >
        <FileText className="h-3 w-3" /> {t("source.document", { page })}
      </button>
    );
  }
  const label = source.startsWith("message")
    ? t("source.message")
    : source === "person"
      ? t("source.person")
      : source === "bureau"
        ? t("source.bureau")
        : source.replace(/[_:]/g, " ");
  return (
    <span className="inline-flex items-center rounded border border-border bg-surface-muted px-1.5 py-0.5 text-[10.5px] text-muted-foreground">
      {label}
    </span>
  );
}
