// The extraction itself: documents × profile → structured output. Two strategies:
//   · 'fields'    — the text in windows, one structured call per window, merged in code
//   · 'sections'  — long numbered documents: split → identity ∥ triage → parallel extraction → merge (pipeline.ts)
// Results are cached by (content hash, profile, rules, model).
import { env } from './env.js'
import { cacheGet, cacheSet, sha256 } from './cache.js'
import { chatJson } from './llm.js'
import { runSections, PROMPT_VERSION, type SectionsResult, type Subject } from './pipeline.js'
import { acquire, type Document, type OnParse, type RawInput } from './inputs.js'
import { outputSchema, type Profile } from './profiles.js'
import { fewShot, listPacks, resolveType, validate, type Pack } from './catalogue.js'
import { classify, type Classification } from './classify.js'
import { recordExtraction } from './metrics.js'
import { dequeue, enqueue } from './review.js'

/** Rules supplied by the calling system (text sent with the request). */
export function withRules(prompt: string, rules?: string): string {
  return rules?.trim() ? `${prompt}\n\nADDITIONAL RULES FROM THE CALLING SYSTEM (they refine the above; where they conflict, they win)\n${rules.trim()}` : prompt
}

export type ServiceEvent =
  | Parameters<OnParse>[0]
  | { type: 'document'; index: number; count: number; name: string; part: Document['part']; chars: number; pages: number; ocrPages?: number }
  | { type: 'stage'; stage: 'analyse' | 'extract' | 'merge'; detail?: string; total?: number }
  | { type: 'progress'; stage: 'extract'; done: number; total: number }
  | { type: 'units'; units: Record<string, unknown>[]; group: number; groups: number }
  | { type: 'classified'; index: number; classification: Classification }
  | { type: 'result'; result: ExtractResponse }
  | { type: 'error'; message: string }

export interface ExtractRequest {
  raw: RawInput
  /** What to extract: a catalogue type (`bank/statement`, `bank/statement@2`, `auto`) or an inline profile. */
  type: string | { profile: Profile }
  /** Caller rules for this channel (from a rules file or sent inline). */
  rules?: string
  /** Who the reader is — replaces {{subject}} in a sections profile's prompts (or is appended as context). */
  subject?: Subject
  emailScope?: 'all' | 'attachments' | 'body'
  noCache?: boolean
  name?: string
  /** Return each document's parsed text with the result (for callers that index or store it). */
  includeText?: boolean
}
export interface DocumentResult {
  part: Document['part']
  name: string
  sha256: string
  contentType: string
  source: { kind: string; pages: number; chars: number; ocrPages?: number; warning?: string }
  mail?: Document['mail']
  /** The parsed text, when `includeText` was asked for. */
  text?: string
  /** The profile's shape — for 'sections': { identity, units } (see SectionsResult). */
  data: unknown
  /** The type this document was read as (its version), and — with `auto` — how it was chosen. */
  type: { id: string; version: number; strategy: Profile['strategy'] }
  classification?: Classification
  /** True when `auto` found no type above the threshold: `data` is the generic shape; a person should decide. */
  needsReview?: boolean
  /** Validator findings from the pack (never errors — the caller decides). */
  warnings?: string[]
  provider: { model: string; calls: number; promptTokens: number; completionTokens: number; costUsd?: number; ms: number; cached: boolean }
  skipped?: string
}
export interface ExtractResponse {
  id: string
  channel: RawInput['channel']
  /** The requested type ('auto', an id, or 'inline'). */
  type: string
  rules: { applied: boolean; sha256?: string }
  documents: DocumentResult[]
  ms: number
}

const WINDOW_CHARS = env.windowChars
const MIN_CHARS = 20

function systemFor(pack: Pack, rules?: string): string {
  const p = pack.profile
  const parts = [`You extract structured information from a document for a calling application. Read only what is in the text; never invent a value — leave a field null or empty when the text does not state it. Dates in ISO 8601 (YYYY-MM-DD) when the full date is given, otherwise as printed. Numbers as plain numbers. Keep strings short and factual.

WHAT TO EXTRACT
${p.instructions.trim()}`]
  if (pack.rules) parts.push(`HOW TO READ THIS KIND OF DOCUMENT\n${pack.rules}`)
  if (pack.reference) parts.push(`REFERENCE\n${pack.reference}`)
  const shots = fewShot(pack)
  if (shots) parts.push(shots)
  parts.push('Output only the JSON the schema requires.')
  return withRules(parts.join('\n\n'), rules)
}

