// Bank statements (F-15.3): transaction rows rebuilt from word positions and
// checked against the running balance: previous balance + credit - debit =
// balance. A single cell that breaks the chain while its neighbours hold is
// repaired arithmetically, and the repair is recorded on the field.
import type { PageRead, Word } from '../read/types.js'
import { findHeaders, assign, type Band, type Column } from './tables.js'
import { findDates, findMoney, parseMoney } from './values.js'

export interface MoneyCell { raw: string | null; printed: number | null; value: number | null; words: Word[] }
export type Check = 'ok' | 'repaired' | 'failed' | 'unchecked'

export interface Txn {
  page: PageRead
  date: { raw: string; value: string; words: Word[] }
  narration: { raw: string; words: Word[] }
  ref: { raw: string; words: Word[] } | null
  debit: MoneyCell
  credit: MoneyCell
  balance: MoneyCell
  check: Check
  /** Which cell was repaired, if any. */
  repaired: 'debit' | 'credit' | 'balance' | null
}

const EPS = 0.005
const eq = (a: number, b: number) => Math.abs(a - b) < EPS

function money(cell: { text: string; words: Word[] } | undefined): MoneyCell {
  if (!cell) return { raw: null, printed: null, value: null, words: [] }
  const f = findMoney(cell.text)
  if (!f.length) return { raw: null, printed: null, value: null, words: [] }
  const m = f[f.length - 1]
  // A balance printed "1,20,000.00 Cr" keeps its suffix in raw.
  const v = parseMoney(m.raw)
  return { raw: m.raw, printed: v, value: v === null ? null : Math.abs(v) * (/dr\.?$/i.test(m.raw) ? -1 : 1), words: cell.words }
}

export function readTransactions(pages: PageRead[], columns: Column[]): { txns: Txn[]; opening: { raw: string; value: number; page: PageRead; words: Word[] } | null } {
  const txns: Txn[] = []
  let opening: { raw: string; value: number; page: PageRead; words: Word[] } | null = null
  let bands: Band[] | null = null
  for (const page of pages) {
    const headers = findHeaders(page, columns, 3)
    let startLine = 0
    if (headers.length) { bands = headers[0].bands; startLine = headers[0].lineIndex + 1 }
    if (!bands) continue
    const bandNames = new Set(bands.map((b) => b.name))
    if (!bandNames.has('date') || !bandNames.has('balance')) continue
    for (let k = startLine; k < page.lines.length; k++) {
      const line = page.lines[k]
      const text = line.text.trim()
      if (/^opening\s+balance/i.test(text) || /\bopening\s+balance\b/i.test(text)) {
        const f = findMoney(text)
        if (f.length && !opening) {
          const m = f[f.length - 1]
          opening = { raw: m.raw, value: m.value, page, words: line.words.filter((w) => m.raw.includes(w.text)) }
        }
        continue
      }
      if (/^(closing\s+balance|total|page\s+\d+|\*+|this is a)/i.test(text)) continue
      const cells = assign(line, bands)
      const dateCell = cells.get('date')
      const d = dateCell ? findDates(dateCell.text)[0] : undefined
      if (d && d.index <= 1) {
        const nar = cells.get('narration')
        const ref = cells.get('cheque_ref')
        txns.push({
          page,
          date: { raw: d.raw, value: d.value, words: dateCell!.words.filter((w) => d.raw.includes(w.text)) },
          narration: { raw: nar?.text ?? '', words: nar?.words ?? [] },
          ref: ref ? { raw: ref.text, words: ref.words } : null,
          debit: money(cells.get('debit')),
          credit: money(cells.get('credit')),
          balance: money(cells.get('balance')),
          check: 'unchecked',
          repaired: null,
        })
      } else if (txns.length && txns[txns.length - 1].page === page) {
        // A narration that wraps onto the next line.
        const nar = cells.get('narration')
        const last = txns[txns.length - 1]
        if (nar && cells.size <= 2 && !findMoney(nar.text).some((m) => Math.abs(m.value) >= 1000 && /[.,]/.test(m.raw))) {
          last.narration = { raw: `${last.narration.raw} ${nar.text}`.trim(), words: [...last.narration.words, ...nar.words] }
        }
      }
    }
  }
  return { txns, opening }
}

/**
 * Walk the chain. `opening` anchors the first row; without it the first
 * printed balance does. Repairs one cell at a time and only when the next row
 * confirms the repair (or the row is the last one).
 */
export function checkBalances(txns: Txn[], opening: number | null): void {
  let prev: number | null = opening
  for (let i = 0; i < txns.length; i++) {
    const t = txns[i]
    const cr = t.credit.value ?? 0
    const dr = t.debit.value ?? 0
    const bal = t.balance.value
    if (prev === null) {
      t.check = 'unchecked'
      prev = bal
      continue
    }
    const expected = Math.round((prev + cr - dr) * 100) / 100
    if (bal !== null && eq(expected, bal)) { t.check = 'ok'; prev = bal; continue }
    const next = txns[i + 1]
    const nextHolds = (base: number) => {
      if (!next || next.balance.value === null) return !next
      return eq(Math.round((base + (next.credit.value ?? 0) - (next.debit.value ?? 0)) * 100) / 100, next.balance.value)
    }
    // (a) the balance cell is wrong or missing.
    if (nextHolds(expected) && (bal === null || next)) {
      t.balance = { ...t.balance, value: expected }
      t.check = 'repaired'
      t.repaired = 'balance'
      prev = expected
      continue
    }
    // (b) the one amount on the row is wrong or missing.
    if (bal !== null && nextHolds(bal)) {
      const delta = Math.round((bal - prev) * 100) / 100
      const hasCr = t.credit.value !== null
      const hasDr = t.debit.value !== null
      if (delta >= 0 && !hasDr) { t.credit = { ...t.credit, value: delta }; t.check = 'repaired'; t.repaired = 'credit'; prev = bal; continue }
      if (delta < 0 && !hasCr) { t.debit = { ...t.debit, value: -delta }; t.check = 'repaired'; t.repaired = 'debit'; prev = bal; continue }
    }
    t.check = 'failed'
    prev = bal ?? expected
  }
}
