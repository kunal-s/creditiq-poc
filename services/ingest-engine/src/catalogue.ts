// The type catalogue: one directory of *profile packs*, each the full description of a document
// type — what to extract (profile.json), how to read that family of documents (rules.md), what the
// prompt may cite (reference/*.md), confirmed input→output pairs (examples/*.json, plus what
// feedback adds under INGEST_FEEDBACK_DIR) and post-checks (validators). Packs are namespaced
// (`bank/statement`), versioned (`@2`) and may extend one another (`sbi/statement` extends
// `bank/statement`). The engine ships no types of its own beyond `generic`; the catalogue is
// content, owned by whoever owns the document types, and loaded fresh from disk on every call.
//
//   types/<namespace>/<type>/profile.json    { version, description, extends?, strategy, instructions, fields | schema | unit/identity/triage, signatures?, validators? }
//   types/<namespace>/<type>/rules.md        appended to the prompt as the pack's rules
//   types/<namespace>/<type>/reference/*.md  appended as REFERENCE (capped)
//   types/<namespace>/<type>/examples/*.json { snippet, mail?, output, note?, source? }
//   feedback/<namespace>/<type>/*.json       examples confirmed or corrected through POST /v1/feedback
import { readdir, readFile, writeFile, mkdir, stat } from 'node:fs/promises'
import { join } from 'node:path'
import { env } from './env.js'
import { inlineProfile, type Field, type InlineProfile, type Profile, type SectionsSpec } from './profiles.js'

/** Cheap, deterministic hints that a document is of this type — checked before any model call. */
export interface Signatures {
  /** Regex on the sender of an e-mail the document came from. */
  sender?: string
  /** Regex on the e-mail subject. */
  subject?: string
  /** Regex on the file name. */
  filename?: string
  /** Regexes on the first ~4 000 characters of text; `all` must all match, `any` needs one. */
  textAll?: string[]
  textAny?: string[]
  /** Confidence to report when the signatures match (default 0.9). */
  confidence?: number
}
export interface Validator { field: string; /** regex the (string) value must match */ pattern?: string; min?: number; max?: number; /** the field must be non-empty */ required?: boolean; message?: string }
export interface Example { id: string; snippet: string; mail?: { from?: string; subject?: string }; output: unknown; note?: string; source: 'pack' | 'feedback'; at?: string }

export interface PackFile extends InlineProfile {
  version?: number
  extends?: string
  signatures?: Signatures
  validators?: Validator[]
}
export interface Pack {
  id: string
  namespace: string
  version: number
  extends?: string
  profile: Profile
  rules: string
  reference: string
  signatures?: Signatures
  validators: Validator[]
  examples: Example[]
  dir: string | null
  builtIn?: boolean
}

const ID = /^[a-z0-9][a-z0-9-]*(\/[a-z0-9][a-z0-9-]*)?$/
export const isTypeId = (s: string) => ID.test(s)
const REFERENCE_CAP = 12_000
const dirOf = (root: string, id: string) => join(root, ...id.split('/'))

async function exists(p: string): Promise<boolean> { try { await stat(p); return true } catch { return false } }
async function readText(p: string): Promise<string> { try { return (await readFile(p, 'utf8')).trim() } catch { return '' } }
async function readJsonFiles<T>(dir: string): Promise<{ name: string; data: T }[]> {
  try {
    const names = (await readdir(dir)).filter((n) => n.endsWith('.json')).sort()
    const out: { name: string; data: T }[] = []
    for (const n of names) { try { out.push({ name: n, data: JSON.parse(await readFile(join(dir, n), 'utf8')) as T }) } catch (e) { console.warn(`[catalogue] ${dir}/${n} skipped:`, e instanceof Error ? e.message : e) } }
    return out
  } catch { return [] }
}

/** Every type id the catalogue holds (namespace/type folders with a profile.json, plus flat <id>.json files). */
export async function listTypeIds(): Promise<string[]> {
  const root = env.typesDir
  const ids = new Set<string>()
  try {
    for (const ns of await readdir(root, { withFileTypes: true })) {
      if (ns.isDirectory()) {
        for (const t of await readdir(join(root, ns.name), { withFileTypes: true })) {
          if (t.isDirectory() && (await exists(join(root, ns.name, t.name, 'profile.json')))) ids.add(`${ns.name}/${t.name}`)
        }
        if (await exists(join(root, ns.name, 'profile.json'))) ids.add(ns.name)
      } else if (ns.name.endsWith('.json')) ids.add(ns.name.replace(/\.json$/, ''))
    }
  } catch { /* no catalogue directory: only generic */ }
  return [...ids].sort()
}

