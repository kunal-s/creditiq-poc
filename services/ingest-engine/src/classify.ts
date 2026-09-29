// Classification by content (FRD F-09). Chooses only from the published
// closed list of document types, or none (unclassified). The file name and
// label hint are never inputs: nothing here can see them.
//
//   tier 1 "signals": the type's required signals all match, none of its
//          contrary signals match, its score reaches classify_threshold and
//          leads the runner-up by tier1_margin (F-09.3). Evaluated per page
//          (page anchors drive splitting) and over the whole document.
//   tier 2 "layout": the type's dictionary table columns appear as a table
//          header on the page (for example date / debit / credit / balance).
//   tier 3 "model":  the model chooses from the closed list or none_of_these;
//          the choice counts only when the page content gives it support.
import type { CompiledType, LoadedConfig } from './config.js'
import type { Candidate, Classification } from './contract.js'
import { aliasesFor } from './extract/aliases.js'
import { findHeaders } from './extract/tables.js'
import { ModelError, type ModelClient } from './llm/index.js'
import type { PageRead } from './read/types.js'

export interface TypeScore {
  type: CompiledType
  score: number
  qualified: boolean
  required: string[]
  supporting: string[]
  contrary: string[]
}

const round3 = (x: number) => Math.round(x * 1000) / 1000

export function scoreText(text: string, cfg: LoadedConfig): TypeScore[] {
  const scores = cfg.types.map((t): TypeScore => {
    const req = t.compiled.required.filter((s) => s.re.test(text)).map((s) => s.pattern)
    const sup = t.compiled.supporting.filter((s) => s.re.test(text)).map((s) => s.pattern)
    const con = t.compiled.contrary.filter((s) => s.re.test(text)).map((s) => s.pattern)
    const reqN = t.compiled.required.length
    const supN = t.compiled.supporting.length
    const supFrac = supN ? sup.length / supN : 0
    let score = reqN ? 0.6 * (req.length / reqN) + 0.4 * supFrac : 0.5 * supFrac
    if (con.length) score *= 0.5
    return { type: t, score: round3(score), qualified: reqN > 0 && req.length === reqN && con.length === 0, required: req, supporting: sup, contrary: con }
  })
  return scores.sort((a, b) => b.score - a.score || a.type.id.localeCompare(b.type.id))
}

/** A tier-1 exit on this text, or null. */
export function tier1(scores: TypeScore[], cfg: LoadedConfig): TypeScore | null {
  const [top, second] = scores
  if (!top?.qualified) return null
  if (top.score < cfg.documentTypes.classify_threshold) return null
  if (second && top.score - second.score < cfg.documentTypes.tier1_margin) return null
  return top
}

export interface PageClass { anchor: TypeScore | null; scores: TypeScore[] }

export function classifyPage(page: PageRead, cfg: LoadedConfig): PageClass {
  const scores = scoreText(page.text, cfg)
  return { anchor: tier1(scores, cfg), scores }
}

function signalList(s: TypeScore): string[] {
  return [
    ...s.required.map((p) => `${s.type.id} required: ${p}`),
    ...s.supporting.map((p) => `${s.type.id} supporting: ${p}`),
    ...s.contrary.map((p) => `${s.type.id} contrary: ${p}`),
  ]
}

/** Share of a type's dictionary table columns that appear as one table header. */
function layoutCoverage(t: CompiledType, pages: PageRead[], cfg: LoadedConfig): { coverage: number; columns: string[] } {
  const dict = t.dictionary ? cfg.dictionaries.get(t.dictionary) : undefined
  let best = { coverage: 0, columns: [] as string[] }
  for (const f of dict?.fields ?? []) {
    if (f.type !== 'table' || f.columns.length < 3) continue
    const cols = f.columns.map((c) => ({ name: c.name, aliases: aliasesFor(dict!.id, `${f.name}.${c.name}`, c.label, c.name) }))
    for (const p of pages.slice(0, 3)) {
      for (const h of findHeaders(p, cols, 2)) {
        const cov = h.bands.length / cols.length
        if (cov > best.coverage) best = { coverage: cov, columns: h.bands.map((b) => b.name) }
      }
    }
  }
  return best
}

function candidates(scores: TypeScore[], first: string[] = [], override = new Map<string, number>()): Candidate[] {
  const out: Candidate[] = []
  const seen = new Set<string>()
  const add = (id: string, c: number) => { if (!seen.has(id) && out.length < 3) { seen.add(id); out.push({ type_id: id, confidence: round3(c) }) } }
  const byId = new Map(scores.map((s) => [s.type.id, s]))
  for (const id of first) add(id, override.get(id) ?? byId.get(id)?.score ?? 0)
  for (const s of [...scores].sort((a, b) => (override.get(b.type.id) ?? b.score) - (override.get(a.type.id) ?? a.score))) add(s.type.id, override.get(s.type.id) ?? s.score)
  return out
}

const SYSTEM = [
  "You classify one document from a business borrower's credit file.",
  'Choose only from the listed type ids, or none_of_these when the document is none of them.',
  'A document can have several types only when it plainly contains each of them (for example an acknowledgement together with a computation).',
  'Judge by the content of the pages only.',
  'Also rank up to three type ids that the document most resembles, best first.',
].join('\n')

export interface ClassifyOutcome { classification: Classification; modelMiss: boolean; modelError: boolean }

