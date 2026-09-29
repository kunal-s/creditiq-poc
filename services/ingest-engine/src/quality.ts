// Page quality grade A/B/C/U with reason codes (FRD F-07.2 to F-07.4).
//
// The grade thresholds come from config/quality.yaml: min_dpi,
// ocr_confidence_floor, ocr_confidence_degraded, min_chars_text_layer.
// The published quality section has no thresholds for blur, skew and shadow,
// so the constants below only choose WHICH reason explains a low grade; they
// cannot lower a page below B on their own: a visible cause makes a legible
// page "degraded" (B, F-07.2); only OCR confidence makes it C or U.
import type { QualitySection } from './config.js'
import type { Grade, PageInfo } from './contract.js'
import type { FileErrorCode, PageRead } from './read/types.js'

/** Below this Laplacian variance a page image reads as blurred. */
export const BLUR_SHARPNESS = 900
/** Above this mean line angle (degrees) a page reads as photographed at an angle. */
export const SKEW_DEGREES = 1.5
/** Above this spread of paper brightness (0..255) a page reads as partly in shadow. */
export const SHADOW_SPREAD = 70
/** A page with less ink than this is blank. */
export const BLANK_INK = 0.0008

const rank: Record<Grade, number> = { A: 0, B: 1, C: 2, U: 3 }
export const worse = (a: Grade, b: Grade): Grade => (rank[a] >= rank[b] ? a : b)

/** Visible causes on a page image, in the order they are reported. */
function causes(p: PageRead, q: QualitySection): string[] {
  const out: string[] = []
  const m = p.metrics
  if (m.dpi !== undefined && m.dpi < q.min_dpi) out.push('resolution')
  if (m.sharpness !== undefined && m.sharpness < BLUR_SHARPNESS) out.push('blur')
  if (m.skewDeg !== undefined && Math.abs(m.skewDeg) > SKEW_DEGREES) out.push('skew')
  if (m.shadow !== undefined && m.shadow > SHADOW_SPREAD) out.push('shadow')
  return out
}

export function gradePage(p: PageRead, q: QualitySection): PageInfo {
  const info = (grade: Grade, reasons: string[]): PageInfo => ({ n: p.n, route: p.route, grade, reasons, ocr_confidence: p.ocrConfidence })
  const chars = p.words.reduce((s, w) => s + w.text.length, 0)
  if (p.route === 'sheet') return chars > 0 ? info('A', []) : info('U', ['blank'])
  if (p.route === 'text') return chars > 0 ? info('A', []) : info('U', ['blank'])
  // OCR route.
  if (!p.words.length && (p.metrics.ink ?? 0) < BLANK_INK) return info('U', ['blank'])
  const seen = causes(p, q)
  const legible = p.words.filter((w) => (w.conf ?? 0) >= q.ocr_confidence_floor && /[\p{L}\p{N}]{2,}/u.test(w.text)).length
  const conf = p.ocrConfidence ?? 0
  if (legible < 5) return info('U', [...seen, 'ocr_floor'])
  if (conf < q.ocr_confidence_floor) return info('C', [...seen, 'ocr_floor'])
  // B: degraded (low resolution, skew, blur, shadow) or OCR confidence under the degraded mark.
  if (conf < q.ocr_confidence_degraded || seen.length) return info('B', seen.length ? seen : ['ocr_floor'])
  return info('A', [])
}

/** A file that cannot be read at all: one page, grade U, with the reason. */
export function unreadable(code: FileErrorCode): PageInfo {
  return { n: 1, route: 'text', grade: 'U', reasons: [code === 'unsupported' ? 'corrupt' : code], ocr_confidence: null }
}

/** F-07.3: the worst grade among non-blank pages (blank-only documents are U). */
export function documentGrade(pages: PageInfo[]): Grade {
  const nonBlank = pages.filter((p) => !(p.grade === 'U' && p.reasons.includes('blank')))
  if (!nonBlank.length) return 'U'
  return nonBlank.reduce<Grade>((g, p) => worse(g, p.grade), 'A')
}
