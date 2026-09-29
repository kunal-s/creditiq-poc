// Contract tests that need no model: parsing, e-mail splitting, profile compilation, the HTTP
// surface and auth. Extraction against a model runs only when AI_API_KEY is set (INGEST_TEST_MODEL=1).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createIngestApp, apiKeyAuth } from '../src/app.js'
import { compileFields, inlineProfile, outputSchema, BUILT_IN, strictify } from '../src/profiles.js'
import { listPacks, loadPack, resolveType, validate, fewShot } from '../src/catalogue.js'
import { bySignature } from '../src/classify.js'
import { acquire } from '../src/inputs.js'
import { toText } from '../src/text.js'

const app = createIngestApp({ auth: async () => ({ ok: true, actor: 'test' }) })
const post = (path: string, form: FormData) => app.request(path, { method: 'POST', body: form })
const textFile = (name: string, s: string, type = 'text/plain') => new File([s], name, { type })

test('plain text parses as one document', async () => {
  const docs = await acquire({ channel: 'file', buf: new TextEncoder().encode('Hello\nWorld'), contentType: 'text/plain', filename: 'a.txt' }, () => {})
  assert.equal(docs.length, 1)
  assert.equal(docs[0].part, 'document')
  assert.equal(docs[0].text.text, 'Hello\nWorld')
})

test('HTML is reduced to its text', async () => {
  const t = await toText(new TextEncoder().encode('<html><body><nav>menu</nav><h1>Title</h1><p>Body <a href="x">link</a></p><script>x()</script></body></html>'), 'text/html', 'p.html')
  assert.equal(t.kind, 'html')
  assert.match(t.text, /TITLE/) // html-to-text upper-cases headings
  assert.match(t.text, /Body link/)
  assert.doesNotMatch(t.text, /menu|x\(\)/)
})

test('an e-mail splits into attachments and body, attachments first', async () => {
  const att = Buffer.from('ARN: AA1\nStatus: FILED').toString('base64')
  const eml = ['Received: from x', 'MIME-Version: 1.0', 'From: a@b.c', 'To: d@e.f', 'Subject: Ack', 'Date: Fri, 18 Sep 2026 10:11:00 +0530', 'Content-Type: multipart/mixed; boundary="B"', '', '--B', 'Content-Type: text/plain', '', 'Body text', '--B', 'Content-Type: text/plain; name="ack.txt"', 'Content-Disposition: attachment; filename="ack.txt"', 'Content-Transfer-Encoding: base64', '', att, '--B--', ''].join('\r\n')
  const docs = await acquire({ channel: 'email', buf: new TextEncoder().encode(eml), contentType: 'message/rfc822', filename: 'm.eml' }, () => {})
  assert.deepEqual(docs.map((d) => d.part), ['attachment', 'body'])
  assert.equal(docs[0].name, 'ack.txt')
  assert.match(docs[0].text.text, /AA1/)
  assert.equal(docs[1].mail?.subject, 'Ack')
  assert.match(docs[1].text.text, /Body text/)
  const only = await acquire({ channel: 'email', buf: new TextEncoder().encode(eml), contentType: 'message/rfc822', filename: 'm.eml' }, () => {}, { emailScope: 'attachments' })
  assert.equal(only.length, 1)
})

test('a text file that merely contains "Date:" is not mistaken for an e-mail', async () => {
  const docs = await acquire({ channel: 'file', buf: new TextEncoder().encode('PO-1\nDate: 10 Sep 2026\nSupplier: X'), contentType: 'text/plain', filename: 'po.txt' }, () => {})
  assert.equal(docs[0].part, 'document')
})

test('fields compile to a strict schema; optional fields are nullable', () => {
  const s = compileFields([{ name: 'a', type: 'string', required: true }, { name: 'b', type: 'date' }, { name: 'c', type: 'object[]', items: [{ name: 'x', type: 'number', required: true }] }]) as { required: string[]; additionalProperties: boolean; properties: Record<string, { type: unknown }> }
  assert.deepEqual(s.required, ['a', 'b', 'c'])
  assert.equal(s.additionalProperties, false)
  assert.equal(s.properties.a.type, 'string')
  assert.deepEqual(s.properties.b.type, ['string', 'null'])
})

