import { readFileSync } from 'node:fs'

const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8')) as { version: string }

/** Reported on every result; bump package.json when behaviour changes. */
export const ENGINE_VERSION = `ingest-engine ${pkg.version}`
