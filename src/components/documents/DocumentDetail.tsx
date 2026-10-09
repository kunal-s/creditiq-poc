import { Link } from "@tanstack/react-router";
import { FileText } from "lucide-react";
import type { ChecklistItemState, FileRecord, LogicalDocument } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t, tOr } from "@/config/terminology";
import { useDocumentTypes } from "@/domain/documents";
import {
  confidencePct,
  effectiveValue,
  fieldLabel,
  formatValue,
  groupFields,
  useFields,
} from "@/domain/extraction";
import { GradeChip } from "./chips";

/** Values shown on the document itself; the rest are one click away. */
const KEY_VALUES = 6;

/** What was found on one document: its type, how readable it is, any flag
 * and any defect the checklist found (F-07 to F-10, F-13). Opened from its
 * register row. */
export function DocumentDetail({
  caseId,
  doc,
  file,
  defects,
}: {
  caseId: string;
  doc: LogicalDocument;
  file: FileRecord | undefined;
  defects: ChecklistItemState[];
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const c = doc.classification;
  const classified = (c?.types.length ?? 0) > 0;
  const hard = doc.pages.filter((p) => p.grade === "C").length;
  const unreadable = doc.pages.filter((p) => p.grade === "U").length;
  const total = doc.pages.length;
  const readability =
    unreadable > 0
      ? t("validation.unreadable", { n: unreadable, total })
      : hard > 0
        ? t("validation.hardToRead", { n: hard, total })
        : total === 1
          ? t("validation.pageClear")
          : t("validation.pagesClear", { n: total });
  const problems = hard + unreadable > 0;

  // What was read from this document: values with a value, in the order they were extracted.
  const fields = useFields(caseId);
  const mine = (fields.data ?? []).filter((f) => f.document_id === doc.id);
  const read = groupFields(mine).plain.filter((f) => effectiveValue(f) != null);
  const scores = read.map((f) => f.confidence).filter((x): x is number => typeof x === "number");
  const average = scores.length ? scores.reduce((a, b) => a + b, 0) / scores.length : null;

  return (
    <div className="space-y-3 border-t border-border bg-surface-muted/40 px-4 py-3">
      <dl className="grid gap-x-6 gap-y-1 text-[12.5px] sm:grid-cols-2" data-testid="doc-summary">
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-muted-foreground">{t("validation.documentType")}</dt>
          <dd className="min-w-0 text-foreground">
            {classified ? c!.types.map(types.name).join(" + ") : t("document.unclassified")}
            {classified && c && (
              <span className="text-muted-foreground">
                {" "}
                · {confidencePct(c.confidence)} · {tOr(`exitTier.${c.exit_tier}`, c.exit_tier)}
              </span>
            )}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-28 shrink-0 text-muted-foreground">{t("validation.readability")}</dt>
          <dd className="min-w-0 text-foreground" data-testid="readability">
            {readability}
          </dd>
        </div>
        {read.length > 0 && (
          <div className="flex gap-2">
            <dt className="w-28 shrink-0 text-muted-foreground">{t("validation.valuesRead")}</dt>
            <dd className="min-w-0 text-foreground" data-testid="values-read">
              {t("validation.valuesSummary", { n: read.length, pct: confidencePct(average) })}
            </dd>
          </div>
        )}
      </dl>
      <div className="space-y-2 text-[12px]">
        {doc.label_mismatch && (
          <p className="rounded border border-flag/35 bg-flag-soft px-3 py-2 text-flag-foreground">
            {t("validation.labelMismatchDetail", {
              label: file?.label_hint ?? file?.original_name ?? "",
              type: classified ? c!.types.map(types.name).join(" + ") : t("document.unclassified"),
            })}
          </p>
        )}
        {!classified && (
          <p className="rounded border border-flag/35 bg-flag-soft px-3 py-2 text-flag-foreground">
            {t("validation.unclassifiedDetail")}{" "}
            <Link to="/review" className="font-medium underline">
              {t("nav.reviewQueue")}
            </Link>
          </p>
        )}
      </div>
      {read.length > 0 && (
        <div data-testid="key-values">
          <p className="field-label">{t("validation.keyValues")}</p>
          <dl className="mt-1 grid gap-x-6 gap-y-1 text-[12.5px] sm:grid-cols-2">
            {read.slice(0, KEY_VALUES).map((f) => (
              <div key={f.id} className="flex gap-2">
                <dt className="w-28 shrink-0 text-muted-foreground">{fieldLabel(f.field)}</dt>
                <dd className="min-w-0 break-words text-foreground">
                  {formatValue(effectiveValue(f))}
                </dd>
              </div>
            ))}
          </dl>
          {read.length > KEY_VALUES && (
            <Link
              to="/appraisals/$caseId/extraction"
              params={{ caseId }}
              hash="fields"
              className="mt-1 inline-block text-[11.5px] font-medium text-primary hover:underline"
            >
              {t("validation.moreValues", { n: read.length - KEY_VALUES })} →
            </Link>
          )}
        </div>
      )}
      {defects.length > 0 && (
        <div>
          <p className="field-label">{t("validation.defects")}</p>
          <ul className="mt-1 space-y-1">
            {defects.map((d) => (
              <li
                key={d.item_id}
                className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive"
                data-testid="defect"
              >
                <span className="font-medium">{d.name}</span> — {d.deficiency}
              </li>
            ))}
          </ul>
        </div>
      )}

      {problems && (
        <div className="min-w-0" data-testid="doc-details">
          <p className="field-label">{t("validation.pages")}</p>
          <table className="mt-1 w-full text-[12px]">
            <thead>
              <tr className="text-left text-[10.5px] uppercase tracking-wide text-muted-foreground">
                <th className="py-1 pr-2 font-medium">{t("validation.page")}</th>
                <th className="py-1 pr-2 font-medium">{t("validation.grade")}</th>
                <th className="py-1 font-medium">{t("validation.reasons")}</th>
              </tr>
            </thead>
            <tbody>
              {doc.pages.map((p) => (
                <tr key={p.n} className="border-t border-border align-top">
                  <td className="tabular py-1 pr-2">
                    <button
                      type="button"
                      className="text-primary hover:underline"
                      onClick={() => viewer.open({ caseId, documentId: doc.id, page: p.n })}
                    >
                      {p.n}
                    </button>
                  </td>
                  <td className="py-1 pr-2">
                    <GradeChip grade={p.grade} />
                  </td>
                  <td className="py-1 text-muted-foreground" data-testid="page-reasons">
                    {(p.reasons ?? []).map((r) => tOr(`gradeReason.${r}`, r)).join(", ") || "—"}
                    {typeof p.ocr_confidence === "number" &&
                      ` · ${t("validation.ocr", { pct: Math.round(p.ocr_confidence * 100) })}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <button
        type="button"
        onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
        className="inline-flex items-center gap-1.5 rounded border border-border bg-surface px-2.5 py-1 text-[12px] font-medium text-primary hover:bg-muted"
      >
        <FileText className="h-3.5 w-3.5" /> {t("validation.openDocument")}
      </button>
    </div>
  );
}
