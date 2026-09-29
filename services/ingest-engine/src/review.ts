// The review queue: documents `auto` could not place. Each is kept (snippet, headers, candidates,
// the generic reading) until a person settles it through POST /v1/feedback. When several look
// alike, the engine can PROPOSE a type — a draft pack written from the samples — for a person to
// accept with PUT /v1/types/…; it never registers one on its own.
import { mkdir, readdir, readFile, unlink, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { env } from './env.js'
import { chatJson } from './llm.js'
import { listTypeIds, type PackFile } from './catalogue.js'
import { validateFields, type Field } from './profiles.js'
import type { Classification } from './classify.js'

export interface ReviewItem {
  sha256: string
  at: string
  name: string
  mail?: { from?: string; subject?: string }
  snippet: string
  candidates: Classification['candidates']
  reason: string
  /** The generic reading, so a person sees something useful before deciding. */
  generic: unknown
}
const dir = () => join(env.feedbackDir, '_review')
const SNIPPET = 1_500

export async function enqueue(item: Omit<ReviewItem, 'at'>): Promise<void> {
  if (!env.feedbackDir) return
  await mkdir(dir(), { recursive: true })
  await writeFile(join(dir(), `${item.sha256.slice(0, 12)}.json`), JSON.stringify({ ...item, snippet: item.snippet.slice(0, SNIPPET), at: new Date().toISOString() }, null, 2) + '\n')
}
export async function dequeue(sha256: string): Promise<boolean> {
  try { await unlink(join(dir(), `${sha256.slice(0, 12)}.json`)); return true } catch { return false }
}
export async function listReview(): Promise<ReviewItem[]> {
  try {
    const out: ReviewItem[] = []
    for (const n of (await readdir(dir())).filter((x) => x.endsWith('.json')).sort()) { try { out.push(JSON.parse(await readFile(join(dir(), n), 'utf8')) as ReviewItem) } catch { /* skip */ } }
    return out.sort((a, b) => (a.at < b.at ? 1 : -1))
  } catch { return [] }
}

// ── Clustering: documents that share vocabulary probably share a type ────────
const STOP = new Set(['the', 'and', 'for', 'with', 'from', 'that', 'this', 'are', 'was', 'were', 'has', 'have', 'not', 'its', 'into', 'per', 'all', 'any', 'each', 'one', 'two', 'date', 'dear', 'regards', 'thanks', 'please', 'you', 'your', 'our'])
const tokens = (s: string) => new Set(s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').split(' ').filter((w) => w.length >= 3 && !STOP.has(w) && !/^\d+$/.test(w)))
const jaccard = (a: Set<string>, b: Set<string>) => { let n = 0; for (const t of a) if (b.has(t)) n += 1; return n / (a.size + b.size - n || 1) }
const SIMILAR = 0.22

export interface Cluster { index: number; items: ReviewItem[]; sharedTerms: string[] }
/** Greedy single-link clusters over the queue; only clusters of `min` or more are worth a proposal. */
export async function clusters(min = 3): Promise<Cluster[]> {
  const items = await listReview()
  const toks = items.map((i) => tokens(`${i.mail?.subject ?? ''} ${i.snippet}`))
  const group = items.map((_, i) => i)
  const find = (i: number): number => (group[i] === i ? i : (group[i] = find(group[i])))
  for (let i = 0; i < items.length; i++) for (let j = i + 1; j < items.length; j++) if (jaccard(toks[i], toks[j]) >= SIMILAR) group[find(i)] = find(j)
  const byRoot = new Map<number, number[]>()
  items.forEach((_, i) => { const r = find(i); byRoot.set(r, [...(byRoot.get(r) ?? []), i]) })
  const out: Cluster[] = []
  for (const members of byRoot.values()) {
    if (members.length < min) continue
    const shared = [...toks[members[0]]].filter((t) => members.every((m) => toks[m].has(t))).slice(0, 12)
    out.push({ index: out.length, items: members.map((m) => items[m]), sharedTerms: shared })
  }
  return out.sort((a, b) => b.items.length - a.items.length).map((c, i) => ({ ...c, index: i }))
}

export interface Proposal { suggestedId: string; pack: PackFile; samples: string[]; rationale: string }
/** Draft a pack from a cluster's samples: the model names the type and its fields; a person reviews and registers it. */
export async function propose(cluster: Cluster): Promise<Proposal> {
  const existing = await listTypeIds()
  const samples = cluster.items.slice(0, 5).map((i, k) => `--- sample ${k + 1}${i.mail ? ` (e-mail from ${i.mail.from ?? '?'}, subject "${i.mail.subject ?? ''}")` : ` (${i.name})`}\n${i.snippet.slice(0, 1200)}`).join('\n\n')
  const schema = { type: 'object', additionalProperties: false, required: ['suggestedId', 'description', 'instructions', 'fields', 'signatures', 'rationale'], properties: {
    suggestedId: { type: 'string', description: 'namespace/type in lowercase letters, digits and dashes, e.g. procurement/purchase-order' },
    description: { type: 'string' }, instructions: { type: 'string', description: 'what to extract and what to ignore, for an extraction model' }, rationale: { type: 'string' },
    fields: { type: 'array', items: { type: 'object', additionalProperties: false, required: ['name', 'type', 'description', 'required'], properties: { name: { type: 'string' }, type: { type: 'string', enum: ['string', 'number', 'boolean', 'date', 'string[]'] }, description: { type: 'string' }, required: { type: 'boolean' } } } },
    signatures: { type: 'array', items: { type: 'string' }, description: 'two to four case-insensitive regular expressions that appear in every document of this kind and rarely elsewhere' },
  } }
  const r = await chatJson<{ suggestedId: string; description: string; instructions: string; fields: Field[]; signatures: string[]; rationale: string }>({
    system: `You design document types for an extraction engine. Given several documents of the same unknown kind, propose one type: a short id (namespace/type), a one-line description, extraction instructions, the fields a downstream system would want (flat — no nested objects; use string[] for lists), and a few signature regexes that identify this kind. Existing types (do not duplicate them): ${existing.join(', ') || 'none'}. Output only the JSON the schema requires.`,
    user: `DOCUMENTS\n${samples}`, jsonSchema: { name: 'type_proposal', strict: true, schema }, temperature: 0.2, model: env.ai.model,
  })
  const id = (r.data.suggestedId || 'unsorted/new-type').toLowerCase().replace(/[^a-z0-9/-]+/g, '-').replace(/^-|-$/g, '')
  const fields = validateFields(r.data.fields.map((f) => ({ ...f, enum: undefined })))
  const signatures = r.data.signatures.filter((s) => { try { new RegExp(s, 'i'); return true } catch { return false } }).slice(0, 4)
  return {
    suggestedId: /^[a-z0-9][a-z0-9-]*\/[a-z0-9][a-z0-9-]*$/.test(id) ? id : `unsorted/${id.replace(/\//g, '-')}`,
    pack: { version: 1, description: r.data.description, strategy: 'fields', instructions: r.data.instructions, fields, signatures: signatures.length ? { textAny: signatures, confidence: 0.8 } : undefined },
    samples: cluster.items.map((i) => i.sha256), rationale: r.data.rationale,
  }
}
