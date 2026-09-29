// Typed values from printed text. Each parser takes the text as printed and
// returns the normalised value, or null when the text is not of that kind.
// Values are never computed from anything but the printed text (F-15.3).

export const MONTHS: Record<string, number> = {
  jan: 1, january: 1, feb: 2, february: 2, mar: 3, march: 3, apr: 4, april: 4, may: 5, jun: 6, june: 6,
  jul: 7, july: 7, aug: 8, august: 8, sep: 9, sept: 9, september: 9, oct: 10, october: 10, nov: 11, november: 11, dec: 12, december: 12,
}
const MONTH_RE = 'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?'

const pad = (n: number) => String(n).padStart(2, '0')

function validYmd(y: number, m: number, d: number): boolean {
  if (m < 1 || m > 12 || d < 1 || y < 1900 || y > 2100) return false
  return d <= new Date(Date.UTC(y, m, 0)).getUTCDate()
}
const iso = (y: number, m: number, d: number) => (validYmd(y, m, d) ? `${y}-${pad(m)}-${pad(d)}` : null)
const year4 = (y: string) => (y.length === 2 ? 2000 + Number(y) : Number(y))

export interface Found<T> { raw: string; value: T; index: number }

/** Every date in a text, in order. Day-first, as printed in India. */
export function findDates(text: string): Found<string>[] {
  const out: Found<string>[] = []
  const patterns: [RegExp, (m: RegExpExecArray) => string | null][] = [
    [/(?<![\d/.-])(\d{4})-(\d{2})-(\d{2})(?![\d])/g, (m) => iso(Number(m[1]), Number(m[2]), Number(m[3]))],
    [/(?<![\d/.-])(\d{1,2})\s?[/.-]\s?(\d{1,2})\s?[/.-]\s?(\d{4}|\d{2})(?![\d/.-]*\d)/g, (m) => iso(year4(m[3]), Number(m[2]), Number(m[1]))],
    [new RegExp(`(?<![A-Za-z\\d])(\\d{1,2})(?:st|nd|rd|th)?[\\s\\-/.,]*(?:of\\s+)?(${MONTH_RE})[a-z]*[\\s\\-/.,']*(\\d{4}|\\d{2})(?![\\d])`, 'gi'), (m) => iso(year4(m[3]), MONTHS[m[2].toLowerCase()] ?? MONTHS[m[2].toLowerCase().slice(0, 3)], Number(m[1]))],
    [new RegExp(`(?<![A-Za-z])(${MONTH_RE})[a-z]*\\.?\\s+(\\d{1,2})(?:st|nd|rd|th)?,?\\s+(\\d{4})(?![\\d])`, 'gi'), (m) => iso(Number(m[3]), MONTHS[m[1].toLowerCase()] ?? MONTHS[m[1].toLowerCase().slice(0, 3)], Number(m[2]))],
  ]
  const taken: [number, number][] = []
  for (const [re, conv] of patterns) {
    let m: RegExpExecArray | null
    while ((m = re.exec(text))) {
      const s = m.index
      const e = s + m[0].length
      if (taken.some(([a, b]) => s < b && e > a)) continue
      const v = conv(m)
      if (!v) continue
      taken.push([s, e])
      out.push({ raw: m[0].trim(), value: v, index: s })
    }
  }
  return out.sort((a, b) => a.index - b.index)
}

export function parseDate(raw: string): string | null {
  const f = findDates(raw)
  return f.length ? f[0].value : null
}