/** Merge per-window objects: arrays concatenate (deduplicated), scalars take the first non-empty value. */
function mergeObjects(parts: Record<string, unknown>[]): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const p of parts) {
    for (const [k, v] of Object.entries(p)) {
      if (Array.isArray(v)) {
        const cur = (out[k] as unknown[] | undefined) ?? []
        const seen = new Set(cur.map((x) => JSON.stringify(x)))
        for (const x of v) { const key = JSON.stringify(x); if (!seen.has(key)) { seen.add(key); cur.push(x) } }
        out[k] = cur
      } else if (v !== null && v !== undefined && v !== '' && (out[k] === null || out[k] === undefined || out[k] === '')) {
        out[k] = v
      } else if (!(k in out)) out[k] = v
    }
  }
  return out
}
const windows = (text: string): string[] => {
  if (text.length <= WINDOW_CHARS) return [text]
  const out: string[] = []
  for (let i = 0; i < text.length; i += WINDOW_CHARS - 800) out.push(text.slice(i, i + WINDOW_CHARS))
  return out
}
const PRICES: Record<string, [number, number]> = { 'gpt-4.1-mini': [0.4, 1.6], 'gpt-4.1-nano': [0.1, 0.4], 'gpt-4.1': [2, 8], 'gpt-4o-mini': [0.15, 0.6], 'gpt-4o': [2.5, 10] }
const cost = (m: string, i: number, o: number) => { const k = Object.keys(PRICES).find((x) => m.startsWith(x)); const p = k ? PRICES[k] : undefined; return p ? Math.round(((i * p[0] + o * p[1]) / 1e6) * 1e4) / 1e4 : undefined }

async function extractFields(doc: Document, pack: Pack, rules: string | undefined, name: string | undefined, noCache: boolean, on: (e: ServiceEvent) => void): Promise<{ data: unknown; provider: DocumentResult['provider'] }> {
  const p = pack.profile
  const schema = outputSchema(p)
  const system = systemFor(pack, rules)
  const key = `ingest-${sha256(`${sha256(doc.text.text)}|${pack.id}@${pack.version}|${JSON.stringify(schema)}|${system}|${env.ai.model}`)}`
  if (!noCache) { const hit = await cacheGet<{ data: unknown; provider: DocumentResult['provider'] }>(key); if (hit) return { ...hit, provider: { ...hit.provider, cached: true, ms: 0 } } }
  const t0 = Date.now()
  const wins = windows(doc.text.text)
  on({ type: 'stage', stage: 'extract', detail: `${wins.length} window(s)` })
  let done = 0, pt = 0, ct = 0, model = env.ai.model
  const parts = await Promise.all(wins.map(async (w, i) => {
    const r = await chatJson<Record<string, unknown>>({ system, user: `${name ? `Document name: ${name}\n` : ''}${doc.mail ? `From an e-mail — From: ${doc.mail.from} · Subject: ${doc.mail.subject}${doc.part === 'attachment' ? ` · attachment ${doc.name}` : ''}\n` : ''}${wins.length > 1 ? `Part ${i + 1} of ${wins.length}.\n` : ''}\nDOCUMENT TEXT\n${w}`, jsonSchema: { name: 'extraction', strict: true, schema }, temperature: 0 })
    pt += r.usage?.prompt_tokens ?? 0; ct += r.usage?.completion_tokens ?? 0; model = r.model
    done += 1; on({ type: 'progress', stage: 'extract', done, total: wins.length })
    return r.data
  }))
  if (wins.length > 1) on({ type: 'stage', stage: 'merge' })
  const data = parts.length === 1 ? parts[0] : mergeObjects(parts)
  const provider = { model, calls: wins.length, promptTokens: pt, completionTokens: ct, costUsd: cost(model, pt, ct), ms: Date.now() - t0, cached: false }
  await cacheSet(key, { data, provider })
  return { data, provider }
}

