import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ChevronLeft, ChevronRight, FileText, X } from "lucide-react";
import type { FieldValue } from "@/api/types";
import { ErrorState } from "@/components/common/States";
import { Chip } from "@/components/common/Panel";
import { Skeleton } from "@/components/ui/skeleton";
import { t } from "@/config/terminology";
import {
  pageGrade,
  pageRange,
  useCaseDocuments,
  useCaseFiles,
  useDocumentTypes,
  usePageImage,
} from "@/domain/documents";
import { confidencePct, effectiveValue, fieldLabel, formatValue } from "@/domain/extraction";
import { GradeChip } from "@/components/documents/chips";
import { cn } from "@/lib/utils";
import { ViewerDecision } from "./ViewerDecision";

// The evidence viewer (F-16): any value, figure or flag opens its source
// page in one click, with the region highlighted where known. The layout is
// the prototype's document viewer; pages are the images the engine renders
// (F-05.6), so no PDF library is needed in the browser.

export type ViewerRequest = {
  caseId: string;
  documentId: string;
  /** Absolute page in the source file; defaults to the document's first page. */
  page?: number;
  /** Normalised [x0, y0, x1, y1], top-left origin. */
  bbox?: [number, number, number, number] | null;
  /** The value being traced, for its confidence and method. */
  field?: FieldValue;
  /** Open with the correction form showing (the row's Correct). */
  correct?: boolean;
  /** Two or more sources shown side by side (F-16.2), for a finding's sides. */
  compare?: CompareSource[];
};

export type CompareSource = {
  documentId: string;
  page?: number;
  bbox?: [number, number, number, number] | null;
  /** What this source says, e.g. "Company PAN: AAACK1234F". */
  label: string;
};

type Ctx = { open: (request: ViewerRequest) => void; close: () => void };

const DocViewerContext = createContext<Ctx | null>(null);

export function useDocViewer(): Ctx {
  const ctx = useContext(DocViewerContext);
  if (!ctx) throw new Error("useDocViewer must be used inside DocViewerProvider");
  return ctx;
}

export function DocViewerProvider({ children }: { children: ReactNode }) {
  const [request, setRequest] = useState<ViewerRequest | null>(null);
  const close = useCallback(() => setRequest(null), []);
  const value = useMemo<Ctx>(() => ({ open: setRequest, close }), [close]);

  useEffect(() => {
    if (!request) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [request, close]);

  return (
    <DocViewerContext.Provider value={value}>
      {children}
      {request && (request.compare?.length ?? 0) >= 2 && (
        <ComparePanel caseId={request.caseId} sources={request.compare ?? []} onClose={close} />
      )}
      {request && (request.compare?.length ?? 0) < 2 && (
        <ViewerPanel
          key={`${request.documentId}-${request.page ?? ""}`}
          request={request}
          onClose={close}
        />
      )}
    </DocViewerContext.Provider>
  );
}

function ViewerPanel({ request, onClose }: { request: ViewerRequest; onClose: () => void }) {
  const documents = useCaseDocuments(request.caseId);
  const files = useCaseFiles(request.caseId);
  const types = useDocumentTypes();
  const doc = documents.data?.find((d) => d.id === request.documentId);
  const file = files.data?.find((f) => f.id === doc?.file_id);
  const first = doc?.page_from ?? request.page ?? 1;
  const last = doc?.page_to ?? request.page ?? 1;
  const [page, setPage] = useState(request.page ?? first);
  const evidencePage = request.page ?? first;
  const grade = doc ? pageGrade(doc, page) : undefined;
  const typeNames = doc?.classification?.types.length
    ? doc.classification.types.map(types.name).join(" + ")
    : t("document.unclassified");
  const field = request.field;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="evidence-viewer">
      <button
        type="button"
        aria-label={t("viewer.close")}
        onClick={onClose}
        className="absolute inset-0 bg-foreground/25"
      />
      <aside
        className="relative flex h-full w-full max-w-[760px] flex-col border-l border-border bg-surface-muted shadow-2xl"
        role="dialog"
        aria-label={t("viewer.title")}
      >
        <header className="flex items-start gap-3 border-b border-border bg-surface px-4 py-3">
          <div className="mt-0.5 rounded border border-border bg-surface-muted p-1.5">
            <FileText className="h-3.5 w-3.5 text-primary" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="field-label">{t("viewer.title")}</p>
            <p
              className="truncate text-[14px] font-semibold text-foreground"
              data-testid="viewer-type"
            >
              {typeNames}
            </p>
            <p
              className="tabular truncate text-[11px] text-muted-foreground"
              data-testid="viewer-file"
            >
              {file?.original_name ?? request.documentId}
              {doc && ` · ${pageRange(doc)}`}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted"
            aria-label={t("viewer.close")}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </header>

        <div className="space-y-2 border-b border-border bg-surface px-4 py-2.5">
          {field && (
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px]">
              <span className="font-medium text-foreground">{fieldLabel(field.field)}</span>
              <span className="tabular text-foreground" data-testid="viewer-value">
                {formatValue(effectiveValue(field))}
              </span>
              <span className="text-muted-foreground">
                {t("viewer.confidence")}{" "}
                <span className="tabular text-foreground">{confidencePct(field.confidence)}</span>
              </span>
              <span className="text-muted-foreground">
                {t("viewer.method")}{" "}
                <span className="text-foreground">{t(`fieldMethod.${field.method}`)}</span>
              </span>
            </div>
          )}
          {field && <ViewerDecision field={field} correct={request.correct ?? false} />}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setPage((n) => Math.max(first, n - 1))}
              disabled={page <= first}
              className="rounded border border-border p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
              aria-label={t("viewer.previousPage")}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
            <span className="tabular text-[11.5px] text-muted-foreground" data-testid="viewer-page">
              {first === last
                ? t("viewer.pageOne", { page })
                : t("viewer.pageOf", { page, first, last })}
            </span>
            <button
              type="button"
              onClick={() => setPage((n) => Math.min(last, n + 1))}
              disabled={page >= last}
              className="rounded border border-border p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
              aria-label={t("viewer.nextPage")}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
            {grade && <GradeChip grade={grade} />}
            {request.bbox && page === evidencePage && (
              <Chip tone="flag">{t("viewer.regionHighlighted")}</Chip>
            )}
            {page !== evidencePage && (
              <button
                type="button"
                onClick={() => setPage(evidencePage)}
                className="ml-auto text-[11.5px] font-medium text-primary hover:underline"
              >
                {t("viewer.backToEvidence", { page: evidencePage })}
              </button>
            )}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-auto bg-surface-muted px-4 py-4">
          <PageImage
            caseId={request.caseId}
            documentId={request.documentId}
            page={page}
            bbox={page === evidencePage ? (request.bbox ?? null) : null}
          />
        </div>
      </aside>
    </div>
  );
}

