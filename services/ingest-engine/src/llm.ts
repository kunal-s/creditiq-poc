// Minimal OpenAI-compatible chat client with structured (JSON-schema) output.
// Works against OpenAI, vLLM, Ollama (/v1) and similar; the endpoint is config.
import { env } from './env.js'

export interface ChatJsonArgs {
  system: string
  user: string
  jsonSchema: { name: string; strict: boolean; schema: Record<string, unknown> }
  temperature?: number
  model?: string
}

export interface ChatJsonResult<T> {
  data: T
  model: string
  usage?: { prompt_tokens?: number; completion_tokens?: number }
}

const RETRIES = 3
const RETRY_ON = new Set([408, 409, 425, 429, 500, 502, 503, 504, 520, 521, 522, 524])
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** Errors from the provider's edge come back as HTML pages; keep the message short and readable. */
function briefError(status: number, body: string): string {
  const text = /<html/i.test(body) ? body.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120) : body.slice(0, 300)
  return `Model call failed: ${status}${text ? ` ${text}` : ''}`
}

export async function chatJson<T>(args: ChatJsonArgs): Promise<ChatJsonResult<T>> {
  let lastError: Error | null = null
  for (let attempt = 0; attempt < RETRIES; attempt++) {
    if (attempt > 0) await sleep(800 * 2 ** (attempt - 1) + Math.random() * 400)
    try {
      return await chatJsonOnce<T>(args)
    } catch (e) {
      lastError = e instanceof Error ? e : new Error(String(e))
      const status = (e as { status?: number }).status
      const retryable = (status !== undefined && RETRY_ON.has(status)) || /fetch failed|timeout|ECONNRESET|socket/i.test(lastError.message)
      if (!retryable) throw lastError
      console.warn(`[llm] attempt ${attempt + 1}/${RETRIES} failed (${status ?? 'network'}); retrying`)
    }
  }
  throw lastError ?? new Error('Model call failed')
}

async function chatJsonOnce<T>(args: ChatJsonArgs): Promise<ChatJsonResult<T>> {
  const res = await fetch(`${env.ai.baseUrl}/chat/completions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: `Bearer ${env.ai.apiKey}` },
    body: JSON.stringify({
      model: args.model ?? env.ai.model,
      temperature: args.temperature ?? 0.1,
      messages: [
        { role: 'system', content: args.system },
        { role: 'user', content: args.user },
      ],
      response_format: { type: 'json_schema', json_schema: args.jsonSchema },
    }),
    signal: AbortSignal.timeout(180_000),
  })
  if (!res.ok) {
    const body = await res.text().catch(() => '')
    throw Object.assign(new Error(briefError(res.status, body)), { status: res.status })
  }
  const json = (await res.json()) as {
    model?: string
    usage?: ChatJsonResult<T>['usage']
    choices: { message: { content: string | null; refusal?: string | null } }[]
  }
  const msg = json.choices?.[0]?.message
  if (!msg?.content) throw new Error(msg?.refusal ? `Model refused: ${msg.refusal}` : 'Model returned no content')
  return { data: JSON.parse(msg.content) as T, model: json.model ?? args.model ?? env.ai.model, usage: json.usage }
}
