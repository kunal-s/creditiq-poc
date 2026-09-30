import { useState } from "react";
import { ArrowRight, FileText } from "lucide-react";
import type { FieldStatus, FieldValue, LogicalDocument } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { FieldValueButton } from "@/components/common/FieldValueButton";
import { ConfidenceChip } from "@/components/common/ConfidenceChip";
import { FieldStatusChip, GradeChip } from "@/components/documents/chips";
import { FieldRowDecision } from "@/components/review/FieldDecision";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { pageRange, useCaseDocuments, useCaseFiles, useDocumentTypes } from "@/domain/documents";
import { fieldLabel, useFields } from "@/domain/extraction";
import { cn } from "@/lib/utils";

const FILTERS = ["all", "in_review", "missing", "corrected"] as const;

/** The FRD §6 grouping of extracted data, from each document type's group. */
const FIELD_SECTIONS = ["identity", "financials", "tax", "banking", "other"] as const;
type FieldSection = (typeof FIELD_SECTIONS)[number];
const SECTION_OF_GROUP: Record<string, FieldSection> = {
  constitution: "identity",
  registration: "identity",
  kyc: "identity",
  financials: "financials",
  working_capital: "financials",
  tax: "tax",
  banking: "banking",
};

function sectionOf(
  doc: LogicalDocument,
  byId: (id: string) => { group?: string } | undefined,
): FieldSection {
  const group = byId(doc.classification?.types[0] ?? "")?.group;
  return (group && SECTION_OF_GROUP[group]) || "other";
}
type Filter = (typeof FILTERS)[number];

