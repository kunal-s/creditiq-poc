// OCR for scanned pages and photographs: words with boxes and confidence
// (tesseract.js `blocks` output), never just the text. The English language
// data is the npm package @tesseract.js-data/eng, loaded from node_modules
// (langPath), so no language data is fetched from a CDN at runtime.
import { createRequire } from 'node:module'
import { dirname, join } from 'node:path'
import { createScheduler, createWorker, OEM, type Scheduler } from 'tesseract.js'
import type { Word } from './types.js'

const require = createRequire(import.meta.url)
const LANG_PATH = join(dirname(require.resolve('@tesseract.js-data/eng/package.json')), '4.0.0_best_int')

let schedulerPromise: Promise<Scheduler> | null = null
let workerCount = 2

export function configureOcr(workers: number): void { workerCount = Math.max(1, Math.floor(workers) || 1) }

function getScheduler(): Promise<Scheduler> {
  if (!schedulerPromise) {
    schedulerPromise = (async () => {
      const s = createScheduler()
      const make = () => createWorker('eng', OEM.LSTM_ONLY, { langPath: LANG_PATH, gzip: true, cacheMethod: 'none' })
      const workers = await Promise.all(Array.from({ length: workerCount }, make))
      for (const w of workers) {
        await w.setParameters({ preserve_interword_spaces: '1' })
        s.addWorker(w)
      }
      return s
    })()
    schedulerPromise.catch(() => { schedulerPromise = null })
  }
  return schedulerPromise
}

export async function terminateOcr(): Promise<void> {
  if (!schedulerPromise) return
  const s = await schedulerPromise.catch(() => null)
  schedulerPromise = null
  await s?.terminate()
}

export interface OcrResult {
  words: Word[]
  /** Character-weighted mean word confidence, 0..100 (null when no words). */
  confidence: number | null
  /** Median baseline angle of the longer lines, in degrees. */
  skewDeg: number | null
}

interface TBox { x0: number; y0: number; x1: number; y1: number }
interface TWord { text: string; confidence: number; bbox: TBox }
interface TLine { words: TWord[]; baseline?: { x0: number; y0: number; x1: number; y1: number }; bbox: TBox }
interface TPara { lines: TLine[] }
interface TBlock { paragraphs: TPara[] }

/** Recognise one page image (PNG bytes) of the given pixel size. */
export async function ocrImage(png: Uint8Array, width: number, height: number): Promise<OcrResult> {
  const scheduler = await getScheduler()
  const { data } = (await scheduler.addJob('recognize', Buffer.from(png), {}, { blocks: true, text: false })) as unknown as { data: { blocks: TBlock[] | null } }
  const words: Word[] = []
  const angles: number[] = []
  for (const b of data.blocks ?? []) {
    for (const p of b.paragraphs ?? []) {
      for (const l of p.lines ?? []) {
        const bl = l.baseline
        if (bl && bl.x1 - bl.x0 > width * 0.25) angles.push((Math.atan2(bl.y1 - bl.y0, bl.x1 - bl.x0) * 180) / Math.PI)
        for (const w of l.words ?? []) {
          const text = (w.text ?? '').trim()
          if (!text) continue
          words.push({ text, x0: w.bbox.x0 / width, y0: w.bbox.y0 / height, x1: w.bbox.x1 / width, y1: w.bbox.y1 / height, conf: w.confidence })
        }
      }
    }
  }
  let confidence: number | null = null
  const chars = words.reduce((s, w) => s + w.text.length, 0)
  if (chars > 0) confidence = Math.round((words.reduce((s, w) => s + (w.conf ?? 0) * w.text.length, 0) / chars) * 10) / 10
  angles.sort((a, b) => a - b)
  const skewDeg = angles.length ? Math.round(angles[Math.floor(angles.length / 2)] * 100) / 100 : null
  return { words, confidence, skewDeg }
}
