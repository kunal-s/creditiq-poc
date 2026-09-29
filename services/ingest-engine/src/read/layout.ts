// Words to lines. Table columns stay apart: a horizontal gap wider than about
// two characters is written as COLUMN_GAP, so "Balance   1,20,000.00" never
// reads as one glued token.
import { COLUMN_GAP, type Line, type PageRead, type Word } from './types.js'

const median = (xs: number[]) => {
  if (!xs.length) return 0
  const s = [...xs].sort((a, b) => a - b)
  return s[Math.floor(s.length / 2)]
}

export function buildLines(words: Word[]): Line[] {
  const ws = words.filter((w) => w.text.trim().length > 0 && w.x1 > w.x0 && w.y1 > w.y0)
  if (!ws.length) return []
  const mh = median(ws.map((w) => w.y1 - w.y0)) || 0.01
  const byCentre = [...ws].sort((a, b) => (a.y0 + a.y1) / 2 - (b.y0 + b.y1) / 2 || a.x0 - b.x0)
  const groups: { yc: number; h: number; words: Word[] }[] = []
  for (const w of byCentre) {
    const yc = (w.y0 + w.y1) / 2
    const h = w.y1 - w.y0
    // Only the most recent few lines can still be open (words are sorted by centre).
    let target: (typeof groups)[number] | undefined
    for (let i = groups.length - 1; i >= Math.max(0, groups.length - 3); i--) {
      const g = groups[i]
      if (Math.abs(g.yc - yc) <= 0.5 * Math.min(Math.max(h, mh * 0.5), Math.max(g.h, mh * 0.5))) { target = g; break }
    }
    if (target) {
      target.words.push(w)
      const n = target.words.length
      target.yc = (target.yc * (n - 1) + yc) / n
      target.h = Math.max(target.h, h)
    } else groups.push({ yc, h, words: [w] })
  }
  return groups.map((g) => lineOf(g.words)).sort((a, b) => a.y0 - b.y0 || a.x0 - b.x0)
}

export function lineOf(words: Word[]): Line {
  const ws = [...words].sort((a, b) => a.x0 - b.x0)
  let text = ''
  const offsets: number[] = []
  ws.forEach((w, i) => {
    if (i > 0) {
      const prev = ws[i - 1]
      const charW = Math.max((prev.x1 - prev.x0) / Math.max(prev.text.length, 1), (w.x1 - w.x0) / Math.max(w.text.length, 1), 1e-4)
      const gap = w.x0 - prev.x1
      text += gap > 2.2 * charW ? COLUMN_GAP : ' '
    }
    offsets.push(text.length)
    text += w.text
  })
  return {
    words: ws,
    text,
    offsets,
    x0: Math.min(...ws.map((w) => w.x0)),
    y0: Math.min(...ws.map((w) => w.y0)),
    x1: Math.max(...ws.map((w) => w.x1)),
    y1: Math.max(...ws.map((w) => w.y1)),
  }
}

export function finishPage(p: Omit<PageRead, 'lines' | 'text'>): PageRead {
  const lines = buildLines(p.words)
  return { ...p, lines, text: lines.map((l) => l.text).join('\n') }
}

/** Union box of some words, rounded to 4 decimals. */
export function unionBox(words: Word[]): [number, number, number, number] | null {
  if (!words.length) return null
  const r = (x: number) => Math.round(Math.min(1, Math.max(0, x)) * 10000) / 10000
  return [r(Math.min(...words.map((w) => w.x0))), r(Math.min(...words.map((w) => w.y0))), r(Math.max(...words.map((w) => w.x1))), r(Math.max(...words.map((w) => w.y1)))]
}
