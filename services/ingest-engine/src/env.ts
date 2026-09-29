// The engine's whole configuration. Nothing about any calling application lives here.
import 'dotenv/config'
import { fileURLToPath } from 'node:url'

const num = (v: string | undefined, d: number) => (v === undefined || v === '' ? d : Number(v))
const root = (p: string) => fileURLToPath(new URL(`../${p}`, import.meta.url))

export const env = {
  port: num(process.env.INGEST_PORT, 3002),
  /** Callers send it as x-api-key or Authorization: Bearer. Empty = open (local use only). */
  apiKey: process.env.INGEST_API_KEY || '',
  /** The type catalogue: types/<namespace>/<type>/profile.json packs (plus flat <id>.json); PUT /v1/types/:id writes here. */
  typesDir: process.env.INGEST_TYPES_DIR || process.env.INGEST_PROFILES_DIR || root('types'),
  /** Where confirmed / corrected examples from POST /v1/feedback are kept, mirrored by type. */
  feedbackDir: process.env.INGEST_FEEDBACK_DIR || root('feedback'),
  /** `type: "auto"` picks a type only at or above this model confidence (0–1). */
  autoThreshold: Math.min(1, Math.max(0, Number(process.env.INGEST_AUTO_THRESHOLD || 0.7))),
  /** Downloads, parses and extractions, keyed by content hash. */
  cacheDir: process.env.INGEST_CACHE_DIR || root('.cache'),
  /** OCR language data, downloaded once. */
  tessdataDir: process.env.INGEST_TESSDATA_DIR || root('.tessdata'),
  ocrWorkers: num(process.env.OCR_WORKERS, 0), // 0 = derived from CPU count
  /** Extractions in flight at once per process; further requests wait, up to maxQueue, then get 503 busy (run more replicas). */
  concurrency: num(process.env.INGEST_CONCURRENCY, 4),
  maxQueue: num(process.env.INGEST_MAX_QUEUE, 32),
  ai: {
    baseUrl: (process.env.AI_BASE_URL || 'https://api.openai.com/v1').replace(/\/$/, ''),
    apiKey: process.env.AI_API_KEY || '',
    model: process.env.AI_MODEL || 'gpt-4.1-mini',
    /** Cheaper model for the sections strategy's identity and triage passes; defaults to AI_MODEL. */
    triageModel: process.env.AI_TRIAGE_MODEL || process.env.AI_MODEL || 'gpt-4.1-mini',
  },
  /** 'fields' strategy: characters per model call. */
  windowChars: num(process.env.INGEST_WINDOW_CHARS, 14_000),
  /** 'sections' strategy tuning (see pipeline.ts). */
  triageMinChars: num(process.env.TRIAGE_MIN_CHARS, 40_000),
  extractGroupChars: num(process.env.EXTRACT_GROUP_CHARS, 5_000),
  extractGroupSections: num(process.env.EXTRACT_GROUP_SECTIONS, 1),
  extractConcurrency: num(process.env.EXTRACT_CONCURRENCY, 8),
  ingestWindowChars: num(process.env.CLAUSES_WINDOW_CHARS, 90_000),
}
export const hasModelProvider = () => env.ai.apiKey.length > 0
