// Field extraction per document against its type's dictionary (F-15).
//
// Deterministic first: identifiers by pattern and checksum, values anchored
// to their captions, tables from word positions, bank rows checked against
// the running balance. The model is asked only for what remains, and only
// for where a value is printed: it returns the text as printed (or, for an
// amount, the row caption) and the page; the value itself is always read
// from the page. Every value is verified on its page's word index (F-15.4).
import type { DictionarySection, FieldDef, IdentifierKind, LoadedConfig } from '../config.js'
import { components } from '../confidence.js'
import type { ExtractedField, Grade, PageInfo, Scalar } from '../contract.js'
import { ModelError, type ModelClient } from '../llm/index.js'
import { unionBox } from '../read/layout.js'
import type { Line, PageRead, Word } from '../read/types.js'
import { aliasesFor } from './aliases.js'
import { cells, findLabelled, wordsInSpan, type Accept, type Candidate, type Hit } from './anchors.js'
import { checkBalances, readTransactions, type MoneyCell } from './bank.js'
import { ANCHORED_TOKEN, checkIdentifier, compact, findIdentifiers } from './identifiers.js'
import { locate, wordTrust } from './locate.js'
import { readRows, type Column } from './tables.js'
import { findDates, findMoney, parseMoney, parseNumber, parsePercent, parsePeriod, parseYearRange } from './values.js'

export interface ExtractContext {
  pages: PageRead[]
  grades: Map<number, PageInfo>
  typeId: string
  typeName: string
  dict: DictionarySection
  classification: number
  config: LoadedConfig
  model: ModelClient | null
}

export interface ExtractOutcome {
  fields: ExtractedField[]
  modelMisses: number
  modelErrors: number
}

// ---------------------------------------------------------------- accept

const firstCell = (s: string) => {
  const c = s.split(/\s{3,}/)[0]
  return { text: c.trim(), start: s.indexOf(c.trim()) }
}

function acceptText(s: string): Candidate | null {
  const { text, start } = firstCell(s)
  if (!text || /^[\s:;.,\-–|]+$/.test(text) || /:\s*$/.test(text) || text.length > 200) return null
  const value = text.replace(/[\s:;,]+$/, '')
  return value ? { raw: text, value, start } : null
}

const acceptDate: Accept = (s) => {
  const d = findDates(s)[0]
  return d && d.index < 40 ? { raw: d.raw, value: d.value, start: d.index } : null
}

const acceptMoney: Accept = (s) => {
  const f = findMoney(s).filter((m) => !/^\d{1,2}$/.test(m.raw) || findMoney(s).length === 1)
  const m = f[0]
  return m ? { raw: m.raw, value: m.value, start: m.index } : null
}

const acceptNumber: Accept = (s) => {
  const m = /-?\d[\d,]*(?:\.\d+)?/.exec(s)
  if (!m) return null
  const v = parseNumber(m[0])
  return v === null ? null : { raw: m[0], value: v, start: m.index }
}

const acceptPercent: Accept = (s) => {
  const m = /-?\d+(?:\.\d+)?\s?%?/.exec(s)
  if (!m) return null
  const v = parsePercent(m[0])
  return v === null ? null : { raw: m[0].trim(), value: v, start: m.index }
}

const acceptBoolean: Accept = (s) => {
  const { text, start } = firstCell(s)
  if (/^(yes|y|true|filed)$/i.test(text)) return { raw: text, value: true, start }
  if (/^(no|n|false|not filed|pending)$/i.test(text)) return { raw: text, value: false, start }
  return null
}

function acceptIdentifier(kind: IdentifierKind): Accept {
  return (s) => {
    const head = s.slice(0, 60)
    const up = head.toUpperCase()
    const m = ANCHORED_TOKEN[kind].exec(up)
    if (!m || m.index > 12) return null
    const raw = head.slice(m.index, m.index + m[0].length)
    const chk = checkIdentifier(kind, raw)
    const invalid = !chk.format || chk.checksum === false
    // A token that is plainly not this identifier (a word, a date) is not a value.
    if (!chk.format && !/\d/.test(raw)) return null
    return { raw, value: compact(raw), start: m.index, invalid }
  }
}

