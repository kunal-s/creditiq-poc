// Record and replay (AD-5). Modes:
//   record  call live, store the answer, return it
//   replay  answer only from recordings; a miss is an explicit error
//   live    call live, store nothing
// Refusals and errors are never recorded as answers.
import { createHash } from 'node:crypto'
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import type { ModelMode } from '../env.js'
import { assertNoSampling, canonicalJson, ModelError, type ModelRequest, type Provider } from './provider.js'

export interface Recording {
  key: string
  provider: string
  model: string
  task: string
  request: unknown
  response: unknown
}

export function recordingKey(provider: string, model: string, body: unknown): string {
  return createHash('sha256').update(canonicalJson({ provider, model, body })).digest('hex')
}

export class ModelClient {
  constructor(public provider: Provider, public mode: ModelMode, private dataRoot: string) {}

  get name(): string { return this.provider.name }

  private path(key: string): string { return join(this.dataRoot, 'recordings', this.provider.name, `${key}.json`) }

  keyFor(req: ModelRequest): string {
    const call = this.provider.build(req)
    return recordingKey(this.provider.name, this.provider.model, call.body)
  }

  async call(req: ModelRequest): Promise<unknown> {
    const call = this.provider.build(req)
    assertNoSampling(call.body)
    const key = recordingKey(this.provider.name, this.provider.model, call.body)
    if (this.mode === 'replay') {
      let rec: Recording
      try { rec = JSON.parse(await readFile(this.path(key), 'utf8')) as Recording } catch {
        throw new ModelError('replay_miss', `no recording for ${this.provider.name} ${req.task} call ${key.slice(0, 12)}`)
      }
      return call.parse(rec.response)
    }
    const response = await call.send(call.body)
    // parse() throws on a refusal or a malformed answer: nothing is stored then.
    const answer = call.parse(response)
    if (this.mode === 'record') {
      const rec: Recording = { key, provider: this.provider.name, model: this.provider.model, task: req.task, request: call.body, response }
      await mkdir(join(this.dataRoot, 'recordings', this.provider.name), { recursive: true })
      const tmp = `${this.path(key)}.tmp`
      await writeFile(tmp, JSON.stringify(rec, null, 2))
      await rename(tmp, this.path(key))
    }
    return answer
  }
}

export { ModelError }
