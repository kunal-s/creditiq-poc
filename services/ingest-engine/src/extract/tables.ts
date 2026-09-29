// Tables from word positions (F-15.2, F-15.3): a header row whose cells
// match the dictionary's column captions fixes the column bands; the rows
// below are cut into cells and each cell goes to the band it overlaps most.
import type { Line, PageRead, Word } from '../read/types.js'
import { cells, labelRe } from './anchors.js'

export interface Column { name: string; aliases: string[] }
export interface Band { name: string; x0: number; x1: number; xc: number }
export interface Header { page: PageRead; lineIndex: number; bands: Band[] }
export interface Cell { text: string; words: Word[]; x0: number; x1: number }
export interface Row { page: PageRead; line: Line; lineIndex: number; cells: Map<string, Cell> }

const norm = (s: string) => s.toLowerCase().replace(/\s+/g, ' ').trim()

/** Edit distance, for captions misread by one character ("Chg./Ref.No."). */
function editDistance(a: string, b: string): number {
  const d = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    let prev = d[0]
    d[0] = i
    for (let j = 1; j <= b.length; j++) {
      const tmp = d[j]
      d[j] = Math.min(d[j] + 1, d[j - 1] + 1, prev + (a[i - 1] === b[j - 1] ? 0 : 1))
      prev = tmp
    }
  }
  return d[b.length]
}

const letters = (s: string) => s.toLowerCase().replace(/[^a-z0-9]/g, '')

function cellMatches(cellText: string, aliases: string[]): number {
  const t = norm(cellText)
  let best = 0
  for (const a of aliases) {
    if (a.startsWith('re:')) continue
    if (t === a) return 1
    const la = letters(a)
    if (la.length >= 5 && editDistance(letters(t), la) <= 1) best = Math.max(best, 0.9)
    const re = labelRe(a)
    const m = re.exec(t)
    if (m) best = Math.max(best, m[0].length / Math.max(t.length, 1))
  }
  return best
}

/** Captions of different columns inside one cell, each with the words it covers. */
function splitCaptions(text: string, words: Word[], columns: Column[], used: Set<string>): Band[] {
  const t = text.toLowerCase()
  const found: { name: string; start: number; end: number }[] = []
  for (const col of columns) {
    if (used.has(col.name)) continue
    for (const a of col.aliases) {
      if (a.startsWith('re:')) continue
      const re = labelRe(a)
      const m = re.exec(t)
      if (m) found.push({ name: col.name, start: m.index, end: m.index + m[0].length })
    }
  }
  found.sort((a, b) => (b.end - b.start) - (a.end - a.start))
  const picked: typeof found = []
  for (const f of found) {
    if (picked.some((p) => p.name === f.name || (f.start < p.end && f.end > p.start))) continue
    picked.push(f)
  }
  if (picked.length < 2) return []
  // Every word must belong to a picked caption, or the cell is one caption with extra words.
  let offset = 0
  const spans = words.map((w) => { const s = t.indexOf(w.text.toLowerCase(), offset); offset = s + w.text.length; return { w, s, e: s + w.text.length } })
  const covered = spans.every(({ s, e }) => picked.some((p) => s >= p.start && e <= p.end))
  if (!covered) return []
  return picked.map((p) => {
    const ws = spans.filter(({ s, e }) => s >= p.start && e <= p.end).map((x) => x.w)
    const x0 = Math.min(...ws.map((w) => w.x0))
    const x1 = Math.max(...ws.map((w) => w.x1))
    return { name: p.name, x0, x1, xc: (x0 + x1) / 2 }
  })
}

/** Find table headers on a page: lines where enough cells match column captions. */
export function findHeaders(page: PageRead, columns: Column[], minMatch = Math.max(2, Math.ceil(columns.length / 2))): Header[] {
  const out: Header[] = []
  page.lines.forEach((line, li) => {
    const cs = cells(line)
    if (cs.length < 2) return
    const used = new Set<string>()
    const bands: Band[] = []
    for (const c of cs) {
      // One cell may hold two captions set close together ("EMI Amount Overdue").
      const parts = splitCaptions(c.text, c.words, columns, used)
      if (parts.length >= 2) {
        for (const p of parts) { used.add(p.name); bands.push(p) }
        continue
      }
      let bestCol: Column | null = null
      let bestScore = 0.34
      for (const col of columns) {
        if (used.has(col.name)) continue
        const s = cellMatches(c.text, col.aliases)
        if (s > bestScore) { bestScore = s; bestCol = col }
      }
      if (bestCol) { used.add(bestCol.name); bands.push({ name: bestCol.name, x0: c.x0, x1: c.x1, xc: (c.x0 + c.x1) / 2 }) }
    }
    if (bands.length >= Math.min(minMatch, columns.length)) out.push({ page, lineIndex: li, bands: bands.sort((a, b) => a.x0 - b.x0) })
  })
  return out
}