function acceptPeriod(fy: string | null): Accept {
  return (s) => {
    const { text, start } = firstCell(s)
    const v = parsePeriod(text, fy)
    return v ? { raw: text, value: v, start } : null
  }
}

function acceptFor(f: FieldDef, fy: string | null = null): Accept {
  switch (f.type) {
    case 'date': return acceptDate
    case 'money_inr': return acceptMoney
    case 'number': return acceptNumber
    case 'percent': return acceptPercent
    case 'boolean': return acceptBoolean
    case 'period': return acceptPeriod(fy)
    case 'identifier': return f.identifier ? acceptIdentifier(f.identifier) : acceptText
    default: return acceptText
  }
}

// ---------------------------------------------------------------- special readers

/** Financial or assessment year printed on the pages ("Year 2025-26"). */
function pageFy(pages: PageRead[]): string | null {
  const hit = findLabelled(pages, ['financial year', 'year', 'f.y.', 'fy'], (s) => {
    const v = parseYearRange(s.slice(0, 20))
    return v ? { raw: s.slice(0, 20).trim().split(/\s{3,}/)[0], value: v, start: 0 } : null
  })
  return hit ? String(hit.value) : null
}

/** Statement period "From 01/04/2025 To 30/06/2025": the two dates on one line. */
function statementPeriod(pages: PageRead[]): { from: Hit; to: Hit } | null {
  for (const page of pages.slice(0, 2)) {
    for (const line of page.lines) {
      if (!/period|from|between/i.test(line.text)) continue
      const ds = findDates(line.text)
      if (ds.length < 2) continue
      const mk = (d: (typeof ds)[number]): Hit => ({ raw: d.raw, value: d.value, page, line, words: wordsInSpan(line, d.index, d.index + d.raw.length), alias: 'period' })
      return { from: mk(ds[0]), to: mk(ds[1]) }
    }
  }
  return null
}

/** Year columns of a financial statement page; the latest is the current year. */
function yearColumns(page: PageRead): { current: number; others: number[] } | null {
  for (const line of page.lines.slice(0, 40)) {
    const toks: { xc: number; year: number }[] = []
    for (const d of findDates(line.text)) {
      const ws = wordsInSpan(line, d.index, d.index + d.raw.length)
      if (ws.length) toks.push({ xc: (Math.min(...ws.map((w) => w.x0)) + Math.max(...ws.map((w) => w.x1))) / 2, year: Number(d.value.slice(0, 4)) + Number(d.value.slice(5, 7)) / 100 })
    }
    if (toks.length < 2) {
      toks.length = 0
      const re = /(?<!\d)(20\d{2})\s?[-–]\s?(\d{2})(?!\d)/g
      let m: RegExpExecArray | null
      while ((m = re.exec(line.text))) {
        const ws = wordsInSpan(line, m.index, m.index + m[0].length)
        if (ws.length) toks.push({ xc: (Math.min(...ws.map((w) => w.x0)) + Math.max(...ws.map((w) => w.x1))) / 2, year: Number(m[1]) })
      }
    }
    if (toks.length >= 2) {
      toks.sort((a, b) => b.year - a.year)
      return { current: toks[0].xc, others: toks.slice(1).map((t) => t.xc) }
    }
  }
  return null
}

/** A statement row's amount for the current year (never a note reference). */
function statementAmount(pages: PageRead[], aliases: string[]): Hit | null {
  const cols = new Map<number, ReturnType<typeof yearColumns>>()
  let hit: Hit | null = null
  const pick = (s: string, line: Line, offset: number, page: PageRead): Candidate | null => {
    const toks = findMoney(s)
    if (!toks.length) return null
    if (!cols.has(page.n)) cols.set(page.n, yearColumns(page))
    const yc = cols.get(page.n)
    const withX = toks.map((t) => {
      const ws = wordsInSpan(line, offset + t.index, offset + t.index + t.raw.length)
      return { t, xc: ws.length ? (Math.min(...ws.map((w) => w.x0)) + Math.max(...ws.map((w) => w.x1))) / 2 : 0 }
    })
    if (yc) {
      const best = withX
        .filter(({ xc }) => yc.others.every((o) => Math.abs(xc - yc.current) < Math.abs(xc - o)))
        .sort((a, b) => Math.abs(a.xc - yc.current) - Math.abs(b.xc - yc.current))[0]
      if (best && Math.abs(best.xc - yc.current) < 0.12) return { raw: best.t.raw, value: best.t.value, start: best.t.index }
      return null
    }
    const notNote = withX.filter(({ t }, i) => !(i < withX.length - 1 && /^\d{1,2}(\.\d)?$/.test(t.raw)))
    const t = notNote[0]?.t
    return t ? { raw: t.raw, value: t.value, start: t.index } : null
  }
  hit = findLabelled(pages, aliases, (s, where) => (where ? pick(s, where.line, where.offset, where.page) : null), { below: false })
  return hit
}

