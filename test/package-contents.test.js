'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')

test('npm package excludes caches and test-only Python files', () => {
  const result = spawnSync('npm', ['pack', '--dry-run', '--json'], { cwd: REPO, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  const start = result.stdout.indexOf('[\n')
  assert.ok(start >= 0, result.stdout)
  const rows = JSON.parse(result.stdout.slice(start))
  const files = rows[0].files.map(row => row.path)
  assert.equal(files.some(file => file.includes('__pycache__') || file.endsWith('.pyc')), false)
  assert.equal(files.some(file => /^scripts\/test_.*\.py$/.test(file)), false)
  assert.ok(files.includes('scripts/token_report.py'))
  assert.ok(files.includes('scripts/adapters/registry.py'))
})
