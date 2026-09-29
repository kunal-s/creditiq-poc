// Tiny file cache keyed by content hash. Parsing/OCR, extraction results and
// URL downloads are cached so that re-running the same document (rehearsals,
// demos) costs no download, no OCR time and no tokens. Lives under
// server/.cache (gitignored).
import { createHash } from 'node:crypto'
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises'

import { env } from './env.js'
import { pathToFileURL } from 'node:url'
const DIR = pathToFileURL(env.cacheDir.endsWith('/') ? env.cacheDir : `${env.cacheDir}/`)

export function sha256(data: Uint8Array | string): string {
  return createHash('sha256').update(data).digest('hex')
}

export async function cacheGet<T>(key: string): Promise<T | null> {
  try {
    return JSON.parse(await readFile(new URL(`${key}.json`, DIR), 'utf8')) as T
  } catch {
    return null
  }
}

export async function cacheSet(key: string, value: unknown): Promise<void> {
  await mkdir(DIR, { recursive: true })
  await writeFile(new URL(`${key}.json`, DIR), JSON.stringify(value))
}

/** Raw bytes with a max age (downloads). */
export async function cacheGetBytes(key: string, maxAgeMs: number): Promise<Uint8Array | null> {
  try {
    const url = new URL(`${key}.bin`, DIR)
    const s = await stat(url)
    if (Date.now() - s.mtimeMs > maxAgeMs) return null
    return new Uint8Array(await readFile(url))
  } catch {
    return null
  }
}

export async function cacheSetBytes(key: string, bytes: Uint8Array): Promise<void> {
  await mkdir(DIR, { recursive: true })
  await writeFile(new URL(`${key}.bin`, DIR), bytes)
}