async function readPackFile(id: string): Promise<{ file: PackFile; dir: string | null } | null> {
  const root = env.typesDir
  const dir = dirOf(root, id)
  if (await exists(join(dir, 'profile.json'))) return { file: JSON.parse(await readFile(join(dir, 'profile.json'), 'utf8')) as PackFile, dir }
  if (await exists(`${dir}.json`)) return { file: JSON.parse(await readFile(`${dir}.json`, 'utf8')) as PackFile, dir: null }
  return null
}

/** Merge a child pack file onto its parent's: fields by name, instructions and rules appended, signatures unioned. */
function inherit(parent: Pack, child: PackFile): PackFile {
  const pp = parent.profile
  const merged: PackFile = { ...child }
  merged.description = child.description ?? pp.description
  merged.strategy = child.strategy ?? pp.strategy
  merged.instructions = child.instructions?.trim() ? `${pp.instructions}\n\nSPECIFICS FOR ${child.description ?? 'THIS VARIANT'}\n${child.instructions.trim()}` : pp.instructions
  if (pp.strategy === 'fields' || !pp.strategy) {
    const byName = new Map((pp.fields ?? []).map((f) => [f.name, f]))
    for (const f of (child.fields ?? []) as Field[]) byName.set(f.name, f)
    merged.fields = child.schema ? undefined : [...byName.values()]
    merged.schema = child.schema ?? (child.fields ? undefined : pp.schema)
  } else if (pp.sections) {
    merged.unit = child.unit ?? pp.sections.unit
    merged.identity = child.identity ?? pp.sections.identity
    merged.triage = child.triage ?? pp.sections.triage
  }
  merged.signatures = { ...(parent.signatures ?? {}), ...(child.signatures ?? {}) }
  merged.validators = [...parent.validators, ...(child.validators ?? [])]
  return merged
}

async function examplesFor(id: string, dir: string | null): Promise<Example[]> {
  const out: Example[] = []
  const fromDir = async (d: string, source: Example['source']) => {
    for (const { name, data } of await readJsonFiles<Omit<Example, 'id' | 'source'>>(d)) {
      if (typeof data?.snippet !== 'string' || data.output === undefined) continue
      out.push({ id: name.replace(/\.json$/, ''), snippet: data.snippet, mail: data.mail, output: data.output, note: data.note, source, at: data.at })
    }
  }
  if (dir) await fromDir(join(dir, 'examples'), 'pack')
  if (env.feedbackDir) await fromDir(dirOf(env.feedbackDir, id), 'feedback')
  return out
}

const packCache = new Map<string, { at: number; pack: Pack }>()
const PACK_TTL_MS = 2_000 // re-read from disk after this; an edited pack applies on the next request
/** Forget a cached pack (and every pack, when a parent may have changed). */
export function invalidatePack(id?: string): void { if (id) packCache.delete(id); else packCache.clear() }

/** Load a type by id, resolving `extends` (parents first) and merging examples and reference text. */
export async function loadPack(id: string, seen: string[] = []): Promise<Pack | null> {
  if (id === 'generic') return genericPack()
  if (!isTypeId(id)) return null
  const hit = packCache.get(id)
  if (hit && Date.now() - hit.at < PACK_TTL_MS) return hit.pack
  const read = await readPackFile(id)
  if (!read) return null
  if (seen.includes(id)) throw new Error(`type ${id}: circular extends (${[...seen, id].join(' → ')})`)
  let file = read.file
  let parent: Pack | null = null
  if (file.extends) {
    parent = await loadPack(file.extends, [...seen, id])
    if (!parent) throw new Error(`type ${id} extends unknown type ${file.extends}`)
    file = inherit(parent, file)
  }
  const profile = inlineProfile({ ...file, id })
  const rules = [parent?.rules ?? '', read.dir ? await readText(join(read.dir, 'rules.md')) : ''].filter(Boolean).join('\n\n')
  let reference = parent?.reference ?? ''
  if (read.dir) {
    try { for (const n of (await readdir(join(read.dir, 'reference'))).filter((x) => x.endsWith('.md')).sort()) reference += `\n\n${await readText(join(read.dir, 'reference', n))}` } catch { /* none */ }
  }
  const pack: Pack = {
    id, namespace: id.includes('/') ? id.split('/')[0] : '',
    version: Number.isInteger(file.version) ? Number(file.version) : 1,
    extends: file.extends,
    profile, rules, reference: reference.trim().slice(0, REFERENCE_CAP),
    signatures: file.signatures, validators: file.validators ?? [],
    examples: [...(parent?.examples ?? []), ...(await examplesFor(id, read.dir))],
    dir: read.dir,
  }
  packCache.set(id, { at: Date.now(), pack })
  return pack
}