test('a caller schema is made strict recursively', () => {
  const s = strictify({ type: 'object', properties: { n: { type: 'string' }, items: { type: 'array', items: { type: 'object', properties: { q: { type: 'number' } } } } } }) as { required: string[]; properties: { items: { items: { required: string[]; additionalProperties: boolean } } } }
  assert.deepEqual(s.required, ['n', 'items'])
  assert.deepEqual(s.properties.items.items.required, ['q'])
  assert.equal(s.properties.items.items.additionalProperties, false)
})

test('the only built-in is generic; every catalogue pack loads and compiles', async () => {
  assert.deepEqual(BUILT_IN.map((p) => p.id), ['generic'])
  const packs = await listPacks()
  const ids = packs.map((p) => p.id)
  for (const want of ['generic', 'finance/invoice', 'bank/statement', 'sbi/statement', 'filing/acknowledgement', 'regulation/clauses']) assert.ok(ids.includes(want), want)
  for (const p of packs) if (p.profile.strategy === 'fields') assert.equal((outputSchema(p.profile) as { type: string }).type, 'object', p.id)
  const clauses = packs.find((p) => p.id === 'regulation/clauses')!
  assert.equal(clauses.profile.strategy, 'sections')
  assert.ok(clauses.rules.includes('numbered paragraph'))
})

test('a child type inherits fields, instructions, rules, signatures, validators and examples from its parent', async () => {
  const sbi = (await loadPack('sbi/statement'))!
  const bank = (await loadPack('bank/statement'))!
  assert.equal(sbi.extends, 'bank/statement')
  const names = sbi.profile.fields!.map((f) => f.name)
  for (const f of bank.profile.fields!) assert.ok(names.includes(f.name), f.name)
  assert.ok(names.includes('ifsc'))
  assert.ok(sbi.profile.instructions.startsWith(bank.profile.instructions))
  assert.ok(sbi.profile.instructions.includes('Txn Date'))
  assert.equal(sbi.rules, bank.rules)
  assert.ok((sbi.signatures?.textAll ?? []).length >= 1 && (sbi.signatures?.textAny ?? []).some((x) => x.includes('State Bank')))
  assert.ok(sbi.validators.length > bank.validators.length)
  assert.ok(sbi.examples.length >= bank.examples.length && bank.examples.length >= 1)
})

test('a pinned version must match the catalogue', async () => {
  const p = await resolveType('finance/invoice@1')
  assert.equal(p.version, 1)
  await assert.rejects(resolveType('finance/invoice@7'), /version 1/)
  await assert.rejects(resolveType('no/such-type'), /unknown type/)
})

test('signatures pick a type without a model, and a child beats its parent', () => {
  const doc = (text: string, mail?: { from: string; subject: string }) => ({ part: 'document' as const, name: 'x.txt', sha256: 'a'.repeat(64), contentType: 'text/plain', text: { text, pages: 1, kind: 'text' as const, bytes: text.length }, mail: mail ? { ...mail, to: '', date: null, messageId: null } : undefined })
  return listPacks().then((packs) => {
    const c1 = bySignature(doc('GSTN acknowledgement\nARN: AA1\nReturn: GSTR-3B\nStatus: FILED'), packs)
    assert.equal(c1?.type, 'filing/acknowledgement'); assert.equal(c1?.by, 'signature')
    const c2 = bySignature(doc('State Bank of India\nStatement of Account\nOpening balance 10\n01-Aug debit 5'), packs)
    assert.equal(c2?.type, 'sbi/statement')
    const c3 = bySignature(doc('Statement of Account\nOpening balance 10\n01-Aug credit 5'), packs)
    assert.equal(c3?.type, 'bank/statement')
    assert.equal(bySignature(doc('Dear all, lunch is at noon.'), packs), null)
  })
})

test('validators produce warnings, never errors; few-shot comes from examples', async () => {
  const inv = (await loadPack('finance/invoice'))!
  assert.deepEqual(validate(inv, { invoiceNumber: 'X', total: 10, supplierTaxId: '27AAACS8577K1ZO' }), [])
  const w = validate(inv, { invoiceNumber: '', total: -1, supplierTaxId: 'nope' })
  assert.equal(w.length, 3)
  assert.ok(fewShot(inv).includes('INV-2026-88'))
})

