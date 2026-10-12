import {
  CheckCircle2,
  ExternalLink,
  FileSearch,
  Info,
  MessageSquareText,
  User,
  type LucideIcon,
} from "lucide-react";
import type { Finding, Provenance, SourceColumn } from "@/api/types";
import { Chip } from "@/components/common/Panel";
import { useDocViewer } from "@/components/docviewer/DocViewer";
import { t } from "@/config/terminology";
import { columnValue, diffSegments } from "@/domain/crossVerification";
import { cn } from "@/lib/utils";
import { ReviewValue } from "./ReviewValue";
import { PROVENANCE_TONE } from "./styles";

const PROVENANCE_ICON: Record<Provenance, LucideIcon> = {
  independent: CheckCircle2,
  borrower_supplied: Info,
  declared: MessageSquareText,
};

// Two to four sources side by side; a single column on a phone.
/** A label longer than this (characters) takes the full width of its column. */
const LONG_LABEL = 48;

const GRID: Record<number, string> = {
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-2 lg:grid-cols-3",
  4: "sm:grid-cols-2 xl:grid-cols-4",
};

/** Each source the rule compared, as a column: what it says, where it comes from, what it
 * covers, and the way to its rows and its page. */
export function SourceColumns({
  caseId,
  finding,
  active,
  onToggle,
}: {
  caseId: string;
  finding: Finding;
  active: string | null;
  onToggle: (key: string) => void;
}) {
  const columns = finding.columns ?? [];
  if (columns.length === 0) return null;
  return (
    <div className={cn("grid gap-px border-b border-border bg-border", GRID[columns.length])}>
      {columns.map((column, i) => (
        <ColumnCell
          key={column.key}
          caseId={caseId}
          column={column}
          reference={finding.reference ?? null}
          active={active === column.key}
          onToggle={() => onToggle(column.key)}
          className={columns.length === 3 && i === 2 ? "sm:col-span-2 lg:col-span-1" : undefined}
        />
      ))}
    </div>
  );
}

function ColumnCell({
  caseId,
  column,
  reference,
  active,
  onToggle,
  className,
}: {
  caseId: string;
  column: SourceColumn;
  reference: string | null;
  active: boolean;
  onToggle: () => void;
  className?: string | undefined;
}) {
  const viewer = useDocViewer();
  const rows = column.rows ?? [];
  const first = column.evidence?.[0];
  // An identifier that differs is marked character by character against the value most
  // sources give; any other differing value is shown in red as a whole.
  const segments =
    column.differs && reference !== null && typeof column.value === "string"
      ? diffSegments(columnValue(column), reference)
      : [];
  const marked = segments.some((s) => s.differs);
  // Each column sizes itself to its own width (a container), so four narrow columns keep a
  // 21-character CIN on one line and put the provenance under the label, alike in every column;
  // wider columns show the provenance at the top right and the value at full size. A long label
  // (the documents of a group that agrees) keeps the full width, the provenance under it.
  const longLabel = column.label.length > LONG_LABEL;
  return (
    <div
      className={cn(
        "@container min-w-0 bg-surface p-3 transition-colors",
        active && "bg-accent ring-1 ring-inset ring-primary/40",
        className,
      )}
      data-testid={`xv-column-${column.key}`}
      data-active={active ? "true" : "false"}
      data-differs={column.differs ? "true" : "false"}
    >
      <div
        className={cn(
          "flex flex-col items-start gap-1",
          !longLabel && "@min-[18rem]:flex-row @min-[18rem]:justify-between @min-[18rem]:gap-2",
        )}
      >
        <p className={cn("field-label min-w-0 break-words", !longLabel && "@min-[18rem]:flex-1")}>
          {column.label}
        </p>
        <ProvenanceTags provenance={column.provenance ?? []} beside={!longLabel} />
      </div>
      <p
        className={cn(
          "tabular mt-1 break-words text-[16px] font-semibold leading-tight @min-[16.5rem]:text-[19px]",
          column.differs && !marked ? "text-destructive" : "text-foreground",
        )}
        data-testid="xv-column-value"
      >
        {marked
          ? segments.map((s, i) =>
              s.differs ? (
                <mark
                  key={i}
                  className="rounded-sm bg-destructive/15 px-px text-destructive underline decoration-destructive/60 decoration-2 underline-offset-4"
                  data-testid="xv-diff"
                >
                  {s.text}
                </mark>
              ) : (
                <span key={i}>{s.text}</span>
              ),
            )
          : columnValue(column)}
      </p>
      {(column.differs || column.relies_on_manual || column.awaiting_review) && (
        <p className="mt-1.5 flex flex-wrap gap-1">
          {column.differs && <Chip tone="critical">{t("crossVerification.column.differs")}</Chip>}
          {column.relies_on_manual && (
            <Chip tone="flag">
              <User className="h-3 w-3" aria-hidden /> {t("crossVerification.column.manual")}
            </Chip>
          )}
          {column.awaiting_review && (
            <ReviewValue caseId={caseId} fieldIds={column.field_ids ?? []} evidence={first} />
          )}
        </p>
      )}
      {column.coverage && (
        <p className="mt-1.5 break-words text-[11.5px] leading-snug text-muted-foreground">
          {column.coverage}
        </p>
      )}
      {(rows.length > 0 || first) && (
        <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1">
          {rows.length > 0 && (
            <button
              type="button"
              onClick={onToggle}
              aria-expanded={active}
              className="inline-flex items-center gap-1 text-[11.5px] font-medium text-primary hover:underline"
              data-testid="xv-open-evidence"
            >
              <FileSearch className="h-3 w-3" aria-hidden />
              {active
                ? t("crossVerification.column.hideEvidence")
                : t("crossVerification.column.openEvidence")}
            </button>
          )}
          {first && (
            <button
              type="button"
              onClick={() =>
                viewer.open({
                  caseId,
                  documentId: first.document_id,
                  page: first.page,
                  bbox: first.bbox ?? null,
                })
              }
              className="inline-flex items-center gap-1 text-[11.5px] text-muted-foreground hover:text-primary hover:underline"
              data-testid="xv-trace"
            >
              {t("crossVerification.column.trace")}
              <ExternalLink className="h-2.5 w-2.5" aria-hidden />
            </button>
          )}
        </p>
      )}
    </div>
  );
}

/** The provenance of a column's sources; `beside` the label at the top right where the column is
 * wide enough. */
function ProvenanceTags({ provenance, beside }: { provenance: Provenance[]; beside: boolean }) {
  if (provenance.length === 0) return null;
  return (
    <span
      className={cn(
        "flex shrink-0 flex-wrap gap-1",
        beside && "@min-[18rem]:max-w-[60%] @min-[18rem]:justify-end",
      )}
    >
      {provenance.map((p) => {
        const Icon = PROVENANCE_ICON[p];
        return (
          <Chip key={p} tone={PROVENANCE_TONE[p]}>
            <Icon className="h-2.5 w-2.5" aria-hidden /> {t(`crossVerification.provenance.${p}`)}
          </Chip>
        );
      })}
    </span>
  );
}
