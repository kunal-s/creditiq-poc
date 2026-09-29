// Shared test plumbing: a temporary data root with the published CreditIQ
// configuration, the stub recordings, and a way to post fixtures to the app.
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { cp, mkdir, mkdtemp, readdir, readFile, writeFile } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'

export const PKG = fileURLToPath(new URL('..', import.meta.url))
export const REPO = resolve(PKG, '../..')
export const FIXTURES = join(PKG, 'tests', 'fixtures')

/**
 * Publish config/ into `root` the way CreditIQ does (engine.cli config publish).
 * Without the Python environment, the YAML is converted directly: the loader
 * fills the same defaults the publisher would.
 */
export async function publishConfig(root: string): Promise<string> {
  const py = join(REPO, '.venv', 'bin', 'python')
  if (existsSync(py)) {
    const r = spawnSync(py, ['-m', 'engine.cli', 'config', 'publish', '--author', 'ingest-tests', '--data-root', root], { cwd: REPO, encoding: 'utf8' })
    if (r.status === 0) {
      const rec = JSON.parse(r.stdout.slice(r.stdout.indexOf('{'))) as { version: string }
      return rec.version
    }
  }
  const sections: Record<string, unknown> = {}
  for (const name of ['document_types', 'quality', 'confidence']) sections[name] = parse(await readFile(join(REPO, 'config', `${name}.yaml`), 'utf8'))
  for (const f of (await readdir(join(REPO, 'config', 'dictionaries'))).filter((x) => x.endsWith('.yaml'))) {
    const d = parse(await readFile(join(REPO, 'config', 'dictionaries', f), 'utf8')) as { id: string }
    sections[`dictionary.${d.id}`] = d
  }
  const version = createHash('sha256').update(JSON.stringify(sections)).digest('hex')
  const dir = join(root, 'config_store', 'versions', version)
  await mkdir(dir, { recursive: true })
  for (const [k, v] of Object.entries(sections)) await writeFile(join(dir, `${k}.json`), JSON.stringify(v))
  return version
}

export async function makeDataRoot(withRecordings = true): Promise<{ root: string; version: string }> {
  const root = await mkdtemp(join(tmpdir(), 'ciq-ingest-test-'))
  const version = await publishConfig(root)
  const rec = join(FIXTURES, 'recordings')
  if (withRecordings && existsSync(rec)) await cp(rec, join(root, 'recordings'), { recursive: true })
  return { root, version }
}

export interface FileSpec { file: string; original_name: string; label_hint?: string | null; content_type: string }

export async function formFor(tcDir: string, caseRef: string, version: string, files: FileSpec[]): Promise<FormData> {
  const form = new FormData()
  const reqFiles = []
  let i = 0
  const parts: [string, Blob][] = []
  for (const f of files) {
    const bytes = await readFile(join(tcDir, f.file))
    const id = `f${++i}`
    reqFiles.push({ file_id: id, sha256: createHash('sha256').update(bytes).digest('hex'), original_name: f.original_name, content_type: f.content_type, label_hint: f.label_hint ?? null })
    parts.push([id, new Blob([bytes], { type: f.content_type })])
  }
  form.set('request', JSON.stringify({ case_ref: caseRef, config_version: version, files: reqFiles }))
  for (const [id, blob] of parts) form.set(id, blob, id)
  return form
}
