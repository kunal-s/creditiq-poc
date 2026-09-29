// Unit and API tests that need no OCR: identifiers, value parsers, the
// running-balance repair, record/replay and the native providers (from
// recorded fixtures only), config versions, auth, health and assignments.
import { after, before, describe, test } from 'node:test'
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, readFileSync } from 'node:fs'
import { mkdir, mkdtemp, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { Ajv2020 } from 'ajv/dist/2020.js'
import { createApp, keyMatches } from '../src/app.js'
import { ConfigStore } from '../src/config.js'
import type { IngestResult } from '../src/contract.js'
import { readEnv } from '../src/env.js'
import { checkBalances, type Txn } from '../src/extract/bank.js'
import { checkIdentifier, findIdentifiers, gstinCheckDigit } from '../src/extract/identifiers.js'
import { findDates, findMoney, parseMoney, parsePeriod } from '../src/extract/values.js'
import { anthropicProvider, closeSchema } from '../src/llm/anthropic.js'
import { geminiProvider, toGeminiSchema } from '../src/llm/gemini.js'
import { createModelClient, ModelClient, ModelError } from '../src/llm/index.js'
import { assertNoSampling, canonicalJson, type ModelRequest } from '../src/llm/provider.js'
import { recordingKey } from '../src/llm/recorder.js'
import { stubProvider } from '../src/llm/stub.js'
import { buildLines } from '../src/read/layout.js'
import { terminateOcr } from '../src/read/ocr.js'
import { FIXTURES, formFor, makeDataRoot, REPO } from './helpers.js'

describe('identifiers (ported from engine/identifiers.py)', () => {
  test('GSTIN check digit matches the Python implementation', () => {
    const samples = ['27AAGCE4821K1Z', '29ABCDE1234F2Z', '07PQRST9876L1Z', '33AAACZ0001A9Z', '24BBBPB4321C1Z']
    const py = join(REPO, '.venv', 'bin', 'python')
    const ours = samples.map(gstinCheckDigit)
    if (existsSync(py)) {
      const r = spawnSync(py, ['-c', `from engine.identifiers import gstin_check_digit as g\nprint(" ".join(g(s) for s in ${JSON.stringify(samples)}))`], { cwd: REPO, encoding: 'utf8' })
      assert.equal(r.status, 0, r.stderr)
      assert.deepEqual(ours, r.stdout.trim().split(' '))
    }
    for (const [i, s] of samples.entries()) {
      const g = s + ours[i]
      assert.deepEqual(checkIdentifier('gstin', g), { format: true, checksum: true })
      const wrong = g.slice(0, 14) + (g[14] === 'A' ? 'B' : 'A')
      assert.equal(checkIdentifier('gstin', wrong).checksum, false)
    }
  })
  test('formats: PAN, CIN, Udyam, IFSC', () => {
    assert.equal(checkIdentifier('pan', 'AAGCE4821K').format, true)
    assert.equal(checkIdentifier('pan', 'AAGXE4821K').format, false)
    assert.equal(checkIdentifier('cin', 'U28990MH2016PTC281734').format, true)
    assert.equal(checkIdentifier('udyam', 'UDYAM-MH-26-0048213').format, true)
    assert.equal(checkIdentifier('ifsc', 'BKYL0004521').format, true)
    assert.equal(checkIdentifier('ifsc', 'BKYL1004521').format, false)
    assert.deepEqual(findIdentifiers('pan', 'PAN: AAGCE4821K and ABKPV7310R').map((x) => x.value), ['AAGCE4821K', 'ABKPV7310R'])
  })
})

describe('value parsers', () => {
  test('money: Indian grouping, brackets, Dr/Cr', () => {
    assert.equal(parseMoney('12,34,567.89'), 1234567.89)
    assert.equal(parseMoney('1,234,567'), 1234567)
    assert.equal(parseMoney('(45,000.00)'), -45000)
    assert.equal(parseMoney('Rs. 5,000'), 5000)
    assert.equal(parseMoney('1,20,000.00 Dr'), -120000)
    assert.equal(parseMoney('12,34'), null)
    assert.equal(parseMoney('01/04/2025'), null)
    assert.deepEqual(findMoney('Revenue   12   18,46,25,400   16,12,80,300').map((m) => m.value), [12, 184625400, 161280300])
  })
  test('dates and periods, day first', () => {
    assert.deepEqual(findDates('From 01/04/2025 To 30/06/2025').map((d) => d.value), ['2025-04-01', '2025-06-30'])
    assert.equal(findDates('as at 31 March 2025')[0].value, '2025-03-31')
    assert.equal(findDates('31/02/2025').length, 0)
    assert.equal(parsePeriod('April', '2025-26'), '2025-04')
    assert.equal(parsePeriod('January', '2025-26'), '2026-01')
    assert.equal(parsePeriod('Apr-2025'), '2025-04')
    assert.equal(parsePeriod('2025-26'), '2025-26')
  })
  test('lines keep table columns apart', () => {
    const w = (text: string, x0: number, x1: number) => ({ text, x0, x1, y0: 0.1, y1: 0.12 })
    const [line] = buildLines([w('Balance', 0.1, 0.18), w('1,20,000.00', 0.6, 0.7), w('Closing', 0.02, 0.09)])
    assert.equal(line.text, 'Closing Balance   1,20,000.00')
  })
})

describe('bank running balance (F-15.3)', () => {
  const cell = (v: number | null, raw?: string) => ({ raw: v === null ? null : raw ?? String(v), printed: v, value: v, words: [] })
  const row = (dr: number | null, cr: number | null, bal: number | null): Txn => ({
    page: {} as Txn['page'], date: { raw: '', value: '', words: [] }, narration: { raw: '', words: [] }, ref: null,
    debit: cell(dr), credit: cell(cr), balance: cell(bal), check: 'unchecked', repaired: null,
  })
  test('a misread balance is repaired from its neighbours', () => {
    const t = [row(null, 100, 1100), row(50, null, 1080), row(null, 20, 1070)] // 1080 should be 1050
    checkBalances(t, 1000)
    assert.deepEqual(t.map((x) => x.check), ['ok', 'repaired', 'ok'])
    assert.equal(t[1].repaired, 'balance')
    assert.equal(t[1].balance.value, 1050)
    assert.equal(t[1].balance.raw, '1080', 'the printed text is kept')
  })
  test('a misread amount is repaired when the balances hold', () => {
    const t = [row(null, 100, 1100), row(80, null, 1050), row(null, 20, 1070)] // debit should be 50
    checkBalances(t, 1000)
    assert.equal(t[1].repaired, 'debit')
    assert.equal(t[1].debit.value, 50)
  })
  test('two errors in a row are not guessed', () => {
    const t = [row(null, 100, 1100), row(80, null, 1090), row(null, 20, 1300)]
    checkBalances(t, 1000)
    assert.ok(t.some((x) => x.check === 'failed'))
  })
})

describe('model layer: record and replay (AD-5)', () => {
  let root = ''
  before(async () => { root = await mkdtemp(join(tmpdir(), 'ciq-llm-')) })
  after(async () => { await rm(root, { recursive: true, force: true }) })
  const req: ModelRequest = { task: 'extract', system: 's', user: 'u', schema: { type: 'object', properties: { a: { type: ['string', 'null'] } } } }

  test('canonical JSON sorts keys at every level', () => {
    assert.equal(canonicalJson({ b: 1, a: { d: [1, { f: 2, e: 3 }], c: null } }), '{"a":{"c":null,"d":[1,{"e":3,"f":2}]},"b":1}')
  })
  test('record, then replay the same answer; a miss is an explicit error', async () => {
    const rec = new ModelClient(stubProvider(() => ({ a: 'x' })), 'record', root)
    assert.deepEqual(await rec.call(req), { a: 'x' })
    const files = await readdir(join(root, 'recordings', 'stub'))
    assert.equal(files.length, 1)
    assert.equal(files[0], `${rec.keyFor(req)}.json`)
    const replay = new ModelClient(stubProvider(), 'replay', root)
    assert.deepEqual(await replay.call(req), { a: 'x' })
    await assert.rejects(replay.call({ ...req, user: 'other' }), (e: unknown) => e instanceof ModelError && e.code === 'replay_miss')
  })
  test('a refusal is never recorded', async () => {
    const dir = await mkdtemp(join(tmpdir(), 'ciq-llm-ref-'))
    const p = stubProvider()
    const refusing = { ...p, build: (r: ModelRequest) => ({ ...p.build(r), send: async () => ({ refusal: 'no' }) }) }
    const c = new ModelClient(refusing, 'record', dir)
    await assert.rejects(c.call(req), (e: unknown) => e instanceof ModelError && e.code === 'refusal')
    assert.equal(existsSync(join(dir, 'recordings')), false)
    await rm(dir, { recursive: true, force: true })
  })
  test('no sampling parameter can be sent (principle 6)', () => {
    assert.throws(() => assertNoSampling({ model: 'x', temperature: 0 }))
    assert.throws(() => assertNoSampling({ generationConfig: { topP: 1 } }))
    for (const p of [anthropicProvider({ apiKey: '', model: 'm', baseUrl: 'http://x' }), geminiProvider({ apiKey: '', model: 'm', baseUrl: 'http://x' })]) {
      const body = p.build(req).body
      assert.doesNotThrow(() => assertNoSampling(body))
      assert.ok(!JSON.stringify(body).includes('temperature'))
    }
  })
  test('stub has no live model', async () => {
    const c = new ModelClient(stubProvider(), 'live', root)
    await assert.rejects(c.call(req), (e: unknown) => e instanceof ModelError && e.code === 'no_live_model')
  })
})

describe('native providers, from recorded responses only (P3)', () => {
  const req: ModelRequest = { task: 'classify', system: 'sys', user: 'doc', schema: { type: 'object', properties: { types: { type: 'array', items: { type: 'string' } }, note: { type: ['string', 'null'] } } } }

  test('anthropic: native Messages body, structured output, replayed answer, refusal', async () => {
    const p = anthropicProvider({ apiKey: '', model: 'claude-opus-5-5', baseUrl: 'https://api.anthropic.com' })
    const call = p.build(req)
    const body = call.body as Record<string, unknown>
    assert.equal(body.model, 'claude-opus-5-5')
    assert.deepEqual(body.messages, [{ role: 'user', content: 'doc' }])
    const schema = (body.output_config as { format: { type: string; schema: Record<string, unknown> } }).format
    assert.equal(schema.type, 'json_schema')
    assert.equal(schema.schema.additionalProperties, false)
    assert.deepEqual(schema.schema.required, ['types', 'note'])
    assert.equal('tool_choice' in body, false)
    // Replay a recorded response through the client, no network.
    const root = await mkdtemp(join(tmpdir(), 'ciq-anth-'))
    const key = recordingKey('anthropic', 'claude-opus-5-5', body)
    await mkdir(join(root, 'recordings', 'anthropic'), { recursive: true })
    const response = JSON.parse(readFileSync(join(FIXTURES, 'providers', 'anthropic-response.json'), 'utf8'))
    await writeFile(join(root, 'recordings', 'anthropic', `${key}.json`), JSON.stringify({ key, provider: 'anthropic', model: 'claude-opus-5-5', task: 'classify', request: body, response }))
    const c = new ModelClient(p, 'replay', root)
    assert.deepEqual(await c.call(req), { types: ['gstr_3b'], note: null })
    assert.throws(() => call.parse({ stop_reason: 'refusal', content: [] }), (e: unknown) => e instanceof ModelError && e.code === 'refusal')
    await assert.rejects(p.build(req).send(body), (e: unknown) => e instanceof ModelError && e.code === 'no_live_model')
    await rm(root, { recursive: true, force: true })
  })

  test('gemini: native generateContent body, nullable schema, replayed answer, safety block', async () => {
    assert.deepEqual(toGeminiSchema({ type: 'object', additionalProperties: false, properties: { a: { type: ['string', 'null'] }, b: { type: 'array', items: { type: 'integer' } } } }), {
      type: 'OBJECT', properties: { a: { type: 'STRING', nullable: true }, b: { type: 'ARRAY', items: { type: 'INTEGER' } } },
    })
    const p = geminiProvider({ apiKey: '', model: 'gemini-2.5-pro', baseUrl: 'https://generativelanguage.googleapis.com' })
    const call = p.build(req)
    const body = call.body as { generationConfig: { responseMimeType: string } }
    assert.equal(body.generationConfig.responseMimeType, 'application/json')
    const response = JSON.parse(readFileSync(join(FIXTURES, 'providers', 'gemini-response.json'), 'utf8'))
    assert.deepEqual(call.parse(response), { types: ['bank_statement'], note: 'statement of account' })
    assert.throws(() => call.parse({ candidates: [{ finishReason: 'SAFETY', content: { parts: [] } }] }), (e: unknown) => e instanceof ModelError && e.code === 'refusal')
    assert.throws(() => call.parse({ promptFeedback: { blockReason: 'OTHER' } }), (e: unknown) => e instanceof ModelError && e.code === 'refusal')
  })

  test('closeSchema closes nested objects', () => {
    const s = closeSchema({ type: 'object', properties: { f: { type: 'array', items: { type: 'object', properties: { x: { type: 'string' } } } } } })
    const inner = ((s.properties as Record<string, { items: Record<string, unknown> }>).f).items
    assert.equal(inner.additionalProperties, false)
    assert.deepEqual(inner.required, ['x'])
  })
})

describe('HTTP surface', () => {
  let root = ''
  let version = ''
  before(async () => { ({ root, version } = await makeDataRoot()) })
  after(async () => { await terminateOcr(); await rm(root, { recursive: true, force: true }) })
  const appWith = (over: Partial<ReturnType<typeof readEnv>> = {}) => {
    const env = { ...readEnv({}), dataRoot: root, ...over }
    return createApp({ env, configs: new ConfigStore(root), model: createModelClient(env) })
  }
  const requestSchema = JSON.parse(readFileSync(join(REPO, 'contracts', 'ingest-request.schema.json'), 'utf8'))
  const ajv = new Ajv2020({ strict: false })
  const validRequest = ajv.compile(requestSchema)

  test('health: version and provider, no base URLs', async () => {
    const res = await appWith().request('/v1/health')
    const body = await res.json() as Record<string, unknown>
    assert.equal(res.status, 200)
    assert.equal(body.model_provider, 'stub')
    assert.ok(!/https?:\/\//.test(JSON.stringify(body)))
  })
  test('API key: constant-time compare, required when set', async () => {
    assert.equal(keyMatches('abc', 'abc'), true)
    assert.equal(keyMatches('abd', 'abc'), false)
    assert.equal(keyMatches('', ''), false, 'an empty key never matches')
    const app = appWith({ apiKey: 'k-123' })
    assert.equal((await app.request('/v1/health')).status, 401)
    assert.equal((await app.request('/v1/health', { headers: { 'x-api-key': 'k-12' } })).status, 401)
    assert.equal((await app.request('/v1/health', { headers: { 'x-api-key': 'k-123' } })).status, 200)
    assert.equal((await app.request('/v1/health', { headers: { authorization: 'Bearer k-123' } })).status, 200)
  })
  test('without a key only loopback callers are served', async () => {
    const app = appWith()
    const from = (addr: string) => app.request('/v1/health', {}, { incoming: { socket: { remoteAddress: addr } } })
    assert.equal((await from('127.0.0.1')).status, 200)
    assert.equal((await from('::1')).status, 200)
    assert.equal((await from('10.1.2.3')).status, 401)
  })
  test('an unknown or malformed config version is refused', async () => {
    const app = appWith()
    const files = [{ file: 'utility_bill.pdf', original_name: 'x.pdf', content_type: 'application/pdf' }]
    const unknown = await app.request('/v1/process', { method: 'POST', body: await formFor(join(FIXTURES, 'TC-09'), 'C1', 'f'.repeat(64), files) })
    assert.equal(unknown.status, 409)
    const bad = await app.request('/v1/process', { method: 'POST', body: await formFor(join(FIXTURES, 'TC-09'), 'C1', '../versions', files) })
    assert.equal(bad.status, 400)
  })
  test('a part whose bytes do not match its sha256 is rejected', async () => {
    const form = await formFor(join(FIXTURES, 'TC-09'), 'C1', version, [{ file: 'utility_bill.pdf', original_name: 'x.pdf', content_type: 'application/pdf' }])
    form.set('f1', new Blob([new Uint8Array([1, 2, 3])]), 'f1')
    const body = await (await appWith().request('/v1/process', { method: 'POST', body: form })).json() as IngestResult
    assert.equal(body.files[0].status, 'rejected')
    assert.equal(body.documents.length, 0)
  })

  const withAssignments = async (tc: string, file: string, assignments: unknown[]) => {
    const form = await formFor(join(FIXTURES, tc), 'C1', version, [{ file, original_name: 'x.pdf', content_type: 'application/pdf' }])
    const req = JSON.parse(String(form.get('request')))
    req.assignments = assignments
    assert.ok(validRequest(req), 'request matches contracts/ingest-request.schema.json')
    form.set('request', JSON.stringify(req))
    return appWith().request('/v1/process', { method: 'POST', body: form })
  }
  test('assignments: a person-assigned range skips classification (exit tier person) and is extracted', async () => {
    const res = await withAssignments('TC-04', 'merged_bundle.pdf', [{ file_id: 'f1', page_from: 2, page_to: 3, type_id: 'bank_statement' }])
    const body = await res.json() as IngestResult
    assert.equal(res.status, 200)
    assert.deepEqual(body.documents.map((d) => [d.page_from, d.page_to]), [[1, 1], [2, 3], [4, 4]])
    const d = body.documents[1]
    assert.equal(d.classification.exit_tier, 'person')
    assert.deepEqual(d.classification.types, ['bank_statement'])
    assert.equal(d.classification.confidence, 1)
    assert.equal(d.fields.find((f) => f.field === 'account_number_masked')?.value, 'XXXXXXXX4521')
    assert.equal(body.documents[0].classification.exit_tier, 'signals')
  })
  test('assignments: an unassigned outside document is unclassified; assigned it is taken as assigned', async () => {
    const res = await withAssignments('TC-09', 'utility_bill.pdf', [{ file_id: 'f1', page_from: 1, page_to: 1, type_id: 'covering_letter' }])
    const body = await res.json() as IngestResult
    assert.deepEqual(body.documents[0].classification.types, ['covering_letter'])
    assert.equal(body.documents[0].classification.exit_tier, 'person')
  })
  test('assignments: an unknown type is a bad request', async () => {
    const res = await withAssignments('TC-09', 'utility_bill.pdf', [{ file_id: 'f1', page_from: 1, page_to: 1, type_id: 'no_such_type' }])
    assert.equal(res.status, 400)
  })
  test('the config file set the tests publish is the one in config/', async () => {
    const dir = join(root, 'config_store', 'versions', version)
    const names = await readdir(dir)
    assert.ok(names.includes('document_types.json') && names.includes('quality.json') && names.includes('confidence.json'))
    assert.ok(names.some((n) => n.startsWith('dictionary.')))
    assert.equal(createHash('sha256').update(version).digest('hex').length, 64)
  })
})
