// The ingestion engine's HTTP surface (main.ts serves it; createIngestApp can also be mounted in
// another Hono application with its own auth). Input: a URL, a file, or an e-mail. Output: the
// profile's shape, per document. The engine writes nothing anywhere but its own cache — the
// caller decides what to do with the result.
//
//   GET  /v1/health
//   GET  /v1/types                        the catalogue: every type with version, description, fields, signatures, example count
//   GET  /v1/types/:namespace/:type       one type in full (resolved through `extends`)
//   PUT  /v1/types/:namespace/:type       register or replace a type's profile.json in the catalogue
//   POST /v1/feedback                     a person confirmed or corrected a result → an example the type learns from
//   GET  /v1/metrics                      per-type counts, review and correction rates, drift alerts
//   GET  /v1/review                       documents `auto` could not place (settle them with /v1/feedback)
//   DELETE /v1/review/:sha256             drop one from the queue without teaching anything
//   GET  /v1/review/clusters              groups of look-alike unplaced documents
//   POST /v1/review/propose               { cluster } → a draft pack for that group; accept it with PUT /v1/types/…
//   POST /v1/parse                        text only (parse + OCR), no model call
//   POST /v1/extract                      one JSON answer
//   POST /v1/extract/stream               Server-Sent Events: stage · progress · document · classified · units · result · error
//
// Request (JSON):      { url, type?: "ns/type" | "ns/type@2" | "auto", profile?: { instructions, fields | schema }, rules?, channel?, subject?, name?, emailScope?, includeText? }
// `type` names a catalogue type (pinned with @version), or "auto" to let the engine choose per document;
// `profile` sends a one-off shape instead. `rules` is the caller's own prompt text for this call.
// Request (multipart): file=<pdf|docx|html|txt|png|jpg|eml> + the same fields as form values (JSON-encoded where objects)
import { Hono, type Context } from 'hono'
import { streamSSE } from 'hono/streaming'
import { z } from 'zod'
import { env, hasModelProvider } from './env.js'
import { acquire, fromUrl, type Channel, type RawInput } from './inputs.js'
import { inlineProfile, outputSchema } from './profiles.js'
import { isTypeId, listPacks, loadPack, savePack, type PackFile } from './catalogue.js'
import { recordFeedback, type Feedback } from './feedback.js'
import { summary } from './metrics.js'
import { clusters, dequeue, listReview, propose } from './review.js'
import { extract, PROMPT_VERSION, type ExtractRequest, type ServiceEvent } from './service.js'

const Subject = z.object({ name: z.string().min(1), description: z.string().min(1) })
const Inline = z.object({ id: z.string().optional(), description: z.string().optional(), instructions: z.string().default(''), fields: z.array(z.unknown()).optional(), schema: z.record(z.unknown()).optional(), strategy: z.enum(['fields', 'sections']).optional(), unit: z.record(z.unknown()).optional(), identity: z.record(z.unknown()).optional(), triage: z.record(z.unknown()).optional() })
const Body = z.object({
  url: z.string().url().optional(),
  type: z.string().optional(),
  profile: z.union([z.string(), Inline]).optional(),
  rules: z.string().optional(),
  channel: z.enum(['url', 'file', 'email']).optional(),
  subject: Subject.optional(),
  name: z.string().optional(),
  emailScope: z.enum(['all', 'attachments', 'body']).optional(),
  noCache: z.boolean().optional(),
  includeText: z.boolean().optional(),
})
type BodyT = z.infer<typeof Body>

export class ServiceError extends Error { constructor(public status: 400 | 401 | 403 | 404 | 422 | 502 | 503, public code: string, message: string) { super(message) } }

/** Who may call: a bearer / x-api-key matching INGEST_API_KEY, or — when mounted — whatever the host decided. */
export interface AppOptions { auth: (c: Context) => Promise<{ ok: boolean; actor: string }> }
export const apiKeyAuth = async (c: Context) => {
  const key = env.apiKey
  if (!key) return { ok: true, actor: 'anonymous' }
  const given = c.req.header('x-api-key') ?? c.req.header('authorization')?.replace(/^Bearer\s+/i, '') ?? ''
  return { ok: given === key, actor: 'api-key' }
}