function searchPhrase(pages: PageRead[], re: RegExp): Hit | null {
  for (const page of pages) {
    for (const line of page.lines) {
      const m = re.exec(line.text)
      if (!m) continue
      const raw = m[1] ?? m[0]
      const s = m.index + m[0].indexOf(raw)
      return { raw, value: raw, page, line, words: wordsInSpan(line, s, s + raw.length), alias: re.source }
    }
  }
  return null
}

// ---------------------------------------------------------------- field building

interface Built { hit: Hit | null; method: 'deterministic' | 'model'; validation?: number; agreement?: number; caps?: string[]; extra?: Record<string, number>; missing?: string }

function gradeOf(ctx: ExtractContext, n: number): Grade { return ctx.grades.get(n)?.grade ?? 'A' }

function build(ctx: ExtractContext, name: string, f: FieldDef, b: Built): ExtractedField {
  const missing = (reason: string, method = b.method, extraCaps: string[] = []): ExtractedField => ({
    field: name, value: null, raw: null, page: null, bbox: null, method,
    confidence_components: extraCaps.length ? components(ctx.config.confidence, { classification: ctx.classification, grade: 'A', readingTrust: 0, validation: 0, agreement: 0, caps: extraCaps }) : {},
    missing_reason: reason,
  })
  if (!b.hit) return missing(b.missing ?? 'not_found')
  const h = b.hit
  // F-15.4: the raw text must be on its page.
  const found = locate(h.page, h.raw, h.words[0]?.y0)
  if (!found) return missing('not_found_on_page', b.method, ['not_found_on_page'])
  const words: Word[] = h.words.length ? h.words : found.words
  let validation = b.validation ?? (f.type === 'text' ? 0.7 : 0.9)
  const caps = [...(b.caps ?? [])]
  if (f.type === 'identifier' && f.identifier) {
    const chk = checkIdentifier(f.identifier, String(h.value))
    if (!chk.format || chk.checksum === false) { validation = 0; caps.push('checksum_fail') } else validation = 1
  }
  return {
    field: name,
    value: h.value as Scalar,
    raw: h.raw,
    page: h.page.n,
    bbox: unionBox(words) ?? found.bbox,
    method: b.method,
    confidence_components: components(ctx.config.confidence, {
      classification: ctx.classification,
      grade: gradeOf(ctx, h.page.n),
      readingTrust: wordTrust(words),
      validation,
      agreement: b.agreement ?? 0.5,
      caps,
      extra: b.extra,
    }),
    missing_reason: null,
  }
}

// ---------------------------------------------------------------- scalar fields

