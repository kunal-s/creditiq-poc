import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { AlertTriangle, CheckCircle2, FileText, HelpCircle, XCircle } from "lucide-react";
import type { ChecklistItemState, FileRecord, LogicalDocument } from "@/api/types";
import { Chip, Kpi, Panel } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { DocStatusChip, GradeChip } from "@/components/documents/chips";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t, tOr } from "@/config/terminology";
import { useChecklist } from "@/domain/checklist";
import { pageRange, useCaseRegister, useDocumentTypes } from "@/domain/documents";
import { cn } from "@/lib/utils";

type Outcome = "pass" | "warn" | "fail";

function outcome(doc: LogicalDocument, defects: ChecklistItemState[]): Outcome {
  if (doc.grade === "U" || doc.status === "in_exception") return "fail";
  if (defects.length > 0) return "fail";
  if (
    doc.grade === "C" ||
    doc.label_mismatch ||
    (doc.classification?.types.length ?? 0) === 0 ||
    doc.status === "in_review"
  )
    return "warn";
  return "pass";
}

const ICON = { pass: CheckCircle2, warn: AlertTriangle, fail: XCircle } as const;
const TONE = { pass: "text-positive", warn: "text-flag", fail: "text-destructive" } as const;

/** Machine checks by document: quality, type and defects (F-07 to F-10, F-13). */
export function DocumentChecksSection({ caseId }: { caseId: string }) {
  const { files, documents } = useCaseRegister(caseId);
  const checklist = useChecklist(caseId);
  const [open, setOpen] = useState<string | null>(null);

  if (files.isError || documents.isError) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <ErrorState
          error={files.error ?? documents.error}
          onRetry={() => void documents.refetch()}
        />
      </div>
    );
  }
  if (!files.data || !documents.data) {
    return (
      <div className="px-4 py-5 sm:px-6">
        <LoadingBlock />
      </div>
    );
  }
  const docs = documents.data.filter((d) => d.status !== "duplicate" && d.status !== "superseded");
  const defectsFor = (id: string) =>
    (checklist.data?.items ?? []).filter(
      (i) => i.deficiency && (i.document_ids ?? []).includes(id),
    );
  const outcomes = docs.map((d) => outcome(d, defectsFor(d.id)));

  return (
    <div className="space-y-4 px-4 py-5 sm:px-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label={t("validation.kpi.checked")}
          value={docs.length}
          note={t("validation.kpi.checkedNote")}
        />
        <Kpi
          label={t("validation.kpi.failing")}
          value={outcomes.filter((o) => o === "fail").length}
          note={t("validation.kpi.failingNote")}
          tone="critical"
        />
        <Kpi
          label={t("validation.kpi.caveat")}
          value={outcomes.filter((o) => o === "warn").length}
          note={t("validation.kpi.caveatNote")}
          tone="flag"
        />
        <Kpi
          label={t("validation.kpi.unclassified")}
          value={docs.filter((d) => (d.classification?.types.length ?? 0) === 0).length}
          note={t("validation.kpi.unclassifiedNote")}
          testId="kpi-unclassified"
        />
      </div>

      <Panel
        title={t("page.validation.title")}
        subtitle={t("validation.subtitle")}
        testId="validation"
      >
        {docs.length === 0 ? (
          <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
            {t("validation.none")}{" "}
            <Link
              to="/appraisals/$caseId/documents"
              params={{ caseId: caseId }}
              className="font-medium text-primary hover:underline"
            >
              {t("caseTab.documents")}
            </Link>
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {docs.map((doc, i) => (
              <DocumentChecks
                key={doc.id}
                caseId={caseId}
                doc={doc}
                file={files.data.find((f) => f.id === doc.file_id)}
                defects={defectsFor(doc.id)}
                worst={outcomes[i]!}
                expanded={open === doc.id}
                onToggle={() => setOpen(open === doc.id ? null : doc.id)}
              />
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

function DocumentChecks({
  caseId,
  doc,
  file,
  defects,
  worst,
  expanded,
  onToggle,
}: {
  caseId: string;
  doc: LogicalDocument;
  file: FileRecord | undefined;
  defects: ChecklistItemState[];
  worst: Outcome;
  expanded: boolean;
  onToggle: () => void;
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const c = doc.classification;
  const classified = (c?.types.length ?? 0) > 0;
  const Icon = ICON[worst];

  return (
    <li data-testid="validation-document" data-document-id={doc.id}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="flex w-full flex-wrap items-center gap-2 px-4 py-2.5 text-left hover:bg-surface-muted/60"
      >
        <Icon className={cn("h-3.5 w-3.5 shrink-0", TONE[worst])} />
        <span className="text-[13px] font-medium text-foreground">
          {classified ? (
            c!.types.map(types.name).join(" + ")
          ) : (
            <span
              className="inline-flex items-center gap-1 text-flag-foreground"
              data-testid="unclassified"
            >
              <HelpCircle className="h-3.5 w-3.5" /> {t("document.unclassified")}
            </span>
          )}
        </span>
        <span className="tabular min-w-0 break-all text-[11px] text-muted-foreground">
          {file?.original_name} · {pageRange(doc)}
        </span>
        {doc.label_mismatch && (
          <Chip tone="flag">
            <AlertTriangle className="h-3 w-3" />
            <span data-testid="label-mismatch">
              {t("documents.labelMismatch", {
                label: file?.label_hint ?? file?.original_name ?? "",
              })}
            </span>
          </Chip>
        )}
        <span className="ml-auto flex items-center gap-2">
          <span className={cn("text-[11.5px] font-medium", TONE[worst])}>
            {t(`validation.outcome.${worst}`)}
          </span>
          <GradeChip grade={doc.grade} />
          <DocStatusChip status={doc.status} />
        </span>
      </button>

      {expanded && (
        <div className="space-y-3 border-t border-border bg-surface-muted/40 px-4 py-3">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="min-w-0">
              <p className="field-label">{t("validation.pages")}</p>
              <table className="mt-1 w-full text-[12px]">
                <thead>
                  <tr className="text-left text-[10.5px] uppercase tracking-wide text-muted-foreground">
                    <th className="py-1 pr-2 font-medium">{t("validation.page")}</th>
                    <th className="py-1 pr-2 font-medium">{t("validation.route")}</th>
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
                      <td className="py-1 pr-2 text-muted-foreground">
                        {t(`pageRoute.${p.route}`)}
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

            <div className="min-w-0 space-y-2 text-[12px]">
              <p className="field-label">{t("validation.classification")}</p>
              {c ? (
                <dl className="space-y-1">
                  <div className="flex gap-2">
                    <dt className="w-28 shrink-0 text-muted-foreground">{t("validation.types")}</dt>
                    <dd className="min-w-0 text-foreground">
                      {classified
                        ? c.types.map(types.name).join(" + ")
                        : t("document.unclassified")}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-28 shrink-0 text-muted-foreground">
                      {t("validation.exitTier")}
                    </dt>
                    <dd className="text-foreground" data-testid="exit-tier">
                      {t(`exitTier.${c.exit_tier}`)}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-28 shrink-0 text-muted-foreground">
                      {t("validation.confidence")}
                    </dt>
                    <dd className="tabular text-foreground">{Math.round(c.confidence * 100)}%</dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-28 shrink-0 text-muted-foreground">
                      {t("validation.signals")}
                    </dt>
                    <dd className="min-w-0 break-words text-foreground">
                      {(c.signals ?? []).length > 0 ? (c.signals ?? []).join(" · ") : "—"}
                    </dd>
                  </div>
                  <div className="flex gap-2">
                    <dt className="w-28 shrink-0 text-muted-foreground">
                      {t("validation.candidates")}
                    </dt>
                    <dd className="min-w-0 text-foreground" data-testid="candidates">
                      {(c.candidates ?? []).length > 0
                        ? (c.candidates ?? [])
                            .map(
                              (k) => `${types.name(k.type_id)} ${Math.round(k.confidence * 100)}%`,
                            )
                            .join(" · ")
                        : "—"}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-muted-foreground">{t("validation.notClassifiedYet")}</p>
              )}
              {doc.label_mismatch && (
                <p className="rounded border border-flag/35 bg-flag-soft px-3 py-2 text-flag-foreground">
                  {t("validation.labelMismatchDetail", {
                    label: file?.label_hint ?? file?.original_name ?? "",
                    type: classified
                      ? c!.types.map(types.name).join(" + ")
                      : t("document.unclassified"),
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
          </div>

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

          <button
            type="button"
            onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
            className="inline-flex items-center gap-1.5 rounded border border-border bg-surface px-2.5 py-1 text-[12px] font-medium text-primary hover:bg-muted"
          >
            <FileText className="h-3.5 w-3.5" /> {t("validation.openDocument")}
          </button>
        </div>
      )}
    </li>
  );
}
