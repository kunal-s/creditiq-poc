// The `sections` strategy — for long documents laid out in numbered units (sections, rules,
// paragraphs, clauses, articles). Tuned for latency and cost:
//
//   text ─► split into sections ─┬─► IDENTITY (front matter)  ─┐  in parallel
//                                └─► TRIAGE (compact index)    ─┤
//                                                               ▼
//                    selected sections ─► grouped (~5k chars, amendments with the
//                    section they amend) ─► EXTRACT groups in parallel ─► merge by key
//
//   unsplittable text ─► windows ─► EXTRACT windows in parallel ─► merge (fallback)
//
// Everything the model is told and everything it returns comes from the caller's profile: the
// instructions, the unit's fields and merge key, the identity fields and prompt, the triage
// criteria. The engine contributes the mechanics — splitting, indexing, grouping, parallelism,
// the strict JSON envelope, page references, de-duplication and caching. Results are cached by
// (document hash, profile, rules, subject, model, PROMPT_VERSION).
import { env } from './env.js'
import { cacheGet, cacheSet, sha256 } from './cache.js'
import { chatJson } from './llm.js'
import { compileFields, type Field, type SectionsSpec } from './profiles.js'
import { sectionIndex, splitSections, type Section } from './sections.js'
import type { SourceText } from './text.js'

/** Bump when the engine's own prompt mechanics or envelope change so cached extractions are not reused. */
export const PROMPT_VERSION = '2026-09-12.1'

/** Who the reader is — injected wherever the profile's prompts say {{subject}}. */
export interface Subject { name: string; description: string }
type Unit = Record<string, unknown>

export interface SectionsResult {
  identity: Record<string, unknown>
  units: Unit[]
  provider: {
    model: string
    strategy: 'triage' | 'windowed'
    /** Parallel extraction calls made. */
    windows: number
    sectionsFound: number
    sectionsSelected: number
    /** What triage chose to read, for transparency. */
    selectedSections?: { id: string; pages: string; reason: string }[]
    promptTokens: number
    completionTokens: number
    costUsd?: number
    ms: number
    cached: boolean
  }
  source: { kind: SourceText['kind']; pages: number; bytes: number; chars: number; charsSent: number; ocrPages?: number; warning?: string }
}

export type SectionsEvent =
  | { type: 'stage'; stage: 'analyse' | 'extract' | 'merge'; detail?: string; total?: number }
  | { type: 'progress'; stage: 'extract'; done: number; total: number }
  | { type: 'units'; units: Unit[]; group: number; groups: number }
export type OnEvent = (e: SectionsEvent) => void

// USD per 1M tokens (input, output) for the models we expect; extend as needed.
const PRICES: Record<string, [number, number]> = { 'gpt-4.1-mini': [0.4, 1.6], 'gpt-4.1-nano': [0.1, 0.4], 'gpt-4o-mini': [0.15, 0.6], 'gpt-4.1': [2, 8] }
function estimateCost(model: string, inTok: number, outTok: number): number | undefined {
  const key = Object.keys(PRICES).find((k) => model.startsWith(k))
  if (!key) return undefined
  const [i, o] = PRICES[key]
  return (inTok * i + outTok * o) / 1e6
}

/** Run up to `limit` promises at once, preserving order of results. */
async function mapLimit<T, R>(items: T[], limit: number, fn: (item: T, index: number) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length)
  let next = 0
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, async () => { while (next < items.length) { const i = next++; out[i] = await fn(items[i], i) } }))
  return out
}

function splitWindows(text: string, max: number): string[] {
  if (text.length <= max) return [text]
  const out: string[] = []
  let rest = text
  while (rest.length > max) {
    const floor = Math.floor(max * 0.8)
    let cut = rest.lastIndexOf('\n\n[[page ', max)
    if (cut < floor) cut = rest.lastIndexOf('\n\n', max)
    if (cut < floor) cut = max
    out.push(rest.slice(0, cut))
    rest = rest.slice(cut)
  }
  if (rest.trim()) out.push(rest)
  return out
}

