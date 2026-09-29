// Standalone entrypoint: npm start (INGEST_PORT, default 3102).
import { serve } from '@hono/node-server'
import { createApp } from './app.js'
import { ConfigStore } from './config.js'
import { readEnv } from './env.js'
import { createModelClient } from './llm/index.js'
import { configureOcr } from './read/ocr.js'
import { ENGINE_VERSION } from './version.js'

const env = readEnv()
const loopback = env.host === '127.0.0.1' || env.host === '::1' || env.host === 'localhost'
if (!env.apiKey && !loopback) {
  console.error('[ingest] refusing to start: INGEST_HOST is not loopback and INGEST_API_KEY is not set')
  process.exit(1)
}
if (!env.dataRoot) {
  console.error('[ingest] refusing to start: CREDITIQ_DATA_ROOT is not set')
  process.exit(1)
}
configureOcr(env.ocrWorkers)
const app = createApp({ env, configs: new ConfigStore(env.dataRoot), model: createModelClient(env) })
serve({ fetch: app.fetch, port: env.port, hostname: env.host }, (info) => {
  console.log(`[ingest] ${ENGINE_VERSION} on ${env.host}:${info.port} · ${env.apiKey ? 'API key required' : 'loopback only'} · model ${env.provider} (${env.mode})`)
})
