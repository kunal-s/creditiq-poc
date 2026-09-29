// Splitting a file into logical documents (FRD F-08). Boundaries come from
// page content only: a change of anchored document type, page numbering
// restarting, a new instance of the same type (another period, account or
// person), or a change of issuer identifiers. A boundary that rests on a weak
// cue alone is marked split_uncertain and goes to review (F-08.6).
import type { CompiledType, LoadedConfig } from './config.js'
import type { PageClass } from './classify.js'
import { findIdentifiers } from './extract/identifiers.js'
import { findDates, parsePeriod, parseYearRange } from './extract/values.js'
import type { PageRead } from './read/types.js'

export interface Segment { pages: PageRead[]; classes: PageClass[]; uncertain: boolean }

export interface PageNo { k: number; of: number | null }

export function pageNumber(page: PageRead): PageNo | null {
  const lines = page.lines
  const edge = [...lines.slice(0, 3), ...lines.slice(-3)]
  for (const l of edge) {
    const t = l.text
    let m = /\bpage\s*(?:no\.?\s*)?(\d{1,3})\s*(?:of|\/)\s*(\d{1,3})\b/i.exec(t)
    if (m) return { k: Number(m[1]), of: Number(m[2]) }
    m = /\bpage\s*(?:no\.?\s*)?(\d{1,3})\b/i.exec(t)
    if (m) return { k: Number(m[1]), of: null }
    m = /^\s*[-–]?\s*(\d{1,3})\s*(?:\/|of)\s*(\d{1,3})\s*[-–]?\s*$/.exec(t)
    if (m) return { k: Number(m[1]), of: Number(m[2]) }
  }
  return null
}

/** Identifiers printed in the top quarter of a page: the issuer or party. */
function headerIds(page: PageRead): Set<string> {
  const top = page.lines.filter((l) => l.y0 < 0.25).map((l) => l.text).join('\n')
  return new Set([...findIdentifiers('gstin', top), ...findIdentifiers('pan', top), ...findIdentifiers('cin', top)].map((x) => x.value))
}

/** What distinguishes one instance of a type from the next on its first page. */
export function fingerprint(page: PageRead, t: CompiledType): string | null {
  const text = page.text
  switch (t.instance_key) {
    case 'period': {
      const fy = parseYearRange(/year[^\n]*/i.exec(text)?.[0] ?? '')
      for (const l of page.lines) {
        if (!/period|month/i.test(l.text)) continue
        const rest = l.text.replace(/^.*?(tax\s+)?(period|month)\s*[:.-]?\s*/i, '')
        const v = parsePeriod(rest.split(/\s{3,}/)[0] ?? '', fy)
        if (v) return v
      }
      return null
    }
    case 'year': {
      const m = /(assessment|financial)\s+year[^\n]*?(20\d{2}\s?[-–]\s?\d{2,4})/i.exec(text)
      if (m) return parseYearRange(m[2])
      const as = /as\s+at[^\n]*/i.exec(text)
      const d = as ? findDates(as[0])[0] : undefined
      return d ? d.value : null
    }
    case 'account': {
      const m = /(?:account|a\/c)\s*(?:no\.?|number)?\s*[:.-]?\s*([Xx*\d][Xx*\d -]{5,}\d{3,4})/i.exec(text)
      return m ? m[1].replace(/\D/g, '').slice(-4) : null
    }
    case 'person': {
      const p = findIdentifiers('pan', text)[0]
      return p ? p.value : null
    }
    default:
      return null
  }
}

const hasWords = (p: PageRead) => p.words.length > 0

export function splitPages(pages: PageRead[], classes: PageClass[], _cfg: LoadedConfig): Segment[] {
  const segs: Segment[] = []
  let cur: Segment | null = null
  let curTypes = new Set<string>()
  let curPrints = new Map<string, string>()
  const start = (i: number, uncertain: boolean) => {
    cur = { pages: [pages[i]], classes: [classes[i]], uncertain }
    segs.push(cur)
    curTypes = new Set()
    curPrints = new Map()
    note(i)
  }
  const note = (i: number) => {
    const a = classes[i].anchor
    if (!a) return
    curTypes.add(a.type.id)
    const fp = fingerprint(pages[i], a.type)
    if (fp && !curPrints.has(a.type.id)) curPrints.set(a.type.id, fp)
  }
  const join = (i: number) => { cur!.pages.push(pages[i]); cur!.classes.push(classes[i]); note(i) }

  for (let i = 0; i < pages.length; i++) {
    const open = cur as Segment | null
    if (!open) { start(i, false); continue }
    const p = pages[i]
    if (!hasWords(p)) { join(i); continue }
    const prev = [...open.pages].reverse().find(hasWords)
    const a = classes[i].anchor
    const no = pageNumber(p)
    const prevNo = prev ? pageNumber(prev) : null
    const continues = Boolean(no && prevNo && no.k === prevNo.k + 1 && (no.of === prevNo.of || no.of === null || prevNo.of === null))
    const restart = Boolean(no && no.k === 1 && (prevNo || a))
    if (a) {
      if (!curTypes.size) {
        // Unanchored lead pages: a separate document unless numbering runs on.
        if (continues) join(i)
        else start(i, false)
        if (!continues && segs.length > 1) segs[segs.length - 2].uncertain = true
        continue
      }
      if (!curTypes.has(a.type.id)) {
        if (continues) join(i)
        else start(i, false)
        continue
      }
      if (restart) { start(i, false); continue }
      const fp = fingerprint(p, a.type)
      const was = curPrints.get(a.type.id)
      if (fp && was && fp !== was && !continues) { start(i, false); continue }
      join(i)
      continue
    }
    if (restart && !continues) { start(i, true); continue }
    const ids = headerIds(p)
    const prevIds = prev ? headerIds(prev) : new Set<string>()
    if (ids.size && prevIds.size && ![...ids].some((x) => prevIds.has(x)) && !continues) { start(i, true); continue }
    join(i)
  }
  return segs
}
