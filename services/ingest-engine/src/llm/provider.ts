// The model layer (FRD AD-5, principle 6).
//
// One provider-neutral request goes in, parsed JSON comes out. Each provider
// turns the neutral request into its native body; the recorder keys every
// call by sha256 of the canonical JSON of {provider, model, body} and stores
// request and response under $CREDITIQ_DATA_ROOT/recordings/<provider>/.
// No sampling parameter (temperature, top_p, top_k, seed) is ever sent.

/** A JSON schema in the common subset every provider accepts. */
export type JsonSchema = Record<string, unknown>

export interface ModelRequest {
  /** What the call is for ("classify", "extract"): part of the key, useful when reading recordings. */
  task: string
  system: string
  user: string
  schema: JsonSchema
}

export interface NativeCall {
  /** The exact JSON body sent to the provider (the recording key covers it). */
  body: unknown
  /** Sends the body live and returns the provider's raw JSON response. */
  send: (body: unknown) => Promise<unknown>
  /** Pulls the answer out of a raw response; throws ModelRefusal or ModelError. */
  parse: (response: unknown) => unknown
}

export interface Provider {
  name: 'stub' | 'anthropic' | 'gemini'
  model: string
  build: (req: ModelRequest) => NativeCall
}

export class ModelError extends Error {
  constructor(public code: 'replay_miss' | 'refusal' | 'no_live_model' | 'bad_response' | 'http', message: string) { super(message) }
}

/** Keys sorted at every level; the same value always serialises the same way. */
export function canonicalJson(v: unknown): string {
  if (v === null || typeof v !== 'object') return JSON.stringify(v)
  if (Array.isArray(v)) return `[${v.map(canonicalJson).join(',')}]`
  const o = v as Record<string, unknown>
  return `{${Object.keys(o).filter((k) => o[k] !== undefined).sort().map((k) => `${JSON.stringify(k)}:${canonicalJson(o[k])}`).join(',')}}`
}

/** Guards principle 6: fails loudly if a sampling parameter reaches a body. */
export function assertNoSampling(body: unknown): void {
  const banned = new Set(['temperature', 'top_p', 'top_k', 'topP', 'topK', 'seed', 'presence_penalty', 'frequency_penalty'])
  const walk = (x: unknown): void => {
    if (!x || typeof x !== 'object') return
    for (const [k, v] of Object.entries(x as Record<string, unknown>)) {
      if (banned.has(k)) throw new Error(`sampling parameter "${k}" must not be sent (principle 6)`)
      walk(v)
    }
  }
  walk(body)
}