// ── Document structure: amendments ride with the section they amend ───────────
const AMENDING_OPENER = /^\s*(?:[A-Za-z][A-Za-z,'’-]*\s+){0,3}\d+[A-Z]{0,2}\.\s+(?:In|For|After|To) section/i

/**
 * Group selected sections for parallel extraction. An amending section ("In section 8 of the
 * principal Act…") is placed with the section it amends so one call reads the unit as amended;
 * otherwise groups are filled in document order up to `maxChars`.
 */
function groupSections(sections: Section[], maxChars: number, maxPrincipal = env.extractGroupSections): Section[][] {
  const byNumber = new Map<string, number>()
  sections.forEach((s, i) => { const m = s.id.match(/^Section (\d+[A-Z]{0,2})$/); if (m && s.part === 'principal' && !byNumber.has(m[1])) byNumber.set(m[1], i) })
  const buddy = new Map<number, number>()
  sections.forEach((s, i) => {
    if (!AMENDING_OPENER.test(s.text)) return
    const m = s.text.slice(0, 240).match(/section (\d+[A-Z]{0,2})\b/i)
    const target = m ? byNumber.get(m[1]) : undefined
    if (target !== undefined && target !== i) buddy.set(i, target)
  })
  const groups: Section[][] = []
  const placed = new Set<number>()
  let cur: Section[] = [], curLen = 0, curPrincipal = 0
  const flush = () => { if (cur.length) groups.push(cur); cur = []; curLen = 0; curPrincipal = 0 }
  const push = (i: number) => { if (placed.has(i)) return; placed.add(i); cur.push(sections[i]); curLen += sections[i].text.length; if (sections[i].part === 'principal') curPrincipal += 1 }
  sections.forEach((s, i) => {
    if (placed.has(i) || buddy.has(i)) return
    const members = [i, ...[...buddy.entries()].filter(([, t]) => t === i).map(([a]) => a)]
    const len = members.reduce((n, k) => n + sections[k].text.length, 0)
    const principalHere = s.part === 'principal' ? 1 : 0
    if (cur.length && (curLen + len > maxChars || curPrincipal + principalHere > maxPrincipal)) flush()
    members.forEach(push)
  })
  sections.forEach((_, i) => { if (placed.has(i)) return; if (cur.length && curLen + sections[i].text.length > maxChars) flush(); push(i) })
  flush()
  return groups
}

// ── Merge: one unit per key across parallel calls ─────────────────────────────
const AMENDED_TAG = /\s*\((?:as )?(?:amended|substituted|inserted)[^)]*\)/gi
const normKey = (p: string) => p.toLowerCase().replace(AMENDED_TAG, '').replace(/[^a-z0-9.()]/g, '')
const pageNum = (ref: unknown) => Number((String(ref ?? '').match(/\d+/) ?? ['0'])[0])
/**
 * "Section 5(3A)" → "Section 5", "12(a)" → "12", "Para 7.3(ii)" → "Para 7.3": a parenthesised
 * sub-reference folds into its unit. "Para 7.3.1" stays — dotted paragraphs are units in themselves.
 */
const sectionRoot = (p: string) => p.replace(AMENDED_TAG, '').replace(/^((?:(?:Section|Sec\.|Rule|Regulation|Reg\.|Entry|Clause|Article|Para(?:graph)?)\s+)?\d+[A-Z]{0,2}(?:\.\d+)*)\s*\([^)]*\).*$/i, '$1').trim()

/**
 * Merge units by the profile's key. The earliest-page occurrence is the base; later ones (a
 * sub-section, an amendment) contribute array entries, and their `textField` — where it says
 * something new — is appended with a page note. Numeric `confidenceField` takes the minimum.
 */
