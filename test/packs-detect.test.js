'use strict'

// Verifies adapters/lib/packs.py detection: file, env, and content predicates match
// at the project root only. Fixtures are built in temp dirs — a fixture committed
// inside this repo would resolve to the 100xprism git toplevel and never match.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')

function fixture(files = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkd-'))
  for (const [name, body] of Object.entries(files)) {
    const target = path.join(dir, name)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.writeFileSync(target, body)
  }
  return dir
}

function detectedSlugs(projectDir, env = {}) {
  const r = spawnSync('python3', [SCRIPT, 'detect', '--project', projectDir, '--json'], {
    encoding: 'utf8',
    env: { ...process.env, DATABRICKS_HOST: '', ...env },
  })
  assert.equal(r.status, 0, r.stderr)
  return JSON.parse(r.stdout).packs.filter((p) => p.detected).map((p) => p.slug)
}

test('matches on a root marker file', () => {
  assert.deepEqual(detectedSlugs(fixture({ 'databricks.yml': '' })), ['databricks'])
})

test('matches on file content', () => {
  assert.deepEqual(
    detectedSlugs(fixture({ 'requirements.txt': 'databricks-sql-connector==3.0.0\n' })),
    ['databricks'],
  )
})

test('matches on an environment variable', () => {
  assert.deepEqual(
    detectedSlugs(fixture({ 'README.md': '# plain' }), { DATABRICKS_HOST: 'https://x.databricks.com' }),
    ['databricks'],
  )
})

test('does not match an unrelated project', () => {
  assert.deepEqual(detectedSlugs(fixture({ 'README.md': '# plain' })), [])
})

test('does not match a marker file nested below the root', () => {
  assert.deepEqual(detectedSlugs(fixture({ 'conf/databricks.yml': '' })), [], 'nested must not match')
})

test('resolves the git toplevel when run from a subdirectory', () => {
  const dir = fixture({ 'databricks.yml': '', 'src/main.py': '' })
  spawnSync('git', ['-C', dir, 'init', '-q'], { encoding: 'utf8' })
  // Detection from src/ must find the marker at the repo root, not miss it.
  assert.deepEqual(detectedSlugs(path.join(dir, 'src')), ['databricks'])
})

test('status lists every declared pack, detected or not', () => {
  const r = spawnSync(
    'python3',
    [SCRIPT, 'status', '--project', fixture({ 'README.md': '# plain' }), '--json'],
    { encoding: 'utf8', env: { ...process.env, DATABRICKS_HOST: '' } },
  )
  assert.equal(r.status, 0, r.stderr)
  const packs = JSON.parse(r.stdout).packs
  assert.equal(packs.length, 1)
  assert.equal(packs[0].slug, 'databricks')
  assert.equal(packs[0].detected, false)
})
