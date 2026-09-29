// What a person confirmed or corrected becomes an example the catalogue learns from: kept under
// INGEST_FEEDBACK_DIR/<namespace>/<type>/<sha8>.json, loaded with the pack's own examples, used
// as few-shot for extraction and as snippets for classification. Nothing is retrained; every
// example is a file a person can read, edit or delete.
import { mkdir, writeFile, readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { env } from './env.js'
import { cacheGet } from './cache.js'
import { invalidatePack, isTypeId, loadPack } from './catalogue.js'
import { recordVerdict } from './metrics.js'
import { dequeue } from './review.js'
import type { SourceText } from './text.js'

export interface Feedback {
  /** The document's sha256 as returned in the extraction response. */
  sha256: string
  /** The type the document turned out to be (the confirmed one, or the corrected one). */
  type: string
  verdict: 'confirmed' | 'corrected'
  /** The output as accepted by the person — the engine's answer, or the corrected version. */
  output?: unknown
  /** What was wrong / what to watch for; shown to the model with the example. */
  note?: string
  /** For a correction: the type the engine had chosen (so its metrics count the miss). */
  from?: string
  mail?: { from?: string; subject?: string }
  /** Head of the document, when the caller has it; otherwise read from the engine's parse cache. */
  snippet?: string
}

const SNIPPET_CHARS = 1_500

export async function recordFeedback(f: Feedback, by: string): Promise<{ path: string; type: string }> {
  if (!env.feedbackDir) throw new Error('INGEST_FEEDBACK_DIR is not set — the engine has nowhere to keep what it learns')
  if (!isTypeId(f.type) || f.type === 'generic') throw new Error('type must be a catalogue type id (<namespace>/<type>)')
  if (!(await loadPack(f.type))) throw new Error(`unknown type ${f.type}`)
  if (!/^[a-f0-9]{64}$/.test(f.sha256 ?? '')) throw new Error('sha256 of the document is required (from the extraction response)')
  let snippet = f.snippet?.trim() ?? ''
  if (!snippet) {
    const parsed = await cacheGet<SourceText>(`parse-${f.sha256}`)
    if (!parsed) throw new Error('the document is no longer in the parse cache — send `snippet` (its opening text) with the feedback')
    snippet = parsed.text
  }
  const dir = join(env.feedbackDir, ...f.type.split('/'))
  await mkdir(dir, { recursive: true })
  const path = join(dir, `${f.sha256.slice(0, 12)}.json`)
  let prior: { at?: string } | null = null
  try { prior = JSON.parse(await readFile(path, 'utf8')) } catch { /* new */ }
  await writeFile(path, JSON.stringify({ snippet: snippet.slice(0, SNIPPET_CHARS), mail: f.mail, output: f.output ?? null, note: f.note, verdict: f.verdict, by, at: new Date().toISOString(), firstAt: prior?.at ?? new Date().toISOString(), sha256: f.sha256 }, null, 2) + '\n')
  invalidatePack()
  void recordVerdict({ type: f.type, verdict: f.verdict, from: f.from })
  void dequeue(f.sha256)
  return { path, type: f.type }
}