export async function extract(req: ExtractRequest, on: (e: ServiceEvent) => void = () => {}): Promise<ExtractResponse> {
  const t0 = Date.now()
  const requested = typeof req.type === 'string' ? req.type : 'inline'
  const fixed: Pack | null = typeof req.type === 'string' ? (req.type === 'auto' ? null : await resolveType(req.type)) : { id: req.type.profile.id, namespace: '', version: 1, profile: req.type.profile, rules: '', reference: '', validators: [], examples: [], dir: null }
  if (fixed?.profile.strategy === 'sections' && !fixed.profile.sections) throw new Error('a sections profile needs unit · identity · triage')
  const packs = fixed ? [] : await listPacks()
  const generic = fixed ?? packs.find((p) => p.id === 'generic')!
  const docs = await acquire(req.raw, on, { emailScope: req.emailScope, noCache: req.noCache })
  const results: DocumentResult[] = []
  const none = { model: '', calls: 0, promptTokens: 0, completionTokens: 0, ms: 0, cached: false }
  for (const [i, doc] of docs.entries()) {
    on({ type: 'document', index: i, count: docs.length, name: doc.name, part: doc.part, chars: doc.text.text.length, pages: doc.text.pages, ocrPages: doc.text.ocrPages })
    const base = { part: doc.part, name: doc.name, sha256: doc.sha256, contentType: doc.contentType, mail: doc.mail, text: req.includeText ? doc.text.text : undefined, source: { kind: doc.text.kind, pages: doc.text.pages, chars: doc.text.text.length, ocrPages: doc.text.ocrPages, warning: doc.text.warning } }
    const typeOf = (p: Pack) => ({ id: p.id, version: p.version, strategy: p.profile.strategy })
    if (doc.text.text.length < MIN_CHARS) { results.push({ ...base, data: null, type: typeOf(generic), provider: none, skipped: doc.text.warning ?? 'no readable text' }); continue }
    // Which type: fixed by the request, or chosen per document.
    let pack = fixed
    let classification: Classification | undefined
    let needsReview = false
    if (!pack) {
      classification = await classify(doc, packs, req.noCache)
      on({ type: 'classified', index: i, classification })
      pack = classification.type ? packs.find((p) => p.id === classification!.type)! : generic
      needsReview = !classification.type
    }
    const p = pack.profile
    let data: unknown, provider: DocumentResult['provider']
    if (p.strategy === 'sections') {
      if (doc.part === 'body') { results.push({ ...base, data: null, type: typeOf(pack), classification, needsReview, provider: none, skipped: 'an e-mail body is not a document of this kind; attachments were read' }); continue }
      const packRules = [pack.rules, req.rules].filter((x) => x?.trim()).join('\n\n') || undefined
      const r: SectionsResult = await runSections({ profileId: `${pack.id}@${pack.version}`, spec: p.sections!, instructions: p.instructions, name: req.name, url: req.raw.url, source: doc.text, subject: req.subject, docHash: doc.sha256, noCache: req.noCache, rules: packRules }, (e) => on(e))
      data = { identity: r.identity, units: r.units, provider: r.provider, source: r.source }
      provider = { model: r.provider.model, calls: r.provider.windows + 2, promptTokens: r.provider.promptTokens, completionTokens: r.provider.completionTokens, costUsd: r.provider.costUsd, ms: r.provider.ms, cached: r.provider.cached }
    } else {
      const r = await extractFields(doc, pack, req.rules, req.name ?? doc.name, Boolean(req.noCache), on)
      data = r.data; provider = r.provider
    }
    const warnings = validate(pack, data)
    results.push({ ...base, data, type: typeOf(pack), classification, needsReview: needsReview || undefined, warnings: warnings.length ? warnings : undefined, provider })
    void recordExtraction({ type: pack.id, by: classification?.by, confidence: classification?.confidence, needsReview, warnings: warnings.length, costUsd: provider.costUsd, tokens: provider.promptTokens + provider.completionTokens })
    if (classification?.type) void dequeue(doc.sha256) // placed now (a new type, a better signature): out of the queue
    if (needsReview && classification) void enqueue({ sha256: doc.sha256, name: doc.name, mail: doc.mail ? { from: doc.mail.from, subject: doc.mail.subject } : undefined, snippet: doc.text.text, candidates: classification.candidates, reason: classification.reason, generic: data })
  }
  return { id: `ING-${sha256(`${req.raw.channel}|${docs.map((d) => d.sha256).join(',')}|${requested}|${Date.now()}`).slice(0, 12)}`, channel: req.raw.channel, type: requested, rules: { applied: Boolean(req.rules?.trim()), sha256: req.rules?.trim() ? sha256(req.rules.trim()) : undefined }, documents: results, ms: Date.now() - t0 }
}
export { PROMPT_VERSION }
