import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ChevronLeft, ChevronRight, FileText, Maximize2, RotateCw, X } from "lucide-react";
import { Link } from "@tanstack/react-router";
import type { FieldValue } from "@/api/types";
import { ErrorState } from "@/components/common/States";
import { Chip } from "@/components/common/Panel";
import { Skeleton } from "@/components/ui/skeleton";
import { t, tOr } from "@/config/terminology";
import {
  pageGrade,
  pageRange,
  useCaseDocuments,
  useCaseFiles,
  useDocumentTypes,
  useFileFigures,
  usePageImage,
  useRecheckIntegrity,
} from "@/domain/documents";
import { marksOf, stateOf } from "@/domain/integrity";
import { IntegrityOverlay } from "@/components/documents/IntegrityOverlay";
import { StateChip } from "@/components/documents/IntegritySummary";
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
  /** Every page a figure rests on, to step through: the viewer opens at `index` (the first by
   * default) and offers the rest, each named by its document type and page. */
  set?: EvidenceStop[];
  index?: number;
};

export type EvidenceStop = {
  documentId: string;
  page: number;
  bbox?: [number, number, number, number] | null;
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

/** The viewer opened at one of the pages a figure rests on, with the others to step to. The same
 * page of a document is offered once. */
export function evidenceRequest(
  caseId: string,
  evidence: readonly {
    document_id: string;
    page: number;
    bbox?: [number, number, number, number] | null;
  }[],
  at: { document_id: string; page: number } | undefined = evidence[0],
): ViewerRequest | null {
  const seen = new Set<string>();
  const set: EvidenceStop[] = [];
  for (const e of evidence) {
    const key = `${e.document_id}:${e.page}`;
    if (seen.has(key)) continue;
    seen.add(key);
    set.push({ documentId: e.document_id, page: e.page, bbox: e.bbox ?? null });
  }
  const index = Math.max(
    0,
    set.findIndex((s) => s.documentId === at?.document_id && s.page === at?.page),
  );
  const stop = set[index];
  return stop ? { caseId, ...stop, set, index } : null;
}

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
          onStep={(index) =>
            setRequest((now) => {
              const stop = now?.set?.[index];
              return now && stop ? { ...now, ...stop, index } : now;
            })
          }
        />
      )}
    </DocViewerContext.Provider>
  );
}

