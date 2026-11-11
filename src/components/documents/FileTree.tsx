import { createContext, useContext, useState, type CSSProperties, type ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Folder,
  HelpCircle,
  RotateCw,
} from "lucide-react";
import type { ChecklistItemState, FileRecord, LogicalDocument, ReviewItem } from "@/api/types";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { useCan } from "@/domain/session";
import {
  countFiles,
  formatBytes,
  instanceLabel,
  isDocumentInProgress,
  pageRange,
  useDocumentTypes,
  useReadAgain,
  type TreeFile,
  type TreeNode,
} from "@/domain/documents";
import { confidencePct } from "@/domain/extraction";
import { Chip } from "@/components/common/Panel";
import { cn } from "@/lib/utils";
import { DocumentActions } from "./DocumentActions";
import { DocumentDetail } from "./DocumentDetail";
import { FileStatusChip } from "./chips";
import { IntegrityChip, IntegrityPanel } from "./IntegrityPanel";
import { hasIntegrity, integrityNeedsPerson, integrityReason, stateOf } from "@/domain/integrity";
import { StageTrack } from "./StageTrack";

/** What every row of the register needs to know about the case. */
export type RegisterContext = {
  borrower: string;
  /** Open review items for a document (type, quality, split, party). */
  itemsFor: (documentId: string) => ReviewItem[];
  /** Checklist defects that name a document. */
  defectsFor: (documentId: string) => ChecklistItemState[];
  /** Checklist items a document is counted towards. */
  satisfiesFor: (documentId: string) => ChecklistItemState[];
};

const Register = createContext<RegisterContext>({
  borrower: "",
  itemsFor: () => [],
  defectsFor: () => [],
  satisfiesFor: () => [],
});

/** Below this a type was placed with doubt, and its confidence is said in amber. */
const SURE = 0.85;

/** The register's columns: one row per document (a file with none has one row of its own). On a
 * phone each row is a short card: the file, then a line for each cell with its column named. The
 * row's own text size is the file name's, so every cell's first line sits on the same line. */
export const REGISTER_ROW =
  "flex flex-col gap-1.5 px-4 py-2.5 text-[12.5px] leading-normal md:grid md:py-2 md:grid-cols-[minmax(0,2.3fr)_3.5rem_minmax(0,1.6fr)_5.5rem_minmax(0,1.8fr)_minmax(0,1.3fr)] md:gap-x-3";
const COLUMNS = ["file", "pages", "type", "confidence", "integrity", "satisfies"] as const;
type Column = (typeof COLUMNS)[number];

/** A column's alignment on the laptop grid, the same in its title and its cells: the confidence is
 * a figure, so it sits right; the integrity check keeps a gap from it. */
const ALIGN: Partial<Record<Column, string>> = {
  confidence: "md:text-right",
  integrity: "md:pl-4",
};

/** The column titles, once above every section. */
export function RegisterHead() {
  return (
    <div
      className={cn(
        REGISTER_ROW,
        "hidden border-b border-border bg-muted/40 py-1.5 text-[10.5px] font-semibold uppercase tracking-wide text-muted-foreground md:grid",
      )}
      data-testid="register-head"
    >
      {COLUMNS.map((c) => (
        <span key={c} className={ALIGN[c]}>
          {t(`documents.table.${c}`)}
        </span>
      ))}
    </div>
  );
}

/** The files of a case as a table: one row per logical document (FRD F-05), with
 * its type, how sure the placing was, the file's integrity check, what it counts
 * towards on the checklist, and what it needs, if anything (§6). */