const MONEY_RE = /(?<![\w.,/-])(\(?-?\s?(?:₹|rs\.?|inr)?\s?-?(?:\d{1,3}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?\)?)(\s?(?:cr|dr)\.?)?(?![\w,/]|\.\d)/gi

/** Money as printed: Indian or western grouping, optional currency, brackets or minus, Cr/Dr. */
export function parseMoney(raw: string): number | null {
  const s = raw.trim()
  if (!s || /\d[/-]\d{1,2}[/-]\d/.test(s)) return null
  const m = /^\(?-?\s?(?:₹|rs\.?|inr)?\s?(-)?\s?([\d,]+(?:\.\d{1,2})?)\)?\s?(cr|dr)?\.?$/i.exec(s.replace(/\s+/g, ' '))
  if (!m) return null
  const digits = m[2]
  if (!/^\d/.test(digits) || /,,/.test(digits) || /,$/.test(digits)) return null
  if (digits.includes(',') && !/^(\d{1,3}(,\d{2})*,\d{3}|\d{1,3}(,\d{3})+)(\.\d{1,2})?$/.test(digits)) return null
  let v = Number(digits.replace(/,/g, ''))
  if (!Number.isFinite(v)) return null
  const negative = /^\(.*\)$/.test(s) || /^\(?-/.test(s) || Boolean(m[1]) || (m[3] ?? '').toLowerCase() === 'dr'
  if (negative) v = -v
  return Math.round(v * 100) / 100
}

/** Money-looking tokens in a line of text, with their positions. */
export function findMoney(text: string): Found<number>[] {
  const out: Found<number>[] = []
  let m: RegExpExecArray | null
  MONEY_RE.lastIndex = 0
  while ((m = MONEY_RE.exec(text))) {
    const raw = (m[1] + (m[2] ?? '')).trim()
    const v = parseMoney(raw)
    if (v === null) continue
    out.push({ raw, value: v, index: m.index + (m[0].length - m[0].trimStart().length) })
  }
  return out
}

export function parseNumber(raw: string): number | null {
  const m = /^-?[\d,]*\d(?:\.\d+)?$/.exec(raw.trim())
  if (!m) return null
  const v = Number(raw.trim().replace(/,/g, ''))
  return Number.isFinite(v) ? v : null
}

export function parsePercent(raw: string): number | null {
  const m = /^(-?\d+(?:\.\d+)?)\s?%?$/.exec(raw.trim())
  return m ? Number(m[1]) : null
}

/** Financial or assessment year "2025-26" / "2025-2026" / "FY 2025-26". */
export function parseYearRange(raw: string): string | null {
  const m = /(?<!\d)(20\d{2})\s?[-–/]\s?(\d{2}|20\d{2})(?!\d)/.exec(raw)
  if (!m) return null
  const a = Number(m[1])
  const b = m[2].length === 2 ? Number(m[1].slice(0, 2) + m[2]) : Number(m[2])
  return b === a + 1 ? `${a}-${String(b).slice(2)}` : null
}

/** Month of a financial year (April starts it). */
export function monthInFy(month: number, fy: string): string {
  const start = Number(fy.slice(0, 4))
  return `${month >= 4 ? start : start + 1}-${pad(month)}`
}

/**
 * A tax period as printed: "April 2025", "Apr-25", "04/2025", "042025".
 * With only a month, `fy` (from the page) supplies the year. A year range
 * alone ("2025-26") is returned as such.
 */
export function parsePeriod(raw: string, fy?: string | null): string | null {
  const s = raw.trim()
  let m = new RegExp(`(?<![A-Za-z])(${MONTH_RE})[a-z]*[\\s,'.-]*(\\d{4}|\\d{2})(?!\\d)`, 'i').exec(s)
  if (m) {
    const month = MONTHS[m[1].toLowerCase()] ?? MONTHS[m[1].toLowerCase().slice(0, 3)]
    const y = year4(m[2])
    // "April 2025-26" reads as a month of a financial year.
    const fyAfter = parseYearRange(s.slice(m.index))
    if (fyAfter && s.slice(m.index).match(/\d{4}\s?[-–]\s?\d{2}/)) return monthInFy(month, fyAfter)
    if (month && y >= 1990 && y <= 2100) return `${y}-${pad(month)}`
  }
  m = /(?<!\d)(0[1-9]|1[0-2])\s?[/-]?\s?(20\d{2})(?!\d)/.exec(s)
  if (m) return `${m[2]}-${m[1]}`
  m = new RegExp(`^(${MONTH_RE})[a-z]*\\.?$`, 'i').exec(s)
  if (m && fy) return monthInFy(MONTHS[m[1].toLowerCase()] ?? MONTHS[m[1].toLowerCase().slice(0, 3)], fy)
  const yr = parseYearRange(s)
  if (yr) return yr
  return null
}

/** Whitespace-collapsed, case-folded, digit groups joined: how raw text is compared with a page. */
export function normaliseForMatch(s: string): string {
  return s
    .toLowerCase()
    .replace(/[‘’]/g, "'")
    .replace(/[–—]/g, '-')
    .replace(/(\d),(?=\d)/g, '$1')
    .replace(/\s+/g, ' ')
    .trim()
}