export async function classifyDocument(pages: PageRead[], pageClasses: PageClass[], cfg: LoadedConfig, model: ModelClient | null): Promise<ClassifyOutcome> {
  const threshold = cfg.documentTypes.classify_threshold
  const margin = cfg.documentTypes.tier1_margin
  const text = pages.map((p) => p.text).join('\n')
  const scores = scoreText(text, cfg)

  // Tier 1 from page anchors (several types when pages anchor different types).
  const anchors = pageClasses.map((c) => c.anchor).filter((a): a is TypeScore => Boolean(a))
  if (anchors.length) {
    const best = new Map<string, TypeScore>()
    for (const a of anchors) if (!best.has(a.type.id) || best.get(a.type.id)!.score < a.score) best.set(a.type.id, a)
    const types = [...best.keys()]
    const confidence = Math.min(...[...best.values()].map((a) => a.score))
    const override = new Map([...best.entries()].map(([k, v]) => [k, v.score]))
    return { classification: { types, confidence: round3(confidence), exit_tier: 'signals', signals: [...best.values()].flatMap(signalList), candidates: candidates(scores, types, override) }, modelMiss: false, modelError: false }
  }
  // Tier 1 over the whole document (signals spread across pages).
  const whole = tier1(scores, cfg)
  if (whole) return { classification: { types: [whole.type.id], confidence: whole.score, exit_tier: 'signals', signals: signalList(whole), candidates: candidates(scores, [whole.type.id]) }, modelMiss: false, modelError: false }

  // Tier 2: table layout matching a type's dictionary, with no contrary signal.
  const layout = new Map<string, { coverage: number; columns: string[] }>()
  for (const t of cfg.types) {
    const l = layoutCoverage(t, pages, cfg)
    if (l.coverage > 0) layout.set(t.id, l)
  }
  const combined = new Map<string, number>()
  for (const s of scores) {
    const l = layout.get(s.type.id)
    combined.set(s.type.id, round3(l && l.coverage >= 0.6 && !s.contrary.length ? 0.5 * s.score + 0.5 * l.coverage : s.score))
  }
  const ranked = [...combined.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  const [top, second] = ranked
  const layoutSignals = (id: string) => (layout.get(id) ? [`${id} layout: table columns ${layout.get(id)!.columns.join(', ')}`] : [])
  if (top && layout.get(top[0]) && layout.get(top[0])!.coverage >= 0.6 && top[1] >= threshold && (!second || top[1] - second[1] >= margin)) {
    const s = scores.find((x) => x.type.id === top[0])!
    return { classification: { types: [top[0]], confidence: top[1], exit_tier: 'layout', signals: [...signalList(s), ...layoutSignals(top[0])], candidates: candidates(scores, [top[0]], combined) }, modelMiss: false, modelError: false }
  }

  // Tier 3: the model, from the closed list.
  const topSignals = ranked.slice(0, 3).flatMap(([id]) => [...signalList(scores.find((x) => x.type.id === id)!), ...layoutSignals(id)])
  // Nothing legible to read: no model call.
  const legible = pages.reduce((n, p) => n + p.words.length, 0) >= 5
  if (model && legible) {
    const ids = cfg.types.map((t) => t.id)
    const user = [
      'Document types:',
      ...cfg.types.map((t) => `- ${t.id}: ${t.name}. ${t.description}`),
      '- none_of_these: the document is none of the types above.',
      '',
      'Document pages:',
      ...pages.slice(0, 6).map((p) => `=== Page ${p.n} ===\n${p.text.slice(0, 4000)}`),
    ].join('\n')
    const schema = {
      type: 'object',
      properties: {
        types: { type: 'array', items: { type: 'string', enum: [...ids, 'none_of_these'] } },
        ranked: { type: 'array', items: { type: 'string', enum: ids } },
      },
    }
    try {
      const a = (await model.call({ task: 'classify', system: SYSTEM, user, schema })) as { types?: string[]; ranked?: string[] }
      const chosen = (a.types ?? []).filter((t) => ids.includes(t))
      const rankedIds = (a.ranked ?? []).filter((t) => ids.includes(t))
      // The model's choice counts only as far as the page content supports it.
      const support = (id: string) => combined.get(id) ?? 0
      const confOf = (id: string) => round3(0.5 + 0.5 * support(id))
      const accepted = (a.types ?? []).includes('none_of_these') ? [] : chosen.filter((id) => confOf(id) >= threshold)
      const signals = [...topSignals, ...(a.types ?? []).map((t) => `model: ${t}`)]
      if (accepted.length) {
        const override = new Map(accepted.map((id) => [id, confOf(id)]))
        return { classification: { types: accepted, confidence: Math.min(...accepted.map(confOf)), exit_tier: 'model', signals, candidates: candidates(scores, [...accepted, ...rankedIds], new Map([...combined, ...override])) }, modelMiss: false, modelError: false }
      }
      return { classification: { types: [], confidence: round3(top?.[1] ?? 0), exit_tier: 'none', signals, candidates: candidates(scores, rankedIds, combined) }, modelMiss: false, modelError: false }
    } catch (e) {
      const miss = e instanceof ModelError && e.code === 'replay_miss'
      return { classification: { types: [], confidence: round3(top?.[1] ?? 0), exit_tier: 'none', signals: [...topSignals, miss ? 'model: unavailable (no recording)' : 'model: error'], candidates: candidates(scores, [], combined) }, modelMiss: miss, modelError: !miss }
    }
  }
  return { classification: { types: [], confidence: round3(top?.[1] ?? 0), exit_tier: 'none', signals: topSignals, candidates: candidates(scores, [], combined) }, modelMiss: false, modelError: false }
}
