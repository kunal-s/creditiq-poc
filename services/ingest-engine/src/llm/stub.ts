// The stub provider: serves recorded answers only (AD-5, until a key is
// supplied). Its native body is the neutral request itself, and its native
// response is { "answer": <json> }. It has no live model: in record or live
// mode it answers only through an injected answerer, which exists for the
// fixture tooling that writes hand-authored recordings.
import { ModelError, type ModelRequest, type Provider } from './provider.js'

export type Answerer = (req: ModelRequest) => unknown | Promise<unknown>

export function stubProvider(answerer?: Answerer): Provider {
  return {
    name: 'stub',
    model: 'stub',
    build: (req) => ({
      body: { task: req.task, system: req.system, user: req.user, schema: req.schema },
      send: async (body) => {
        if (!answerer) throw new ModelError('no_live_model', 'the stub provider has no live model; use INGEST_MODEL_MODE=replay')
        const answer = await answerer(body as ModelRequest)
        if (answer === undefined) throw new ModelError('no_live_model', `no hand-written answer for this ${req.task} call`)
        return { answer }
      },
      parse: (response) => {
        const r = response as { answer?: unknown; refusal?: string }
        if (r?.refusal) throw new ModelError('refusal', r.refusal)
        if (r?.answer === undefined) throw new ModelError('bad_response', 'stub response has no answer')
        return r.answer
      },
    }),
  }
}
