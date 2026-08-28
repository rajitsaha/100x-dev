'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'scripts', 'context-footprint.js')

test('context footprint reports all adapters and enforces lean must budgets', () => {
  const result = spawnSync('node', [SCRIPT, '--json'], { cwd: REPO, encoding: 'utf8' })
  assert.equal(result.status, 0, result.stderr)
  const report = JSON.parse(result.stdout)
  assert.equal(report.schema_version, 1)
  for (const tool of ['claude', 'cursor', 'codex', 'pi']) {
    assert.ok(report.tools[tool], `${tool} missing`)
    assert.ok(report.tools[tool].must.indexed < 20, `${tool} must index too large`)
    assert.equal(report.tools[tool].must.within_budget, true)
  }
  assert.ok(report.tools.claude.all.estimated_tokens > report.tools.claude.must.estimated_tokens)
})