function deterministic(ctx: ExtractContext, f: FieldDef, fy: string | null, period: ReturnType<typeof statementPeriod>): Built {
  const d = ctx.dict.id
  const aliases = aliasesFor(d, f.name, f.label, f.name)
  const pages = ctx.pages
  const key = `${d}.${f.name}`

  if (key === 'bank_statement.period_from' && period) return { hit: period.from, method: 'deterministic' }
  if (key === 'bank_statement.period_to' && period) return { hit: period.to, method: 'deterministic' }
  if (key === 'bank_statement.account_number_masked') {
    const hit = findLabelled(pages, aliases, (s) => {
      const m = /[Xx*\d][Xx*\d -]{5,}\d{3,4}/.exec(s.slice(0, 40))
      return m ? { raw: m[0].trim(), value: m[0].trim(), start: m.index } : null
    })
    return { hit, method: 'deterministic' }
  }
  if (key === 'financial_statements.audited') {
    const yes = searchPhrase(pages, /(?:independent\s+)?auditor'?s'?\s+report/i)
    if (yes) return { hit: { ...yes, value: true }, method: 'deterministic' }
    const no = searchPhrase(pages, /\b(?:provisional|unaudited)\b/i)
    return { hit: no ? { ...no, value: false } : null, method: 'deterministic' }
  }
  if (key === 'financial_statements.auditor') {
    const hit = searchPhrase(pages, /[Ff]or\s+([A-Z][A-Za-z.&' ]+?(?:&\s*Co\.?|Associates|LLP))(?=\s{2,}|\s*$|,)/)
    return { hit, method: 'deterministic' }
  }
  if (d === 'financial_statements' && f.type === 'money_inr') return { hit: statementAmount(pages, aliases), method: 'deterministic' }

  const accept = acceptFor(f, fy)
  // An amount is printed beside its caption; below a caption sits a column's first row.
  const numeric = f.type === 'money_inr' || f.type === 'number' || f.type === 'percent'
  let hit = findLabelled(pages, aliases, accept, { below: !numeric })
  if (f.type === 'identifier' && f.identifier) {
    const all = pages.flatMap((p) => findIdentifiers(f.identifier!, p.text).map((x) => ({ ...x, page: p })))
    if (hit) {
      const agree = all.some((x) => x.value === hit!.value)
      return { hit, method: 'deterministic', agreement: agree ? 1 : 0.5 }
    }
    // Unanchored: the first valid occurrence in reading order (the borrower's own
    // identifier heads its documents; a customer's appears in the body, F-15.5).
    const valid = all.find((x) => { const c = checkIdentifier(f.identifier!, x.value); return c.format && c.checksum !== false })
    if (valid) {
      const line = valid.page.lines.find((l) => l.text.toUpperCase().replace(/\s+/g, '').includes(valid.value)) ?? valid.page.lines[0]
      const at = line.text.toUpperCase().indexOf(valid.raw.toUpperCase())
      hit = { raw: valid.raw, value: valid.value, page: valid.page, line, words: at >= 0 ? wordsInSpan(line, at, at + valid.raw.length) : [], alias: 'pattern' }
      return { hit, method: 'deterministic', agreement: 0.5 }
    }
    return { hit: null, method: 'deterministic' }
  }
  return { hit, method: 'deterministic' }
}

// ---------------------------------------------------------------- tables

function tableColumns(d: string, f: FieldDef): Column[] {
  return f.columns.map((c) => ({ name: c.name, aliases: aliasesFor(d, `${f.name}.${c.name}`, c.label, c.name) }))
}

function cellValue(c: FieldDef, text: string): { raw: string; value: Scalar; start: number } | null {
  const hit = acceptFor(c)(text)
  if (hit) return { raw: hit.raw, value: hit.value as Scalar, start: hit.start }
  return null
}

function extractTable(ctx: ExtractContext, f: FieldDef): ExtractedField[] {
  const cols = tableColumns(ctx.dict.id, f)
  const out: ExtractedField[] = []
  // A row is a line where at least two cells read as their column's type.
  const valid = (cs: Map<string, { text: string }>) => f.columns.filter((c) => { const x = cs.get(c.name); return x ? cellValue(c, x.text) !== null : false }).length >= Math.min(2, f.columns.length)
  const rows = readRows(ctx.pages, cols, { valid })
  rows.forEach((row, i) => {
    for (const c of f.columns) {
      const cell = row.cells.get(c.name)
      if (!cell) continue
      const v = cellValue(c, cell.text)
      if (!v) continue
      const covering = cell.words.filter((w) => v.raw.includes(w.text))
      out.push(build(ctx, `${f.name}[${i}].${c.name}`, c, { hit: { raw: v.raw, value: v.value as string, page: row.page, line: row.line, words: covering.length ? covering : cell.words, alias: 'table' }, method: 'deterministic' }))
    }
  })
  if (!out.length) out.push(build(ctx, f.name, f, { hit: null, method: 'deterministic', missing: 'not_found' }))
  return out
}

function extractTransactions(ctx: ExtractContext, f: FieldDef, openingField: ExtractedField | undefined): ExtractedField[] {
  const cols = tableColumns(ctx.dict.id, f)
  const { txns, opening } = readTransactions(ctx.pages, cols)
  const openingValue = typeof openingField?.value === 'number' ? openingField.value : opening?.value ?? null
  checkBalances(txns, openingValue)
  const out: ExtractedField[] = []
  const status = (check: string) => ({ ok: 1, repaired: 0.7, failed: 0.2, unchecked: 0.6 })[check] ?? 0.6
  txns.forEach((t, i) => {
    const base = { method: 'deterministic' as const, agreement: t.check === 'ok' ? 1 : 0.5 }
    const colDef = (n: string) => f.columns.find((c) => c.name === n)
    const push = (col: string, raw: string, value: Scalar, words: Word[], validation: number, extra?: Record<string, number>) => {
      const def = colDef(col)
      if (!def) return
      const line = t.page.lines.find((l) => words.some((w) => l.words.includes(w))) ?? t.page.lines[0]
      out.push(build(ctx, `${f.name}[${i}].${col}`, def, { hit: { raw, value: value as string, page: t.page, line, words, alias: 'table' }, ...base, validation, extra }))
    }
    push('date', t.date.raw, t.date.value, t.date.words, 0.9)
    if (t.narration.raw) push('narration', t.narration.raw, t.narration.raw, t.narration.words, 0.7)
    if (t.ref?.raw) push('cheque_ref', t.ref.raw, t.ref.raw, t.ref.words, 0.7)
    const moneyCell = (col: 'debit' | 'credit' | 'balance', m: MoneyCell) => {
      if (m.value === null) return
      const repaired = t.repaired === col
      if (m.raw === null) {
        // Repaired from the chain with nothing legible printed: page of the row, no raw.
        const def = colDef(col)
        if (!def) return
        out.push({
          field: `${f.name}[${i}].${col}`, value: m.value, raw: null, page: t.page.n, bbox: null, method: 'deterministic',
          confidence_components: components(ctx.config.confidence, { classification: ctx.classification, grade: gradeOf(ctx, t.page.n), readingTrust: 0, validation: status(t.check), agreement: 0.5, extra: { 'repair.running_balance': 1 } }),
          missing_reason: null,
        })
        return
      }
      const ws = m.words.filter((w) => m.raw!.includes(w.text))
      push(col, m.raw, m.value, ws.length ? ws : m.words, status(t.check), repaired ? { 'repair.running_balance': 1 } : undefined)
    }
    moneyCell('debit', t.debit)
    moneyCell('credit', t.credit)
    moneyCell('balance', t.balance)
  })
  if (!out.length) out.push(build(ctx, f.name, f, { hit: null, method: 'deterministic', missing: 'not_found' }))
  return out
}

// ---------------------------------------------------------------- model fill

const WINDOW_CHARS = 12_000

function windows(pages: PageRead[]): PageRead[][] {
  const out: PageRead[][] = []
  let cur: PageRead[] = []
  let size = 0
  for (const p of pages) {
    if (cur.length && size + p.text.length > WINDOW_CHARS) { out.push(cur); cur = []; size = 0 }
    cur.push(p)
    size += p.text.length
  }
  if (cur.length) out.push(cur)
  return out
}

const SYSTEM = [
  'You locate fields in one business document, reading only the page text given.',
  'For each requested field, return the text exactly as it is printed on the page (raw) and the page number it is printed on.',
  'For an amount or a number, return the caption or row label exactly as printed (row_label) and leave raw null; the caller reads the number from that row.',
  'Return null for a field that is not printed. Never compute, convert, complete or infer a value, and never use knowledge from outside the document.',
].join('\n')

interface ModelAnswer { fields: { field: string; raw: string | null; row_label: string | null; page: number | null }[] }

async function modelFill(ctx: ExtractContext, missing: FieldDef[], outcome: ExtractOutcome): Promise<Map<string, Built>> {
  const result = new Map<string, Built>()
  if (!ctx.model || !missing.length) return result
  const names = missing.map((f) => f.name)
  const schema = {
    type: 'object',
    properties: {
      fields: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            field: { type: 'string', enum: names },
            raw: { type: ['string', 'null'] },
            row_label: { type: ['string', 'null'] },
            page: { type: ['integer', 'null'] },
          },
        },
      },
    },
  }
  for (const win of windows(ctx.pages)) {
    const pending = missing.filter((f) => !result.get(f.name)?.hit)
    if (!pending.length) break
    const user = [
      `Document type: ${ctx.typeName}`,
      'Fields:',
      ...pending.map((f) => `- ${f.name} (${f.type}): ${f.label}${f.description ? `. ${f.description}` : ''}`),
      '',
      'Pages:',
      ...win.map((p) => `=== Page ${p.n} ===\n${p.text}`),
    ].join('\n')
    let answer: ModelAnswer
    try {
      answer = (await ctx.model.call({ task: 'extract', system: SYSTEM, user, schema })) as ModelAnswer
    } catch (e) {
      const reason = e instanceof ModelError && e.code === 'replay_miss' ? 'model_unavailable' : 'model_error'
      if (reason === 'model_unavailable') outcome.modelMisses++
      else outcome.modelErrors++
      for (const f of pending) if (!result.has(f.name)) result.set(f.name, { hit: null, method: 'model', missing: reason })
      continue
    }
    for (const a of answer?.fields ?? []) {
      const f = pending.find((x) => x.name === a.field)
      if (!f) continue
      const page = win.find((p) => p.n === a.page)
      if (!page) { result.set(f.name, { hit: null, method: 'model', missing: a.raw || a.row_label ? 'not_found_on_page' : 'not_found', caps: [] }); continue }
      let hit: Hit | null = null
      if ((f.type === 'money_inr' || f.type === 'number' || f.type === 'percent') && a.row_label) {
        hit = ctx.dict.id === 'financial_statements' ? statementAmount([page], [a.row_label.toLowerCase()]) : findLabelled([page], [a.row_label.toLowerCase()], acceptFor(f), { below: false })
      } else if (a.raw) {
        const c = acceptFor(f, pageFy([page]))(a.raw)
        if (c) {
          const loc = locate(page, c.raw)
          hit = loc ? { raw: c.raw, value: c.value, page, line: page.lines.find((l) => loc.words.some((w) => l.words.includes(w))) ?? page.lines[0], words: loc.words, alias: 'model', invalid: c.invalid } : null
          if (!loc) { result.set(f.name, { hit: null, method: 'model', missing: 'not_found_on_page', caps: ['not_found_on_page'] }); continue }
        }
      }
      if (hit) result.set(f.name, { hit, method: 'model', agreement: 0.5 })
      else if (!result.has(f.name)) result.set(f.name, { hit: null, method: 'model', missing: a.raw || a.row_label ? 'not_found_on_page' : 'not_found' })
    }
  }
  return result
}

