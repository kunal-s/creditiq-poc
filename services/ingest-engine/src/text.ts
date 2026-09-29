// Acquire + parse: turn a URL or an uploaded file into plain text with page markers.
// Deliberately small — PDF via unpdf (pdf.js), HTML via html-to-text, everything
// else read as UTF-8. Pages with no text layer (scans) go through OCR.
import { extractText, getDocumentProxy } from 'unpdf'
import { convert } from 'html-to-text'
import { ocrPages, pdfCanvasFactory } from './ocr.js'
import { cacheGetBytes, cacheSetBytes, sha256 } from './cache.js'

const FETCH_TTL_MS = 6 * 60 * 60 * 1000

export interface SourceText {
  text: string
  pages: number
  kind: 'pdf' | 'html' | 'docx' | 'text'
  bytes: number
  /** Pages that had no text layer and were OCR'd. */
  ocrPages?: number
  /** Set when OCR is disabled and pages had no text layer. */
  warning?: string
}

/** A page with fewer characters than this is treated as image-only and sent to OCR. */
const MIN_TEXT_CHARS_PER_PAGE = 40

const PAGE_MARK = (n: number) => `\n\n[[page ${n}]]\n`

export async function fetchSource(url: string): Promise<{ buf: Uint8Array; contentType: string; cached: boolean }> {
  const key = `fetch-${sha256(url)}`
  const hit = await cacheGetBytes(key, FETCH_TTL_MS)
  const typeHit = hit ? await cacheGetBytes(`${key}-type`, FETCH_TTL_MS) : null
  if (hit && typeHit) return { buf: hit, contentType: new TextDecoder().decode(typeHit), cached: true }
  const res = await fetch(url, {
    headers: { 'user-agent': 'Mozilla/5.0 (compatible; ingest-engine/0.1)', accept: 'application/pdf,text/html;q=0.9,*/*;q=0.8' },
    redirect: 'follow',
    signal: AbortSignal.timeout(30_000),
  })
  if (!res.ok) throw new Error(`Fetch failed: ${res.status} ${res.statusText}`)
  const contentType = res.headers.get('content-type') ?? ''
  const buf = new Uint8Array(await res.arrayBuffer())
  await cacheSetBytes(key, buf)
  await cacheSetBytes(`${key}-type`, new TextEncoder().encode(contentType))
  return { buf, contentType, cached: false }
}

function looksLikePdf(buf: Uint8Array): boolean {
  return buf.length > 4 && buf[0] === 0x25 && buf[1] === 0x50 && buf[2] === 0x44 && buf[3] === 0x46 // %PDF
}

export async function toText(
  buf: Uint8Array,
  contentType: string,
  filename = '',
  opts: { ocr?: boolean; onOcrStart?: (total: number) => void; onOcrProgress?: (done: number, total: number) => void } = {},
): Promise<SourceText> {
  const bytes = buf.length // pdf.js detaches the buffer; read the size first
  const isPdf = looksLikePdf(buf) || /pdf/i.test(contentType) || /\.pdf$/i.test(filename)
  if (isPdf) {
    const pdf = await getDocumentProxy(buf, { CanvasFactory: await pdfCanvasFactory() })
    const { text } = await extractText(pdf, { mergePages: false })
    const pages = (Array.isArray(text) ? text : [String(text)]).map((p) => p.trim())
    const blank = pages.map((p, i) => (p.length < MIN_TEXT_CHARS_PER_PAGE ? i + 1 : 0)).filter(Boolean)
    let warning: string | undefined
    if (blank.length && opts.ocr !== false) {
      opts.onOcrStart?.(blank.length)
      const recognised = await ocrPages(pdf, blank, opts.onOcrProgress)
      for (const [n, t] of recognised) pages[n - 1] = t
    } else if (blank.length) {
      warning = `${blank.length} of ${pages.length} pages have no text layer (scanned); OCR was skipped.`
    }
    const joined = pages.map((p, i) => PAGE_MARK(i + 1) + p).join('')
    return { text: joined.trim(), pages: pages.length, kind: 'pdf', bytes, ocrPages: blank.length || undefined, warning }
  }
  const isDocx = /wordprocessingml/i.test(contentType) || /\.docx$/i.test(filename) || (buf[0] === 0x50 && buf[1] === 0x4b && /\.docx$/i.test(filename))
  if (isDocx) {
    const { default: mammoth } = await import('mammoth')
    const { value } = await mammoth.extractRawText({ buffer: Buffer.from(buf) })
    return { text: value.trim(), pages: 1, kind: 'docx', bytes }
  }
  const raw = new TextDecoder('utf-8').decode(buf)
  if (/html/i.test(contentType) || /^\s*<(!doctype|html)/i.test(raw) || /\.html?$/i.test(filename)) {
    const text = convert(raw, {
      wordwrap: false,
      selectors: [
        { selector: 'a', options: { ignoreHref: true } },
        { selector: 'img', format: 'skip' },
        { selector: 'nav', format: 'skip' },
        { selector: 'script', format: 'skip' },
        { selector: 'style', format: 'skip' },
      ],
    })
    return { text: text.trim(), pages: 1, kind: 'html', bytes }
  }
  return { text: raw.trim(), pages: 1, kind: 'text', bytes }
}
