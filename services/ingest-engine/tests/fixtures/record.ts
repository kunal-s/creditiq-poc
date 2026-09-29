// Writes tests/fixtures/recordings/stub/ from the hand-written answers:
// every fixture request is processed with the stub provider in record mode,
// so each model call the tests will make has a recording to replay.
//   npx tsx tests/fixtures/record.ts
import { readdir, readFile, rm, cp, mkdir } from 'node:fs/promises'
import { existsSync } from 'node:fs'
import { join } from 'node:path'
import { createApp } from '../../src/app.js'
import { ConfigStore } from '../../src/config.js'
import { readEnv } from '../../src/env.js'
import { ModelClient } from '../../src/llm/index.js'
import { stubProvider } from '../../src/llm/stub.js'
import { terminateOcr } from '../../src/read/ocr.js'
import { FIXTURES, formFor, makeDataRoot, type FileSpec } from '../helpers.js'
import { answer } from './model-answers.js'

async function main(): Promise<void> {
  const { root, version } = await makeDataRoot(false)
  const env = { ...readEnv({}), dataRoot: root }
  const model = new ModelClient(stubProvider(answer), 'record', root)
  const app = createApp({ env, configs: new ConfigStore(root), model })
  for (const tc of (await readdir(FIXTURES)).filter((d) => d.startsWith('TC-')).sort()) {
    const spec = JSON.parse(await readFile(join(FIXTURES, tc, 'expected.json'), 'utf8')) as { requests: { name: string; files: FileSpec[] }[] }
    for (const r of spec.requests) {
      const res = await app.request('/v1/process', { method: 'POST', body: await formFor(join(FIXTURES, tc), `REC-${tc}`, version, r.files) })
      console.log(`${tc} ${r.name}: ${res.status}`)
    }
  }
  const out = join(FIXTURES, 'recordings')
  await rm(out, { recursive: true, force: true })
  if (existsSync(join(root, 'recordings'))) {
    await mkdir(out, { recursive: true })
    await cp(join(root, 'recordings'), out, { recursive: true })
  }
  console.log(`recordings: ${existsSync(join(out, 'stub')) ? (await readdir(join(out, 'stub'))).length : 0}`)
  await terminateOcr()
  await rm(root, { recursive: true, force: true })
}

main().catch((e) => { console.error(e); process.exit(1) })
