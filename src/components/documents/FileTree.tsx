import { useState } from "react";
import { Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  HelpCircle,
  Loader2,
} from "lucide-react";
import type { FileRecord, LogicalDocument } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import {
  countFiles,
  formatBytes,
  isDocumentInProgress,
  pageRange,
  useDocumentTypes,
  type TreeFile,
  type TreeNode,
} from "@/domain/documents";
import { Chip } from "@/components/common/Panel";
import { DocStatusChip, FileStatusChip, GradeChip } from "./chips";

/** The files of a case as a tree, each with its logical documents (FRD F-05 mock). */
export function FileTree({
  caseId,
  nodes,
  files,
}: {
  caseId: string;
  nodes: TreeNode[];
  files: FileRecord[];
}) {
  return (
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
        {reading && (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" /> {t("documents.reading")}
          </span>
        )}
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
  const classified = (doc.classification?.types.length ?? 0) > 0;

  return (
    <li
      className="ml-4 flex flex-wrap items-center gap-x-3 gap-y-1 border-l border-border py-1.5 pl-3 pr-4"
      style={{ marginLeft: 30 + depth * 14 }}
      data-testid="tree-document"
      data-document-id={doc.id}
    >
      <span className="tabular w-14 shrink-0 text-[11px] text-muted-foreground">
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
      {!classified && !isDocumentInProgress(doc) && (
        <Link to="/exceptions" className="text-[11px] font-medium text-primary hover:underline">
          {t("documents.toReviewQueue")}
        </Link>
      )}
      {isDocumentInProgress(doc) && (
        <Loader2 className="h-3 w-3 animate-spin text-muted-foreground" />
      )}
      <GradeChip grade={doc.grade} />
      <DocStatusChip status={doc.status} />
    </li>
  );
}
