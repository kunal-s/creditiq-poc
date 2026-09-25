import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import {
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  GitCompareArrows,
  X,
} from "lucide-react";
import {
  DEFECT_LABEL,
  DOC_BASE,
  findDoc,
  openingPage,
  snippetsForPage,
  useDocManifest,
  VERDICT_LABEL,
  type DocManifest,
  type ManifestDocument,
} from "@/data/doc-manifest";
import { PdfPage } from "@/components/docviewer/PdfPage";
import { cn } from "@/lib/utils";

type ViewerRequest =
  | { mode: "single"; filename: string; page?: number }
  | {
      mode: "compare";
      left: { filename: string; page?: number };
      right: { filename: string; page?: number };
    };

type Ctx = {
  manifest: DocManifest | undefined;
  /** Returns the manifest entry for a filename, or undefined when the file is not in the set. */
  doc: (filename: string | undefined | null) => ManifestDocument | undefined;
  open: (request: ViewerRequest) => void;
};

const DocViewerContext = createContext<Ctx | null>(null);

export function useDocViewer() {
  const ctx = useContext(DocViewerContext);
  if (!ctx) throw new Error("useDocViewer must be used inside DocViewerProvider");
  return ctx;
}

const VERDICT_TONE: Record<ManifestDocument["verdict"], string> = {
  satisfied: "border-positive/40 bg-positive-soft text-positive",
  insufficient: "border-destructive/35 bg-destructive/10 text-destructive",
  missing: "border-flag/35 bg-flag-soft text-flag-foreground",
};

export function DocViewerProvider({ children }: { children: ReactNode }) {
  const { data: manifest } = useDocManifest();
  const [request, setRequest] = useState<ViewerRequest | null>(null);

  const doc = useCallback(
    (filename: string | undefined | null) => findDoc(manifest, filename),
    [manifest],
  );
  const value = useMemo<Ctx>(() => ({ manifest, doc, open: setRequest }), [manifest, doc]);

  return (
    <DocViewerContext.Provider value={value}>
      {children}
      {request && manifest && (
        <ViewerPanel request={request} manifest={manifest} onClose={() => setRequest(null)} />
      )}
    </DocViewerContext.Provider>
  );
}

function VerdictBadge({ doc }: { doc: ManifestDocument }) {
  return (
    <span className="flex flex-wrap items-center gap-1.5">
      <span
        className={cn(
          "rounded border px-1.5 py-0.5 text-[10.5px] font-medium uppercase tracking-wide",
          VERDICT_TONE[doc.verdict],
        )}
      >
        {VERDICT_LABEL[doc.verdict]}
      </span>
      {doc.defect_type && (
        <span className="rounded border border-flag/35 bg-flag-soft px-1.5 py-0.5 text-[10.5px] font-medium uppercase tracking-wide text-flag-foreground">
          {DEFECT_LABEL[doc.defect_type]}
        </span>
      )}
    </span>
  );
}

function ViewerPanel({
  request,
  manifest,
  onClose,
}: {
  request: ViewerRequest;
  manifest: DocManifest;
  onClose: () => void;
}) {
  const compare = request.mode === "compare";
  const panes =
    request.mode === "compare"
      ? [request.left, request.right]
      : [{ filename: request.filename, page: request.page }];

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        aria-label="Close document viewer"
        onClick={onClose}
        className="absolute inset-0 bg-foreground/25"
      />
      <aside
        className={cn(
          "relative flex h-full w-full flex-col border-l border-border bg-surface-muted shadow-2xl",
          compare ? "max-w-[1180px]" : "max-w-[760px]",
        )}
      >
        <header className="flex items-start gap-3 border-b border-border bg-surface px-4 py-3">
          <div className="mt-0.5 rounded border border-border bg-surface-muted p-1.5">
            {compare ? (
              <GitCompareArrows className="h-3.5 w-3.5 text-primary" />
            ) : (
              <FileText className="h-3.5 w-3.5 text-primary" />
            )}
          </div>
          <div className="min-w-0 flex-1">
            <p className="field-label">
              {compare ? "Cross-document comparison" : "Document viewer"} · reference date{" "}
              {manifest.reference_date}
            </p>
            <p className="truncate text-[14px] font-semibold text-foreground">
              {panes
                .map((p) => findDoc(manifest, p.filename)?.requirement ?? p.filename)
                .join(compare ? "  vs  " : "")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted"
            aria-label="Close"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </header>

        <div className={cn("flex min-h-0 flex-1 divide-x divide-border overflow-hidden")}>
          {panes.map((p) => (
            <Pane
              key={p.filename}
              manifest={manifest}
              filename={p.filename}
              initialPage={p.page}
              width={compare ? 470 : 640}
            />
          ))}
        </div>
      </aside>
    </div>
  );
}

function Pane({
  manifest,
  filename,
  initialPage,
  width,
}: {
  manifest: DocManifest;
  filename: string;
  initialPage?: number | undefined;
  width: number;
}) {
  const doc = findDoc(manifest, filename);
  const [page, setPage] = useState(initialPage ?? openingPage(doc));
  const [pageCount, setPageCount] = useState(doc?.page_count ?? 1);
  const highlights = snippetsForPage(doc, page);
  const url = `${DOC_BASE}/${filename}`;

  return (
    <section className="flex min-w-0 flex-1 flex-col">
      <div className="space-y-2 border-b border-border bg-surface px-4 py-2.5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="truncate text-[12.5px] font-medium text-foreground">
              {doc?.title ?? filename}
            </p>
            <p className="tabular truncate text-[11px] text-muted-foreground">{filename}</p>
          </div>
          {doc && <VerdictBadge doc={doc} />}
        </div>

        {doc?.reason && (
          <p className="max-w-3xl text-[11.5px] leading-relaxed text-muted-foreground">
            {doc.reason}
          </p>
        )}

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setPage((n) => Math.max(1, n - 1))}
            disabled={page <= 1}
            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <span className="tabular text-[11.5px] text-muted-foreground">
            Page {page} of {pageCount}
          </span>
          <button
            type="button"
            onClick={() => setPage((n) => Math.min(pageCount, n + 1))}
            disabled={page >= pageCount}
            className="rounded border border-border p-1 text-muted-foreground hover:bg-muted disabled:opacity-40"
            aria-label="Next page"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          {highlights.length > 0 && (
            <span className="rounded border border-flag/35 bg-flag-soft px-1.5 py-0.5 text-[10.5px] font-medium text-flag-foreground">
              {highlights.length} highlighted passage{highlights.length === 1 ? "" : "s"} on this
              page
            </span>
          )}
          <a
            href={url}
            target="_blank"
            rel="noreferrer"
            className="ml-auto inline-flex items-center gap-1 text-[11.5px] font-medium text-primary hover:underline"
          >
            Open file <ExternalLink className="h-3 w-3" />
          </a>
        </div>

        {(doc?.evidence.length ?? 0) > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {doc?.evidence.map((e, i) => (
              <button
                key={`${e.page}-${i}`}
                type="button"
                onClick={() => setPage(e.page)}
                className={cn(
                  "max-w-full truncate rounded border px-1.5 py-0.5 text-[11px]",
                  e.page === page
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border bg-surface-muted text-muted-foreground hover:bg-muted",
                )}
                title={e.snippet}
              >
                p{e.page} · “{e.snippet}”
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-auto bg-surface-muted px-4 py-4">
        <PdfPage
          url={url}
          page={page}
          highlights={highlights}
          width={width}
          onPageCount={setPageCount}
        />
      </div>
    </section>
  );
}