async function readRequest(c: Context, on: (e: ServiceEvent) => void): Promise<{ req: Omit<ExtractRequest, 'type'>; body: BodyT; type: ExtractRequest['type'] }> {
  const ct = c.req.header('content-type') ?? ''
  let body: BodyT
  let raw: RawInput
  if (ct.includes('multipart/form-data')) {
    const form = await c.req.formData()
    const file = form.get('file')
    if (!(file instanceof File)) throw new ServiceError(400, 'bad_request', 'file is required (multipart field "file")')
    const fields: Record<string, unknown> = {}
    for (const [k, raw] of form.entries()) {
      if (k === 'file') continue
      // `-F profile=@my-profile.json` arrives as a file part: read it as text like any other field.
      const v = typeof raw === 'string' ? raw : await raw.text()
      fields[k] = k === 'profile' && v.trim().startsWith('{') ? JSON.parse(v) : k === 'subject' ? JSON.parse(v) : k === 'noCache' || k === 'includeText' ? v === 'true' : v
    }
    body = Body.parse(fields)
    const channel: Channel = body.channel ?? (/\.eml$/i.test(file.name) || /rfc822/.test(file.type) ? 'email' : 'file')
    raw = { channel, buf: new Uint8Array(await file.arrayBuffer()), contentType: file.type || 'application/octet-stream', filename: file.name }
  } else {
    body = Body.parse(await c.req.json().catch(() => { throw new ServiceError(400, 'bad_request', 'JSON body expected') }))
    if (!body.url) throw new ServiceError(400, 'bad_request', 'url is required (or send multipart with a file)')
    raw = await fromUrl(body.url, on).catch((e) => { throw new ServiceError(422, 'fetch_failed', e instanceof Error ? e.message : String(e)) })
    if (body.channel) raw.channel = body.channel
  }
  // What to extract: a catalogue type (`type`, or a string `profile` for compatibility), an inline profile, or generic.
  let type: ExtractRequest['type']
  const named = body.type ?? (typeof body.profile === 'string' ? body.profile : undefined)
  if (named) {
    if (named !== 'auto' && named !== 'generic' && !isTypeId(named.replace(/@\d+$/, ''))) throw new ServiceError(400, 'bad_type', `type must be <namespace>/<type>[@version], "generic" or "auto"`)
    if (named !== 'auto') { const id = named.replace(/@\d+$/, ''); if (!(await loadPack(id).catch((e) => { throw new ServiceError(400, 'bad_type', e instanceof Error ? e.message : String(e)) }))) throw new ServiceError(404, 'unknown_type', `no type "${id}" — GET /v1/types lists the catalogue`) }
    type = named
  } else if (body.profile && typeof body.profile === 'object') {
    try { type = { profile: inlineProfile(body.profile as Parameters<typeof inlineProfile>[0]) } } catch (e) { throw new ServiceError(400, 'bad_profile', e instanceof Error ? e.message : String(e)) }
  } else type = 'generic'
  return { req: { raw, rules: body.rules, subject: body.subject, emailScope: body.emailScope, noCache: body.noCache, name: body.name, includeText: body.includeText }, body, type }
}

/**
 * Bounded concurrency (Phase B): a process runs at most env.concurrency extractions at once and
 * holds at most env.maxQueue waiting; beyond that it answers 503 busy so a load balancer can send
 * the request to another replica (the engine is stateless — run as many as the load needs).
 */
let inFlight = 0
const waiting: (() => void)[] = []
export async function withSlot<T>(fn: () => Promise<T>): Promise<T> {
  if (inFlight >= env.concurrency) {
    if (waiting.length >= env.maxQueue) throw new ServiceError(503, 'busy', `this replica is at capacity (${env.concurrency} running, ${waiting.length} waiting) — retry, or run more replicas`)
    await new Promise<void>((resolve) => waiting.push(resolve))
  }
  inFlight += 1
  try { return await fn() } finally { inFlight -= 1; waiting.shift()?.() }
}
export const load = () => ({ running: inFlight, waiting: waiting.length, concurrency: env.concurrency, maxQueue: env.maxQueue })