function genericPack(): Pack {
  const g = inlineProfile({ id: 'generic', instructions: '' })
  return { id: 'generic', namespace: '', version: 1, profile: { ...g, builtIn: true }, rules: '', reference: '', validators: [], examples: [], dir: null, builtIn: true }
}

/** Resolve a request's type: `id`, `id@version` (must match the catalogue's version), `generic`. */
export async function resolveType(spec: string): Promise<Pack> {
  const m = spec.match(/^(.+?)(?:@(\d+))?$/)
  const id = m?.[1] ?? spec
  const pinned = m?.[2] ? Number(m[2]) : undefined
  const pack = await loadPack(id)
  if (!pack) throw new TypeError(`unknown type "${id}" — GET /v1/types lists the catalogue`)
  if (pinned !== undefined && pinned !== pack.version) throw new TypeError(`type ${id} is at version ${pack.version}; the request pinned @${pinned} — review the change and bump the pin`)
  return pack
}

export async function listPacks(): Promise<Pack[]> {
  const out: Pack[] = [genericPack()]
  for (const id of await listTypeIds()) { try { const p = await loadPack(id); if (p) out.push(p) } catch (e) { console.warn(`[catalogue] ${id} skipped:`, e instanceof Error ? e.message : e) } }
  return out
}

/** Write (or replace) a pack's profile.json under the catalogue root — a custom type registered over the API. */
export async function savePack(id: string, file: PackFile): Promise<Pack> {
  if (!isTypeId(id) || id === 'generic') throw new Error('type id must be <namespace>/<type> in lowercase letters, digits and dashes')
  if (file.extends) { if (!(await loadPack(file.extends))) throw new Error(`extends unknown type ${file.extends}`) }
  else inlineProfile({ ...file, id }) // validates shape and strategy
  if (file.validators) validateValidators(file.validators)
  if (file.signatures) validateSignatures(file.signatures)
  const dir = dirOf(env.typesDir, id)
  await mkdir(dir, { recursive: true })
  const body: PackFile = { version: Number.isInteger(file.version) ? file.version : 1, description: file.description ?? '', extends: file.extends, strategy: file.strategy, instructions: file.instructions ?? '', fields: file.fields, schema: file.schema, unit: file.unit, identity: file.identity, triage: file.triage, signatures: file.signatures, validators: file.validators }
  await writeFile(join(dir, 'profile.json'), JSON.stringify(body, null, 2) + '\n')
  packCache.delete(id)
  return (await loadPack(id))!
}
export function validateSignatures(s: Signatures): void {
  for (const k of ['sender', 'subject', 'filename'] as const) if (s[k]) new RegExp(s[k]!, 'im')
  for (const k of ['textAll', 'textAny'] as const) for (const r of s[k] ?? []) new RegExp(r, 'im')
}
export function validateValidators(v: Validator[]): void {
  for (const x of v) { if (!x.field) throw new Error('validator.field is required'); if (x.pattern) new RegExp(x.pattern) }
}

/** Run a pack's validators over extracted data → warnings (never errors: the caller decides). */
export function validate(pack: Pack, data: unknown): string[] {
  const out: string[] = []
  if (!data || typeof data !== 'object') return out
  const d = data as Record<string, unknown>
  for (const v of pack.validators) {
    const val = d[v.field]
    const empty = val === null || val === undefined || val === '' || (Array.isArray(val) && !val.length)
    if (v.required && empty) { out.push(v.message ?? `${v.field} is empty`); continue }
    if (empty) continue
    if (v.pattern && typeof val === 'string' && !new RegExp(v.pattern).test(val)) out.push(v.message ?? `${v.field} "${val}" does not match ${v.pattern}`)
    if (typeof val === 'number') { if (v.min !== undefined && val < v.min) out.push(v.message ?? `${v.field} ${val} < ${v.min}`); if (v.max !== undefined && val > v.max) out.push(v.message ?? `${v.field} ${val} > ${v.max}`) }
  }
  return out
}

/** Few-shot material for the extraction prompt: up to `n` confirmed outputs of this type (feedback first — the caller's own documents). */
export function fewShot(pack: Pack, n = 2): string {
  const picked = [...pack.examples].sort((a, b) => (a.source === 'feedback' ? -1 : 0) - (b.source === 'feedback' ? -1 : 0)).slice(0, n)
  if (!picked.length) return ''
  return `EXAMPLES OF CORRECT OUTPUT FOR THIS TYPE (from confirmed documents; match their conventions)\n${picked.map((e, i) => `Example ${i + 1}${e.note ? ` — ${e.note}` : ''}:\n${JSON.stringify(e.output)}`).join('\n')}`
}

export type { Field, Profile, SectionsSpec }
