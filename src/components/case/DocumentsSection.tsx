import { useMemo, useState, type ReactNode } from "react";
import { AlertTriangle, CheckCircle2, ChevronDown, ChevronRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import type { FileRecord, FileStatus, LogicalDocument, ReviewItem } from "@/api/types";
import { Panel } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { FileTree, RegisterHead, type RegisterContext } from "@/components/documents/FileTree";
import { UploadZone } from "@/components/documents/UploadZone";
import { FileStatusChip } from "@/components/documents/chips";
import { t } from "@/config/terminology";
import { DocumentChecklist } from "./DocumentChecklist";
import { useCase } from "@/domain/cases";
import { useChecklist } from "@/domain/checklist";
import {
  buildFileTree,
  countFiles,
  fileGroup,
  partitionTree,
  useCaseRegister,
  useUpload,
  type FileGroup,
} from "@/domain/documents";
import { integrityNeedsPerson } from "@/domain/integrity";
import { errorKind } from "@/domain/errors";
import { reviewTarget, useReviewQueue } from "@/domain/review";
import { useCan, useSession } from "@/domain/session";
import { cn } from "@/lib/utils";

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
      satisfiesFor: (id) => items.filter((i) => (i.document_ids ?? []).includes(id)),
    };
  }, [canReview, review.data, checklist.data, c?.borrower]);
}

/** A document a person should act on here: an open review item, a flag, or a status that
 * waits on someone. A gap in the checklist item it counts towards is not one: it is said on
 * the row and resolved on the completeness step. */
function needsAttention(doc: LogicalDocument, context: RegisterContext): boolean {
  return (
    context.itemsFor(doc.id).length > 0 ||
    doc.label_mismatch === true ||
    doc.status === "unclassified" ||
    doc.status === "in_exception" ||
    doc.status === "in_review"
  );
}

/** One section of the register: its heading, then its files. */
function Section({
  title,
  tone,
  testId,
  children,
}: {
  title: ReactNode;
  tone?: "attention" | "quiet";
  testId: string;
  children: ReactNode;
}) {
  return (
    <section data-testid={testId}>
      <h3
        className={cn(
          "flex items-center gap-1.5 border-b border-border px-4 py-1.5 text-[11.5px] font-semibold",
          tone === "attention" ? "bg-flag-soft/40 text-flag-foreground" : "text-muted-foreground",
        )}
      >
        {title}
      </h3>
      {children}
    </section>
  );
}

/** The register in three sections: what needs a person first, then what is
 * still being read, then everything ready, folded into one line. */