test('a sections profile validates its unit, identity and triage', () => {
  const p = inlineProfile({ id: 'articles', instructions: 'Extract the articles that bind the buyer. {{subject}}', strategy: 'sections', unit: { name: 'articles', key: 'ref', pageField: 'page', fields: [{ name: 'ref', type: 'string', required: true }, { name: 'page', type: 'string' }, { name: 'duty', type: 'string', required: true }] }, identity: { instructions: 'Read the front matter.', fields: [{ name: 'title', type: 'string', required: true }] }, triage: { instructions: 'Select articles that bind the buyer.' } })
  assert.equal(p.strategy, 'sections')
  assert.equal(p.sections?.unit.name, 'articles')
  assert.equal(p.sections?.unit.keyNormalise, 'exact')
  assert.throws(() => inlineProfile({ instructions: 'x', strategy: 'sections' }), /needs `unit`/)
  assert.throws(() => inlineProfile({ instructions: 'x', strategy: 'sections', unit: { name: 'u', key: 'nope', fields: [{ name: 'a', type: 'string' }] } }), /unit.key/)
})

test('string fields may carry an enum; optional enums admit null', () => {
  const s = compileFields([{ name: 'sev', type: 'string', enum: ['High', 'Low'], required: true }, { name: 'kind', type: 'string', enum: ['A'] }]) as { properties: Record<string, { enum: unknown[] }> }
  assert.deepEqual(s.properties.sev.enum, ['High', 'Low'])
  assert.deepEqual(s.properties.kind.enum, ['A', null])
})

test('inline profile falls back to generic fields when only instructions are given', () => {
  const p = inlineProfile({ instructions: 'Find the invoice number.' })
  assert.ok(p.fields && p.fields.length > 3)
  const q = inlineProfile({ instructions: 'x', fields: [{ name: 'k', type: 'string' }] })
  assert.equal(q.fields?.length, 1)
})

test('inline profile rejects bad field definitions', () => {
  assert.throws(() => inlineProfile({ instructions: 'x', fields: [{ name: 'bad name', type: 'string' }] }), /identifier/)
  assert.throws(() => inlineProfile({ instructions: 'x', fields: [{ name: 'k', type: 'blob' as never }] }), /type must be/)
})

test('GET /v1/health and /v1/profiles answer', async () => {
  const h = await app.request('/v1/health')
  assert.equal(h.status, 200)
  assert.equal(((await h.json()) as { service: string }).service, 'ingest-engine')
  const p = (await (await app.request('/v1/types')).json()) as { types: { id: string }[] }
  assert.ok(p.types.some((x) => x.id === 'generic'))
})

test('POST /v1/parse returns the text without a model', async () => {
  const form = new FormData()
  form.set('file', textFile('a.txt', 'Some words here'))
  const r = await post('/v1/parse', form)
  assert.equal(r.status, 200)
  const j = (await r.json()) as { channel: string; documents: { text: string }[] }
  assert.equal(j.channel, 'file')
  assert.equal(j.documents[0].text, 'Some words here')
})

test('profile, subject and rules may arrive as multipart file parts (curl -F name=@file)', async () => {
  const form = new FormData()
  form.set('file', textFile('a.txt', 'Some words here'))
  form.set('profile', new File([JSON.stringify({ instructions: 'x', fields: [{ name: 'k', type: 'string' }] })], 'p.json', { type: 'application/json' }))
  form.set('rules', new File(['Be brief.'], 'r.md', { type: 'text/markdown' }))
  const r = await post('/v1/extract', form)
  // Without a model key the request is refused at the provider check — after the form parsed cleanly.
  assert.equal(r.status, process.env.AI_API_KEY ? 200 : 503)
})

test('POST /v1/extract refuses an unknown type, a bad type id and a stale pin', async () => {
  const form = () => { const f = new FormData(); f.set('file', textFile('a.txt', 'x')); return f }
  let f = form(); f.set('type', 'no/such-type'); assert.equal((await post('/v1/extract', f)).status, process.env.AI_API_KEY ? 404 : 503)
  f = form(); f.set('type', 'Bad Type!'); assert.equal((await post('/v1/extract', f)).status, process.env.AI_API_KEY ? 400 : 503)
})

