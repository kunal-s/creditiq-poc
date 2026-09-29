// F-15.4: every value is checked against its page's word index. The raw text
// must occur among the page's words (whitespace, case and Indian digit
// grouping normalised); the words it covers give the region (bbox).
import type { Bbox } from '../contract.js'
import { unionBox } from '../read/layout.js'
import type { PageRead, Word } from '../read/types.js'
import { normaliseForMatch } from './values.js'

interface Indexed { s: string; owner: number[] }

const cache = new WeakMap<PageRead, { spaced: Indexed; tight: Indexed }>()

function index(page: PageRead): { spaced: Indexed; tight: Indexed } {
  let hit = cache.get(page)
  if (hit) return hit
  const words: Word[] = page.lines.flatMap((l) => l.words)
  const build = (sep: string): Indexed => {
    let s = ''
    const owner: number[] = []
    words.forEach((w, i) => {
      const t = normaliseForMatch(w.text)
      if (!t) return
      if (s && sep) { s += sep; owner.push(-1) }
      for (const ch of t) { s += ch; owner.push(i) }
    })
    return { s, owner }
  }
  hit = { spaced: build(' '), tight: build('') }
  cache.set(page, hit)
  return hit
}

/** Words of a page in reading order (the order `locate` indexes them). */
export const readingWords = (page: PageRead): Word[] => page.lines.flatMap((l) => l.words)

/**
 * Where `raw` is printed on `page`, or null if it is not. `near` (a y
 * position) prefers the occurrence closest to it when raw occurs twice.
 */
export function locate(page: PageRead, raw: string, near?: number): { bbox: Bbox | null; words: Word[] } | null {
  const needle = normaliseForMatch(raw)
  if (!needle) return null
  const idx = index(page)
  const words = readingWords(page)
  const tryIn = (ix: Indexed, n: string) => {
    const hits: number[] = []
    let from = 0
    while (true) {
      const at = ix.s.indexOf(n, from)
      if (at < 0) break
      // The match must start and end on word boundaries of the index.
      const before = at === 0 || ix.owner[at - 1] !== ix.owner[at] || ix.owner[at - 1] === -1
      const after = at + n.length >= ix.s.length || ix.owner[at + n.length] !== ix.owner[at + n.length - 1] || ix.owner[at + n.length] === -1
      if (before && after) hits.push(at)
      else if (/^[\d.,-]+$/.test(n) === false && n.length >= 6) hits.push(at)
      from = at + 1
    }
    return hits.map((at) => {
      const set = new Set<number>()
      for (let k = at; k < at + n.length; k++) if (ix.owner[k] >= 0) set.add(ix.owner[k])
      return [...set].map((i) => words[i])
    })
  }
  let found = tryIn(idx.spaced, needle)
  if (!found.length) found = tryIn(idx.tight, needle.replace(/\s+/g, ''))
  if (!found.length) return null
  let best = found[0]
  if (near !== undefined && found.length > 1) {
    const dist = (ws: Word[]) => Math.abs(ws[0].y0 - near)
    best = found.reduce((a, b) => (dist(b) < dist(a) ? b : a))
  }
  return { bbox: unionBox(best), words: best }
}

/** Mean OCR confidence (0..1) of some words; 1 for text-layer and sheet words. */
export function wordTrust(words: Word[]): number {
  const confs = words.map((w) => w.conf).filter((c): c is number => c !== undefined)
  if (!confs.length) return 1
  return Math.round((confs.reduce((a, b) => a + b, 0) / confs.length / 100) * 1000) / 1000
}
