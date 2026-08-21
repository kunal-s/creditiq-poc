import { useEffect, useRef, useState } from "react";

type Rect = { left: number; top: number; width: number; height: number };

let pdfjsPromise: Promise<typeof import("pdfjs-dist")> | null = null;

async function getPdfjs() {
  if (!pdfjsPromise) {
    pdfjsPromise = (async () => {
      const pdfjs = await import("pdfjs-dist");
      const worker = await import("pdfjs-dist/build/pdf.worker.min.mjs?url");
      pdfjs.GlobalWorkerOptions.workerSrc = worker.default;
      return pdfjs;
    })();
  }
  return pdfjsPromise;
}

const docCache = new Map<string, Promise<any>>();

function loadDoc(url: string) {
  let existing = docCache.get(url);
  if (!existing) {
    existing = getPdfjs().then((pdfjs) => pdfjs.getDocument({ url }).promise);
    docCache.set(url, existing);
  }
  return existing;
}

function normalise(s: string) {
  return s.replace(/\s+/g, " ").trim().toLowerCase();
}

/**
 * Renders one page of a PDF and draws highlight boxes over any text that
 * belongs to the snippets recorded for that page in the manifest.
 */
export function PdfPage({
  url,
  page,
  highlights,
  width,
  onPageCount,
}: {
  url: string;
  page: number;
  highlights: string[];
  width: number;
  onPageCount?: (n: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const [rects, setRects] = useState<Rect[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setRects([]);

    (async () => {
      try {
        const [pdfjs, pdf] = await Promise.all([getPdfjs(), loadDoc(url)]);
        if (cancelled) return;
        onPageCount?.(pdf.numPages);
        const target = Math.min(Math.max(page, 1), pdf.numPages);
        const pdfPage = await pdf.getPage(target);
        if (cancelled) return;

        const base = pdfPage.getViewport({ scale: 1 });
        const scale = width / base.width;
        const viewport = pdfPage.getViewport({ scale });
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const canvas = canvasRef.current;
        if (!canvas) return;
        canvas.width = Math.floor(viewport.width * dpr);
        canvas.height = Math.floor(viewport.height * dpr);
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        await pdfPage.render({ canvasContext: ctx, viewport }).promise;
        if (cancelled) return;
        setSize({ w: viewport.width, h: viewport.height });

        const wanted = highlights.map(normalise).filter(Boolean);
        if (wanted.length > 0) {
          const text = await pdfPage.getTextContent();
          if (cancelled) return;
          const found: Rect[] = [];
          for (const raw of text.items as any[]) {
            const str: string = raw.str ?? "";
            const value = normalise(str);
            if (value.length < 3) continue;
            const hit = wanted.some((w) => w.includes(value) || value.includes(w));
            if (!hit) continue;
            const tx = pdfjs.Util.transform(viewport.transform, raw.transform);
            const fontHeight = Math.hypot(tx[2], tx[3]);
            found.push({
              left: tx[4],
              top: tx[5] - fontHeight,
              width: (raw.width ?? 0) * scale,
              height: fontHeight * 1.25,
            });
          }
          setRects(found);
        }
        setLoading(false);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "This document could not be rendered");
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url, page, width, highlights.join("|")]);

  return (
    <div className="relative mx-auto" style={{ width, minHeight: size?.h ?? width * 1.35 }}>
      <canvas
        ref={canvasRef}
        style={{ width, height: size?.h ?? undefined }}
        className="block rounded border border-border bg-white shadow-sm"
      />
      {rects.map((r, i) => (
        <span
          key={i}
          aria-hidden
          className="pointer-events-none absolute rounded-[2px] bg-flag/40 ring-1 ring-flag"
          style={{ left: r.left, top: r.top, width: r.width, height: r.height }}
        />
      ))}
      {loading && !error && (
        <p className="absolute inset-x-0 top-6 text-center text-[12px] text-muted-foreground">Rendering page…</p>
      )}
      {error && (
        <p className="rounded border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12px] text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
