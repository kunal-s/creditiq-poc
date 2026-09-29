// End to end: every fixture request goes through POST /v1/process (stub
// provider, replay mode), the answer is validated against
// contracts/ingest-result.schema.json, and compared with the reviewer's
// values in expected.json. Prints the per-TC accuracy summary (C1, C3).
import { after, before, describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { rm } from 'node:fs/promises'
import { join } from 'node:path'
import { Ajv2020 } from 'ajv/dist/2020.js'
import { createApp } from '../src/app.js'
import { ConfigStore } from '../src/config.js'
import type { IngestDocument, IngestResult } from '../src/contract.js'
import { readEnv } from '../src/env.js'
import { createModelClient } from '../src/llm/index.js'
import { terminateOcr } from '../src/read/ocr.js'
import { FIXTURES, formFor, makeDataRoot, REPO, type FileSpec } from './helpers.js'

type Value = string | number | boolean | null
interface Expect { field: string; value: Value; page: number | null; key?: boolean }
interface DocExpect { file: string; page_from: number; page_to: number; types?: string[]; instance_key?: string | null; fields?: Expect[]; scanned?: boolean; grades?: string[]; reasons_any?: string[]; candidates_min?: number }
interface RequestSpec { name: string; files: FileSpec[]; documents: DocExpect[]; same_doc_key?: string[][]; duplicate_pair?: string[]; file_status?: Record<string, string> }
interface TcSpec { tc: string; title: string; requests: RequestSpec[] }

const schema = JSON.parse(readFileSync(join(REPO, 'contracts', 'ingest-result.schema.json'), 'utf8'))
const ajv = new Ajv2020({ allErrors: true, strict: false })
const validate = ajv.compile(schema)

interface Tally { docs: number; typed: number; fields: Record<'digital' | 'scanned', { n: number; ok: number; keyN: number; keyOk: number }> }
const tallies = new Map<string, Tally>()
const tally = (tc: string): Tally => {
  let t = tallies.get(tc)
  if (!t) { t = { docs: 0, typed: 0, fields: { digital: { n: 0, ok: 0, keyN: 0, keyOk: 0 }, scanned: { n: 0, ok: 0, keyN: 0, keyOk: 0 } } }; tallies.set(tc, t) }
  return t
}

const norm = (s: string) => s.replace(/\s+/g, ' ').trim().toLowerCase()
function same(exp: Value, got: unknown): boolean {
  if (exp === null) return got === null || got === undefined
  if (typeof exp === 'number') return typeof got === 'number' && Math.abs(got - exp) < 0.01
  if (typeof exp === 'boolean') return got === exp
  return typeof got === 'string' && norm(got) === norm(exp)
}

let root = ''
let version = ''
let app: ReturnType<typeof createApp>

before(async () => {
  ;({ root, version } = await makeDataRoot())
  const env = { ...readEnv({}), dataRoot: root }
  app = createApp({ env, configs: new ConfigStore(root), model: createModelClient(env) })
})

after(async () => {
  await terminateOcr()
  await rm(root, { recursive: true, force: true })
  const pct = (a: number, b: number) => (b ? `${((100 * a) / b).toFixed(1)}%` : '-')
  const rows = [...tallies.entries()].sort(([a], [b]) => a.localeCompare(b))
  const lines = ['', 'Accuracy by test case (C1 = classification by content; C3 = field values with the right page)', '', '| TC | C1 docs | C3 digital (all) | C3 digital (key) | C3 scanned (all) | C3 scanned (key) |', '|---|---|---|---|---|---|']
  const tot = { docs: 0, typed: 0, d: { n: 0, ok: 0, keyN: 0, keyOk: 0 }, s: { n: 0, ok: 0, keyN: 0, keyOk: 0 } }
  for (const [tc, t] of rows) {
    const d = t.fields.digital
    const s = t.fields.scanned
    lines.push(`| ${tc} | ${t.typed}/${t.docs} ${pct(t.typed, t.docs)} | ${d.ok}/${d.n} ${pct(d.ok, d.n)} | ${d.keyOk}/${d.keyN} ${pct(d.keyOk, d.keyN)} | ${s.ok}/${s.n} ${pct(s.ok, s.n)} | ${s.keyOk}/${s.keyN} ${pct(s.keyOk, s.keyN)} |`)
    tot.docs += t.docs; tot.typed += t.typed
    for (const k of ['n', 'ok', 'keyN', 'keyOk'] as const) { tot.d[k] += d[k]; tot.s[k] += s[k] }
  }
  lines.push(`| all | ${tot.typed}/${tot.docs} ${pct(tot.typed, tot.docs)} | ${tot.d.ok}/${tot.d.n} ${pct(tot.d.ok, tot.d.n)} | ${tot.d.keyOk}/${tot.d.keyN} ${pct(tot.d.keyOk, tot.d.keyN)} | ${tot.s.ok}/${tot.s.n} ${pct(tot.s.ok, tot.s.n)} | ${tot.s.keyOk}/${tot.s.keyN} ${pct(tot.s.keyOk, tot.s.keyN)} |`, '')
  console.log(lines.join('\n'))
})

const validateRequest = ajv.compile(JSON.parse(readFileSync(join(REPO, 'contracts', 'ingest-request.schema.json'), 'utf8')))

async function post(tcDir: string, files: FileSpec[], caseRef = 'BBG-2025-000001'): Promise<{ status: number; body: IngestResult }> {
  const form = await formFor(tcDir, caseRef, version, files)
  assert.ok(validateRequest(JSON.parse(String(form.get('request')))), `request schema: ${ajv.errorsText(validateRequest.errors)}`)
  const res = await app.request('/v1/process', { method: 'POST', body: form })
  return { status: res.status, body: (await res.json()) as IngestResult }
}

const tcs = readdirSync(FIXTURES).filter((d) => /^TC-\d+$/.test(d)).sort()
const firstKeys = new Map<string, string>()

for (const tc of tcs) {
  const spec = JSON.parse(readFileSync(join(FIXTURES, tc, 'expected.json'), 'utf8')) as TcSpec
  describe(`${tc}: ${spec.title}`, () => {
    for (const r of spec.requests) {
      test(r.name, async () => {
        const { status, body } = await post(join(FIXTURES, tc), r.files)
        assert.equal(status, 200, JSON.stringify(body).slice(0, 300))
        // The contract, exactly.
        const ok = validate(body)
        assert.ok(ok, `schema: ${ajv.errorsText(validate.errors)}`)
        assert.equal(body.config_version, version)
        assert.equal(body.model_provider, 'stub')
        assert.equal(body.files.length, r.files.length)
        const idOf = new Map(r.files.map((f, i) => [f.file, `f${i + 1}`]))
        for (const [file, st] of Object.entries(r.file_status ?? {})) assert.equal(body.files.find((o) => o.file_id === idOf.get(file))?.status, st, `${file} status`)

        // Evidence: every value carries its page and the text as printed (F-15.1, F-15.4).
        for (const d of body.documents) {
          for (const f of d.fields) {
            if (f.value === null) { assert.equal(f.page, null, `${f.field}: a missing value has no page`); assert.ok(f.missing_reason, `${f.field}: missing without reason`); continue }
            assert.ok(f.page !== null && f.page >= d.page_from && f.page <= d.page_to, `${f.field}: page ${f.page} outside ${d.page_from}-${d.page_to}`)
            if (f.raw === null) assert.equal(f.confidence_components['repair.running_balance'], 1, `${f.field}: no raw text without a recorded repair`)
          }
        }

        const t = tally(tc)
        for (const e of r.documents) {
          const d: IngestDocument | undefined = body.documents.find((x) => x.file_id === idOf.get(e.file) && x.page_from === e.page_from)
          assert.ok(d, `${e.file}: no document starting at page ${e.page_from}; got ${body.documents.filter((x) => x.file_id === idOf.get(e.file)).map((x) => `${x.page_from}-${x.page_to}`).join(', ')}`)
          assert.equal(d.page_to, e.page_to, `${e.file} p${e.page_from}: page range`)
          if (e.types) {
            t.docs++
            const typedOk = JSON.stringify([...d.classification.types].sort()) === JSON.stringify([...e.types].sort())
            if (typedOk) t.typed++
            assert.deepEqual([...d.classification.types].sort(), [...e.types].sort(), `${e.file} p${e.page_from}: types (signals ${d.classification.signals.slice(0, 6).join('; ')})`)
            if (!e.types.length) {
              assert.equal(d.classification.exit_tier, 'none')
              assert.equal(d.fields.length, 0, 'an unclassified document is not extracted')
            }
          }
          if (e.candidates_min) assert.ok(d.classification.candidates.length >= e.candidates_min, 'top candidates')
          if (e.instance_key !== undefined && e.instance_key !== null) assert.equal(d.instance_key, e.instance_key, `${e.file}: instance key`)
          if (e.grades) assert.ok(e.grades.includes(d.pages[0].grade), `${e.file}: grade ${d.pages[0].grade} (${d.pages[0].reasons.join(',')}) not in ${e.grades.join('/')}`)
          for (const reason of e.reasons_any ?? []) assert.ok(d.pages.some((p) => p.reasons.includes(reason)), `${e.file}: reason ${reason} missing (${d.pages.map((p) => p.reasons.join(',')).join(' | ')})`)
          const bucket = t.fields[e.scanned ? 'scanned' : 'digital']
          for (const x of e.fields ?? []) {
            const got = d.fields.find((f) => f.field === x.field)
            const good = same(x.value, got?.value ?? null) && (x.value === null || got?.page === x.page)
            bucket.n++
            if (good) bucket.ok++
            else if (process.env.SHOW_MISSES) console.log(`MISS ${tc} ${e.file} ${x.field}: expected ${JSON.stringify(x.value)} p${x.page}, got ${JSON.stringify(got?.value)} raw=${JSON.stringify(got?.raw)} p${got?.page} ${got?.missing_reason ?? ''}`)
            if (x.key) { bucket.keyN++; if (good) bucket.keyOk++ }
          }
        }
        for (const group of r.same_doc_key ?? []) {
          const keys = group.map((file) => body.documents.find((d) => d.file_id === idOf.get(file))?.doc_key)
          assert.ok(keys[0] && keys.every((k) => k === keys[0]), `same doc_key for ${group.join(', ')}`)
        }
        if (r.duplicate_pair) {
          const [a, b] = r.duplicate_pair.map((file) => body.documents.find((d) => d.file_id === idOf.get(file))!)
          assert.ok(a.duplicate_of_key === b.doc_key || b.duplicate_of_key === a.doc_key, 'one copy points to the other')
          assert.ok(!(a.duplicate_of_key && b.duplicate_of_key), 'only one copy is the duplicate')
        }
        // Stable keys across requests (order independence, TC-03).
        for (const d of body.documents) {
          const k = `${r.files[Number(d.file_id.slice(1)) - 1].file}:${tc}:${d.page_from}`
          if (firstKeys.has(k)) assert.equal(firstKeys.get(k), d.doc_key)
          else firstKeys.set(k, d.doc_key)
        }
      })
    }
  })
}

test('TC-03: the same bytes give the same doc_key in a later request', async () => {
  const a = await post(join(FIXTURES, 'TC-03'), [{ file: 'udyam.pdf', original_name: 'a.pdf', content_type: 'application/pdf' }])
  const b = await post(join(FIXTURES, 'TC-03'), [{ file: 'udyam_copy.pdf', original_name: 'b.pdf', content_type: 'application/pdf' }], 'BBG-2025-000002')
  assert.equal(a.body.documents[0].doc_key, b.body.documents[0].doc_key)
})

test('C3 targets: at least 90% on digital and 80% on scanned documents (FRD F-15.7)', () => {
  let d = { n: 0, ok: 0 }
  let s = { n: 0, ok: 0 }
  for (const t of tallies.values()) {
    d = { n: d.n + t.fields.digital.n, ok: d.ok + t.fields.digital.ok }
    s = { n: s.n + t.fields.scanned.n, ok: s.ok + t.fields.scanned.ok }
  }
  assert.ok(d.n > 0 && s.n > 0)
  assert.ok(d.ok / d.n >= 0.9, `digital C3 ${(d.ok / d.n).toFixed(3)}`)
  assert.ok(s.ok / s.n >= 0.8, `scanned C3 ${(s.ok / s.n).toFixed(3)}`)
})
