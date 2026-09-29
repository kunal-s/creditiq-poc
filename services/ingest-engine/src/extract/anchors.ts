// Label-anchored values (F-15.2): a caption on the page, and the value to its
// right on the same line or directly below it.
import type { Line, PageRead, Word } from '../read/types.js'

export interface Candidate { raw: string; value: string | number | boolean; start: number; invalid?: boolean }
/** Where the text handed to an Accept sits: its line and its offset in the line text. */
export interface AcceptContext { page: PageRead; line: Line; offset: number }
/** Picks a value out of the text after a label; `start` is its offset inside `s`. */
export type Accept = (s: string, where?: AcceptContext) => Candidate | null

export interface Hit {
  raw: string
  value: string | number | boolean
  page: PageRead
  line: Line
  words: Word[]
  invalid?: boolean
  alias: string
}

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const reCache = new Map<string, RegExp>()

export function labelRe(alias: string): RegExp {
  let re = reCache.get(alias)
  if (!re) {
    if (alias.startsWith('re:')) re = new RegExp(alias.slice(3), 'giu')
    else {
      // Apostrophes vary between straight and curly (and OCR drops them).
      const body = alias.trim().split(/\s+/).map((w) => esc(w).replace(/['’‘]/g, "['’‘`]?")).join('\\s*')
      re = new RegExp(`(?<![\\p{L}\\p{N}])${body}(?![\\p{L}])`, 'giu')
    }
    reCache.set(alias, re)
  }
  re.lastIndex = 0
  return re
}

/** Words covering characters [start, end) of a line's text. */
export function wordsInSpan(line: Line, start: number, end: number): Word[] {
  return line.words.filter((w, i) => {
    const s = line.offsets[i]
    const e = s + w.text.length
    return s < end && e > start
  })
}

/** Cells of a line: runs of words split at column gaps, with their character spans. */
export function cells(line: Line): { text: string; start: number; end: number; words: Word[]; x0: number; x1: number }[] {
  const out: { text: string; start: number; end: number; words: Word[]; x0: number; x1: number }[] = []
  const re = /\S+(?: \S+)*/g
  let m: RegExpExecArray | null
  while ((m = re.exec(line.text))) {
    const ws = wordsInSpan(line, m.index, m.index + m[0].length)
    if (!ws.length) continue
    out.push({ text: m[0], start: m.index, end: m.index + m[0].length, words: ws, x0: Math.min(...ws.map((w) => w.x0)), x1: Math.max(...ws.map((w) => w.x1)) })
  }
  return out
}

/** A caption must open its cell (after at most a bullet such as "2(a)." or "(iv)"). */
function opensCell(text: string, at: number): boolean {
  const before = text.slice(0, at)
  const cell = before.split(/\s{3,}/).pop() ?? ''
  return /^[\s\d().\-:]*(?:\(?[a-z]{1,3}[).]|[a-z]\.)?[\s\d().\-]*$/i.test(cell) && cell.length <= 8
}

const LABELISH = /:\s*$/

export interface FindOptions {
  /** Look below the caption when nothing follows it on the line (form layouts). */
  below?: boolean
  /** Only these pages (1-based absolute numbers). */
  pages?: number[]
}

export function findLabelled(pages: PageRead[], aliases: string[], accept: Accept, opts: FindOptions = {}): Hit | null {
  const scope = opts.pages ? pages.filter((p) => opts.pages!.includes(p.n)) : pages
  for (const alias of aliases) {
    for (const page of scope) {
      for (let li = 0; li < page.lines.length; li++) {
        const line = page.lines[li]
        const re = labelRe(alias)
        let m: RegExpExecArray | null
        while ((m = re.exec(line.text))) {
          if (alias.startsWith('re:')) {
            const g = m[1]
            if (g === undefined) continue
            const gStart = m.index + m[0].indexOf(g)
            const c = accept(g, { page, line, offset: gStart })
            if (!c) continue
            const s = gStart + c.start
            return { raw: c.raw, value: c.value, page, line, words: wordsInSpan(line, s, s + c.raw.length), invalid: c.invalid, alias }
          }
          if (!opensCell(line.text, m.index)) continue
          const after = m.index + m[0].length
          const rest = line.text.slice(after)
          const lead = /^[\s:.\-–=|]*/.exec(rest)?.[0].length ?? 0
          const stripped = rest.slice(lead)
          if (stripped.trim() && !LABELISH.test(stripped.split(/\s{3,}/)[0])) {
            const c = accept(stripped, { page, line, offset: after + lead })
            if (c) {
              const s = after + lead + c.start
              return { raw: c.raw, value: c.value, page, line, words: wordsInSpan(line, s, s + c.raw.length), invalid: c.invalid, alias }
            }
          }
          if (opts.below !== false && !stripped.trim()) {
            const hit = below(page, li, m.index, after, accept)
            if (hit) return { ...hit, page, alias }
          }
        }
      }
    }
  }
  return null
}

/** The value under a caption: the next line or two, in the caption's column. */
function below(page: PageRead, li: number, start: number, end: number, accept: Accept): Omit<Hit, 'page' | 'alias'> | null {
  const line = page.lines[li]
  const lw = wordsInSpan(line, start, end)
  if (!lw.length) return null
  const lx0 = Math.min(...lw.map((w) => w.x0))
  const lh = line.y1 - line.y0
  for (let k = li + 1; k < Math.min(page.lines.length, li + 3); k++) {
    const next = page.lines[k]
    if (next.y0 - line.y1 > 2.5 * lh) break
    for (const cell of cells(next)) {
      if (cell.x1 < lx0 - 0.01 || cell.x0 > lx0 + 0.25) continue
      const c = accept(cell.text, { page, line: next, offset: cell.start })
      if (!c) continue
      const s = cell.start + c.start
      return { raw: c.raw, value: c.value, line: next, words: wordsInSpan(next, s, s + c.raw.length), invalid: c.invalid }
    }
  }
  return null
}
