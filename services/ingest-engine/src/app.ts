// The sidecar's HTTP surface (FRD AD-2):
//
//   GET  /v1/health    liveness, engine version, model provider and mode
//   POST /v1/process   multipart: part "request" (IngestRequest JSON) and one
//                      part per file named by its file_id; answers IngestResult
//
// Auth: when INGEST_API_KEY is set, every call must send it as x-api-key or
// Authorization: Bearer (compared in constant time). When it is not set, the
// service binds to 127.0.0.1 only (main.ts) and also refuses any caller that
// is not on the loopback interface.
import { createHash, timingSafeEqual } from 'node:crypto'
import { Hono, type Context } from 'hono'
import { bodyLimit } from 'hono/body-limit'
import { ConfigError, type ConfigStore } from './config.js'
import type { Env } from './env.js'
import type { ModelClient } from './llm/index.js'
import { parseRequest, processRequest, RequestError } from './process.js'
import { ENGINE_VERSION } from './version.js'

const digest = (s: string) => createHash('sha256').update(s).digest()

export function keyMatches(given: string, key: string): boolean {
  if (!key) return false
  return timingSafeEqual(digest(given), digest(key))
}

const LOOPBACK = /^(127\.\d+\.\d+\.\d+|::1|::ffff:127\.\d+\.\d+\.\d+)$/

function remoteAddress(c: Context): string | undefined {
  const env = c.env as { incoming?: { socket?: { remoteAddress?: string } } } | undefined
  return env?.incoming?.socket?.remoteAddress
}

export interface AppDeps { env: Env; configs: ConfigStore; model: ModelClient; maxBodyBytes?: number }

let running = 0
const waiting: (() => void)[] = []
const MAX_RUNNING = 2
async function withSlot<T>(fn: () => Promise<T>): Promise<T> {
  if (running >= MAX_RUNNING) await new Promise<void>((r) => waiting.push(r))
  running++
  try { return await fn() } finally { running--; waiting.shift()?.() }
}

export function createApp(deps: AppDeps): Hono {
  const app = new Hono()
  app.use('*', async (c, next) => {
    const key = deps.env.apiKey
    if (key) {
      const given = c.req.header('x-api-key') ?? c.req.header('authorization')?.replace(/^Bearer\s+/i, '') ?? ''
      if (!keyMatches(given, key)) return c.json({ error: 'unauthorised', message: 'send the API key as x-api-key or a bearer token' }, 401)
    } else {
      // No key: loopback callers only. (In-process calls in tests carry no socket.)
      const addr = remoteAddress(c)
      if (addr !== undefined && !LOOPBACK.test(addr)) return c.json({ error: 'unauthorised', message: 'this service accepts local callers only' }, 401)
    }
    await next()
  })

  app.get('/v1/health', (c) =>
    c.json({ ok: true, service: 'ingest-engine', engine_version: ENGINE_VERSION, model_provider: deps.model.name, model_mode: deps.model.mode, ocr: 'tesseract.js, English, local language data' }))

  app.post('/v1/process', bodyLimit({ maxSize: deps.maxBodyBytes ?? 250 * 1024 * 1024, onError: (c) => c.json({ error: 'too_large', message: 'the request body is too large' }, 413) }), async (c) => {
    try {
      const ct = c.req.header('content-type') ?? ''
      if (!ct.includes('multipart/form-data')) throw new RequestError(400, 'send multipart/form-data with a "request" part and one part per file_id')
      const form = await c.req.formData()
      const reqPart = form.get('request')
      if (reqPart === null) throw new RequestError(400, 'the "request" part is missing')
      const reqText = typeof reqPart === 'string' ? reqPart : await reqPart.text()
      let json: unknown
      try { json = JSON.parse(reqText) } catch { throw new RequestError(400, 'the "request" part is not JSON') }
      const req = parseRequest(json)
      const payloads = new Map<string, Uint8Array>()
      for (const f of req.files) {
        const part = form.get(f.file_id)
        if (part && typeof part !== 'string') payloads.set(f.file_id, new Uint8Array(await part.arrayBuffer()))
        else if (typeof part === 'string') payloads.set(f.file_id, new TextEncoder().encode(part))
      }
      return c.json(await withSlot(() => processRequest(req, payloads, { configs: deps.configs, model: deps.model })))
    } catch (e) {
      if (e instanceof RequestError) return c.json({ error: 'bad_request', message: e.message }, e.status)
      if (e instanceof ConfigError) return c.json({ error: e.status === 409 ? 'unknown_config_version' : 'config_error', message: e.message }, e.status)
      console.error('[ingest] process failed:', e)
      return c.json({ error: 'internal', message: 'processing failed; see the service log' }, 500)
    }
  })
  return app
}
