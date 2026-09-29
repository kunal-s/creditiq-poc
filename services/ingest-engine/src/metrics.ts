// Per-type operating metrics, so the people who own a type can see it drift: how often `auto`
// chose it (and how — signature or model), how often nothing was chosen (review rate), how often a
// person confirmed vs corrected it, validator warnings, cost. Counters live in one JSON file under
// the feedback directory; a rolling window of recent events gives the rates that matter now.
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { env } from './env.js'

export interface TypeMetrics {
  requests: number
  auto: { signature: number; model: number; none: number }
  confidenceSum: number
  confidenceN: number
  warnings: number
  confirmed: number
  corrected: number
  correctedAway: number
  costUsd: number
  tokens: number
  lastAt: string | null
}
interface Event { at: string; type: string; kind: 'extract' | 'review' | 'confirmed' | 'corrected'; by?: string; confidence?: number }
interface Store { types: Record<string, TypeMetrics>; recent: Event[] }

const WINDOW = 200
const file = () => join(env.feedbackDir, '_metrics.json')
const blank = (): TypeMetrics => ({ requests: 0, auto: { signature: 0, model: 0, none: 0 }, confidenceSum: 0, confidenceN: 0, warnings: 0, confirmed: 0, corrected: 0, correctedAway: 0, costUsd: 0, tokens: 0, lastAt: null })

let store: Store | null = null
let saving: Promise<void> = Promise.resolve()
async function load(): Promise<Store> {
  if (store) return store
  try { store = JSON.parse(await readFile(file(), 'utf8')) as Store } catch { store = { types: {}, recent: [] } }
  return store
}
function save(): void {
  saving = saving.then(async () => { if (!store) return; await mkdir(env.feedbackDir, { recursive: true }); await writeFile(file(), JSON.stringify(store)) }).catch((e) => console.warn('[metrics] not saved:', e instanceof Error ? e.message : e))
}
const at = () => new Date().toISOString()
function push(s: Store, e: Event) { s.recent.push(e); if (s.recent.length > WINDOW) s.recent.splice(0, s.recent.length - WINDOW) }

/** One extracted document. `type` is what it was read as; `by` how auto chose it (absent when the caller named the type). */
export async function recordExtraction(e: { type: string; by?: 'signature' | 'model' | 'none'; confidence?: number; needsReview?: boolean; warnings?: number; costUsd?: number; tokens?: number }): Promise<void> {
  if (!env.feedbackDir) return
  const s = await load()
  const t = (s.types[e.type] ??= blank())
  t.requests += 1
  if (e.by) t.auto[e.by] += 1
  if (typeof e.confidence === 'number' && e.by && e.by !== 'none') { t.confidenceSum += e.confidence; t.confidenceN += 1 }
  t.warnings += e.warnings ?? 0
  t.costUsd += e.costUsd ?? 0
  t.tokens += e.tokens ?? 0
  t.lastAt = at()
  push(s, { at: t.lastAt, type: e.type, kind: e.needsReview ? 'review' : 'extract', by: e.by, confidence: e.confidence })
  save()
}
/** A person's verdict: confirmed the type, or corrected it (from → to). */
export async function recordVerdict(e: { type: string; verdict: 'confirmed' | 'corrected'; from?: string }): Promise<void> {
  if (!env.feedbackDir) return
  const s = await load()
  const t = (s.types[e.type] ??= blank())
  if (e.verdict === 'confirmed') t.confirmed += 1; else t.corrected += 1
  if (e.verdict === 'corrected' && e.from && e.from !== e.type) { const f = (s.types[e.from] ??= blank()); f.correctedAway += 1 }
  push(s, { at: at(), type: e.type, kind: e.verdict })
  save()
}

export interface TypeSummary extends TypeMetrics {
  type: string
  avgConfidence: number | null
  /** Over the rolling window: share of this type's extractions that ended in review (auto only). */
  reviewRate: number | null
  /** Over the rolling window: corrected ÷ (confirmed + corrected). */
  correctionRate: number | null
  alerts: string[]
}
const REVIEW_ALERT = 0.3, CORRECTION_ALERT = 0.25, MIN_N = 5

/** Per-type summary with the rates that indicate drift, plus the alerts they trigger. */
export async function summary(): Promise<{ types: TypeSummary[]; window: number; alerts: string[] }> {
  const s = await load()
  const out: TypeSummary[] = []
  const alerts: string[] = []
  for (const [type, m] of Object.entries(s.types)) {
    const recent = s.recent.filter((e) => e.type === type)
    const autoN = recent.filter((e) => (e.kind === 'extract' && e.by) || e.kind === 'review').length
    const reviews = recent.filter((e) => e.kind === 'review').length
    const verdicts = recent.filter((e) => e.kind === 'confirmed' || e.kind === 'corrected')
    const reviewRate = autoN >= MIN_N ? reviews / autoN : null
    const correctionRate = verdicts.length >= MIN_N ? verdicts.filter((e) => e.kind === 'corrected').length / verdicts.length : null
    const a: string[] = []
    // `generic` is where unplaced documents land, so its review rate is the queue itself, not drift.
    if (type !== 'generic' && reviewRate !== null && reviewRate > REVIEW_ALERT) a.push(`${Math.round(reviewRate * 100)}% of recent auto-classified documents of this kind needed review — signatures or examples are missing a new layout`)
    if (correctionRate !== null && correctionRate > CORRECTION_ALERT) a.push(`${Math.round(correctionRate * 100)}% of recent verdicts were corrections — the instructions or fields no longer fit`)
    if (m.correctedAway >= MIN_N) a.push(`${m.correctedAway} document(s) first read as this type were reassigned by a person — tighten its signatures`)
    for (const x of a) alerts.push(`${type}: ${x}`)
    out.push({ type, ...m, avgConfidence: m.confidenceN ? Math.round((m.confidenceSum / m.confidenceN) * 100) / 100 : null, reviewRate: reviewRate === null ? null : Math.round(reviewRate * 100) / 100, correctionRate: correctionRate === null ? null : Math.round(correctionRate * 100) / 100, alerts: a })
  }
  const unplaced = s.recent.filter((e) => e.kind === 'review').length
  if (unplaced >= MIN_N) alerts.push(`${unplaced} of the last ${Math.min(s.recent.length, WINDOW)} auto-classified documents found no type — GET /v1/review/clusters may have a type to propose`)
  return { types: out.sort((a, b) => b.requests - a.requests), window: WINDOW, alerts }
}
