// Profiles: what to look for and the shape to return it in. A profile arrives inline with a
// request or as a pack in the type catalogue (catalogue.ts); this module is the shape language —
// the field DSL, strict JSON-schema compilation and validation — plus the one built-in, `generic`.

export type FieldType = 'string' | 'number' | 'boolean' | 'date' | 'string[]' | 'object[]'
export interface Field { name: string; type: FieldType; description?: string; required?: boolean; /** for string: the allowed values */ enum?: string[]; /** for object[]: the item's fields */ items?: Field[] }
export type Strategy = 'fields' | 'sections'
/**
 * The `sections` strategy's contract: what one unit looks like and how duplicates merge, what the
 * document's identity fields are, and how to pick the sections worth reading. All words are the
 * caller's; `{{subject}}` in any instructions is replaced by the request's subject.
 */
export interface SectionsSpec {
  unit: {
    /** The array's key in the output, and how the instructions refer to it ("clauses", "articles", "controls"). */
    name: string
    fields: Field[]
    /** The field that identifies a unit across parallel calls (e.g. "provision"). */
    key: string
    /** 'section-root' folds "Section 5(3A)" into "Section 5"; 'exact' merges only identical keys. */
    keyNormalise?: 'section-root' | 'exact'
    /** A field holding the page reference, used to pick the earliest occurrence as the base. */
    pageField?: string
    /** A text field: a later occurrence's differing text is appended with a page note. */
    textField?: string
    /** A numeric field: merged units take the minimum. */
    confidenceField?: string
    /** Drop units whose field matches the pattern (case-insensitive). */
    skipIf?: { field: string; pattern: string }
  }
  identity?: { instructions: string; fields: Field[]; defaults?: Record<string, unknown> }
  triage?: { instructions: string; /** Sections whose opening matches are always read (regex, case-insensitive). */ alwaysInclude?: string }
}
export interface Profile {
  id: string
  description: string
  /** Plain-language rules: what counts, what to skip, how to fill each field. Appended to the system prompt. */
  instructions: string
  fields?: Field[]
  /** Raw JSON schema for the output object (strict: every property required, no extras). Wins over `fields`. */
  schema?: Record<string, unknown>
  strategy: Strategy
  /** Required when strategy is 'sections'. */
  sections?: SectionsSpec
  builtIn?: boolean
}

// ── Built-in: one. The engine has no opinion about document types; callers describe theirs
// (inline with the request, or as packs in the catalogue — types/ ships a starter set).
const F = (name: string, type: FieldType, description: string, required = false, items?: Field[]): Field => ({ name, type, description, required, items })

export const GENERIC: Profile = {
  id: 'generic', builtIn: true, strategy: 'fields',
  description: 'Any document → title, summary, dates, amounts, parties, references and key points. Send `instructions` (and optionally `fields`) to steer it.',
  instructions: `Read the document and fill the fields faithfully from the text. Leave a field empty rather than guess.`,
  fields: [F('title', 'string', 'Title or subject', true), F('documentType', 'string', 'What kind of document this is'), F('summary', 'string', 'Three-sentence summary', true), F('dates', 'object[]', 'Dates that matter', false, [F('label', 'string', 'What the date is', true), F('date', 'date', 'ISO date', true)]), F('amounts', 'object[]', 'Amounts that matter', false, [F('label', 'string', 'What the amount is', true), F('value', 'number', 'Numeric value', true), F('currency', 'string', 'Currency', false)]), F('parties', 'string[]', 'Organisations and people named'), F('references', 'string[]', 'Reference, file or document numbers'), F('keyPoints', 'string[]', 'The points a reader must not miss')],
}
export const BUILT_IN: Profile[] = [GENERIC]

// ── Schema compilation (strict JSON schema, as structured outputs require) ────
function fieldSchema(f: Field): Record<string, unknown> {
  const desc = f.description ? { description: f.description } : {}
  const nullable = (t: string) => (f.required ? { type: t, ...desc } : { type: [t, 'null'], ...desc })
  switch (f.type) {
    case 'string': return f.enum ? (f.required ? { type: 'string', enum: f.enum, ...desc } : { type: ['string', 'null'], enum: [...f.enum, null], ...desc }) : nullable('string')
    case 'date': return f.required ? { type: 'string', description: `${f.description ?? ''} (ISO 8601 date)`.trim() } : { type: ['string', 'null'], description: `${f.description ?? ''} (ISO 8601 date, or null)`.trim() }
    case 'number': return nullable('number')
    case 'boolean': return nullable('boolean')
    case 'string[]': return { type: 'array', items: { type: 'string' }, ...desc }
    case 'object[]': return { type: 'array', items: compileFields(f.items ?? []), ...desc }
  }
}
export function compileFields(fields: Field[]): Record<string, unknown> {
  return { type: 'object', properties: Object.fromEntries(fields.map((f) => [f.name, fieldSchema(f)])), required: fields.map((f) => f.name), additionalProperties: false }
}
/** Make a caller-supplied JSON schema strict: every property required, no extras, recursively. */
export function strictify(schema: Record<string, unknown>): Record<string, unknown> {
  const s = { ...schema }
  if (s.type === 'object' && s.properties && typeof s.properties === 'object') {
    const props = Object.fromEntries(Object.entries(s.properties as Record<string, Record<string, unknown>>).map(([k, v]) => [k, strictify(v)]))
    return { ...s, properties: props, required: Object.keys(props), additionalProperties: false }
  }
  if (s.type === 'array' && s.items && typeof s.items === 'object') return { ...s, items: strictify(s.items as Record<string, unknown>) }
  return s
}
export function outputSchema(p: Profile): Record<string, unknown> {
  if (p.schema) return strictify(p.schema)
  return compileFields(p.fields ?? [])
}

