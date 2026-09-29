import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight, Loader2 } from "lucide-react";
import { toast } from "sonner";
import type { FileRecord, FileStatus, LogicalDocument } from "@/api/types";
import { CaseScreen } from "@/components/shell/CaseScreen";
import { PageHeader } from "@/components/shell/PageHeader";
import { Panel } from "@/components/common/Panel";
import { ErrorState, LoadingBlock } from "@/components/common/States";
import { FileTree } from "@/components/documents/FileTree";
import { UploadZone } from "@/components/documents/UploadZone";
import { FileStatusChip } from "@/components/documents/chips";
import { t } from "@/config/terminology";
import { buildFileTree, useCaseRegister, useUpload } from "@/domain/documents";
import { errorKind } from "@/domain/errors";
import { useSession } from "@/domain/session";

export const Route = createFileRoute("/appraisals/$id/upload")({
  head: () => ({
    meta: [{ title: `${t("page.documents.title")} — ${t("tenant.product.name")}` }],
  }),
  component: DocumentsStep,
});

function DocumentsStep() {
  const { id } = Route.useParams();
  return (
    <CaseScreen caseId={id}>
      {(c) => (
        <div>
          <PageHeader
            eyebrow={`${t("nav.group.appraisal")} · ${c.id}`}
            title={t("page.documents.title")}
            purpose={t("page.documents.purpose")}
            actions={
              <Link
                to="/docready/$caseId/checklist"
                params={{ caseId: c.id }}
                className="flex h-9 items-center gap-1.5 rounded border border-border bg-surface px-3 text-[12.5px] font-medium text-foreground hover:bg-muted"
              >
                {t("docreadyTab.checklist")} <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            }
          />
          <Documents caseId={c.id} />
        </div>
      )}
    </CaseScreen>
  );
}

const STATUS_ORDER: FileStatus[] = ["registered", "duplicate", "exception", "rejected", "ignored"];

function Documents({ caseId }: { caseId: string }) {
  const session = useSession();
  const canUpload = session?.user.permissions.includes("document.upload") ?? false;
  const { files, documents, polling } = useCaseRegister(caseId);
  const upload = useUpload(caseId);

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
            <FileTree
              caseId={caseId}
              files={files.data}
              nodes={buildFileTree(files.data, documents.data)}
            />
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
