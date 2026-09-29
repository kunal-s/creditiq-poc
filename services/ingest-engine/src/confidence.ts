// Confidence components per field (F-17.1). The engine computes
//   confidence = min(applicable caps) x sum(weight_i x component_i)
// from config/confidence.yaml; this service reports the components and the
// caps that apply, and never a model's self-reported confidence.
//
// Keys: the weight names of the published confidence section
// (classification, page_grade, reading_trust, validation, agreement), each in
// [0, 1]; "cap.<name>" for every published cap that applies, with its value;
// "repair.running_balance" = 1 when a bank cell was repaired arithmetically.
import type { ConfidenceSection } from './config.js'
import type { Grade } from './contract.js'

export const GRADE_COMPONENT: Record<Grade, number> = { A: 1, B: 0.85, C: 0.6, U: 0.2 }

export interface ComponentInput {
  classification: number
  grade: Grade
  readingTrust: number
  validation: number
  agreement: number
  caps?: string[]
  extra?: Record<string, number>
}

const r3 = (x: number) => Math.round(Math.min(1, Math.max(0, x)) * 1000) / 1000

export function components(c: ConfidenceSection, i: ComponentInput): Record<string, number> {
  const out: Record<string, number> = {}
  const values: Record<string, number> = {
    classification: i.classification,
    page_grade: GRADE_COMPONENT[i.grade],
    reading_trust: i.readingTrust,
    validation: i.validation,
    agreement: i.agreement,
  }
  for (const [k, v] of Object.entries(values)) if (k in c.weights) out[k] = r3(v)
  const caps = new Set(i.caps ?? [])
  if (i.grade === 'C') caps.add('grade_c_page')
  for (const cap of caps) if (cap in c.caps) out[`cap.${cap}`] = c.caps[cap]
  for (const [k, v] of Object.entries(i.extra ?? {})) out[k] = v
  return out
}