/** Extracted fields by document, with confidence and page (F-15, F-16). */
export function ExtractedDataSection({ caseId }: { caseId: string }) {
  const fields = useFields(caseId);
  const documents = useCaseDocuments(caseId);
  const [filter, setFilter] = useState<Filter>("all");
  const types = useDocumentTypes();

  if (fields.isError || documents.isError) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <ErrorState error={fields.error ?? documents.error} onRetry={() => void fields.refetch()} />
      </div>
    );
  }
  if (!fields.data || !documents.data) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <LoadingBlock />
      </div>
    );
  }
  const all = fields.data;
  const shown = all.filter((f) => filter === "all" || f.status === filter);
  const groups = documents.data
    .map((doc) => ({ doc, fields: shown.filter((f) => f.document_id === doc.id) }))
    .filter((g) => g.fields.length > 0);
  const count = (s: FieldStatus) => all.filter((f) => f.status === s).length;

  return (
    <div className="grid gap-4 px-4 py-5 sm:px-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-4">
        <div className="flex flex-wrap gap-1" role="group" aria-label={t("data.filter")}>
          {FILTERS.map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={cn(
                "rounded border px-2 py-1 text-[11.5px] transition-colors",
                filter === f
                  ? "border-primary/50 bg-primary/10 font-medium text-primary"
                  : "border-border text-muted-foreground hover:bg-muted",
              )}
            >
              {f === "all" ? t("data.filterAll") : t(`fieldStatus.${f}`)}
            </button>
          ))}
        </div>
        {all.length === 0 ? (
          <Panel title={t("page.data.title")}>
            <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
              {t("data.none")}
            </p>
          </Panel>
        ) : groups.length === 0 ? (
          <Panel title={t("page.data.title")}>
            <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
              {t("data.noneMatch")}
            </p>
          </Panel>
        ) : (
          FIELD_SECTIONS.map((section) => {
            const members = groups.filter((g) => sectionOf(g.doc, types.byId) === section);
            if (members.length === 0) return null;
            return (
              <section key={section} className="space-y-3" data-testid={`field-section-${section}`}>
                <h3 className="text-[12px] font-semibold uppercase tracking-wide text-muted-foreground">
                  {t(`fieldSection.${section}`)}
                </h3>
                {members.map((g) => (
                  <DocumentFields key={g.doc.id} caseId={caseId} doc={g.doc} fields={g.fields} />
                ))}
              </section>
            );
          })
        )}
      </div>

      <div className="min-w-0 space-y-3">
        <Panel title={t("data.summary")} testId="data-summary">
          <div className="grid grid-cols-2 divide-x divide-border border-b border-border">
            <div className="px-4 py-3">
              <p className="text-[22px] font-semibold tabular-nums text-foreground">{all.length}</p>
              <p className="text-[11.5px] text-muted-foreground">{t("data.fields")}</p>
            </div>
            <div className="px-4 py-3">
              <p className="text-[22px] font-semibold tabular-nums text-flag-foreground">
                {count("in_review")}
              </p>
              <p className="text-[11.5px] text-muted-foreground">{t("fieldStatus.in_review")}</p>
            </div>
          </div>
          <dl className="divide-y divide-border text-[12.5px]">
            {(["accepted", "corrected", "missing", "rejected"] as const).map((s) => (
              <div key={s} className="flex justify-between gap-3 px-4 py-2">
                <dt className="text-muted-foreground">{t(`fieldStatus.${s}`)}</dt>
                <dd className="tabular-nums">{count(s)}</dd>
              </div>
            ))}
          </dl>
          {count("in_review") > 0 && filter !== "in_review" && (
            <div className="border-t border-border px-4 py-3">
              <button
                type="button"
                onClick={() => setFilter("in_review")}
                className="flex h-8 w-full items-center justify-center gap-1.5 rounded border border-border bg-surface text-[12.5px] font-medium text-foreground hover:bg-muted"
                data-testid="show-in-review"
              >
                {t("data.showInReview", { n: count("in_review") })}
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function DocumentFields({
  caseId,
  doc,
  fields,
}: {
  caseId: string;
  doc: LogicalDocument;
  fields: FieldValue[];
}) {
  const types = useDocumentTypes();
  const files = useCaseFiles(caseId);
  const viewer = useDocViewer();
  const file = files.data?.find((f) => f.id === doc.file_id);
  const title = doc.classification?.types.length
    ? doc.classification.types.map(types.name).join(" + ")
    : t("document.unclassified");

  return (
    <Panel
      title={title}
      testId="field-group"
      subtitle={
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <span className="break-all">{file?.original_name}</span>
          <span>· {pageRange(doc)}</span>
          {doc.instance_key && <span>· {doc.instance_key}</span>}
        </span>
      }
      action={
        <span className="flex items-center gap-2">
          <GradeChip grade={doc.grade} />
          <button
            type="button"
            onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
            className="inline-flex items-center gap-1 rounded border border-border px-2 py-0.5 text-[11.5px] font-medium text-primary hover:bg-muted"
          >
            <FileText className="h-3 w-3" /> {t("validation.openDocument")}
          </button>
        </span>
      }
    >
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[12.5px]">
          <thead>
            <tr className="border-b border-border text-left text-[10.5px] uppercase tracking-[0.06em] text-muted-foreground">
              <th className="px-4 py-2 font-medium">{t("data.col.field")}</th>
              <th className="px-3 py-2 font-medium">{t("data.col.value")}</th>
              <th className="px-3 py-2 font-medium">{t("data.col.confidence")}</th>
              <th className="px-3 py-2 font-medium">{t("data.col.method")}</th>
              <th className="px-4 py-2 font-medium">{t("data.col.status")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {fields.map((f) => (
              <tr key={f.id} className="align-top" data-testid="field-row">
                <td className="px-4 py-2 text-muted-foreground">{fieldLabel(f.field)}</td>
                <td className="px-3 py-2">
                  <FieldValueButton caseId={caseId} field={f} />
                  {f.raw && f.status !== "missing" && (
                    <div className="mt-0.5 text-[11px] text-muted-foreground">
                      {t("data.raw", { raw: f.raw })}
                    </div>
                  )}
                </td>
                <td className="px-3 py-2">
                  <ConfidenceChip
                    confidence={f.confidence}
                    components={f.confidence_components}
                    flagged={f.status === "in_review"}
                  />
                </td>
                <td className="px-3 py-2 text-muted-foreground">{t(`fieldMethod.${f.method}`)}</td>
                <td className="px-4 py-2">
                  <FieldStatusChip status={f.status} />
                  <FieldRowDecision field={f} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
