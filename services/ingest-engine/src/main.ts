// Standalone entrypoint: the ingestion engine on its own port, authenticated by INGEST_API_KEY.
//   npm run dev · npm start          (INGEST_PORT, default 3002)
// It shares nothing with any calling application: the caller sends the profile (or its id) and
// its own rules text with every request. Configuration is env.ts — model provider, port, key,
// profile directory, cache and OCR directories.
import { serve } from '@hono/node-server'
import { env } from './env.js'
import { prewarmOcr } from './ocr.js'
import { apiKeyAuth, createIngestApp } from './app.js'

prewarmOcr()
const app = createIngestApp({ auth: apiKeyAuth })
serve({ fetch: app.fetch, port: env.port }, (info) => {
  console.log(`[ingest] engine on :${info.port} · ${env.apiKey ? 'API key required' : 'OPEN — set INGEST_API_KEY'} · types from ${env.typesDir} · feedback to ${env.feedbackDir} · auto threshold ${env.autoThreshold}`)
})
