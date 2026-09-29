// The published CreditIQ configuration, read per version (FRD F-00.3, AD-2).
//
// A version is a directory $CREDITIQ_DATA_ROOT/config_store/versions/<id>/
// holding one JSON file per section, written once by the CreditIQ config
// writer. This service only reads it: a version is loaded on first use, frozen
// and kept for the life of the process. There is no hot reload and no way to
// change a loaded version; a new configuration is a new version id.
import { readFile, readdir, stat } from 'node:fs/promises'
import { join } from 'node:path'

export interface SignalSet { required: string[]; supporting: string[]; contrary: string[] }

export type InstanceKey = 'none' | 'period' | 'year' | 'account' | 'person' | 'property'

export interface DocumentTypeDef {
  id: string
  name: string
  group: string
  description: string
  satisfies: string[]
  instance_key: InstanceKey
  personal: boolean
  partner_output: boolean
  dictionary: string | null
  signals: SignalSet
}

export interface DocumentTypesSection {
  tier1_margin: number
  classify_threshold: number
  types: DocumentTypeDef[]
}

export type FieldType = 'text' | 'date' | 'money_inr' | 'number' | 'percent' | 'identifier' | 'boolean' | 'period' | 'table'
export type IdentifierKind = 'pan' | 'gstin' | 'cin' | 'udyam' | 'din' | 'ifsc' | 'tan' | 'udin' | 'itr_ack'

export interface FieldDef {
  name: string
  label: string
  type: FieldType
  key_field: boolean
  identifier: IdentifierKind | null
  description: string
  columns: FieldDef[]
}

export interface DictionarySection { id: string; fields: FieldDef[] }

export interface QualitySection {
  min_dpi: number
  ocr_confidence_floor: number
  ocr_confidence_degraded: number
  min_chars_text_layer: number
  reason_codes: Record<string, string>
}

export interface ConfidenceSection {
  weights: Record<string, number>
  caps: Record<string, number>
  key_field_review_threshold: number
  manual_entry_cap: number
}

/** A compiled signal: the pattern as configured, and its JavaScript form. */
export interface CompiledSignal { pattern: string; re: RegExp }

export interface CompiledType extends DocumentTypeDef {
  compiled: { required: CompiledSignal[]; supporting: CompiledSignal[]; contrary: CompiledSignal[] }
}

export interface LoadedConfig {
  version: string
  documentTypes: DocumentTypesSection
  types: CompiledType[]
  typeById: Map<string, CompiledType>
  dictionaries: Map<string, DictionarySection>
  quality: QualitySection
  confidence: ConfidenceSection
  /** Signal patterns that did not compile in JavaScript (reported by /v1/health). */
  signalProblems: string[]
}

export class ConfigError extends Error {
  constructor(public status: 400 | 409 | 500, message: string) { super(message) }
}

const VERSION_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/

const deepFreeze = <T>(o: T): T => {
  if (o && typeof o === 'object' && !Object.isFrozen(o)) {
    Object.freeze(o)
    for (const v of Object.values(o as Record<string, unknown>)) deepFreeze(v)
  }
  return o
}

/**
 * Python `re` patterns as published. The configured patterns use the common
 * subset; the few Python-only constructs are translated here, and anything
 * that still fails to compile is reported, never silently changed.
 */
export function compilePattern(pattern: string): RegExp {
  const js = pattern.replace(/\(\?P</g, '(?<').replace(/\\Z/g, '$').replace(/\\A/g, '^')
  return new RegExp(js, 'im')
}

function normaliseField(f: Partial<FieldDef> & { name: string; label: string; type: FieldType }): FieldDef {
  return {
    name: f.name,
    label: f.label,
    type: f.type,
    key_field: Boolean(f.key_field),
    identifier: f.identifier ?? null,
    description: f.description ?? '',
    columns: (f.columns ?? []).map((c) => normaliseField(c)),
  }
}

async function readJson<T>(path: string): Promise<T> {
  return JSON.parse(await readFile(path, 'utf8')) as T
}

export class ConfigStore {
  private cache = new Map<string, Promise<LoadedConfig>>()
  constructor(private dataRoot: string) {}

  versionsDir(): string { return join(this.dataRoot, 'config_store', 'versions') }

  async load(version: string): Promise<LoadedConfig> {
    if (!this.dataRoot) throw new ConfigError(500, 'CREDITIQ_DATA_ROOT is not set')
    if (!VERSION_RE.test(version) || version.includes('..')) throw new ConfigError(400, 'config_version is not a valid version id')
    let p = this.cache.get(version)
    if (!p) {
      p = this.read(version)
      this.cache.set(version, p)
      p.catch(() => this.cache.delete(version))
    }
    return p
  }

  private async read(version: string): Promise<LoadedConfig> {
    const dir = join(this.versionsDir(), version)
    const isDir = await stat(dir).then((s) => s.isDirectory()).catch(() => false)
    if (!isDir) throw new ConfigError(409, `unknown config_version ${version}`)
    const documentTypes = await readJson<DocumentTypesSection>(join(dir, 'document_types.json'))
    const quality = await readJson<QualitySection>(join(dir, 'quality.json'))
    const confidence = await readJson<ConfidenceSection>(join(dir, 'confidence.json'))
    const dictionaries = new Map<string, DictionarySection>()
    for (const name of (await readdir(dir)).sort()) {
      const m = /^dictionary\.(.+)\.json$/.exec(name)
      if (!m) continue
      const d = await readJson<{ id: string; fields: FieldDef[] }>(join(dir, name))
      dictionaries.set(m[1], { id: d.id, fields: d.fields.map((f) => normaliseField(f)) })
    }
    const signalProblems: string[] = []
    const compileAll = (typeId: string, kind: string, list: string[] | undefined): CompiledSignal[] =>
      (list ?? []).flatMap((pattern) => {
        try { return [{ pattern, re: compilePattern(pattern) }] } catch (e) {
          signalProblems.push(`${typeId}.${kind}: ${e instanceof Error ? e.message : String(e)}`)
          return []
        }
      })
    const types: CompiledType[] = documentTypes.types.map((t) => {
      const signals: SignalSet = { required: t.signals?.required ?? [], supporting: t.signals?.supporting ?? [], contrary: t.signals?.contrary ?? [] }
      return {
        id: t.id,
        name: t.name,
        group: t.group,
        description: t.description,
        satisfies: t.satisfies ?? [],
        instance_key: t.instance_key ?? 'none',
        personal: Boolean(t.personal),
        partner_output: Boolean(t.partner_output),
        dictionary: t.dictionary ?? null,
        signals,
        compiled: {
          required: compileAll(t.id, 'required', signals.required),
          supporting: compileAll(t.id, 'supporting', signals.supporting),
          contrary: compileAll(t.id, 'contrary', signals.contrary),
        },
      }
    })
    const loaded: LoadedConfig = {
      version,
      documentTypes: { tier1_margin: documentTypes.tier1_margin, classify_threshold: documentTypes.classify_threshold, types: documentTypes.types },
      types,
      typeById: new Map(types.map((t) => [t.id, t])),
      dictionaries,
      quality,
      confidence,
      signalProblems,
    }
    // RegExp objects are stateless for .test() without the g flag; freezing the
    // plain data makes an accidental in-place edit throw.
    deepFreeze(loaded.documentTypes)
    deepFreeze(loaded.quality)
    deepFreeze(loaded.confidence)
    for (const d of dictionaries.values()) deepFreeze(d)
    return Object.freeze(loaded)
  }
}