export function createIngestApp(opts: AppOptions): Hono {
  const app = new Hono()
  app.use('*', async (c, next) => {
    const a = await opts.auth(c)
    if (!a.ok) return c.json({ error: 'unauthorised', message: 'send x-api-key or a bearer token' }, 401)
    c.set('actor' as never, a.actor as never)
    await next()
  })
  const fail = (c: Context, e: unknown) => {
    if (e instanceof ServiceError) return c.json({ error: e.code, message: e.message }, e.status)
    if (e instanceof z.ZodError) return c.json({ error: 'bad_request', message: e.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('; ') }, 400)
    return c.json({ error: 'internal', message: e instanceof Error ? e.message : String(e) }, 500)
  }

  app.get('/v1/health', (c) => c.json({ ok: true, service: 'ingest-engine', load: load(), promptVersion: PROMPT_VERSION, provider: hasModelProvider() ? { model: env.ai.model, baseUrl: env.ai.baseUrl } : null, ocr: true, inputs: ['url', 'pdf', 'docx', 'html', 'txt', 'png', 'jpg', 'tiff', 'eml'] }))
  const view = (p: Awaited<ReturnType<typeof listPacks>>[number], full = false) => ({ id: p.id, version: p.version, namespace: p.namespace, extends: p.extends, description: p.profile.description, strategy: p.profile.strategy, builtIn: Boolean(p.builtIn), examples: p.examples.length, feedback: p.examples.filter((e) => e.source === 'feedback').length, signatures: p.signatures, validators: p.validators.length ? p.validators : undefined, fields: p.profile.fields, sections: p.profile.sections, ...(full ? { instructions: p.profile.instructions, rules: p.rules, reference: p.reference, schema: p.profile.strategy === 'fields' ? outputSchema(p.profile) : undefined, exampleList: p.examples.map((e) => ({ id: e.id, source: e.source, note: e.note, at: e.at })) } : {}) })
  app.get('/v1/types', async (c) => c.json({ types: (await listPacks()).map((p) => view(p)) }))
  app.get('/v1/types/:ns/:type', async (c) => { try { const p = await loadPack(`${c.req.param('ns')}/${c.req.param('type')}`); return p ? c.json(view(p, true)) : c.json({ error: 'unknown_type' }, 404) } catch (e) { return fail(c, e) } })
  app.get('/v1/types/:id', async (c) => { try { const p = await loadPack(c.req.param('id')); return p ? c.json(view(p, true)) : c.json({ error: 'unknown_type' }, 404) } catch (e) { return fail(c, e) } })
  app.put('/v1/types/:ns/:type', async (c) => { try { const b = (await c.req.json()) as PackFile; return c.json({ type: view(await savePack(`${c.req.param('ns')}/${c.req.param('type')}`, b), true) }) } catch (e) { return e instanceof Error && !(e instanceof z.ZodError) ? c.json({ error: 'bad_type', message: e.message }, 400) : fail(c, e) } })
  app.get('/v1/metrics', async (c) => c.json(await summary()))
  app.get('/v1/review', async (c) => c.json({ review: await listReview() }))
  app.get('/v1/review/clusters', async (c) => c.json({ clusters: (await clusters(Number(c.req.query('min') || 3))).map((k) => ({ index: k.index, size: k.items.length, sharedTerms: k.sharedTerms, items: k.items.map((i) => ({ sha256: i.sha256, name: i.name, subject: i.mail?.subject, at: i.at })) })) }))
  app.delete('/v1/review/:sha', async (c) => c.json({ removed: await dequeue(c.req.param('sha')) }))
  app.post('/v1/review/propose', async (c) => {
    try {
      if (!hasModelProvider()) throw new ServiceError(503, 'no_provider', 'AI_API_KEY is not set on the service')
      const b = (await c.req.json().catch(() => ({}))) as { cluster?: number; min?: number }
      const all = await clusters(b.min ?? 3)
      const k = all[b.cluster ?? 0]
      if (!k) throw new ServiceError(404, 'no_cluster', all.length ? `clusters 0–${all.length - 1} exist` : 'no cluster of that size in the review queue yet')
      const p = await propose(k)
      return c.json({ ...p, accept: { method: 'PUT', path: `/v1/types/${p.suggestedId}`, body: p.pack } })
    } catch (e) { return fail(c, e) }
  })
  app.post('/v1/feedback', async (c) => {
    try { const f = (await c.req.json()) as Feedback; return c.json({ ok: true, ...(await recordFeedback(f, String(c.get('actor' as never) ?? ''))) }) }
    catch (e) { return e instanceof Error && !(e instanceof z.ZodError) ? c.json({ error: 'bad_feedback', message: e.message }, 400) : fail(c, e) }
  })

  // Text only — parse + OCR, no model. Useful to see what the extractor will read.
  app.post('/v1/parse', async (c) => {
    try {
      const { req } = await readRequest(c, () => {})
      const docs = await acquire(req.raw, () => {}, { emailScope: req.emailScope, noCache: req.noCache })
      return c.json({ channel: req.raw.channel, documents: docs.map((d) => ({ part: d.part, name: d.name, sha256: d.sha256, contentType: d.contentType, mail: d.mail, source: { kind: d.text.kind, pages: d.text.pages, chars: d.text.text.length, ocrPages: d.text.ocrPages, warning: d.text.warning }, text: d.text.text })) })
    } catch (e) { return fail(c, e) }
  })
  app.post('/v1/extract', async (c) => {
    try {
      if (!hasModelProvider()) throw new ServiceError(503, 'no_provider', 'AI_API_KEY is not set on the service')
      const { req, type } = await readRequest(c, () => {})
      return c.json(await withSlot(() => extract({ ...req, type })))
    } catch (e) { return fail(c, e) }
  })
  app.post('/v1/extract/stream', (c) =>
    streamSSE(c, async (stream) => {
      let seq = 0
      const send = (e: ServiceEvent) => stream.writeSSE({ data: JSON.stringify(e), event: e.type, id: String(++seq) })
      try {
        if (!hasModelProvider()) throw new ServiceError(503, 'no_provider', 'AI_API_KEY is not set on the service')
        const { req, type } = await readRequest(c, send)
        const result = await withSlot(() => extract({ ...req, type }, send))
        await send({ type: 'result', result })
      } catch (e) {
        await send({ type: 'error', message: e instanceof ServiceError ? `${e.code}: ${e.message}` : e instanceof Error ? e.message : String(e) })
      }
    }),
  )
  return app
}
