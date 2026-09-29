// POST /v1/process, end to end, for one request: read, grade, split,
// classify, extract, validate, per file (FRD F-07 to F-09, F-11, F-15).
import { createHash } from 'node:crypto'
import { classifyDocument, classifyPage, scoreText, type PageClass } from './classify.js'
import type { ConfigStore, LoadedConfig } from './config.js'
import type { Classification, ExtractedField, IngestDocument, IngestFile, IngestFileOutcome, IngestRequest, IngestResult, PageInfo, Stage, StageTiming, TypeAssignment } from './contract.js'
import { defectsOf, docKey, identityOf, instanceKeyOf, markDuplicates, shingles } from './documents.js'
import { extractDocument } from './extract/extract.js'
import type { ModelClient } from './llm/index.js'
import { readFile } from './read/index.js'
import type { FileRead, PageRead } from './read/types.js'
import { documentGrade, gradePage, unreadable } from './quality.js'
import { splitPages, type Segment } from './split.js'
import { ENGINE_VERSION } from './version.js'

export class RequestError extends Error {
  constructor(public status: 400 | 413, message: string) { super(message) }
}

export function parseRequest(json: unknown): IngestRequest {
  const r = json as Partial<IngestRequest>
  if (!r || typeof r !== 'object') throw new RequestError(400, 'request must be a JSON object')
  if (typeof r.case_ref !== 'string' || !r.case_ref) throw new RequestError(400, 'case_ref is required')
  if (typeof r.config_version !== 'string' || !r.config_version) throw new RequestError(400, 'config_version is required')
  if (!Array.isArray(r.files)) throw new RequestError(400, 'files must be a list')
  const ids = new Set<string>()
  for (const f of r.files as Partial<IngestFile>[]) {
    if (!f || typeof f.file_id !== 'string' || !f.file_id) throw new RequestError(400, 'every file needs a file_id')
    if (ids.has(f.file_id)) throw new RequestError(400, `file_id ${f.file_id} is repeated`)
    ids.add(f.file_id)
    if (typeof f.sha256 !== 'string' || typeof f.content_type !== 'string' || typeof f.original_name !== 'string') throw new RequestError(400, `file ${f.file_id}: sha256, original_name and content_type are required`)
  }
  const assignments = r.assignments ?? []
  if (!Array.isArray(assignments)) throw new RequestError(400, 'assignments must be a list')
  for (const a of assignments as Partial<TypeAssignment>[]) {
    if (!a || typeof a.file_id !== 'string' || !ids.has(a.file_id)) throw new RequestError(400, 'every assignment needs the file_id of a file in this request')
    if (!Number.isInteger(a.page_from) || !Number.isInteger(a.page_to) || a.page_from! < 1 || a.page_to! < a.page_from!) throw new RequestError(400, `assignment for ${a.file_id}: page_from and page_to must be pages, page_from <= page_to`)
    if (typeof a.type_id !== 'string' || !a.type_id) throw new RequestError(400, `assignment for ${a.file_id}: type_id is required`)
  }
  return { case_ref: r.case_ref, config_version: r.config_version, files: r.files as IngestFile[], assignments: assignments as TypeAssignment[] }
}

const sha256 = (b: Uint8Array) => createHash('sha256').update(b).digest('hex')

export interface Deps { configs: ConfigStore; model: ModelClient }

