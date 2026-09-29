// Anthropic, native Messages API (POST /v1/messages).
//
// JSON comes back through structured outputs (output_config.format with a
// JSON schema). Forced tool use (tool_choice "tool") is rejected by the
// current default model, so it is not used. No sampling parameter and no
// thinking setting is sent: the body is exactly what the recording key hashes.
// Plain fetch keeps the body byte-for-byte under our control for the key.
import { ModelError, type JsonSchema, type Provider } from './provider.js'

export interface AnthropicOptions { apiKey: string; model: string; baseUrl: string; maxTokens?: number }

/** Structured outputs need every object closed and every property required. */
export function closeSchema(s: JsonSchema): JsonSchema {
  const walk = (x: unknown): unknown => {
    if (Array.isArray(x)) return x.map(walk)
    if (!x || typeof x !== 'object') return x
    const o = Object.fromEntries(Object.entries(x as Record<string, unknown>).map(([k, v]) => [k, walk(v)]))
    if (o.type === 'object' && o.properties && typeof o.properties === 'object') {
      o.additionalProperties = false
      o.required = Object.keys(o.properties as object)
    }
    return o
  }
  return walk(s) as JsonSchema
}

export function anthropicProvider(opts: AnthropicOptions): Provider {
  return {
    name: 'anthropic',
    model: opts.model,
    build: (req) => {
      const body = {
        model: opts.model,
        max_tokens: opts.maxTokens ?? 8000,
        system: req.system,
        messages: [{ role: 'user', content: req.user }],
        output_config: { format: { type: 'json_schema', schema: closeSchema(req.schema) } },
      }
      return {
        body,
        send: async (b) => {
          if (!opts.apiKey) throw new ModelError('no_live_model', 'ANTHROPIC_API_KEY is not set')
          const res = await fetch(`${opts.baseUrl}/v1/messages`, {
            method: 'POST',
            headers: { 'content-type': 'application/json', 'x-api-key': opts.apiKey, 'anthropic-version': '2023-06-01' },
            body: JSON.stringify(b),
            signal: AbortSignal.timeout(300_000),
          })
          if (!res.ok) throw new ModelError('http', `anthropic ${res.status}: ${(await res.text().catch(() => '')).slice(0, 200)}`)
          return res.json()
        },
        parse: (response) => {
          const r = response as { stop_reason?: string; content?: { type: string; text?: string }[] }
          if (r?.stop_reason === 'refusal') throw new ModelError('refusal', 'the model declined the request')
          if (r?.stop_reason === 'max_tokens') throw new ModelError('bad_response', 'the answer was cut off at max_tokens')
          const text = (r?.content ?? []).filter((c) => c.type === 'text').map((c) => c.text ?? '').join('')
          if (!text) throw new ModelError('bad_response', 'no text content in the response')
          try { return JSON.parse(text) } catch { throw new ModelError('bad_response', 'the response is not JSON') }
        },
      }
    },
  }
}
