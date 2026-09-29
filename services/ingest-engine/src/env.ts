// The service's own settings, from the environment. Nothing here changes what
// the pipeline decides: document types, dictionaries and thresholds come from
// the published CreditIQ configuration (config.ts).
import { fileURLToPath } from 'node:url'

const num = (v: string | undefined, d: number) => (v === undefined || v === '' ? d : Number(v))
const pkgRoot = fileURLToPath(new URL('..', import.meta.url))

export type ProviderName = 'stub' | 'anthropic' | 'gemini'
export type ModelMode = 'record' | 'replay' | 'live'

export interface Env {
  port: number
  /** Interface to bind. Anything other than loopback requires INGEST_API_KEY (main.ts refuses otherwise). */
  host: string
  /** Callers send it as x-api-key or Authorization: Bearer. Empty: the service binds to 127.0.0.1 only. */
  apiKey: string
  /** CreditIQ data root: published configuration and model recordings live under it. */
  dataRoot: string
  ocrWorkers: number
  provider: ProviderName
  mode: ModelMode
  anthropic: { apiKey: string; model: string; baseUrl: string }
  gemini: { apiKey: string; model: string; baseUrl: string }
  pkgRoot: string
}

export function readEnv(e: NodeJS.ProcessEnv = process.env): Env {
  const provider = (e.INGEST_MODEL_PROVIDER || 'stub') as ProviderName
  if (!['stub', 'anthropic', 'gemini'].includes(provider)) throw new Error(`INGEST_MODEL_PROVIDER must be stub, anthropic or gemini (got ${provider})`)
  const mode = (e.INGEST_MODEL_MODE || 'replay') as ModelMode
  if (!['record', 'replay', 'live'].includes(mode)) throw new Error(`INGEST_MODEL_MODE must be record, replay or live (got ${mode})`)
  return {
    port: num(e.INGEST_PORT, 3102),
    host: e.INGEST_HOST || '127.0.0.1',
    apiKey: e.INGEST_API_KEY || '',
    dataRoot: e.CREDITIQ_DATA_ROOT || '',
    ocrWorkers: num(e.OCR_WORKERS, 2),
    provider,
    mode,
    anthropic: {
      apiKey: e.ANTHROPIC_API_KEY || '',
      model: e.ANTHROPIC_MODEL || 'claude-opus-5-5',
      baseUrl: 'https://api.anthropic.com',
    },
    gemini: {
      apiKey: e.GEMINI_API_KEY || '',
      model: e.GEMINI_MODEL || 'gemini-2.5-pro',
      baseUrl: 'https://generativelanguage.googleapis.com',
    },
    pkgRoot,
  }
}