export async function processRequest(req: IngestRequest, payloads: Map<string, Uint8Array>, deps: Deps): Promise<IngestResult> {
  const cfg = await deps.configs.load(req.config_version)
  for (const a of req.assignments) {
    if (!cfg.typeById.has(a.type_id)) throw new RequestError(400, `assignment for ${a.file_id}: type ${a.type_id} is not in configuration ${cfg.version}`)
  }
  const timings: StageTiming[] = []
  const outcomes: IngestFileOutcome[] = []
  const documents: IngestDocument[] = []
  const forDup: { doc: IngestDocument; sh: Set<string> }[] = []
  const reads = new Map<string, Promise<FileRead>>()

  for (const f of req.files) {
    const bytes = payloads.get(f.file_id)
    if (!bytes) { outcomes.push({ file_id: f.file_id, status: 'rejected', reason: 'no file part was sent for this file_id' }); continue }
    const actual = sha256(bytes)
    if (actual !== f.sha256.toLowerCase()) { outcomes.push({ file_id: f.file_id, status: 'rejected', reason: 'the bytes do not match the declared sha256' }); continue }
    const time = async <T>(stage: Stage, fn: () => Promise<T> | T): Promise<T> => {
      const t0 = performance.now()
      try { return await fn() } finally { timings.push({ stage, file_id: f.file_id, ms: Math.round(performance.now() - t0) }) }
    }
    // The same bytes twice in one request are read once (content-addressed).
    let read = reads.get(actual)
    if (!read) { read = readFile(bytes, f.content_type, cfg.quality.min_chars_text_layer); reads.set(actual, read) }
    const fr = await time('read', () => read!)
    const result = await processFile(f, actual, fr, cfg, deps.model, time, req.assignments.filter((a) => a.file_id === f.file_id))
    outcomes.push(result.outcome)
    documents.push(...result.documents.map((d) => d.doc))
    forDup.push(...result.documents)
  }
  const t0 = performance.now()
  markDuplicates(forDup)
  if (req.files.length) timings.push({ stage: 'validate', file_id: req.files[0].file_id, ms: Math.round(performance.now() - t0) })
  return { case_ref: req.case_ref, config_version: cfg.version, engine_version: ENGINE_VERSION, model_provider: deps.model.name, files: outcomes, documents, timings }
}

type Timer = <T>(stage: Stage, fn: () => Promise<T> | T) => Promise<T>

interface Planned extends Segment { assigned?: string }

/**
 * Logical documents for a file: each person-assigned page range is one
 * document as assigned (F-09.5); the pages in between are split by content.
 * Overlapping or out-of-range assignments are ignored and reported.
 */
function plan(pages: PageRead[], classes: PageClass[], cfg: LoadedConfig, assignments: TypeAssignment[], notes: string[]): Planned[] {
  const last = pages[pages.length - 1].n
  const taken: TypeAssignment[] = []
  for (const a of [...assignments].sort((x, y) => x.page_from - y.page_from)) {
    if (a.page_to > last) { notes.push(`assignment ${a.page_from}-${a.page_to} is outside the file's ${last} page(s) and was not applied`); continue }
    if (taken.some((t) => a.page_from <= t.page_to && a.page_to >= t.page_from)) { notes.push(`assignment ${a.page_from}-${a.page_to} overlaps another and was not applied`); continue }
    taken.push(a)
  }
  const out: Planned[] = []
  let i = 0
  const runSplit = (to: number) => {
    const idx = pages.map((p, k) => k).filter((k) => k >= i && pages[k].n < to)
    if (idx.length) out.push(...splitPages(idx.map((k) => pages[k]), idx.map((k) => classes[k]), cfg))
    i = idx.length ? idx[idx.length - 1] + 1 : i
  }
  for (const a of taken) {
    runSplit(a.page_from)
    const idx = pages.map((p, k) => k).filter((k) => pages[k].n >= a.page_from && pages[k].n <= a.page_to)
    out.push({ pages: idx.map((k) => pages[k]), classes: idx.map((k) => classes[k]), uncertain: false, assigned: a.type_id })
    i = idx[idx.length - 1] + 1
  }
  runSplit(Number.POSITIVE_INFINITY)
  return out
}

/** Exit tier "person": the assigned type, with the content's own ranking kept as candidates. */
function assignedClassification(typeId: string, pages: PageRead[], cfg: LoadedConfig): Classification {
  const scores = scoreText(pages.map((p) => p.text).join('\n'), cfg)
  const candidates = [{ type_id: typeId, confidence: 1 }, ...scores.filter((s) => s.type.id !== typeId).slice(0, 2).map((s) => ({ type_id: s.type.id, confidence: s.score }))]
  return { types: [typeId], confidence: 1, exit_tier: 'person', signals: [`person: assigned ${typeId}`], candidates }
}