export function FileTree({
  caseId,
  nodes,
  files,
  context,
  testId = "file-tree",
}: {
  caseId: string;
  nodes: TreeNode[];
  files: FileRecord[];
  context?: RegisterContext;
  testId?: string;
}) {
  const inner = (
    <div className="divide-y divide-border" data-testid={testId}>
      {nodes.map((node) => (
        <Node
          key={node.kind === "file" ? node.file.id : node.path}
          caseId={caseId}
          node={node}
          files={files}
          depth={0}
        />
      ))}
    </div>
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
    return <FileRows caseId={caseId} node={node} files={files} depth={depth} />;
  return (
    <div data-testid="tree-folder">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-1.5 px-4 py-1.5 text-left hover:bg-surface-muted/60"
        style={{ paddingLeft: 16 + depth * 14 }}
      >
        {open ? (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
        <Folder className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        <span className="min-w-0 text-[12.5px] font-medium text-foreground [overflow-wrap:anywhere]">
          {breakable(node.name)}
        </span>
        <span className="shrink-0 text-[11px] text-muted-foreground">
          {t("documents.fileCount", { n: countFiles(node.children) })}
        </span>
      </button>
      {open && (
        <div className="divide-y divide-border border-t border-border">
          {node.children.map((child) => (
            <Node
              key={child.kind === "file" ? child.file.id : child.path}
              caseId={caseId}
              node={child}
              files={files}
              depth={depth + 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/** The file's integrity check, in its column: its status and one reason when a
 * person should look (a click opens the summary and the decision), else one quiet word. */
function IntegrityCell({
  file,
  open,
  onToggle,
}: {
  file: FileRecord;
  open: boolean;
  onToggle: () => void;
}) {
  if (integrityNeedsPerson(file)) {
    const reason = integrityReason(file);
    return (
      <span className="flex min-w-0 flex-col items-start gap-0.5">
        <IntegrityChip file={file} open={open} onToggle={onToggle} />
        {reason && (
          <span className="text-[11px] text-muted-foreground" data-testid="integrity-reason">
            {reason}
          </span>
        )}
      </span>
    );
  }
  return (
    <span className="text-[11px] text-muted-foreground" data-testid="integrity-quiet">
      {hasIntegrity(file) ? (
        t(`documents.table.integrityState.${stateOf(file)}`)
      ) : (
        <span className="hidden md:inline">{t("documents.table.none")}</span>
      )}
    </span>
  );
}

/** One file: a row for each of its documents, or one row of its own while it has none. */
function FileRows({
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
  const [showIntegrity, setShowIntegrity] = useState(false);
  const canUpload = useCan("document.upload");
  const readAgain = useReadAgain(caseId);
  const { defectsFor } = useContext(Register);
  const integrity = (
    <IntegrityCell file={file} open={showIntegrity} onToggle={() => setShowIntegrity((v) => !v)} />
  );
  const noIntegrity = !integrityNeedsPerson(file) && !hasIntegrity(file);
  const panel = showIntegrity && integrityNeedsPerson(file) && (
    <IntegrityPanel caseId={caseId} file={file} documents={documents} depth={depth} />
  );

  if (documents.length === 0) {
    const original = file.duplicate_of ? files.find((f) => f.id === file.duplicate_of) : undefined;
    const reading = file.status === "registered";
    return (
      <div data-testid="tree-file" data-status={file.status} style={indent(depth, false)}>
        <div className={REGISTER_ROW}>
          <FileCell file={file} depth={depth}>
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
          </FileCell>
          <Empty />
          {/* A file with no documents yet: where it stands, in the type's place. */}
          <RegisterCell column="type">
            <span className="flex flex-wrap items-center gap-1.5">
              {reading ? <StageTrack doc={undefined} /> : <FileStatusChip status={file.status} />}
              {file.status === "exception" && canUpload && (
                <button
                  type="button"
                  onClick={() => readAgain.mutate(file.id)}
                  disabled={readAgain.isPending}
                  title={t("documents.readAgainHelp")}
                  data-testid="read-again"
                  className="inline-flex shrink-0 items-center gap-1 rounded border border-primary/40 bg-primary/5 px-1.5 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/10 disabled:opacity-50"
                >
                  <RotateCw className={readAgain.isPending ? "h-3 w-3 animate-spin" : "h-3 w-3"} />
                  {t(readAgain.isPending ? "documents.readingAgain" : "documents.readAgain")}
                </button>
              )}
            </span>
          </RegisterCell>
          <Empty column="confidence" />
          <RegisterCell column="integrity" empty={noIntegrity}>
            {integrity}
          </RegisterCell>
          <Empty />
        </div>
        {panel}
      </div>
    );
  }

  // One file split into parts: its integrity check is the file's, said once; a checklist defect
  // that names several parts is shown on the first of them.
  const seen = new Set<string>();
  const firstDefects = documents.map((doc) =>
    defectsFor(doc.id).filter((d) => !seen.has(d.item_id) && seen.add(d.item_id)),
  );
  return (
    <div data-testid="tree-file" data-status={file.status}>
      {documents.map((doc, i) => (
        <DocumentRow
          key={doc.id}
          caseId={caseId}
          doc={doc}
          file={file}
          depth={depth}
          part={documents.length > 1 ? i + 1 : null}
          integrity={i === 0 ? integrity : <SameFile />}
          integrityEmpty={i === 0 && noIntegrity}
          panel={i === 0 ? panel : null}
          shownDefects={firstDefects[i]!.length}
        />
      ))}
    </div>
  );
}

/** A later part of a split file: its integrity check is the file's, on the first part. */
function SameFile() {
  return (
    <span className="text-[11px] text-muted-foreground" data-testid="integrity-same-file">
      {t("documents.table.sameFile")}
    </span>
  );
}

/** A cell's column name, on a phone only, where the row's cells stand without their headings. */
function PhoneLabel({ column }: { column: Column }) {
  return (
    <span className="w-[5.25rem] shrink-0 pt-[3px] text-[10px] font-semibold uppercase leading-tight tracking-wide text-muted-foreground md:hidden">
      {t(`documents.table.phone.${column}`)}
    </span>
  );
}

/** How far a row's cells and actions sit in on a phone: under the file name, past its toggle. */
function indent(depth: number, toggle: boolean): CSSProperties {
  return { ["--indent" as string]: `${depth * 14 + (toggle ? 26 : 0)}px` };
}

/** One cell: a column of the grid on a laptop; on a phone a line of its own with the column named
 * beside it, left out when it has nothing to say. */
export function RegisterCell({
  column,
  empty = false,
  className,
  children,
}: {
  column: Column;
  empty?: boolean;
  /** Placement on the laptop grid, e.g. a span over columns that have nothing to say. */
  className?: string;
  children: ReactNode;
}) {
  return (
    <span
      className={cn(
        "flex min-w-0 items-start gap-2 max-md:pl-[var(--indent,0px)] md:block",
        ALIGN[column],
        empty && "max-md:hidden",
        className,
      )}
    >
      <PhoneLabel column={column} />
      <span className="min-w-0 flex-1">{children}</span>
    </span>
  );
}

/** A laptop cell with nothing in it, aligned as its column is. */
function Empty({ column }: { column?: Column }) {
  return (
    <span
      className={cn("hidden text-[11px] text-muted-foreground md:inline", column && ALIGN[column])}
    >
      {t("documents.table.none")}
    </span>
  );
}

/** A file name that may wrap after an underscore or hyphen, so a long name breaks between its
 * words rather than inside one (and never before its extension). */
function breakable(name: string): ReactNode[] {
  return name.split(/(?<=[_-])/).flatMap((part, i) => (i === 0 ? [part] : [<wbr key={i} />, part]));
}

function FileCell({
  file,
  depth,
  part,
  pages,
  toggle,
  children,
}: {
  file: FileRecord;
  depth: number;
  part?: number | null;
  /** The document's pages: in their own column on a laptop, beside the size on a phone. */
  pages?: string;
  toggle?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <span className="flex min-w-0 items-start gap-1.5" style={{ paddingLeft: depth * 14 }}>
      {toggle}
      <span className="min-w-0">
        <span className="block text-[12.5px] font-medium text-foreground">
          <span className="[overflow-wrap:anywhere]">{breakable(file.original_name)}</span>
          {part != null && (
            <span className="whitespace-nowrap font-normal text-muted-foreground">
              {" › "}
              {t("documents.table.part", { n: part })}
            </span>
          )}
        </span>
        <span className="block text-[11px] text-muted-foreground">
          {formatBytes(file.size_bytes)}
          {pages && <span className="tabular md:hidden"> · {pages}</span>}
          {children}
        </span>
      </span>
    </span>
  );
}

/** What a document needs, if anything: shown under its type. */
function DocStatus({ caseId, doc }: { caseId: string; doc: LogicalDocument }) {
  const canReadData = useCan("data.read");
  const canReview = useCan("review.read");
  if (isDocumentInProgress(doc)) return <StageTrack doc={doc} />;
  if (doc.status === "unclassified" || doc.status === "in_exception")
    return canReview ? (
      <Chip tone="flag">{t("documents.table.needsPerson")}</Chip>
    ) : (
      <span className="text-[11px] text-muted-foreground" data-testid="waiting-review">
        {t("documents.waitingReview")}
      </span>
    );
  if (doc.status === "in_review")
    return canReadData ? (
      <Link
        to="/appraisals/$caseId/extraction"
        params={{ caseId }}
        hash="fields"
        className="text-[11px] font-medium text-primary hover:underline"
        data-testid="check-values"
      >
        {t("documents.checkValues")} →
      </Link>
    ) : (
      <Chip tone="flag">{t("documents.table.needsPerson")}</Chip>
    );
  if (doc.status === "duplicate" || doc.status === "superseded")
    return <Chip tone="muted">{t(`documents.table.docStatus.${doc.status}`)}</Chip>;
  // Placed and read: nothing to say.
  return null;
}

function DocumentRow({
  caseId,
  doc,
  file,
  depth,
  part,
  integrity,
  integrityEmpty,
  panel,
  shownDefects,
}: {
  caseId: string;
  doc: LogicalDocument;
  file: FileRecord;
  depth: number;
  part: number | null;
  integrity: ReactNode;
  /** The file has no integrity check to show: a phone leaves the line out. */
  integrityEmpty: boolean;
  panel: ReactNode;
  /** The checklist defects not already shown on an earlier part of the same file. */
  shownDefects: number;
}) {
  const viewer = useDocViewer();
  const types = useDocumentTypes();
  const { borrower, itemsFor, defectsFor, satisfiesFor } = useContext(Register);
  const [open, setOpen] = useState(false);
  const classified = (doc.classification?.types.length ?? 0) > 0;
  const confidence = doc.classification?.confidence;
  const items = itemsFor(doc.id);
  const defects = defectsFor(doc.id);
  const satisfies = satisfiesFor(doc.id);

  return (
    <div data-testid="tree-document" data-document-id={doc.id} style={indent(depth, true)}>
      <div className={REGISTER_ROW}>
        <FileCell
          file={file}
          depth={depth}
          part={part}
          pages={pageRange(doc)}
          toggle={
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
          }
        />
        <span className="tabular hidden text-[11.5px] text-muted-foreground md:inline">
          {pageRange(doc)}
        </span>
        <RegisterCell column="type">
          <span className="flex min-w-0 flex-col items-start gap-1">
            <button
              type="button"
              onClick={() => viewer.open({ caseId, documentId: doc.id, page: doc.page_from })}
              className="text-left text-[12.5px] text-foreground hover:text-primary hover:underline"
            >
              {classified ? (
                <span data-testid="document-type">
                  {doc.classification!.types.map(types.name).join(" + ")}
                  {instanceLabel(doc.instance_key) && (
                    <span className="text-muted-foreground">
                      {" "}
                      · {instanceLabel(doc.instance_key)}
                    </span>
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
            {doc.classification?.exit_tier === "sibling" && (
              <Chip tone="info" title={t("documents.foundWithinHelp")}>
                <span data-testid="found-within">{t("documents.foundWithin")}</span>
              </Chip>
            )}
            {doc.label_mismatch && (
              <Chip tone="flag" title={t("documents.labelMismatchHelp")}>
                <AlertTriangle className="h-3 w-3" />
                <span data-testid="label-mismatch">
                  {t("documents.labelMismatch", { label: file.label_hint ?? file.original_name })}
                </span>
              </Chip>
            )}
            <DocStatus caseId={caseId} doc={doc} />
          </span>
        </RegisterCell>
        <RegisterCell column="confidence" empty={!classified || confidence == null}>
          <span
            className={cn(
              "tabular text-[12px] font-medium",
              confidence != null && confidence < SURE ? "text-flag-foreground" : "text-foreground",
            )}
            data-testid="document-confidence"
          >
            {classified && confidence != null ? (
              confidencePct(confidence)
            ) : (
              <span className="hidden md:inline">{t("documents.table.none")}</span>
            )}
          </span>
        </RegisterCell>
        <RegisterCell column="integrity" empty={integrityEmpty}>
          {integrity}
        </RegisterCell>
        <RegisterCell column="satisfies" empty={satisfies.length === 0 && shownDefects === 0}>
          <span className="flex min-w-0 flex-col items-start gap-1 text-[11.5px] text-foreground">
            {satisfies.length > 0 ? (
              <span data-testid="document-satisfies">
                {satisfies.map((i) => i.name).join(", ")}
              </span>
            ) : (
              <span className="hidden text-muted-foreground md:inline">
                {t("documents.table.none")}
              </span>
            )}
            {shownDefects > 0 && (
              <Chip tone="critical">
                <span data-testid="defect-count">
                  {t("documents.defects", { n: shownDefects })}
                </span>
              </Chip>
            )}
          </span>
        </RegisterCell>
      </div>
      {panel}
      {items.length > 0 && (
        <div className="pb-2.5 pl-10 pr-4 max-md:pl-[calc(1rem+var(--indent,0px))]">
          <DocumentActions doc={doc} items={items} borrower={borrower} />
        </div>
      )}
      {open && <DocumentDetail caseId={caseId} doc={doc} file={file} defects={defects} />}
    </div>
  );
}
