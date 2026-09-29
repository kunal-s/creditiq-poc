// Per-document keys and roll-ups: doc_key, instance_key, identity, defects
// (F-13.3) and near-duplicates (F-08.5).
import { createHash } from 'node:crypto'
import type { CompiledType } from './config.js'
import type { DocumentDefect, ExtractedField, IngestDocument } from './contract.js'
import type { PageRead } from './read/types.js'
import { pageNumber } from './split.js'

/** Stable across re-runs and request order: the file's bytes and the page range. */
export function docKey(fileSha256: string, from: number, to: number): string {
  return createHash('sha256').update(`doc:${fileSha256.toLowerCase()}:${from}-${to}`).digest('hex').slice(0, 32)
}

const val = (fields: ExtractedField[], name: string) => {
  const f = fields.find((x) => x.field === name && x.value !== null && x.value !== undefined)
  return f ? String(f.value) : null
}

/** F-10 identity fields, as extracted (never normalised toward another document). */
export function identityOf(fields: ExtractedField[]): Record<string, string> {
  const out: Record<string, string> = {}
  const pick = (key: string, names: string[]) => {
    for (const n of names) { const v = val(fields, n); if (v) { out[key] = v; return } }
  }
  pick('name', ['name', 'legal_name', 'company_name', 'enterprise_name', 'account_holder', 'subject_name'])
  pick('pan', ['pan'])
  pick('din', ['din'])
  pick('dob', ['date_of_birth'])
  pick('gstin', ['gstin'])
  pick('cin', ['cin'])
  return out
}

/** F-08.3: what tells this instance apart from the next of its type. */
export function instanceKeyOf(t: CompiledType | undefined, fields: ExtractedField[]): string | null {
  if (!t) return null
  switch (t.instance_key) {
    case 'period': return val(fields, 'period')
    case 'year': {
      const ay = val(fields, 'assessment_year')
      if (ay) return `AY${ay}`
      const pe = val(fields, 'period_end')
      return pe ? `FY-end ${pe}` : null
    }
    case 'account': {
      const a = val(fields, 'account_number_masked')
      return a ? `acct-${a.replace(/[^0-9]/g, '').slice(-4) || a}` : null
    }
    case 'person': return val(fields, 'pan') ?? val(fields, 'name')
    case 'property': return val(fields, 'property_description') ?? val(fields, 'survey_number')
    default: return null
  }
}

export function defectsOf(pages: PageRead[], t: CompiledType | undefined, fields: ExtractedField[]): DocumentDefect[] {
  const out: DocumentDefect[] = []
  const nums = pages.map((p) => ({ n: p.n, no: pageNumber(p) })).filter((x) => x.no)
  if (nums.length) {
    const of = Math.max(...nums.map((x) => x.no!.of ?? 0))
    const seen = new Set(nums.map((x) => x.no!.k))
    if (of > 0) {
      const absent = Array.from({ length: of }, (_, i) => i + 1).filter((k) => !seen.has(k))
      if (absent.length) out.push({ code: 'pages_absent', detail: `Printed page numbers ${absent.join(', ')} of ${of} are not in the document.`, pages: [] })
    }
    for (let i = 1; i < nums.length; i++) {
      const a = nums[i - 1]
      const b = nums[i]
      if (b.no!.k !== a.no!.k + 1 && b.no!.k !== 1) out.push({ code: 'pagination_break', detail: `Printed page ${a.no!.k} is followed by printed page ${b.no!.k}.`, pages: [a.n, b.n] })
    }
  }
  if (t?.id && fields.some((f) => /^transactions\[\d+\]\.date$/.test(f.field))) {
    const dates = fields.filter((f) => /^transactions\[\d+\]\.date$/.test(f.field) && typeof f.value === 'string').map((f) => ({ d: Date.parse(String(f.value)), page: f.page ?? 0 }))
    const from = val(fields, 'period_from')
    const to = val(fields, 'period_to')
    const pts = [...(from ? [{ d: Date.parse(from), page: 0 }] : []), ...dates.sort((a, b) => a.d - b.d), ...(to ? [{ d: Date.parse(to), page: 0 }] : [])]
    for (let i = 1; i < pts.length; i++) {
      const days = (pts[i].d - pts[i - 1].d) / 86_400_000
      if (days > 35) {
        out.push({ code: 'period_gap', detail: `No transactions between ${new Date(pts[i - 1].d).toISOString().slice(0, 10)} and ${new Date(pts[i].d).toISOString().slice(0, 10)}.`, pages: [...new Set([pts[i - 1].page, pts[i].page].filter((n) => n > 0))] })
      }
    }
  }
  return out
}

/** Word 3-shingles of a document's text, for near-duplicate detection. */
export function shingles(pages: PageRead[]): Set<string> {
  const words = pages.flatMap((p) => p.text.toLowerCase().match(/[a-z0-9]+/g) ?? [])
  const out = new Set<string>()
  for (let i = 0; i + 2 < words.length; i++) out.add(`${words[i]} ${words[i + 1]} ${words[i + 2]}`)
  return out
}

const jaccardContain = (a: Set<string>, b: Set<string>) => {
  if (!a.size) return 0
  let inter = 0
  for (const x of a) if (b.has(x)) inter++
  return inter / a.size
}

const gradeRank = { A: 0, B: 1, C: 2, U: 3 } as const

/**
 * F-08.5: the same content at a different hash, or a document contained in
 * another. The kept copy is the better one (grade, then more pages, then the
 * smaller key); the others point to it. Byte-identical files share doc_key
 * and are left to the engine's hash check.
 */
export function markDuplicates(docs: { doc: IngestDocument; sh: Set<string> }[]): void {
  const worst = (d: IngestDocument) => Math.max(...d.pages.map((p) => gradeRank[p.grade]))
  const better = (a: IngestDocument, b: IngestDocument) =>
    worst(a) !== worst(b) ? worst(a) < worst(b) : a.pages.length !== b.pages.length ? a.pages.length > b.pages.length : a.doc_key < b.doc_key
  for (const x of docs) {
    if (x.sh.size < 20) continue
    let keeper: IngestDocument | null = null
    for (const y of docs) {
      if (x === y || y.doc.doc_key === x.doc.doc_key || y.sh.size < 20) continue
      const shareTypes = x.doc.classification.types.some((t) => y.doc.classification.types.includes(t)) || (!x.doc.classification.types.length && !y.doc.classification.types.length)
      if (!shareTypes) continue
      const xInY = jaccardContain(x.sh, y.sh)
      const yInX = jaccardContain(y.sh, x.sh)
      const same = xInY >= 0.9 && yInX >= 0.9
      const contained = xInY >= 0.9 && y.doc.pages.length > x.doc.pages.length
      if ((same && better(y.doc, x.doc)) || contained) {
        if (!keeper || better(y.doc, keeper)) keeper = y.doc
      }
    }
    if (keeper) x.doc.duplicate_of_key = keeper.doc_key
  }
}