async function processFile(f: IngestFile, sha: string, fr: FileRead, cfg: LoadedConfig, model: ModelClient, time: Timer, assignments: TypeAssignment[] = []): Promise<{ outcome: IngestFileOutcome; documents: { doc: IngestDocument; sh: Set<string> }[] }> {
  if (fr.error) {
    const page = unreadable(fr.error.code)
    if (fr.error.code === 'unsupported') return { outcome: { file_id: f.file_id, status: 'rejected', reason: fr.error.detail }, documents: [] }
    const doc: IngestDocument = {
      doc_key: docKey(sha, 1, 1), file_id: f.file_id, page_from: 1, page_to: 1, pages: [page],
      classification: { types: [], confidence: 0, exit_tier: 'none', signals: [], candidates: [] },
      instance_key: null, fields: [], identity: {}, defects: [], duplicate_of_key: null, split_uncertain: false,
    }
    return { outcome: { file_id: f.file_id, status: 'exception', reason: `${page.reasons[0]}: ${fr.error.detail}` }, documents: [{ doc, sh: new Set() }] }
  }
  if (!fr.pages.length) return { outcome: { file_id: f.file_id, status: 'exception', reason: 'blank: the file has no pages' }, documents: [] }

  const grades = await time('grade', () => new Map<number, PageInfo>(fr.pages.map((p) => [p.n, gradePage(p, cfg.quality)])))
  const classes = await time('split', () => fr.pages.map((p) => classifyPage(p, cfg)))
  const notes: string[] = []
  const segments = await time('split', () => plan(fr.pages, classes, cfg, assignments, notes))

  let misses = 0
  let errors = 0
  const docs: { doc: IngestDocument; sh: Set<string> }[] = []
  for (const seg of segments) {
    const pages: PageRead[] = seg.pages
    const infos = pages.map((p) => grades.get(p.n)!)
    const grade = documentGrade(infos)
    const cls = seg.assigned
      ? { classification: assignedClassification(seg.assigned, pages, cfg), modelMiss: false, modelError: false }
      : await time('classify', () => classifyDocument(pages, seg.classes as PageClass[], cfg, model))
    if (cls.modelMiss) misses++
    if (cls.modelError) errors++
    const c = cls.classification
    const fields: ExtractedField[] = []
    for (const typeId of c.types) {
      const t = cfg.typeById.get(typeId)
      const dict = t?.dictionary ? cfg.dictionaries.get(t.dictionary) : undefined
      if (!t || !dict) continue
      const out = await time('extract', () => extractDocument({
        pages, grades, typeId, typeName: t.name, dict, classification: c.confidence, config: cfg,
        // Nothing legible: no model call (manual entry resolves grade U, F-07.5).
        model: grade === 'U' ? null : model,
      }))
      misses += out.modelMisses
      errors += out.modelErrors
      for (const x of out.fields) {
        const i = fields.findIndex((y) => y.field === x.field)
        if (i < 0) fields.push(x)
        else if (fields[i].value === null && x.value !== null) fields[i] = x
      }
    }
    const primary = cfg.typeById.get(c.types[0] ?? '')
    const doc = await time('validate', (): IngestDocument => ({
      doc_key: docKey(sha, pages[0].n, pages[pages.length - 1].n),
      file_id: f.file_id,
      page_from: pages[0].n,
      page_to: pages[pages.length - 1].n,
      pages: infos,
      classification: c,
      instance_key: instanceKeyOf(primary, fields),
      fields,
      identity: identityOf(fields),
      defects: defectsOf(pages, primary, fields),
      duplicate_of_key: null,
      split_uncertain: seg.uncertain,
    }))
    docs.push({ doc, sh: shingles(pages) })
  }
  const exceptions = docs.filter((d) => documentGrade(d.doc.pages) === 'U')
  if (exceptions.length) notes.push(`${[...new Set(exceptions.flatMap((d) => d.doc.pages.flatMap((p) => p.reasons)))].join(', ') || 'unreadable'}: ${exceptions.length} of ${docs.length} document(s) unreadable`)
  if (misses) notes.push(`${misses} model call(s) had no recording (replay); affected results are unclassified or missing`)
  if (errors) notes.push(`${errors} model call(s) failed`)
  return { outcome: { file_id: f.file_id, status: exceptions.length ? 'exception' : 'processed', reason: notes.length ? notes.join('; ') : null }, documents: docs }
}