// ---------------------------------------------------------------- driver

export async function extractDocument(ctx: ExtractContext): Promise<ExtractOutcome> {
  const outcome: ExtractOutcome = { fields: [], modelMisses: 0, modelErrors: 0 }
  const fy = pageFy(ctx.pages)
  const period = ctx.dict.id === 'bank_statement' ? statementPeriod(ctx.pages) : null
  const scalars = new Map<string, Built>()
  for (const f of ctx.dict.fields) {
    if (f.type === 'table') continue
    scalars.set(f.name, deterministic(ctx, f, fy, period))
  }
  const missing = ctx.dict.fields.filter((f) => f.type !== 'table' && !scalars.get(f.name)?.hit)
  const filled = await modelFill(ctx, missing, outcome)
  for (const f of ctx.dict.fields) {
    if (f.type === 'table') continue
    const det = scalars.get(f.name)!
    const b = det.hit ? det : filled.get(f.name) ?? det
    outcome.fields.push(build(ctx, f.name, f, b))
  }
  for (const f of ctx.dict.fields) {
    if (f.type !== 'table') continue
    if (ctx.dict.id === 'bank_statement' && f.name === 'transactions') outcome.fields.push(...extractTransactions(ctx, f, outcome.fields.find((x) => x.field === 'opening_balance')))
    else outcome.fields.push(...extractTable(ctx, f))
  }
  return outcome
}

export { cells }
export const _test = { acceptIdentifier, acceptMoney, statementAmount, parseMoney }