function mergeUnits(lists: Unit[][], spec: SectionsSpec['unit']): Unit[] {
  const byKey = new Map<string, Unit>()
  const skip = spec.skipIf ? new RegExp(spec.skipIf.pattern, 'i') : null
  const keyOf = (u: Unit) => String(u[spec.key] ?? '')
  for (const list of lists) {
    for (const raw of list) {
      if (skip && spec.skipIf && skip.test(String(raw[spec.skipIf.field] ?? ''))) continue
      let u: Unit = { ...raw }
      const rawKey = keyOf(raw)
      if (spec.keyNormalise === 'section-root') {
        const root = sectionRoot(rawKey), sub = rawKey.replace(AMENDED_TAG, '').trim()
        if (root !== sub) {
          // A sub-section folds into its section; its list entries carry the sub-reference so nothing is lost.
          u[spec.key] = root
          for (const [k, v] of Object.entries(u)) if (Array.isArray(v) && v.every((x) => typeof x === 'string')) u[k] = (v as string[]).map((x) => `${sub.replace(root, '').trim()} ${x}`.trim())
        }
      }
      u[spec.key] = keyOf(u).replace(AMENDED_TAG, '')
      const key = normKey(keyOf(u))
      const prev = byKey.get(key)
      if (!prev) { byKey.set(key, u); continue }
      const pf = spec.pageField
      const base = pf && pageNum(u[pf]) < pageNum(prev[pf]) ? u : prev
      const extra = base === u ? prev : u
      const merged: Unit = { ...base }
      for (const [k, v] of Object.entries(extra)) {
        if (Array.isArray(v)) { const cur = Array.isArray(base[k]) ? [...(base[k] as unknown[])] : []; const seen = new Set(cur.map((x) => JSON.stringify(x))); for (const x of v) { const j = JSON.stringify(x); if (!seen.has(j)) { seen.add(j); cur.push(x) } } merged[k] = cur }
      }
      if (spec.textField && typeof extra[spec.textField] === 'string' && extra[spec.textField] !== base[spec.textField]) {
        const samePage = !pf || pageNum(u[pf]) === pageNum(prev[pf])
        merged[spec.textField] = `${String(base[spec.textField] ?? '')}${samePage ? ` ${extra[spec.textField]}` : ` As amended (${extra[pf!]}): ${extra[spec.textField]}`}`.slice(0, 800)
      }
      if (pf && base[pf] !== extra[pf]) merged[pf] = `${base[pf]}, ${String(extra[pf]).replace(/^pp?\.\s*/, '')}`
      if (spec.confidenceField && typeof base[spec.confidenceField] === 'number' && typeof extra[spec.confidenceField] === 'number') merged[spec.confidenceField] = Math.min(base[spec.confidenceField] as number, extra[spec.confidenceField] as number)
      byKey.set(key, merged)
    }
  }
  return [...byKey.values()]
}

/** The dedicated identity pass wins; extraction calls fill what it left empty. */
function mergeIdentity(primary: Record<string, unknown> | null, seen: Record<string, unknown>[], fields: Field[], defaults: Record<string, unknown>, name?: string): Record<string, unknown> {
  const out: Record<string, unknown> = {}
  for (const f of fields) {
    const empty = (v: unknown) => v === null || v === undefined || (typeof v === 'string' && !v.trim())
    let v: unknown = primary?.[f.name]
    if (empty(v)) for (const s of seen) { if (!empty(s[f.name])) { v = s[f.name]; break } }
    if (empty(v)) v = defaults[f.name] ?? (f.type === 'string[]' || f.type === 'object[]' ? [] : f.type === 'boolean' ? false : f.type === 'number' ? 0 : '')
    out[f.name] = v
  }
  if (fields.some((f) => f.name === 'title') && !String(out.title ?? '').trim()) out.title = name ?? 'Untitled document'
  return out
}

// ── Prompts: the profile's words, the engine's mechanics ──────────────────────
const inject = (text: string, subject?: Subject) => {
  const s = subject ? `${subject.name}: ${subject.description}` : ''
  return text.includes('{{subject}}') ? text.replaceAll('{{subject}}', s || '(not supplied)') : subject ? `${text}\n\nCONTEXT — WHO IS READING\n${s}` : text
}
const withRules = (prompt: string, rules?: string) => (rules?.trim() ? `${prompt}\n\nADDITIONAL RULES FROM THE CALLING SYSTEM (they refine the above; where they conflict, they win)\n${rules.trim()}` : prompt)

