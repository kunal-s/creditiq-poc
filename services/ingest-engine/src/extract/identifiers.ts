// Indian identifiers: patterns and checks, ported from engine/identifiers.py.
// Only GSTIN has a public checksum; the others are format checks. Invalid
// identifiers are reported, never corrected (principle 7).
import type { IdentifierKind } from '../config.js'

const GSTIN_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'

export function gstinCheckDigit(first14: string): string {
  if (first14.length !== 14) throw new Error('expected 14 characters')
  let total = 0
  for (let i = 0; i < 14; i++) {
    const v = GSTIN_ALPHABET.indexOf(first14[i])
    if (v < 0) throw new Error(`character ${first14[i]} is not valid in a GSTIN`)
    const p = v * (1 + (i % 2))
    total += Math.floor(p / 36) + (p % 36)
  }
  return GSTIN_ALPHABET[(36 - (total % 36)) % 36]
}

const FORMAT: Record<IdentifierKind, RegExp> = {
  pan: /^[A-Z]{3}[ABCFGHJLPT][A-Z][0-9]{4}[A-Z]$/,
  gstin: /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/,
  cin: /^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$/,
  udyam: /^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$/,
  ifsc: /^[A-Z]{4}0[A-Z0-9]{6}$/,
  tan: /^[A-Z]{4}[0-9]{5}[A-Z]$/,
  din: /^[0-9]{8}$/,
  itr_ack: /^[0-9]{15}$/,
  udin: /^[0-9]{8}[A-Z0-9]{10}$/,
}

/** Search patterns (uppercase text). DIN, ITR and UDIN are too generic to search unanchored. */
const SEARCH: Partial<Record<IdentifierKind, RegExp>> = {
  pan: /(?<![A-Z0-9])[A-Z]{3}[ABCFGHJLPT][A-Z][0-9]{4}[A-Z](?![A-Z0-9])/g,
  gstin: /(?<![A-Z0-9])[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z](?![A-Z0-9])/g,
  cin: /(?<![A-Z0-9])[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}(?![A-Z0-9])/g,
  udyam: /(?<![A-Z0-9])UDYAM\s?-\s?[A-Z]{2}\s?-\s?[0-9]{2}\s?-\s?[0-9]{7}(?![0-9])/g,
  ifsc: /(?<![A-Z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Z0-9])/g,
  tan: /(?<![A-Z0-9])[A-Z]{4}[0-9]{5}[A-Z](?![A-Z0-9])/g,
}

/** Tokens that may hold an identifier after a label (anchored search). */
export const ANCHORED_TOKEN: Record<IdentifierKind, RegExp> = {
  pan: /[A-Z0-9]{10}/,
  gstin: /[A-Z0-9]{15}/,
  cin: /[A-Z0-9]{21}/,
  udyam: /UDYAM\s?-\s?[A-Z]{2}\s?-\s?\d{2}\s?-\s?\d{7}/,
  ifsc: /[A-Z0-9]{11}/,
  tan: /[A-Z0-9]{10}/,
  din: /(?<!\d)\d{8}(?!\d)/,
  itr_ack: /(?<!\d)\d{15}(?!\d)/,
  udin: /(?<![A-Z0-9])\d{8}[A-Z0-9]{10}(?![A-Z0-9])/,
}

export const compact = (s: string) => s.toUpperCase().replace(/\s+/g, '')

export interface IdCheck { format: boolean; checksum: boolean | null }

export function checkIdentifier(kind: IdentifierKind, value: string): IdCheck {
  const v = compact(value)
  const format = FORMAT[kind].test(v)
  if (kind !== 'gstin') return { format, checksum: null }
  if (!format) return { format, checksum: false }
  return { format, checksum: gstinCheckDigit(v.slice(0, 14)) === v[14] }
}

export function findIdentifiers(kind: IdentifierKind, text: string): { raw: string; value: string; index: number }[] {
  const re = SEARCH[kind]
  if (!re) return []
  const up = text.toUpperCase()
  const out: { raw: string; value: string; index: number }[] = []
  re.lastIndex = 0
  let m: RegExpExecArray | null
  while ((m = re.exec(up))) out.push({ raw: text.slice(m.index, m.index + m[0].length), value: compact(m[0]), index: m.index })
  return out
}