// ── Registry ──────────────────────────────────────────────────────────────────
export interface InlineProfile { id?: string; description?: string; instructions: string; fields?: Field[]; schema?: Record<string, unknown>; /** 'sections' selects the long-document pipeline (unit · identity · triage below); default 'fields'. */ strategy?: Strategy; unit?: SectionsSpec['unit']; identity?: SectionsSpec['identity']; triage?: SectionsSpec['triage'] }
const validFieldTypes = new Set<FieldType>(['string', 'number', 'boolean', 'date', 'string[]', 'object[]'])
export function validateFields(fields: unknown): Field[] {
  if (!Array.isArray(fields)) throw new Error('fields must be an array')
  return fields.map((f, i) => {
    const x = f as Partial<Field>
    if (!x || typeof x.name !== 'string' || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(x.name)) throw new Error(`fields[${i}].name must be an identifier`)
    if (!x.type || !validFieldTypes.has(x.type)) throw new Error(`fields[${i}].type must be one of ${[...validFieldTypes].join(', ')}`)
    if (x.enum !== undefined && (!Array.isArray(x.enum) || !x.enum.every((e) => typeof e === 'string') || x.type !== 'string')) throw new Error(`fields[${i}].enum must be a list of strings on a string field`)
    return { name: x.name, type: x.type, description: typeof x.description === 'string' ? x.description : undefined, required: Boolean(x.required), enum: x.enum, items: x.type === 'object[]' ? validateFields(x.items ?? []) : undefined }
  })
}

/** A profile from its JSON form (file or request). */
function fromInline(id: string, p: InlineProfile): Profile {
  const strategy: Strategy = p.strategy === 'sections' ? 'sections' : 'fields'
  if (typeof p.instructions !== 'string' || !p.instructions.trim()) throw new Error('instructions are required')
  if (strategy === 'sections') {
    if (!p.unit || typeof p.unit !== 'object') throw new Error('a sections profile needs `unit` { name, key, fields }')
    if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(p.unit.name ?? '')) throw new Error('unit.name must be an identifier')
    const fields = validateFields(p.unit.fields)
    if (!p.unit.key || !fields.some((f) => f.name === p.unit!.key)) throw new Error('unit.key must name one of unit.fields')
    for (const k of ['pageField', 'textField', 'confidenceField'] as const) if (p.unit[k] && !fields.some((f) => f.name === p.unit![k])) throw new Error(`unit.${k} must name one of unit.fields`)
    if (p.unit.skipIf) new RegExp(p.unit.skipIf.pattern, 'i')
    if (p.triage?.alwaysInclude) new RegExp(p.triage.alwaysInclude, 'i')
    const sections: SectionsSpec = {
      unit: { ...p.unit, fields, keyNormalise: p.unit.keyNormalise ?? 'exact' },
      identity: p.identity ? { instructions: String(p.identity.instructions ?? ''), fields: validateFields(p.identity.fields ?? []), defaults: p.identity.defaults } : undefined,
      triage: p.triage ? { instructions: String(p.triage.instructions ?? ''), alwaysInclude: p.triage.alwaysInclude } : undefined,
    }
    return { id, description: p.description ?? '', instructions: p.instructions, strategy, sections }
  }
  const fields = p.fields ? validateFields(p.fields) : undefined
  if (!fields && !p.schema) throw new Error('fields or schema is required')
  return { id, description: p.description ?? '', instructions: p.instructions, fields, schema: p.schema, strategy }
}

/** An inline profile sent with the request. Instructions alone → the generic shape with those instructions; `strategy: 'sections'` → the long-document pipeline. */
export function inlineProfile(p: InlineProfile): Profile {
  if (p.strategy === 'sections') return fromInline(p.id ?? 'inline', p)
  return fromInline(p.id ?? 'inline', { ...p, instructions: p.instructions?.trim() ? p.instructions : GENERIC.instructions, fields: p.fields ?? (p.schema ? undefined : GENERIC.fields) })
}