function Register({
  caseId,
  files,
  documents,
  context,
}: {
  caseId: string;
  files: FileRecord[];
  documents: LogicalDocument[];
  context: RegisterContext;
}) {
  const groups = partitionTree(buildFileTree(files, documents), (f) =>
    fileGroup(f, (d) => needsAttention(d, context), integrityNeedsPerson),
  );
  const n = {
    attention: countFiles(groups.attention),
    reading: countFiles(groups.reading),
    ready: countFiles(groups.ready),
  };
  const [showReady, setShowReady] = useState<boolean | null>(null);
  // Nothing waiting and nothing being read: the ready files are the register.
  const readyOpen = showReady ?? (n.attention === 0 && n.reading === 0);
  const tree = (key: FileGroup) => (
    <FileTree
      caseId={caseId}
      files={files}
      context={context}
      nodes={groups[key]}
      testId={`files-${key}`}
    />
  );
  return (
    <div data-testid="file-tree">
      <RegisterHead />
      {n.attention > 0 && (
        <Section
          tone="attention"
          testId="section-attention"
          title={
            <>
              <AlertTriangle className="h-3.5 w-3.5" />
              {t("documents.section.attention", { n: n.attention })}
            </>
          }
        >
          {tree("attention")}
        </Section>
      )}
      {n.reading > 0 && (
        <Section
          testId="section-reading"
          title={
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              {t("documents.section.reading", { n: n.reading })}
            </>
          }
        >
          {tree("reading")}
        </Section>
      )}
      {n.ready > 0 && (
        <section data-testid="section-ready">
          <button
            type="button"
            onClick={() => setShowReady(!readyOpen)}
            aria-expanded={readyOpen}
            data-testid="show-ready"
            className="flex w-full items-center justify-between gap-2 border-b border-border px-4 py-2 text-left text-[12px] text-muted-foreground hover:bg-surface-muted/60"
          >
            <span className="inline-flex items-center gap-1.5">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {t(
                n.attention + n.reading > 0
                  ? "documents.section.readyQuiet"
                  : "documents.section.ready",
                {
                  n: n.ready,
                },
              )}
            </span>
            <span className="inline-flex items-center gap-1 font-medium text-primary">
              {t(readyOpen ? "documents.section.hide" : "documents.section.show")}
              {readyOpen ? (
                <ChevronDown className="h-3.5 w-3.5" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5" />
              )}
            </span>
          </button>
          {readyOpen && tree("ready")}
        </section>
      )}
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
    <div className="grid gap-4 px-4 py-5 sm:px-6 @min-[49rem]/main:grid-cols-[minmax(0,1fr)_320px]">
      <div className="order-2 min-w-0 space-y-4 @min-[49rem]/main:order-1">
        {/* First: what the appraisal needs, what has come in for each, what is missing, with an
            upload on each row; every file received follows. */}
        <DocumentChecklist caseId={caseId} variant="files" />
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
            <Register
              caseId={caseId}
              files={files.data}
              documents={documents.data}
              context={context}
            />
          )}
        </Panel>
      </div>

      {/* On a phone: adding files first, then the files, then the counts. */}
      <div className="min-w-0 space-y-4 @max-[49rem]/main:contents @min-[49rem]/main:order-2 @min-[49rem]/main:sticky @min-[49rem]/main:top-4 @min-[49rem]/main:self-start">
        {canUpload && (
          <div className="order-1 min-w-0">
            <Panel title={t("documents.add")} testId="add-documents">
              <div className="space-y-2 p-3">
                <UploadZone compact onFiles={onFiles} busy={upload.isPending} />
                {upload.isError && <ErrorState error={upload.error} compact />}
              </div>
            </Panel>
          </div>
        )}
        <div className="order-3 min-w-0">
          <Summary files={files.data} documents={documents.data} context={context} />
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: "flag" | "ok" }) {
  return (
    <div className="rounded border border-border bg-surface-muted/50 px-3 py-2">
      <p
        className={cn(
          "tabular text-[20px] font-semibold leading-none",
          tone === "flag" && value > 0 ? "text-flag-foreground" : "text-foreground",
        )}
      >
        {value}
      </p>
      <p className="mt-1 text-[11px] leading-tight text-muted-foreground">{label}</p>
    </div>
  );
}

function Summary({
  files,
  documents,
  context,
}: {
  files: FileRecord[] | undefined;
  documents: LogicalDocument[] | undefined;
  context: RegisterContext;
}) {
  if (!files || !documents) return null;
  const count = (s: FileStatus) => files.filter((f) => f.status === s).length;
  const unclassified = documents.filter((d) => (d.classification?.types.length ?? 0) === 0).length;
  const mismatched = documents.filter((d) => d.label_mismatch).length;
  const attention = documents.filter((d) => needsAttention(d, context)).length;
  return (
    <Panel title={t("documents.summary")} testId="documents-summary">
      {/* One list: the documents, then the files by status; a status with no file is left out. */}
      <dl className="divide-y divide-border text-[12.5px]">
        {(
          [
            [t("documents.logical"), documents.length, false],
            [t("documents.needsAttention"), attention, true],
            [t("document.unclassified"), unclassified, true],
            [t("documents.labelMismatches"), mismatched, true],
          ] as const
        ).map(([label, value, flag]) => (
          <div key={label} className="flex items-center justify-between gap-3 px-4 py-1.5">
            <dt className="text-muted-foreground">{label}</dt>
            <dd
              className={cn(
                "tabular font-medium",
                flag && value > 0 ? "text-flag-foreground" : "text-foreground",
              )}
            >
              {value}
            </dd>
          </div>
        ))}
        {STATUS_ORDER.filter((s) => s === "registered" || count(s) > 0).map((s) => (
          <div key={s} className="flex items-center justify-between gap-3 px-4 py-1.5">
            <dt>
              <FileStatusChip status={s} />
            </dt>
            <dd className="tabular" data-testid={`count-${s}`}>
              {count(s)}
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}
