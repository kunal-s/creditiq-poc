// OCR for PDF pages that carry no text layer (scans) and for standalone images. Used ONLY for those pages — pages with a text
// layer never go through here. Renders with pdf.js → @napi-rs/canvas and
// recognises with tesseract.js (WASM) on a small pool of workers; language
// data is fetched once and cached under server/.tessdata.
import { createIsomorphicCanvasFactory, renderPageAsImage, type getDocumentProxy } from 'unpdf'
import { availableParallelism } from 'node:os'
import { createScheduler, createWorker, type Scheduler } from 'tesseract.js'
import { env } from './env.js'

type PDFDocumentProxy = Awaited<ReturnType<typeof getDocumentProxy>>

// unpdf 1.x renders through @napi-rs/canvas, loaded lazily so a text-only run never pays for it.
const canvasImport = () => import('@napi-rs/canvas')

/** pdf.js needs the canvas factory at document-open time to paint image XObjects. */
export const pdfCanvasFactory = () => createIsomorphicCanvasFactory(canvasImport)

const WORKERS = Math.max(1, env.ocrWorkers || Math.min(6, Math.max(2, availableParallelism() - 1)))
const TESSDATA = env.tessdataDir

let schedulerPromise: Promise<Scheduler> | null = null
function getScheduler(): Promise<Scheduler> {
  if (!schedulerPromise) {
    schedulerPromise = (async () => {
      const s = createScheduler()
      // The first worker downloads/caches the language data; the rest reuse it.
      s.addWorker(await createWorker('eng', 1, { cachePath: TESSDATA }))
      await Promise.all(Array.from({ length: WORKERS - 1 }, async () => s.addWorker(await createWorker('eng', 1, { cachePath: TESSDATA }))))
      return s
    })()
  }
  return schedulerPromise
}

/** Start the worker pool ahead of the first request so OCR has no cold start. */
export function prewarmOcr(): void {
  getScheduler().catch((e) => console.warn('[ocr] prewarm failed:', e instanceof Error ? e.message : e))
}

export interface OcrProgress {
  (done: number, total: number): void
}

/** Recognise the given (1-based) page numbers in parallel; returns text per page number. */
export async function ocrPages(pdf: PDFDocumentProxy, pageNumbers: number[], onProgress?: OcrProgress): Promise<Map<number, string>> {
  const out = new Map<number, string>()
  if (!pageNumbers.length) return out
  const scheduler = await getScheduler()
  let done = 0
  await Promise.all(
    pageNumbers.map(async (n) => {
      const png = await renderPageAsImage(pdf, n, { canvasImport, scale: 2 })
      const { data } = await scheduler.addJob('recognize', Buffer.from(png))
      out.set(n, data.text.trim())
      done += 1
      onProgress?.(done, pageNumbers.length)
    }),
  )
  return out
}

/** Recognise a standalone image (PNG · JPEG · TIFF · BMP · WebP) — scanned letters, photographed receipts. */
export async function ocrImage(image: Uint8Array): Promise<string> {
  const scheduler = await getScheduler()
  const { data } = await scheduler.addJob('recognize', Buffer.from(image))
  return data.text.trim()
}