/** F-16.2: the sources of a finding side by side, each at its own page. */
function ComparePanel({
  caseId,
  sources,
  onClose,
}: {
  caseId: string;
  sources: CompareSource[];
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end" data-testid="evidence-compare">
      <button
        type="button"
        aria-label={t("viewer.close")}
        onClick={onClose}
        className="absolute inset-0 bg-foreground/25"
      />
      <aside
        className="relative flex h-full w-full max-w-[1500px] flex-col border-l border-border bg-surface-muted shadow-2xl"
        role="dialog"
        aria-label={t("viewer.compareTitle")}
      >
        <header className="flex items-center gap-3 border-b border-border bg-surface px-4 py-3">
          <FileText className="h-4 w-4 text-primary" />
          <p className="flex-1 text-[14px] font-semibold text-foreground">
            {t("viewer.compareTitle")}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted"
            aria-label={t("viewer.close")}
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </header>
        <div
          className={cn(
            "grid min-h-0 flex-1 gap-px bg-border",
            sources.length === 2 ? "grid-cols-2" : "grid-cols-2 xl:grid-cols-3",
          )}
        >
          {sources.slice(0, 3).map((source, i) => (
            <ComparePane key={`${source.documentId}-${i}`} caseId={caseId} source={source} />
          ))}
        </div>
      </aside>
    </div>
  );
}

function ComparePane({ caseId, source }: { caseId: string; source: CompareSource }) {
  const documents = useCaseDocuments(caseId);
  const files = useCaseFiles(caseId);
  const types = useDocumentTypes();
  const doc = documents.data?.find((d) => d.id === source.documentId);
  const file = files.data?.find((f) => f.id === doc?.file_id);
  const first = doc?.page_from ?? source.page ?? 1;
  const last = doc?.page_to ?? source.page ?? 1;
  const evidencePage = source.page ?? first;
  const [page, setPage] = useState(evidencePage);
  const typeNames = doc?.classification?.types.length
    ? doc.classification.types.map(types.name).join(" + ")
    : "";
  return (
    <section className="flex min-h-0 flex-col bg-surface-muted" data-testid="compare-pane">
      <div className="space-y-1 border-b border-border bg-surface px-4 py-2.5">
        <p className="text-[12.5px] font-semibold text-foreground">{source.label}</p>
        <p className="tabular truncate text-[11px] text-muted-foreground">
          {[typeNames, file?.original_name].filter(Boolean).join(" · ")}
        </p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPage((n) => Math.max(first, n - 1))}
            disabled={page <= first}
            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
            aria-label={t("viewer.previousPage")}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="tabular text-[11.5px] text-muted-foreground" data-testid="compare-page">
            {first === last
              ? t("viewer.pageOne", { page })
              : t("viewer.pageOf", { page, first, last })}
          </span>
          <button
            type="button"
            onClick={() => setPage((n) => Math.min(last, n + 1))}
            disabled={page >= last}
            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
            aria-label={t("viewer.nextPage")}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-3 py-3">
        <PageImage
          caseId={caseId}
          documentId={source.documentId}
          page={page}
          bbox={page === evidencePage ? (source.bbox ?? null) : null}
        />
      </div>
    </section>
  );
}

export function PageImage({
  caseId,
  documentId,
  page,
  bbox,
}: {
  caseId: string;
  documentId: string;
  page: number;
  bbox: [number, number, number, number] | null;
}) {
  const image = usePageImage(caseId, documentId, page);
  if (image.isError) return <ErrorState error={image.error} compact />;
  if (!image.url) {
    return (
      <div
        className="mx-auto w-full max-w-[640px]"
        role="status"
        aria-label={t("viewer.rendering")}
      >
        <Skeleton className="aspect-[1/1.41] w-full" />
      </div>
    );
  }
  const [x0, y0, x1, y1] = bbox ?? [0, 0, 0, 0];
  return (
    <div className="relative mx-auto w-full max-w-[640px]">
      <img
        src={image.url}
        alt={t("viewer.pageAlt", { page })}
        className="block w-full rounded border border-border bg-white shadow-sm"
        data-testid="viewer-image"
      />
      {bbox && (
        <span
          aria-hidden
          data-testid="viewer-bbox"
          className={cn("pointer-events-none absolute rounded-[2px] bg-flag/30 ring-2 ring-flag")}
          style={{
            left: `${x0 * 100}%`,
            top: `${y0 * 100}%`,
            width: `${(x1 - x0) * 100}%`,
            height: `${(y1 - y0) * 100}%`,
          }}
        />
      )}
    </div>
  );
}
