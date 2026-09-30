import { useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import type { FileRecord, FileStatus, LogicalDocument, ReviewItem } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { FileTree, type RegisterContext } from "@/components/documents/FileTree";
import { UploadZone } from "@/components/documents/UploadZone";
import { FileStatusChip } from "@/components/documents/chips";
import { t } from "@/config/terminology";
import { useCase } from "@/domain/cases";
import { useChecklist } from "@/domain/checklist";
import {
  buildFileTree,
  filterTree,
  isDocumentInProgress,
  useCaseRegister,
  useUpload,
} from "@/domain/documents";
import { errorKind } from "@/domain/errors";
import { reviewTarget, useReviewQueue } from "@/domain/review";
import { useCan, useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

type Filter = "all" | "attention" | "processing";
const FILTERS: Filter[] = ["all", "attention", "processing"];

/** Open review items and checklist defects by document, for the register rows. */
function useRegisterContext(caseId: string): RegisterContext {
  const canReview = useCan("review.read");
  const review = useReviewQueue({ caseId });
  const checklist = useChecklist(caseId);
  const { data: c } = useCase(caseId);
  return useMemo(() => {
    const byDoc = new Map<string, ReviewItem[]>();
    for (const item of canReview ? (review.data ?? []) : []) {
      const { kind, id } = reviewTarget(item.ref);
      if (item.status !== "open" || (kind !== "document" && kind !== "party")) continue;
      byDoc.set(id, [...(byDoc.get(id) ?? []), item]);
    }
    const items = checklist.data?.items ?? [];
    return {
      borrower: c?.borrower ?? "",
      itemsFor: (id) => byDoc.get(id) ?? [],
      defectsFor: (id) => items.filter((i) => i.deficiency && (i.document_ids ?? []).includes(id)),
    };
  }, [canReview, review.data, checklist.data, c?.borrower]);
}

/** A document a person should look at: an open review item, a flag, or a defect. */
function needsAttention(doc: LogicalDocument, context: RegisterContext): boolean {
  return (
    context.itemsFor(doc.id).length > 0 ||
    context.defectsFor(doc.id).length > 0 ||
    doc.label_mismatch === true ||
    doc.status === "unclassified" ||
    doc.status === "in_exception" ||
    doc.status === "in_review"
  );
}

function FilterChips({
  value,
  onChange,
  counts,
}: {
  value: Filter;
  onChange: (f: Filter) => void;
  counts: Record<Filter, number>;
}) {
  return (
    <div
      className="flex flex-wrap gap-1.5 border-b border-border px-4 py-2"
      data-testid="document-filters"
    >
      {FILTERS.map((f) => (
        <button
          key={f}
          type="button"
          aria-pressed={value === f}
          onClick={() => onChange(f)}
          data-testid={`filter-${f}`}
          className={cn(
            "rounded border px-2 py-0.5 text-[11.5px] font-medium transition-colors",
            value === f
              ? "border-primary bg-primary text-primary-foreground"
              : "border-border bg-surface text-muted-foreground hover:bg-muted",
          )}
        >
          {t(`documents.filter.${f}`, { n: counts[f] })}
        </button>
      ))}
    </div>
  );
}

const STATUS_ORDER: FileStatus[] = ["registered", "duplicate", "exception", "rejected", "ignored"];

/** Upload and the file register (F-05). */
export function DocumentsSection({ caseId }: { caseId: string }) {
  const session = useSession();
  const canUpload = session?.user.permissions.includes("document.upload") ?? false;
  const { files, documents, polling } = useCaseRegister(caseId);
  const upload = useUpload(caseId);
  const context = useRegisterContext(caseId);
  const [filter, setFilter] = useState<Filter>("all");

  const onFiles = (list: File[]) => {
    upload.mutate(list, {
      onSuccess: (result) => toast.success(t("documents.uploaded", { n: result.files.length })),
      onError: (error) =>
        toast(t(`state.${errorKind(error)}.title`), {
          description: t(`state.${errorKind(error)}.description`),
        }),
    });
  };

  return (
    <div className="grid gap-4 px-4 py-5 sm:px-6 lg:grid-cols-[minmax(0,1fr)_300px]">
      <div className="min-w-0 space-y-4">
        {canUpload && (
          <Panel title={t("documents.add")} subtitle={t("documents.addHelp")}>
            <div className="space-y-3 p-4">
              <UploadZone onFiles={onFiles} busy={upload.isPending} />
              {upload.isError && <ErrorState error={upload.error} compact />}
            </div>
          </Panel>
        )}

        <Panel
          title={t("documents.received")}
          subtitle={
            polling ? (
              <span className="inline-flex items-center gap-1" data-testid="polling">
                <Loader2 className="h-3 w-3 animate-spin" /> {t("documents.processing")}
              </span>
            ) : (
              t("documents.receivedHelp")
            )
          }
          testId="files-received"
        >
          {files.isError || documents.isError ? (
            <div className="p-4">
              <ErrorState
                error={files.error ?? documents.error}
                onRetry={() => {
                  void files.refetch();
                  void documents.refetch();
                }}
              />
            </div>
          ) : !files.data || !documents.data ? (
            <div className="p-4">
              <LoadingBlock rows={4} className="border-0 p-0" />
            </div>
          ) : files.data.length === 0 ? (
            <p className="px-4 py-8 text-center text-[12.5px] text-muted-foreground">
              {t("documents.none")}
            </p>
          ) : (
            <>
              <FilterChips
                value={filter}
                onChange={setFilter}
                counts={{
                  all: documents.data.length,
                  attention: documents.data.filter((d) => needsAttention(d, context)).length,
                  processing: documents.data.filter(isDocumentInProgress).length,
                }}
              />
              <FileTree
                caseId={caseId}
                files={files.data}
                context={context}
                nodes={
                  filter === "all"
                    ? buildFileTree(files.data, documents.data)
                    : filterTree(
                        buildFileTree(files.data, documents.data),
                        filter === "attention"
                          ? (d) => needsAttention(d, context)
                          : isDocumentInProgress,
                        (f) =>
                          filter === "attention"
                            ? f.status === "exception" || f.status === "rejected"
                            : f.status === "registered",
                      )
                }
              />
            </>
          )}
        </Panel>
      </div>

      <div className="min-w-0 space-y-3">
        <Summary files={files.data} documents={documents.data} />
      </div>
    </div>
  );
}

function Summary({
  files,
  documents,
}: {
  files: FileRecord[] | undefined;
  documents: LogicalDocument[] | undefined;
}) {
  if (!files || !documents) return null;
  const count = (s: FileStatus) => files.filter((f) => f.status === s).length;
  const unclassified = documents.filter((d) => (d.classification?.types.length ?? 0) === 0).length;
  const mismatched = documents.filter((d) => d.label_mismatch).length;
  return (
    <Panel title={t("documents.summary")} testId="documents-summary">
      <dl className="divide-y divide-border text-[12.5px]">
        {STATUS_ORDER.map((s) => (
          <div key={s} className="flex items-center justify-between gap-3 px-4 py-2">
            <dt>
              <FileStatusChip status={s} />
            </dt>
            <dd className="tabular" data-testid={`count-${s}`}>
              {count(s)}
            </dd>
          </div>
        ))}
        <div className="flex justify-between gap-3 px-4 py-2">
          <dt className="text-muted-foreground">{t("documents.logical")}</dt>
          <dd className="tabular">{documents.length}</dd>
        </div>
        <div className="flex justify-between gap-3 px-4 py-2">
          <dt className="text-muted-foreground">{t("document.unclassified")}</dt>
          <dd className="tabular">{unclassified}</dd>
        </div>
        <div className="flex justify-between gap-3 px-4 py-2">
          <dt className="text-muted-foreground">{t("documents.labelMismatches")}</dt>
          <dd className="tabular">{mismatched}</dd>
        </div>
      </dl>
    </Panel>
  );
}
