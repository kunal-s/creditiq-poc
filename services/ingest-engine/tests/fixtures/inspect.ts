// Development aid: process one fixture request and print a compact view.
//   npx tsx tests/fixtures/inspect.ts TC-17 [request-index] [--text]
import { readFile, rm } from 'node:fs/promises'
import { join } from 'node:path'
import { createApp } from '../../src/app.js'
import { ConfigStore } from '../../src/config.js'
import type { IngestResult } from '../../src/contract.js'
import { readEnv } from '../../src/env.js'
import { createModelClient } from '../../src/llm/index.js'
import { readFile as readDoc } from '../../src/read/index.js'
import { terminateOcr } from '../../src/read/ocr.js'
import { FIXTURES, formFor, makeDataRoot, type FileSpec } from '../helpers.js'

async function main(): Promise<void> {
  const [tc, idx = '0'] = process.argv.slice(2).filter((a) => !a.startsWith('--'))
  const showText = process.argv.includes('--text')
  const { root, version } = await makeDataRoot()
  const env = { ...readEnv({}), dataRoot: root }
  const app = createApp({ env, configs: new ConfigStore(root), model: createModelClient(env) })
  const spec = JSON.parse(await readFile(join(FIXTURES, tc, 'expected.json'), 'utf8')) as { requests: { name: string; files: FileSpec[] }[] }
  const r = spec.requests[Number(idx)]
  if (showText) {
    for (const f of r.files) {
      const fr = await readDoc(new Uint8Array(await readFile(join(FIXTURES, tc, f.file))), f.content_type, 40)
      for (const p of fr.pages) console.log(`--- ${f.file} p${p.n} ${p.route} conf=${p.ocrConfidence} ${JSON.stringify(p.metrics)}\n${p.text}`)
    }
  }
  const res = await app.request('/v1/process', { method: 'POST', body: await formFor(join(FIXTURES, tc), 'DBG', version, r.files) })
  const out = (await res.json()) as IngestResult
  console.log(JSON.stringify(out.files))
  for (const d of out.documents) {
    console.log(`\n# ${d.file_id} p${d.page_from}-${d.page_to} ${JSON.stringify(d.classification.types)} ${d.classification.exit_tier} ${d.classification.confidence} key=${d.instance_key} dup=${d.duplicate_of_key} unc=${d.split_uncertain}`)
    console.log(`  grades ${d.pages.map((p) => `${p.n}:${p.grade}${p.reasons.length ? `(${p.reasons.join(',')})` : ''}${p.ocr_confidence ?? ''}`).join(' ')}`)
    console.log(`  cand ${JSON.stringify(d.classification.candidates)} defects ${JSON.stringify(d.defects)}`)
    for (const f of d.fields.slice(0, 80)) console.log(`  ${f.field} = ${JSON.stringify(f.value)} raw=${JSON.stringify(f.raw)} p${f.page} ${f.method}${f.missing_reason ? ` MISSING ${f.missing_reason}` : ''}`)
  }
  await terminateOcr()
  await rm(root, { recursive: true, force: true })
}

main().catch((e) => { console.error(e); process.exit(1) })
