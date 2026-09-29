// `type: "auto"` — decide which catalogue type a document is. Order of authority: the packs'
// signatures (sender, subject, file name, text patterns — deterministic and free), then one cheap
// model call over the document's head and the catalogue's descriptions with a few confirmed
// example snippets per type. Below the confidence threshold nothing is chosen: the caller gets
// `generic` output plus the candidates and `needsReview`, and a person decides (POST /v1/feedback
// then teaches the classifier for next time).
import { env } from './env.js'
import { chatJson } from './llm.js'
import { cacheGet, cacheSet, sha256 } from './cache.js'
import type { Document } from './inputs.js'
import type { Pack } from './catalogue.js'

export interface Classification {
  type: string | null
  confidence: number
  /** 'signature' (deterministic), 'model', or 'none' (below threshold / no candidates). */
  by: 'signature' | 'model' | 'none'
  reason: string
  candidates: { type: string; confidence: number; reason?: string }[]
}

const HEAD = 4_000
const rx = (s?: string) => (s ? new RegExp(s, 'im') : null) // multiline: ^ and $ match line starts and ends

/** Deterministic pass: every pack whose signatures all hold. */
export function bySignature(doc: Document, packs: Pack[]): Classification | null {
  const head = doc.text.text.slice(0, HEAD)
  const hits: { type: string; confidence: number; reason: string }[] = []
  for (const p of packs) {
    const s = p.signatures
    if (!s || p.builtIn) continue
    const checks: [string, boolean][] = []
    if (s.sender) checks.push([`sender ~ /${s.sender}/`, Boolean(doc.mail?.from && rx(s.sender)!.test(doc.mail.from))])
    if (s.subject) checks.push([`subject ~ /${s.subject}/`, Boolean(doc.mail?.subject && rx(s.subject)!.test(doc.mail.subject))])
    if (s.filename) checks.push([`file ~ /${s.filename}/`, rx(s.filename)!.test(doc.name)])
    for (const t of s.textAll ?? []) checks.push([`text ~ /${t}/`, rx(t)!.test(head)])
    if (s.textAny?.length) checks.push([`text ~ any of ${s.textAny.length}`, s.textAny.some((t) => rx(t)!.test(head))])
    if (checks.length && checks.every(([, ok]) => ok)) hits.push({ type: p.id, confidence: s.confidence ?? 0.9, reason: checks.map(([c]) => c).join(', ') })
  }
  if (!hits.length) return null
  // A more specific type (one that extends another hit) wins over its parent.
  const specific = hits.filter((h) => !hits.some((o) => o !== h && packs.find((p) => p.id === o.type)?.extends === h.type))
  const best = specific.sort((a, b) => b.confidence - a.confidence)[0]
  if (specific.length > 1 && specific[0].confidence === specific[1].confidence) return { type: null, confidence: 0, by: 'none', reason: `signatures of ${specific.map((h) => h.type).join(' and ')} all match — ambiguous`, candidates: specific }
  return { type: best.type, confidence: best.confidence, by: 'signature', reason: best.reason, candidates: hits }
}

const SNIPPET = 260
export async function classify(doc: Document, packs: Pack[], noCache = false): Promise<Classification> {
  const candidates = packs.filter((p) => !p.builtIn)
  if (!candidates.length) return { type: null, confidence: 0, by: 'none', reason: 'the catalogue has no types', candidates: [] }
  const sig = bySignature(doc, candidates)
  if (sig?.type) return sig
  const head = doc.text.text.slice(0, HEAD)
  const catalogueHash = sha256(candidates.map((p) => `${p.id}@${p.version}:${p.profile.description}:${p.examples.length}`).join('|'))
  const key = `classify-${sha256(`${doc.sha256}|${catalogueHash}|${env.ai.triageModel}`)}`
  if (!noCache) { const hit = await cacheGet<Classification>(key); if (hit) return hit }
  const list = candidates.map((p) => {
    const ex = p.examples.slice(0, 2).map((e) => `    e.g. "${e.snippet.replace(/\s+/g, ' ').slice(0, SNIPPET)}"`).join('\n')
    return `- ${p.id}: ${p.profile.description}${ex ? `\n${ex}` : ''}`
  }).join('\n')
  const schema = { type: 'object', additionalProperties: false, required: ['genre', 'type', 'fits', 'confidence', 'reason', 'alternatives'], properties: { genre: { type: 'string', description: 'what kind of document this is, in your own words (e.g. "delivery challan", "tax invoice", "board minutes")' }, type: { type: 'string', description: 'the closest listed type id, or "none"' }, fits: { type: 'boolean', description: 'true only if the document IS an instance of that type — not merely related to it (an order is not an invoice; a delivery note is not an order; a reminder about a filing is not the acknowledgement)' }, confidence: { type: 'number', description: '0–1, how certain the match is' }, reason: { type: 'string' }, alternatives: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['type', 'confidence'], properties: { type: { type: 'string' }, confidence: { type: 'number' } } } } } }
  const r = await chatJson<{ genre: string; type: string; fits: boolean; confidence: number; reason: string; alternatives: { type: string; confidence: number }[] }>({
    system: `You classify a document into exactly one of the document types below, by what the document IS (its genre and issuer), not by what it mentions or relates to. First name its genre in your own words; then pick the closest listed type and say whether the document truly is an instance of it (fits) — a related-but-different genre does not fit, however similar the fields look. Answer "none" with fits=false when no type is the document's own genre; never force a match. Confidence 0–1 reflects how certain the match is; use specific values (0.83, 0.41), not round ones.\n\nTYPES\n${list}`,
    user: `${doc.mail ? `E-mail — From: ${doc.mail.from} · Subject: ${doc.mail.subject}${doc.part === 'attachment' ? ` · attachment ${doc.name}` : ''}\n` : `File: ${doc.name}\n`}\nDOCUMENT (first ${HEAD} characters)\n${head}`,
    jsonSchema: { name: 'classification', strict: true, schema }, temperature: 0, model: env.ai.triageModel,
  })
  const known = new Set(candidates.map((p) => p.id))
  const alts = (r.data.alternatives ?? []).filter((a) => known.has(a.type)).sort((a, b) => b.confidence - a.confidence)
  const chosen = known.has(r.data.type) ? r.data.type : null
  const conf = Math.max(0, Math.min(1, Number(r.data.confidence) || 0))
  const reason = `${r.data.genre ? `${r.data.genre}: ` : ''}${r.data.reason}`
  const out: Classification = chosen && r.data.fits && conf >= env.autoThreshold
    ? { type: chosen, confidence: conf, by: 'model', reason, candidates: [{ type: chosen, confidence: conf, reason: r.data.reason }, ...alts.filter((a) => a.type !== chosen)] }
    : { type: null, confidence: conf, by: 'none', reason: chosen && !r.data.fits ? `closest is ${chosen}, but the document is a different kind — ${reason}` : chosen ? `${chosen} at ${conf.toFixed(2)} is below the ${env.autoThreshold} threshold — ${reason}` : reason, candidates: [...(chosen ? [{ type: chosen, confidence: conf, reason: r.data.reason }] : []), ...alts.filter((a) => a.type !== chosen)] }
  await cacheSet(key, out)
  return out
}
