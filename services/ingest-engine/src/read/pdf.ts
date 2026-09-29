// PDF pages: the text layer with word positions (pdf.js getTextContent), or
// OCR when the layer is missing or not trustworthy (F-07.1).
import { createIsomorphicCanvasFactory, getDocumentProxy, getResolvedPDFJS, renderPageAsImage } from 'unpdf'
import { canvasImport, measure } from './image.js'
import { finishPage } from './layout.js'
import { ocrImage } from './ocr.js'
import type { FileRead, PageRead, Word } from './types.js'

type PDFDocumentProxy = Awaited<ReturnType<typeof getDocumentProxy>>

interface TextItem { str: string; transform: number[]; width: number; height: number }

/** Share of characters that look like real text (letters, digits, common punctuation). */
function plausibleShare(s: string): number {
  const chars = s.replace(/\s+/g, '')
  if (!chars.length) return 0
  const good = chars.match(/[\p{L}\p{N}.,:;()\-/&%₹'"@#*+=\[\]]/gu)?.length ?? 0
  return good / chars.length
}

async function textLayerWords(pdf: PDFDocumentProxy, n: number): Promise<{ words: Word[]; chars: number; plausible: number; width: number; height: number }> {
  const page = await pdf.getPage(n)
  const vp = page.getViewport({ scale: 1 })
  const tc = await page.getTextContent()
  const words: Word[] = []
  let all = ''
  for (const raw of tc.items as unknown as TextItem[]) {
    if (typeof raw.str !== 'string' || !raw.str.trim()) continue
    all += raw.str
    const [a, b, c, d, e, f] = raw.transform
    const fontH = Math.hypot(c, d) || raw.height || Math.hypot(a, b)
    const len = raw.str.length
    const dirX = Math.hypot(a, b) ? a / Math.hypot(a, b) : 1
    const dirY = Math.hypot(a, b) ? b / Math.hypot(a, b) : 0
    const re = /\S+/g
    let m: RegExpExecArray | null
    while ((m = re.exec(raw.str))) {
      const s = (m.index / len) * raw.width
      const t = ((m.index + m[0].length) / len) * raw.width
      // Corners in PDF space along the baseline, from 0.2 em below to 0.8 em above.
      const pts = [
        [e + dirX * s, f + dirY * s - 0.2 * fontH],
        [e + dirX * t, f + dirY * t + 0.8 * fontH],
        [e + dirX * s, f + dirY * s + 0.8 * fontH],
        [e + dirX * t, f + dirY * t - 0.2 * fontH],
      ].map(([x, y]) => vp.convertToViewportPoint(x, y) as number[])
      const xs = pts.map((p) => p[0])
      const ys = pts.map((p) => p[1])
      words.push({ text: m[0], x0: Math.min(...xs) / vp.width, y0: Math.min(...ys) / vp.height, x1: Math.max(...xs) / vp.width, y1: Math.max(...ys) / vp.height })
    }
  }
  page.cleanup()
  const chars = all.replace(/\s+/g, '').length
  return { words, chars, plausible: plausibleShare(all), width: vp.width, height: vp.height }
}

/** Pixel size of the largest image painted on the page (a scan is one page-sized image). */
async function largestImage(pdf: PDFDocumentProxy, n: number): Promise<{ w: number; h: number } | null> {
  const { OPS } = await getResolvedPDFJS()
  const page = await pdf.getPage(n)
  const ops = await page.getOperatorList()
  let best: { w: number; h: number } | null = null
  ops.fnArray.forEach((fn: number, i: number) => {
    if (fn !== OPS.paintImageXObject && fn !== OPS.paintInlineImageXObject) return
    const args = ops.argsArray[i] as unknown[]
    const w = Number(args?.[1])
    const h = Number(args?.[2])
    if (Number.isFinite(w) && Number.isFinite(h) && (!best || w * h > best.w * best.h)) best = { w, h }
  })
  page.cleanup()
  return best
}

export async function readPdf(buf: Uint8Array, minTextChars: number): Promise<FileRead> {
  let pdf: PDFDocumentProxy
  try {
    // pdf.js may detach the buffer it is given; hand it a copy.
    pdf = await getDocumentProxy(new Uint8Array(buf), { CanvasFactory: await createIsomorphicCanvasFactory(canvasImport), disableFontFace: true })
  } catch (e) {
    const name = (e as { name?: string })?.name ?? ''
    const msg = e instanceof Error ? e.message : String(e)
    if (name === 'PasswordException' || /password/i.test(msg)) return { kind: 'pdf', pages: [], error: { code: 'encrypted', detail: 'The PDF is password-protected.' } }
    return { kind: 'pdf', pages: [], error: { code: 'corrupt', detail: `The PDF cannot be opened (${msg.slice(0, 120)}).` } }
  }
  const pages: PageRead[] = []
  try {
    for (let n = 1; n <= pdf.numPages; n++) {
      let layer: Awaited<ReturnType<typeof textLayerWords>>
      try { layer = await textLayerWords(pdf, n) } catch {
        pages.push(finishPage({ n, route: 'text', words: [], ocrConfidence: null, metrics: {}, textLayerChars: 0 }))
        continue
      }
      // The text layer is trusted when it has enough plausible characters.
      if (layer.chars >= minTextChars && layer.plausible >= 0.85) {
        pages.push(finishPage({ n, route: 'text', words: layer.words, ocrConfidence: null, metrics: {}, textLayerChars: layer.chars }))
        continue
      }
      const img = await largestImage(pdf, n).catch(() => null)
      const pageInches = layer.width / 72
      const dpi = img ? Math.round(img.w / pageInches) : undefined
      // Render near the scan's own resolution (at least 2x, at most 4x the PDF's 72 dpi).
      const scale = Math.min(4, Math.max(2, img ? img.w / layer.width : 2))
      const png = new Uint8Array(await renderPageAsImage(pdf, n, { canvasImport, scale }))
      const m = await measure(png)
      const ocr = m.ink < 0.0008 ? { words: [], confidence: null, skewDeg: null } : await ocrImage(png, m.width, m.height)
      pages.push(finishPage({
        n,
        route: 'ocr',
        words: ocr.words,
        ocrConfidence: ocr.confidence,
        metrics: { dpi, sharpness: m.sharpness, shadow: m.shadow, ink: m.ink, skewDeg: ocr.skewDeg ?? undefined },
        textLayerChars: layer.chars,
      }))
    }
  } finally {
    // Release pdf.js resources (the proxy's cleanup; the loading task owns destroy()).
    await Promise.resolve((pdf as unknown as { cleanup?: () => unknown }).cleanup?.()).catch(() => {})
    await Promise.resolve((pdf as unknown as { loadingTask?: { destroy?: () => unknown } }).loadingTask?.destroy?.()).catch(() => {})
  }
  return { kind: 'pdf', pages }
}
