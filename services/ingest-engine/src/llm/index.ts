import type { Env } from '../env.js'
import { anthropicProvider } from './anthropic.js'
import { geminiProvider } from './gemini.js'
import type { Provider } from './provider.js'
import { ModelClient } from './recorder.js'
import { stubProvider, type Answerer } from './stub.js'

export function createModelClient(env: Env, answerer?: Answerer): ModelClient {
  let provider: Provider
  if (env.provider === 'anthropic') provider = anthropicProvider(env.anthropic)
  else if (env.provider === 'gemini') provider = geminiProvider(env.gemini)
  else provider = stubProvider(answerer)
  return new ModelClient(provider, env.mode, env.dataRoot)
}

export { ModelClient } from './recorder.js'
export { ModelError, type ModelRequest } from './provider.js'
