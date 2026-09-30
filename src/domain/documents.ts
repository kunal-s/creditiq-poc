import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/api/client";
import type {
  DocumentStatus,
  DocumentTypeDef,
  FileRecord,
  Grade,
  LogicalDocument,
} from "@/api/types";

/** Statuses a document may still leave without a person acting (FRD §7). */
const IN_PROGRESS: ReadonlySet<DocumentStatus> = new Set([
  "received",
  "graded",
  "split",
  "classified",
  "extracted",
]);

export function isDocumentInProgress(doc: LogicalDocument): boolean {
  return IN_PROGRESS.has(doc.status);
}

const POLL_MS = 3000;

/** A registered file whose documents have not appeared yet is still being read. */
function pending(files: FileRecord[] | undefined, docs: LogicalDocument[] | undefined): boolean {
  if (docs?.some(isDocumentInProgress)) return true;
  if (!files || !docs) return false;
  const withDocs = new Set(docs.map((d) => d.file_id));
  return files.some((f) => f.status === "registered" && !withDocs.has(f.id));
}

/** Files and logical documents for a case, polled while any is non-final (F-02.2). */
export function useCaseRegister(caseId: string) {
  const client = useQueryClient();
  const files = useQuery({
    queryKey: ["cases", caseId, "files"],
    queryFn: () => api.caseFiles(caseId),
    refetchInterval: () =>
      pending(
        client.getQueryData<FileRecord[]>(["cases", caseId, "files"]),
        client.getQueryData<LogicalDocument[]>(["cases", caseId, "documents"]),
      )
        ? POLL_MS
        : false,
  });
  const documents = useQuery({
    queryKey: ["cases", caseId, "documents"],
    queryFn: () => api.caseDocuments(caseId),
    refetchInterval: () =>
      pending(
        client.getQueryData<FileRecord[]>(["cases", caseId, "files"]),
        client.getQueryData<LogicalDocument[]>(["cases", caseId, "documents"]),
      )
        ? POLL_MS
        : false,
  });
  return { files, documents, polling: pending(files.data, documents.data) };
}

export function useCaseDocuments(caseId: string) {
  return useQuery({
    queryKey: ["cases", caseId, "documents"],
    queryFn: () => api.caseDocuments(caseId),
  });
}

export function useCaseFiles(caseId: string) {
  return useQuery({ queryKey: ["cases", caseId, "files"], queryFn: () => api.caseFiles(caseId) });
}

/** F-05: upload single files, several files or ZIP archives. */
export function useUpload(caseId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (files: File[]) => api.uploadFiles(caseId, files),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: ["cases", caseId] });
    },
  });
}

/** The published closed list of document types (F-09.1). */
export function useDocumentTypes() {
  const query = useQuery({
    queryKey: ["config", "document-types"],
    queryFn: api.documentTypes,
    staleTime: Infinity,
  });
  const byId = useCallback(
    (id: string): DocumentTypeDef | undefined => query.data?.types.find((d) => d.id === id),
    [query.data],
  );
  const name = useCallback((id: string) => byId(id)?.name ?? id.replace(/_/g, " "), [byId]);
  return { ...query, byId, name };
}

/** Rendered page image as an object URL, fetched with the session token. */
export function usePageImage(caseId: string, documentId: string, page: number) {
  const query = useQuery({
    queryKey: ["cases", caseId, "documents", documentId, "pages", page],
    queryFn: () => api.pageImage(caseId, documentId, page),
    staleTime: Infinity,
  });
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    if (!query.data) {
      setUrl(null);
      return;
    }
    const next = URL.createObjectURL(query.data);
    setUrl(next);
    return () => URL.revokeObjectURL(next);
  }, [query.data]);
  return { ...query, url };
}

/** Worst grade first. */
export const GRADE_ORDER: Record<Grade, number> = { U: 0, C: 1, B: 2, A: 3 };

export function pageGrade(doc: LogicalDocument, page: number): Grade | undefined {
  return doc.pages.find((p) => p.n === page)?.grade;
}

export function pageRange(doc: Pick<LogicalDocument, "page_from" | "page_to">): string {
  return doc.page_from === doc.page_to ? `p${doc.page_from}` : `p${doc.page_from}–${doc.page_to}`;
}

export function formatBytes(n: number): string {
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
  if (n >= 1024) return `${Math.round(n / 1024)} KB`;
  return `${n} B`;
}

export type TreeFolder = {
  kind: "folder";
  name: string;
  path: string;
  children: TreeNode[];
};
export type TreeFile = {
  kind: "file";
  file: FileRecord;
  documents: LogicalDocument[];
};
export type TreeNode = TreeFolder | TreeFile;

