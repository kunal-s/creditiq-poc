// Gemini, native generateContent with a response schema. Gemini's schema is
// an OpenAPI subset: a union with null ("type": ["string", "null"]) becomes
// { type: STRING, nullable: true }, and additionalProperties is dropped.
import { ModelError, type JsonSchema, type Provider } from './provider.js'

export interface GeminiOptions { apiKey: string; model: string; baseUrl: string }

export function toGeminiSchema(s: unknown): unknown {
  if (Array.isArray(s)) return s.map(toGeminiSchema)
  if (!s || typeof s !== 'object') return s
  const o = s as Record<string, unknown>
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(o)) {
    if (k === 'additionalProperties' || k === '$schema' || k === 'title') continue
    if (k === 'type') {
      const types = Array.isArray(v) ? v : [v]
      const nonNull = types.filter((t) => t !== 'null')
      if (nonNull.length !== 1) throw new Error(`gemini schema: cannot express type ${JSON.stringify(v)}`)
      out.type = String(nonNull[0]).toUpperCase()
      if (types.includes('null')) out.nullable = true
    } else if (k === 'properties' && v && typeof v === 'object') {
      out.properties = Object.fromEntries(Object.entries(v as Record<string, unknown>).map(([pk, pv]) => [pk, toGeminiSchema(pv)]))
    } else out[k] = toGeminiSchema(v)
  }
  return out
}

const REFUSED = new Set(['SAFETY', 'RECITATION', 'PROHIBITED_CONTENT', 'BLOCKLIST', 'SPII'])

export function geminiProvider(opts: GeminiOptions): Provider {
  return {
    name: 'gemini',
    model: opts.model,
    build: (req) => {
      const body = {
        systemInstruction: { parts: [{ text: req.system }] },
        contents: [{ role: 'user', parts: [{ text: req.user }] }],
        generationConfig: { responseMimeType: 'application/json', responseSchema: toGeminiSchema(req.schema as JsonSchema) },
      }
      return {
        body,
        send: async (b) => {
          if (!opts.apiKey) throw new ModelError('no_live_model', 'GEMINI_API_KEY is not set')
          const res = await fetch(`${opts.baseUrl}/v1beta/models/${encodeURIComponent(opts.model)}:generateContent`, {
            method: 'POST',
            headers: { 'content-type': 'application/json', 'x-goog-api-key': opts.apiKey },
            body: JSON.stringify(b),
            signal: AbortSignal.timeout(300_000),
          })
          if (!res.ok) throw new ModelError('http', `gemini ${res.status}: ${(await res.text().catch(() => '')).slice(0, 200)}`)
          return res.json()
        },
        parse: (response) => {
          const r = response as { promptFeedback?: { blockReason?: string }; candidates?: { finishReason?: string; content?: { parts?: { text?: string }[] } }[] }
          if (r?.promptFeedback?.blockReason) throw new ModelError('refusal', `blocked: ${r.promptFeedback.blockReason}`)
          const c = r?.candidates?.[0]
          if (!c) throw new ModelError('bad_response', 'no candidate in the response')
          if (c.finishReason && REFUSED.has(c.finishReason)) throw new ModelError('refusal', `finish reason ${c.finishReason}`)
          if (c.finishReason === 'MAX_TOKENS') throw new ModelError('bad_response', 'the answer was cut off')
          const text = (c.content?.parts ?? []).map((p) => p.text ?? '').join('')
          try { return JSON.parse(text) } catch { throw new ModelError('bad_response', 'the response is not JSON') }
        },
      }
    },
  }
}
