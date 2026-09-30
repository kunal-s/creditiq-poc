import { createContext, useContext, useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  HelpCircle,
} from "lucide-react";
import type { ChecklistItemState, FileRecord, LogicalDocument, ReviewItem } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useCan } from "@/domain/session";
import {
  countFiles,
  formatBytes,
  pageRange,
  useDocumentTypes,
  type TreeFile,
  type TreeNode,
} from "@/domain/documents";
import { Chip } from "@/components/common/Panel";
import { DocumentActions } from "./DocumentActions";
import { DocumentDetail } from "./DocumentDetail";
import { FileStatusChip, GradeChip } from "./chips";
import { StageTrack } from "./StageTrack";

/** What every row of the register needs to know about the case. */
export type RegisterContext = {
  borrower: string;
  /** Open review items for a document (type, quality, split, party). */
  itemsFor: (documentId: string) => ReviewItem[];
  /** Checklist defects that name a document. */
  defectsFor: (documentId: string) => ChecklistItemState[];
};

const Register = createContext<RegisterContext>({
  borrower: "",
  itemsFor: () => [],
  defectsFor: () => [],
});

/** The files of a case as a tree, each with its logical documents (FRD F-05
 * mock), and each document with its track, flags and what to do next (§6). */
export function FileTree({
  caseId,
  nodes,
  files,
  context,
}: {
  caseId: string;
  nodes: TreeNode[];
  files: FileRecord[];
  context?: RegisterContext;
}) {
  const inner = (
    <ul className="divide-y divide-border" data-testid="file-tree">
      {nodes.map((node) => (
        <Node
          key={node.kind === "file" ? node.file.id : node.path}
          caseId={caseId}
          node={node}
          files={files}
          depth={0}
        />
      ))}
    </ul>
  );
  return context ? <Register.Provider value={context}>{inner}</Register.Provider> : inner;
}