/**
 * The files of a case as a tree (F-05.5): archive members sit under their
 * archive and folders, from `archive_path`; loose files at the top level.
 */
export function buildFileTree(files: FileRecord[], documents: LogicalDocument[]): TreeNode[] {
  const root: TreeFolder = { kind: "folder", name: "", path: "", children: [] };
  const docsByFile = new Map<string, LogicalDocument[]>();
  for (const d of documents) {
    const list = docsByFile.get(d.file_id) ?? [];
    list.push(d);
    docsByFile.set(d.file_id, list);
  }
  for (const file of files) {
    const segments = (file.archive_path ?? "").split("/").filter(Boolean);
    // The path may end with the member's own name; the leaf shows it anyway.
    if (segments.length > 0 && segments[segments.length - 1] === file.original_name) {
      segments.pop();
    }
    let folder = root;
    let path = "";
    for (const segment of segments) {
      path = path ? `${path}/${segment}` : segment;
      let next = folder.children.find(
        (c): c is TreeFolder => c.kind === "folder" && c.name === segment,
      );
      if (!next) {
        next = { kind: "folder", name: segment, path, children: [] };
        folder.children.push(next);
      }
      folder = next;
    }
    const docs = (docsByFile.get(file.id) ?? []).sort((a, b) => a.page_from - b.page_from);
    folder.children.push({ kind: "file", file, documents: docs });
  }
  return root.children;
}

export function countFiles(nodes: TreeNode[]): number {
  return nodes.reduce((n, node) => n + (node.kind === "file" ? 1 : countFiles(node.children)), 0);
}

/** The steps a document passes through in stage 1 and 2 (FRD §5, §7). */
export const DOC_STEPS = ["received", "quality", "split", "classified", "extracted"] as const;
export type DocStep = (typeof DOC_STEPS)[number];
export type StepState = "running" | "attention" | "done" | "off";

/**
 * Where a document is on its track: how many steps are complete, and the
 * state of the step after them. A registered file with no documents yet is
 * still being received (`doc` undefined).
 */
export function docTrack(doc: LogicalDocument | undefined): { done: number; state: StepState } {
  if (!doc) return { done: 0, state: "running" };
  switch (doc.status) {
    case "received":
      return { done: 1, state: "running" };
    case "graded":
      return { done: 2, state: "running" };
    case "split":
      return { done: 3, state: "running" };
    case "classified":
    case "extracted":
      return { done: 4, state: "running" };
    case "accepted":
      return { done: 5, state: "done" };
    case "in_review":
      return { done: 4, state: "attention" };
    case "unclassified":
      return { done: 3, state: "attention" };
    case "in_exception":
      return { done: 1, state: "attention" };
    case "superseded":
    case "duplicate":
      return { done: 0, state: "off" };
  }
}

/** Filter a file tree to the documents that pass; files and folders left
 * empty are dropped. Files without documents pass through `keepFile`. */
export function filterTree(
  nodes: TreeNode[],
  keep: (doc: LogicalDocument) => boolean,
  keepFile: (file: FileRecord) => boolean,
): TreeNode[] {
  const out: TreeNode[] = [];
  for (const node of nodes) {
    if (node.kind === "folder") {
      const children = filterTree(node.children, keep, keepFile);
      if (children.length > 0) out.push({ ...node, children });
    } else if (node.documents.length === 0) {
      if (keepFile(node.file)) out.push(node);
    } else {
      const documents = node.documents.filter(keep);
      if (documents.length > 0) out.push({ ...node, documents });
    }
  }
  return out;
}

const SIGNAL = /^(\S+) (required|supporting|contrary): /;

/**
 * Classification signals in words: the sidecar reports each matched pattern
 * as "<type> <required|supporting|contrary>: <pattern>". The patterns are
 * configuration, not something a reader needs, so they are counted per type.
 * Any other signal is shown as given.
 */
export function summariseSignals(
  signals: string[],
  typeName: (id: string) => string,
): { type: string; required: number; supporting: number; contrary: number }[] | string[] {
  const counts = new Map<string, { required: number; supporting: number; contrary: number }>();
  const other: string[] = [];
  for (const signal of signals) {
    const m = SIGNAL.exec(signal);
    if (!m) {
      other.push(signal);
      continue;
    }
    const entry = counts.get(m[1]!) ?? { required: 0, supporting: 0, contrary: 0 };
    entry[m[2] as "required" | "supporting" | "contrary"] += 1;
    counts.set(m[1]!, entry);
  }
  if (counts.size === 0) return other;
  return [...counts].map(([id, c]) => ({ type: typeName(id), ...c }));
}
