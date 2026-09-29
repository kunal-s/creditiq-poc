// The per-page word index (FRD F-07.1). Every downstream step (grade,
// split, classify, extract, verify) reads pages through this shape only.
import type { Route } from '../contract.js'

/** One word, with its box in normalised page coordinates (0..1, top-left origin). */
export interface Word {
  text: string
  x0: number
  y0: number
  x1: number
  y1: number
  /** OCR word confidence, 0..100. Absent for text-layer and sheet words. */
  conf?: number
}

/** Words on one visual line, left to right. */
export interface Line {
  words: Word[]
  /** Words joined with one space; a wide horizontal gap (a column break) becomes COLUMN_GAP. */
  text: string
  /** Character offset of each word inside `text`. */
  offsets: number[]
  x0: number
  y0: number
  x1: number
  y1: number
}

/** Image measurements for the quality grade (F-07.2, F-07.4). */
export interface PageMetrics {
  /** Effective resolution of the page image. */
  dpi?: number
  /** Sharpness: variance of the Laplacian on the normalised grey image. Lower is blurrier. */
  sharpness?: number
  /** Mean text-line angle in degrees. */
  skewDeg?: number
  /** Spread of background brightness across the page (0..255). */
  shadow?: number
  /** Fraction of dark pixels. */
  ink?: number
}

export interface PageRead {
  /** Absolute page number in the source file, from 1. */
  n: number
  route: Route
  words: Word[]
  lines: Line[]
  /** Lines joined with newlines: the page text every regex runs against. */
  text: string
  /** Mean OCR word confidence (0..100), weighted by characters; null when not OCR'd. */
  ocrConfidence: number | null
  metrics: PageMetrics
  /** Characters in the text layer before any OCR (text route diagnostics). */
  textLayerChars?: number
}

export type FileErrorCode = 'corrupt' | 'encrypted' | 'unsupported'

export interface FileRead {
  kind: 'pdf' | 'image' | 'sheet' | 'unknown'
  pages: PageRead[]
  error?: { code: FileErrorCode; detail: string }
}

/** Column separator used inside line text. Regexes split cells on /\s{3,}/. */
export const COLUMN_GAP = '   '
