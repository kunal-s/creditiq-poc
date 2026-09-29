// Read a file into the per-page word index, choosing the route by content
// (magic bytes first; the declared content type only breaks ties).
import { finishPage } from './layout.js'
import { loadImageFile, measure } from './image.js'
import { ocrImage } from './ocr.js'
import { readPdf } from './pdf.js'
import { readCsv, readXlsx } from './sheet.js'
import type { FileRead } from './types.js'

const startsWith = (b: Uint8Array, sig: number[]) => sig.every((v, i) => b[i] === v)

export function sniff(buf: Uint8Array, contentType: string): FileRead['kind'] | 'csv' {
  if (startsWith(buf, [0x25, 0x50, 0x44, 0x46])) return 'pdf' // %PDF
  if (startsWith(buf, [0x89, 0x50, 0x4e, 0x47]) || startsWith(buf, [0xff, 0xd8, 0xff]) || startsWith(buf, [0x47, 0x49, 0x46, 0x38]) || startsWith(buf, [0x42, 0x4d])) return 'image'
  if (startsWith(buf, [0x52, 0x49, 0x46, 0x46]) && buf[8] === 0x57 && buf[9] === 0x45) return 'image' // RIFF....WEBP
  if (startsWith(buf, [0x50, 0x4b, 0x03, 0x04]) && /spreadsheet|excel|xlsx/i.test(contentType)) return 'sheet'
  if (startsWith(buf, [0x50, 0x4b, 0x03, 0x04])) {
    // A zip: an .xlsx carries xl/workbook.xml.
    const head = new TextDecoder('latin1').decode(buf.subarray(0, Math.min(buf.length, 65536)))
    if (head.includes('xl/')) return 'sheet'
  }
  if (/pdf/i.test(contentType)) return 'pdf'
  if (/^image\//i.test(contentType)) return 'image'
  if (/csv/i.test(contentType)) return 'csv'
  return 'unknown'
}

/** Pixels per inch of a photographed or scanned page image, assuming A4. */
const a4Dpi = (w: number, h: number) => Math.round(Math.max(w, h) > 0 ? (w <= h ? w / 8.27 : w / 11.69) : 0)

export async function readFile(buf: Uint8Array, contentType: string, minTextChars: number): Promise<FileRead> {
  const kind = sniff(buf, contentType)
  if (kind === 'pdf') return readPdf(buf, minTextChars)
  if (kind === 'sheet') return readXlsx(buf)
  if (kind === 'csv') return readCsv(buf)
  if (kind === 'image') {
    let img
    try { img = await loadImageFile(buf) } catch (e) {
      return { kind: 'image', pages: [], error: { code: 'corrupt', detail: `The image cannot be decoded (${e instanceof Error ? e.message.slice(0, 120) : 'unknown error'}).` } }
    }
    const m = await measure(img.png)
    const ocr = m.ink < 0.0008 ? { words: [], confidence: null, skewDeg: null } : await ocrImage(img.png, img.width, img.height)
    return {
      kind: 'image',
      pages: [finishPage({ n: 1, route: 'ocr', words: ocr.words, ocrConfidence: ocr.confidence, metrics: { dpi: a4Dpi(img.width, img.height), sharpness: m.sharpness, shadow: m.shadow, ink: m.ink, skewDeg: ocr.skewDeg ?? undefined } })],
    }
  }
  return { kind: 'unknown', pages: [], error: { code: 'unsupported', detail: `Files of type ${contentType || 'unknown'} are not read.` } }
}