test('GET /v1/types lists the catalogue; GET /v1/types/:ns/:type resolves a child', async () => {
  const t = (await (await app.request('/v1/types')).json()) as { types: { id: string; version: number; examples: number }[] }
  assert.ok(t.types.some((x) => x.id === 'bank/statement' && x.version === 1 && x.examples >= 1))
  const sbi = (await (await app.request('/v1/types/sbi/statement')).json()) as { extends: string; fields: { name: string }[]; rules: string }
  assert.equal(sbi.extends, 'bank/statement')
  assert.ok(sbi.fields.some((f) => f.name === 'ifsc') && sbi.rules.length > 0)
})

test('POST /v1/feedback validates and refuses an unknown type', async () => {
  const r = await app.request('/v1/feedback', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ sha256: 'f'.repeat(64), type: 'no/such', verdict: 'confirmed' }) })
  assert.equal(r.status, 400)
})

test('API-key auth rejects a missing or wrong key and accepts the right one', async () => {
  process.env.INGEST_API_KEY = 'k1'
  const { env } = await import('../src/env.js')
  env.apiKey = 'k1'
  const secured = createIngestApp({ auth: apiKeyAuth })
  assert.equal((await secured.request('/v1/health')).status, 401)
  assert.equal((await secured.request('/v1/health', { headers: { 'x-api-key': 'wrong' } })).status, 401)
  assert.equal((await secured.request('/v1/health', { headers: { authorization: 'Bearer k1' } })).status, 200)
  env.apiKey = ''
})

test('extraction against the model (only with INGEST_TEST_MODEL=1)', { skip: process.env.INGEST_TEST_MODEL !== '1' || !process.env.AI_API_KEY }, async () => {
  const form = new FormData()
  form.set('file', textFile('inv.txt', 'Invoice INV-9\nSupplier: Gamma Ltd\nTotal: 450'))
  form.set('type', 'finance/invoice@1')
  form.set('noCache', 'true')
  const r = await post('/v1/extract', form)
  assert.equal(r.status, 200)
  const j = (await r.json()) as { documents: { data: { invoiceNumber: string; total: number } }[] }
  assert.equal(j.documents[0].data.invoiceNumber, 'INV-9')
  assert.equal(j.documents[0].data.total, 450)
})

test('review queue: enqueue, list, cluster look-alikes, dequeue; metrics summarise and alert', async () => {
  const { enqueue, listReview, clusters, dequeue } = await import('../src/review.js')
  const { recordExtraction, recordVerdict, summary } = await import('../src/metrics.js')
  const { env } = await import('../src/env.js')
  const { mkdtempSync } = await import('node:fs'); const { tmpdir } = await import('node:os'); const { join } = await import('node:path')
  const saved = env.feedbackDir; env.feedbackDir = mkdtempSync(join(tmpdir(), 'ingest-fb-'))
  try {
    const mk = (n: number, text: string) => ({ sha256: String(n).repeat(64).slice(0, 64), name: `d${n}.txt`, snippet: text, candidates: [], reason: 'none', generic: null })
    for (let i = 1; i <= 3; i++) await enqueue(mk(i, `DELIVERY CHALLAN DC-00${i}\nTransporter: Example Carriers\nConsignee: Example Buyer Ltd\nVehicle MH-04-AB-${i}`))
    await enqueue(mk(4, 'Board minutes of the Audit Committee meeting held on 3 September; attendance and resolutions.'))
    assert.equal((await listReview()).length, 4)
    const c = await clusters(3)
    assert.equal(c.length, 1); assert.equal(c[0].items.length, 3)
    assert.ok(c[0].sharedTerms.includes('challan'))
    assert.equal(await dequeue(mk(4, '').sha256), true)
    assert.equal((await listReview()).length, 3)
    for (let i = 0; i < 6; i++) await recordExtraction({ type: 'x/y', by: 'model', confidence: 0.8, needsReview: i < 3 })
    for (let i = 0; i < 5; i++) await recordVerdict({ type: 'x/y', verdict: i < 2 ? 'confirmed' : 'corrected' })
    const m = await summary()
    const t = m.types.find((x) => x.type === 'x/y')!
    assert.equal(t.requests, 6); assert.equal(t.confirmed, 2); assert.equal(t.corrected, 3)
    assert.equal(t.reviewRate, 0.5); assert.equal(t.correctionRate, 0.6)
    assert.ok(t.alerts.length === 2, t.alerts.join(' | '))
  } finally { env.feedbackDir = saved }
})