function ViewerPanel({
  request,
  onClose,
  onStep,
}: {
  request: ViewerRequest;
  onClose: () => void;
  onStep: (index: number) => void;
}) {
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
  // F-07A: what the file's integrity checks found, drawn on the page shown.
  const found = file?.integrity;
  const { marks, pagesReplaced } = useMemo(() => marksOf(found ?? []), [found]);
  const [showMarks, setShowMarks] = useState(true);
  const [showFigures, setShowFigures] = useState(false);
  const [focus, setFocus] = useState<string | null>(null);
  const figures = useFileFigures(request.caseId, file?.id, showFigures);
  const marksHere = marks.filter((m) => m.page === page);
  const onPage = showMarks ? marksHere : [];
  const figuresHere = showFigures ? (figures.data ?? []).filter((f) => f.page === page) : undefined;
  // Kept apart on the page: suspicious marks, what is only in the file's records
  // (metadata observations), and checks that have not run.
  const status = file?.integrity_status;
  const onRecordsOnly = (codes: readonly string[]) =>
    codes.filter((c) => !(found ?? []).find((f) => f.code === c)?.evidence?.some((e) => e.rect));
  const recordsOnly = onRecordsOnly(status?.suspicious ?? []);
  const metadataOnly = onRecordsOnly(status?.informational ?? []);
  const pending = status?.pending ?? [];
  const recheck = useRecheckIntegrity(request.caseId);
  const canRecheck = file?.status === "registered" && pending.length > 0;
  const title = (c: string) => tOr(`fileIntegrity.check.${c}`, c);

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
          {(request.set?.length ?? 0) > 1 && (
            <EvidenceSteps
              set={request.set!}
              index={request.index ?? 0}
              name={(id) => {
                const d = documents.data?.find((x) => x.id === id);
                return d?.classification?.types.length
                  ? d.classification.types.map(types.name).join(" + ")
                  : t("document.unclassified");
              }}
              onStep={onStep}
            />
          )}
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
          {file && stateOf(file) !== "not_applicable" && stateOf(file) !== "not_checked" && (
            <div
              className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-border pt-2 text-[11.5px]"
              data-testid="viewer-integrity"
            >
              {file && <StateChip file={file} />}
              <label className="inline-flex cursor-pointer items-center gap-1.5 text-muted-foreground">
                <input
                  type="checkbox"
                  checked={showMarks}
                  onChange={(e) => setShowMarks(e.target.checked)}
                  className="h-3.5 w-3.5"
                  data-testid="viewer-show-marks"
                />
                {t("fileIntegrity.overlay.marks")} ({marksHere.length})
              </label>
              <label className="inline-flex cursor-pointer items-center gap-1.5 text-muted-foreground">
                <input
                  type="checkbox"
                  checked={showFigures}
                  onChange={(e) => setShowFigures(e.target.checked)}
                  className="h-3.5 w-3.5"
                  data-testid="viewer-show-figures"
                />
                {t("fileIntegrity.overlay.figures")}
              </label>
              <Link
                to="/appraisals/$caseId/files/$fileId/integrity"
                params={{ caseId: request.caseId, fileId: file.id }}
                onClick={onClose}
                className="ml-auto inline-flex items-center gap-1 font-medium text-primary hover:underline"
              >
                <Maximize2 className="h-3 w-3" />
                {t("fileIntegrity.view.open")}
              </Link>
              {recordsOnly.length > 0 && (
                <p
                  className="w-full text-[11px] text-destructive"
                  data-testid="viewer-records-only"
                >
                  {t("fileIntegrity.overlay.recordsOnly", {
                    checks: recordsOnly.map(title).join(", "),
                  })}
                </p>
              )}
              {metadataOnly.length > 0 && (
                <p
                  className="w-full text-[11px] text-flag-foreground"
                  data-testid="viewer-metadata-only"
                >
                  {t("fileIntegrity.overlay.metadataOnly", {
                    checks: metadataOnly.map(title).join(", "),
                  })}
                </p>
              )}
              {pending.length > 0 && (
                <p
                  className="flex w-full flex-wrap items-center gap-2 text-[11px] text-muted-foreground"
                  data-testid="viewer-pending"
                >
                  {t("fileIntegrity.overlay.pending", { n: pending.length })}
                  {canRecheck && (
                    <button
                      type="button"
                      onClick={() => recheck.mutate(file.id)}
                      disabled={recheck.isPending || recheck.isSuccess}
                      className="inline-flex items-center gap-1 rounded border border-primary/40 px-1.5 py-0.5 font-medium text-primary hover:bg-primary/10 disabled:opacity-60"
                    >
                      <RotateCw
                        className={cn(
                          "h-3 w-3",
                          (recheck.isPending || recheck.isSuccess) && "animate-spin",
                        )}
                      />
                      {t(
                        recheck.isPending || recheck.isSuccess
                          ? "fileIntegrity.rechecking"
                          : "fileIntegrity.summary.runRemaining",
                      )}
                    </button>
                  )}
                </p>
              )}
              {pagesReplaced.has(page) && (
                <p className="w-full text-[11px] text-flag-foreground">
                  {t("fileIntegrity.view.pageReplaced")}
                </p>
              )}
              {showFigures && figures.data && figures.data.length === 0 && (
                <p className="w-full text-[11px] text-muted-foreground">
                  {t("fileIntegrity.overlay.noFigures")}
                </p>
              )}
            </div>
          )}
        </div>

        <div className="min-h-0 flex-1 overflow-auto bg-surface-muted px-4 py-4">
          <PageImage
            caseId={request.caseId}
            documentId={request.documentId}
            page={page}
            bbox={page === evidencePage ? (request.bbox ?? null) : null}
            overlay={
              <IntegrityOverlay
                marks={onPage}
                figures={figuresHere}
                focus={focus}
                onPick={(m) => setFocus((k) => (k === m.key ? null : m.key))}
              />
            }
          />
        </div>
        {onPage.length > 0 && (
          <footer
            className="flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-border bg-surface px-4 py-2 text-[11px]"
            data-testid="viewer-mark-dock"
          >
            <span className="font-medium text-foreground">
              {t("fileIntegrity.view.marksOnPage", { n: onPage.length })}
            </span>
            {onPage.map((m) => (
              <button
                key={m.key}
                type="button"
                onClick={() => setFocus((k) => (k === m.key ? null : m.key))}
                className={cn(
                  "rounded px-1.5 py-0.5 text-[10.5px] font-medium",
                  focus === m.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/70",
                )}
              >
                {tOr(`fileIntegrity.mark.${m.finding.code}`, m.finding.code)}
              </button>
            ))}
            <span className="ml-auto text-muted-foreground">{t("fileIntegrity.overlay.hint")}</span>
          </footer>
        )}
      </aside>
    </div>
  );
}

/** The pages a figure rests on, one at a time: which one is shown, a list naming each by its
 * document type and page, and the way to the one before and after. */
function EvidenceSteps({
  set,
  index,
  name,
  onStep,
}: {
  set: EvidenceStop[];
  index: number;
  name: (documentId: string) => string;
  onStep: (index: number) => void;
}) {
  return (
    <div
      className="flex flex-wrap items-center gap-2 rounded border border-primary/20 bg-info-soft/40 px-2.5 py-1.5"
      data-testid="viewer-evidence"
    >
      <span
        className="text-[11.5px] font-medium text-foreground"
        data-testid="viewer-evidence-count"
      >
        {t("viewer.evidenceOf", { n: index + 1, total: set.length })}
      </span>
      <button
        type="button"
        onClick={() => onStep(index - 1)}
        disabled={index === 0}
        className="rounded border border-border bg-surface p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
        aria-label={t("viewer.previousEvidence")}
        data-testid="viewer-evidence-previous"
      >
        <ChevronLeft className="h-3.5 w-3.5" />
      </button>
      <select
        value={index}
        onChange={(e) => onStep(Number(e.target.value))}
        className="min-w-0 flex-1 rounded border border-border bg-surface px-2 py-1 text-[12px] text-foreground"
        aria-label={t("viewer.chooseEvidence")}
        data-testid="viewer-evidence-select"
      >
        {set.map((stop, i) => (
          <option key={`${stop.documentId}-${stop.page}-${i}`} value={i}>
            {t("viewer.evidenceOption", { n: i + 1, type: name(stop.documentId), page: stop.page })}
          </option>
        ))}
      </select>
      <button
        type="button"
        onClick={() => onStep(index + 1)}
        disabled={index >= set.length - 1}
        className="rounded border border-border bg-surface p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
        aria-label={t("viewer.nextEvidence")}
        data-testid="viewer-evidence-next"
      >
        <ChevronRight className="h-3.5 w-3.5" />
      </button>
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
  overlay,
}: {
  caseId: string;
  documentId: string;
  page: number;
  bbox: [number, number, number, number] | null;
  /** Drawn over the page once it has loaded, in the page's own box (F-07A marks). */
  overlay?: ReactNode;
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
      {overlay}
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
