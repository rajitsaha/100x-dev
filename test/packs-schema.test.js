'use strict'

// Verifies packs/packs.json parses and that scripts/meta-check.py rejects malformed
// pack declarations. Every negative case runs against a TEMPORARY registry passed via
// --packs: node --test runs files concurrently, so mutating the tracked packs.json in
// place would race with the suites that read it.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const PACKS = path.join(REPO, 'packs', 'packs.json')
const META = path.join(REPO, 'scripts', 'meta-check.py')

function metaCheck(registryPath) {
  const argv = registryPath ? [META, '--packs', registryPath] : [META]
  return spawnSync('python3', argv, { cwd: REPO, encoding: 'utf8' })
}

// Writes a mutated copy to a temp file and validates THAT — never the tracked file.
function withTempRegistry(mutate) {
  const data = JSON.parse(fs.readFileSync(PACKS, 'utf8'))
  mutate(data)
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pks-'))
  const file = path.join(dir, 'packs.json')
  fs.writeFileSync(file, JSON.stringify(data, null, 2) + '\n')
  return metaCheck(file)
}

test('the shipped registry is valid', () => {
  const data = JSON.parse(fs.readFileSync(PACKS, 'utf8'))
  assert.equal(data.schema, 1)
  assert.ok(data.packs.databricks, 'databricks pack declared')
  assert.equal(metaCheck().status, 0)
})

test('rejects an unknown install platform key', () => {
  const r = withTempRegistry((d) => { d.packs.databricks.install.antigravity = { manual: ['x'] } })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /unknown install key 'antigravity'/)
})

test('rejects a missing required field', () => {
  const r = withTempRegistry((d) => { delete d.packs.databricks.source })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /missing required key `source`/)
})

test('rejects a nested detect path', () => {
  const r = withTempRegistry((d) => { d.packs.databricks.detect.files.push('conf/databricks.yml') })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /detect path .* must be a bare filename/)
})

test('rejects an uncompilable detect pattern', () => {
  const r = withTempRegistry((d) => { d.packs.databricks.detect.contains[0].pattern = '([' })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /pattern invalid/)
})

test('the tracked registry is left untouched by the negative cases', () => {
  assert.equal(metaCheck().status, 0, 'real registry still valid after temp-file tests')
})
