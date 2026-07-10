import { execFileSync } from 'node:child_process'
import { readFileSync, unlinkSync } from 'node:fs'

const COMMITTED = new URL('../src/api/schema.d.ts', import.meta.url)
const SCRATCH = new URL('../src/api/.schema.check.d.ts', import.meta.url)

const committed = readFileSync(COMMITTED, 'utf8')
execFileSync(
  'pnpm',
  ['exec', 'openapi-typescript', '../server/openapi.json', '-o', SCRATCH.pathname],
  { stdio: 'inherit' },
)
const fresh = readFileSync(SCRATCH, 'utf8')
unlinkSync(SCRATCH)

if (committed !== fresh) {
  console.error(
    'drift-check: web/src/api/schema.d.ts is stale; run `pnpm run generate:api` in web/ and commit the result',
  )
  process.exit(1)
}

console.log('drift-check: schema.d.ts matches the server OpenAPI spec')