export async function runSections(
  args: { profileId: string; spec: SectionsSpec; instructions: string; name?: string; url?: string; source: SourceText; subject?: Subject; docHash: string; noCache?: boolean; rules?: string },
  onEvent: OnEvent = () => {},
): Promise<SectionsResult> {
  const { spec } = args
  const cacheKey = `sections-${sha256(`${args.docHash}|${PROMPT_VERSION}|${env.ai.model}|${args.profileId}|${args.instructions}|${JSON.stringify(spec)}|${args.subject?.name ?? ''}|${args.subject?.description ?? ''}|${args.rules ?? ''}`)}`
  if (!args.noCache) { const hit = await cacheGet<SectionsResult>(cacheKey); if (hit) return { ...hit, provider: { ...hit.provider, cached: true, ms: 0 } } }

  const t0 = Date.now()
  const unitSchema = compileFields(spec.unit.fields)
  const identityFields = spec.identity?.fields ?? []
  const identitySchema = compileFields(identityFields) as { properties: Record<string, unknown>; required: string[] }
  // Each extraction call returns the identity fields it can see plus the units in its text.
  const extractionSchema = { type: 'object', additionalProperties: false, required: [...identitySchema.required, spec.unit.name], properties: { ...identitySchema.properties, [spec.unit.name]: { type: 'array', items: unitSchema } } }
  const system = withRules(`${inject(args.instructions, args.subject)}\n\nOUTPUT\n- Return the ${spec.unit.name} found in the text you are given${identityFields.length ? `, and the document's identity fields (${identityFields.map((f) => f.name).join(', ')}) as far as this excerpt shows them — empty strings for what it does not state` : ''}.\n- Output only the JSON the schema requires.`, args.rules)
  const header = (win?: { index: number; count: number }) => [args.name ? `Document name supplied by the caller: ${args.name}` : '', args.url ? `Source URL: ${args.url}` : '', win && win.count > 1 ? `This is excerpt ${win.index + 1} of ${win.count} of the document. Extract the ${spec.unit.name} found in THIS excerpt only.` : ''].filter(Boolean).join('\n')

  let model = env.ai.model, cost = 0, promptTokens = 0, completionTokens = 0
  const account = (m: string, usage?: { prompt_tokens?: number; completion_tokens?: number }) => { const i = usage?.prompt_tokens ?? 0, o = usage?.completion_tokens ?? 0; promptTokens += i; completionTokens += o; cost += estimateCost(m, i, o) ?? 0 }

  // ── Stage 1: identity (front matter) in parallel with triage (section index)
  onEvent({ type: 'stage', stage: 'analyse' })
  const sections = splitSections(args.source.text)
  const canTriage = Boolean(spec.triage) && sections.length >= 8 && args.source.text.length > env.triageMinChars
  const head = args.source.text.slice(0, 8000)

  const identityCall = spec.identity
    ? chatJson<Record<string, unknown>>({ system: `${inject(spec.identity.instructions, args.subject)}\n\nOutput only the JSON the schema requires.`, user: `${header()}\n\nOPENING TEXT\n${head}`, jsonSchema: { name: 'identity', strict: true, schema: identitySchema }, temperature: 0, model: env.ai.triageModel })
        .then((r) => { account(r.model, r.usage); return r.data })
        .catch(() => null)
    : Promise.resolve(null)

  const triageSchema = { type: 'object', additionalProperties: false, required: ['documentTitle', 'selected'], properties: { documentTitle: { type: 'string' }, selected: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['index', 'reason'], properties: { index: { type: 'integer' }, reason: { type: 'string' } } } } } }
  const triageCall = canTriage
    ? chatJson<{ documentTitle: string; selected: { index: number; reason: string }[] }>({
        system: `${inject(spec.triage!.instructions, args.subject)}\n\nYou will receive a compact INDEX of the numbered sections found in the document — one line each with the section id, its pages and its opening words. Return documentTitle (the document this index belongs to) and the selected indices, each with a short reason. Output only the JSON the schema requires.`,
        user: `Document: ${args.name ?? '(untitled)'}\n\nSECTION INDEX (one line per section: #index id (pages) — opening words)\n${sectionIndex(sections, 150)}`,
        jsonSchema: { name: 'triage', strict: true, schema: triageSchema }, temperature: 0, model: env.ai.triageModel,
      }).then((r) => { account(r.model, r.usage); return r.data })
    : Promise.resolve(null)

  const [identity, triage] = await Promise.all([identityCall, triageCall])

  // ── Stage 2: build the parallel units of extraction
  let strategy: SectionsResult['provider']['strategy'] = 'windowed'
  let units: string[]
  let selectedSections: SectionsResult['provider']['selectedSections']
  if (triage) {
    const idx = new Set(triage.selected.map((s) => s.index).filter((i) => i >= 0 && i < sections.length))
    // An amending section that was selected is strong evidence that the section it amends matters: read them together.
    for (const i of [...idx]) {
      const sec = sections[i]
      if (!AMENDING_OPENER.test(sec.text)) continue
      const m = sec.text.slice(0, 240).match(/section (\d+[A-Z]{0,2})\b/i)
      if (!m) continue
      const principal = sections.findIndex((x) => x.part === 'principal' && x.id === `Section ${m[1]}`)
      if (principal >= 0) idx.add(principal)
    }
    // Sections the profile says to always read (e.g. penalty sections, so consequences attach to duties).
    if (spec.triage?.alwaysInclude) { const rx = new RegExp(spec.triage.alwaysInclude, 'i'); sections.forEach((sec, i) => { if (sec.part === 'principal' && rx.test(sec.text.slice(0, 160))) idx.add(i) }) }
    if (idx.size > 0) {
      strategy = 'triage'
      const selected = sections.filter((_, i) => idx.has(i))
      const reasons = new Map(triage.selected.map((s) => [s.index, s.reason]))
      selectedSections = [...idx].sort((a, b) => a - b).map((i) => ({ id: sections[i].id, pages: sections[i].pages, reason: reasons.get(i) ?? 'read alongside a selected section' }))
      const principalCount = selected.filter((x) => x.part === 'principal').length
      const perCall = Math.max(env.extractGroupSections, Math.ceil(principalCount / env.extractConcurrency))
      units = groupSections(selected, env.extractGroupChars, perCall).map((g) => g.map((s) => `[[${s.pages}]]\n${s.text}`).join('\n\n'))
    } else units = splitWindows(args.source.text, env.ingestWindowChars)
  } else units = splitWindows(args.source.text, env.ingestWindowChars)
  const charsSent = units.reduce((n, u) => n + u.length, 0)

  // ── Stage 3: extract every unit in parallel, streaming units as they land
  onEvent({ type: 'stage', stage: 'extract', total: units.length, detail: strategy === 'triage' ? `${selectedSections?.length ?? 0} of ${sections.length} sections` : `${units.length} window(s)` })
  let done = 0
  const perUnit = await mapLimit(units, env.extractConcurrency, async (text, i) => {
    const res = await chatJson<Record<string, unknown>>({ system, user: `${header({ index: i, count: units.length })}\n\nDOCUMENT TEXT\n${text}`, jsonSchema: { name: 'extraction', strict: true, schema: extractionSchema } })
    model = res.model
    account(res.model, res.usage)
    const found = Array.isArray(res.data[spec.unit.name]) ? (res.data[spec.unit.name] as Unit[]) : []
    done += 1
    onEvent({ type: 'progress', stage: 'extract', done, total: units.length })
    onEvent({ type: 'units', units: found, group: i, groups: units.length })
    return { identity: res.data, units: found }
  })

  // ── Stage 4: merge
  onEvent({ type: 'stage', stage: 'merge' })
  const merged = mergeUnits(perUnit.map((p) => p.units), spec.unit)
  const id = mergeIdentity(identity, perUnit.map((p) => p.identity), identityFields, spec.identity?.defaults ?? {}, args.name)

  const result: SectionsResult = {
    identity: id,
    units: merged,
    provider: { model, strategy, windows: units.length, sectionsFound: sections.length, sectionsSelected: selectedSections?.length ?? 0, selectedSections, promptTokens, completionTokens, costUsd: cost > 0 ? Math.round(cost * 10000) / 10000 : undefined, ms: Date.now() - t0, cached: false },
    source: { kind: args.source.kind, pages: args.source.pages, bytes: args.source.bytes, chars: args.source.text.length, charsSent, ocrPages: args.source.ocrPages, warning: args.source.warning },
  }
  await cacheSet(cacheKey, result)
  return result
}