const NUMERIC = /^[(-]?(?:₹|rs\.?)?[\d,]*\d(?:\.\d+)?\)?(?:cr|dr)?\.?$|^-$/i

/**
 * Assign a line's words to header bands. Amounts are right-aligned under
 * their header, so a number goes to the band whose left or right edge it
 * lines up with; text is left-aligned, so a word goes to the last band that
 * starts at or before it (a long narration never spills into the next column).
 */
export function assign(line: Line, bands: Band[]): Map<string, Cell> {
  const out = new Map<string, Cell>()
  const byX0 = [...bands].sort((a, b) => a.x0 - b.x0)
  const bandOf = (w: Word, numericCell: boolean): string => {
    // A number inside running text ("INV 1021") stays with its text.
    if (NUMERIC.test(w.text) && (numericCell || /[.,]\d/.test(w.text))) {
      let best = byX0[0]
      let d = Infinity
      for (const b of byX0) {
        const e = Math.min(Math.abs(w.x1 - b.x1), Math.abs(w.x0 - b.x0))
        if (e < d) { d = e; best = b }
      }
      return best.name
    }
    let chosen = byX0[0]
    for (const b of byX0) if (b.x0 <= w.x0 + 0.012) chosen = b
    return chosen.name
  }
  for (const c of cells(line)) {
    const groups: { band: string; words: Word[] }[] = []
    const numericCell = c.words.every((w) => NUMERIC.test(w.text))
    for (const w of c.words) {
      const b = bandOf(w, numericCell)
      const last = groups[groups.length - 1]
      if (last && last.band === b) last.words.push(w)
      else groups.push({ band: b, words: [w] })
    }
    for (const g of groups) {
      const x0 = Math.min(...g.words.map((w) => w.x0))
      const x1 = Math.max(...g.words.map((w) => w.x1))
      const text = g.words.map((w) => w.text).join(' ')
      const prev = out.get(g.band)
      if (prev) out.set(g.band, { text: `${prev.text} ${text}`, words: [...prev.words, ...g.words], x0: Math.min(prev.x0, x0), x1: Math.max(prev.x1, x1) })
      else out.set(g.band, { text, words: g.words, x0, x1 })
    }
  }
  return out
}

const STOP = /^(total|grand total|closing balance|opening balance|page \d+|\*\*|note[s]?:|this is a computer)/i

/** Rows under each header until the table visibly ends. */
export function readRows(pages: PageRead[], columns: Column[], opts: { minCells?: number; valid?: (cells: Map<string, Cell>) => boolean } = {}): Row[] {
  const rows: Row[] = []
  let lastBands: Band[] | null = null
  for (const page of pages) {
    const headers = findHeaders(page, columns)
    // A continuation page without a repeated header keeps the last bands.
    const starts: { li: number; bands: Band[] }[] = headers.map((h) => ({ li: h.lineIndex, bands: h.bands }))
    if (!starts.length && lastBands) starts.push({ li: -1, bands: lastBands })
    for (let s = 0; s < starts.length; s++) {
      const { li, bands } = starts[s]
      lastBands = bands
      const end = s + 1 < starts.length ? starts[s + 1].li : page.lines.length
      let prevY = li >= 0 ? page.lines[li].y1 : -1
      const lh = li >= 0 ? page.lines[li].y1 - page.lines[li].y0 : 0.015
      for (let k = li + 1; k < end; k++) {
        const line = page.lines[k]
        if (STOP.test(line.text.trim())) { if (/^(total|grand total)/i.test(line.text.trim())) break; continue }
        if (prevY >= 0 && line.y0 - prevY > 4 * lh && rows.length) break
        const assigned = assign(line, bands)
        if (assigned.size < (opts.minCells ?? 2)) continue
        if (opts.valid && !opts.valid(assigned)) {
          // A line that is not a row ends the table once rows have started.
          if (rows.length && rows[rows.length - 1].page === page) break
          continue
        }
        rows.push({ page, line, lineIndex: k, cells: assigned })
        prevY = line.y1
      }
    }
  }
  return rows
}