function Node({
  caseId,
  node,
  files,
  depth,
}: {
  caseId: string;
  node: TreeNode;
  files: FileRecord[];
  depth: number;
}) {
  const [open, setOpen] = useState(true);
  if (node.kind === "file")
    return <FileRow caseId={caseId} node={node} files={files} depth={depth} />;
  return (
    <li data-testid="tree-folder">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-4 py-2 text-left hover:bg-surface-muted/60"
        style={{ paddingLeft: 16 + depth * 14 }}
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <Folder className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="min-w-0 break-all text-[12.5px] font-medium text-foreground">
          {node.name}
        </span>
        <span className="shrink-0 text-[11px] text-muted-foreground">
          {t("documents.fileCount", { n: countFiles(node.children) })}
        </span>
      </button>
      {open && (
        <ul className="divide-y divide-border border-t border-border">
          {node.children.map((child) => (
            <Node
              key={child.kind === "file" ? child.file.id : child.path}
              caseId={caseId}
              node={child}
              files={files}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function FileRow({
  caseId,
  node,
  files,
  depth,
}: {
  caseId: string;
  node: TreeFile;
  files: FileRecord[];
  depth: number;
}) {
  const { file, documents } = node;
  const original = file.duplicate_of ? files.find((f) => f.id === file.duplicate_of) : undefined;
  const reading = file.status === "registered" && documents.length === 0;

  return (
    <li data-testid="tree-file" data-status={file.status}>
      <div
        className="flex flex-wrap items-start gap-x-3 gap-y-1 px-4 py-2.5"
        style={{ paddingLeft: 16 + depth * 14 }}
      >
        <FileText className="mt-0.5 h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <p className="break-all text-[12.5px] font-medium text-foreground">
            {file.original_name}
          </p>
          <p className="text-[11px] text-muted-foreground">
            {formatBytes(file.size_bytes)}
            {file.status === "duplicate" && (
              <span data-testid="duplicate-of">
                {" · "}
                {t("documents.duplicateOf", {
                  name:
                    original?.archive_path ?? original?.original_name ?? file.duplicate_of ?? "",
                })}
              </span>
            )}
            {file.reason && file.status !== "duplicate" && <> · {file.reason}</>}
          </p>
        </div>
        {reading && <StageTrack doc={undefined} />}
        <FileStatusChip status={file.status} />
      </div>
      {documents.length > 0 && (
        <ul className="pb-2">
          {documents.map((doc) => (
            <DocumentRow key={doc.id} caseId={caseId} doc={doc} file={file} depth={depth} />
          ))}
        </ul>
      )}
    </li>
  );
}

function DocumentRow({
  caseId,
  doc,
  file,
  depth,
}: {
  caseId: string;
  doc: LogicalDocument;
  file: FileRecord;
  depth: number;
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const { borrower, itemsFor, defectsFor } = useContext(Register);
  const [open, setOpen] = useState(false);
  const canReadData = useCan("data.read");
  const canReview = useCan("review.read");
  const classified = (doc.classification?.types.length ?? 0) > 0;
  const items = itemsFor(doc.id);
  const defects = defectsFor(doc.id);

  return (
    <li
      className="border-l border-border"
      style={{ marginLeft: 30 + depth * 14 }}
      data-testid="tree-document"
      data-document-id={doc.id}
    >
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1.5 pl-3 pr-4">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={t("documents.details")}
          className="grid h-5 w-5 shrink-0 place-items-center rounded text-muted-foreground hover:bg-muted"
          data-testid="document-toggle"
        >
          {open ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </button>
        <span className="tabular w-12 shrink-0 text-[11px] text-muted-foreground">
          {pageRange(doc)}
        </span>
        <button
          type="button"
          onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
          className="min-w-0 flex-1 text-left text-[12.5px] text-foreground hover:text-primary hover:underline"
        >
          {classified ? (
            <span data-testid="document-type">
              {doc.classification!.types.map(types.name).join(" + ")}
              {doc.instance_key && (
                <span className="text-muted-foreground"> · {doc.instance_key}</span>
              )}
            </span>
          ) : (
            <span
              className="inline-flex items-center gap-1 text-flag-foreground"
              data-testid="unclassified"
            >
              <HelpCircle className="h-3.5 w-3.5" /> {t("document.unclassified")}
            </span>
          )}
        </button>
        {doc.label_mismatch && (
          <Chip tone="flag" title={t("documents.labelMismatchHelp")}>
            <AlertTriangle className="h-3 w-3" />
            <span data-testid="label-mismatch">
              {t("documents.labelMismatch", { label: file.label_hint ?? file.original_name })}
            </span>
          </Chip>
        )}
        {defects.length > 0 && (
          <Chip tone="critical">
            <span data-testid="defect-count">{t("documents.defects", { n: defects.length })}</span>
          </Chip>
        )}
        <StageTrack doc={doc} />
        <GradeChip grade={doc.grade} />
      </div>
      {doc.status === "in_review" && canReadData && (
        <div className="pb-2 pl-[5.25rem] pr-4">
          <Link
            to="/appraisals/$caseId/extraction"
            params={{ caseId }}
            hash="fields"
            className="text-[11px] font-medium text-primary hover:underline"
            data-testid="check-values"
          >
            {t("documents.checkValues")} →
          </Link>
        </div>
      )}
      {!canReview && (doc.status === "unclassified" || doc.status === "in_exception") && (
        <div className="pb-2 pl-[5.25rem] pr-4">
          <span className="text-[11px] text-muted-foreground" data-testid="waiting-review">
            {t("documents.waitingReview")}
          </span>
        </div>
      )}
      {items.length > 0 && (
        <div className="pb-2 pl-[5.25rem] pr-4">
          <DocumentActions doc={doc} items={items} borrower={borrower} />
        </div>
      )}
      {open && <DocumentDetail caseId={caseId} doc={doc} file={file} defects={defects} />}
    </li>
  );
}
