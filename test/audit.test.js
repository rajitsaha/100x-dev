'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const { audit } = require('../lib/audit')

function tmp() { return fs.mkdtempSync(path.join(os.tmpdir(), '100x-audit-')) }

function skill(dir, name, description) {
  const target = path.join(dir, name)
  fs.mkdirSync(target, { recursive: true })
  fs.writeFileSync(path.join(target, 'SKILL.md'), `---\nname: ${name}\ndescription: ${description}\n---\n`)
}

test('audit inventories standing context without treating estimates as exact usage', () => {
  const home = tmp(), project = tmp(), repo = tmp()
  skill(path.join(home, '.claude', 'skills'), 'gate', 'Run the gate.')
  fs.mkdirSync(path.join(project, '.cursor', 'rules'), { recursive: true })
  fs.writeFileSync(path.join(project, '.cursor', 'rules', 'gate.mdc'), '---\ndescription: Run the gate.\n---\n')
  fs.writeFileSync(path.join(project, 'AGENTS.md'), 'project rules\n')
  fs.mkdirSync(path.join(home, '.claude'), { recursive: true })
  fs.writeFileSync(path.join(home, '.claude', 'settings.json'), JSON.stringify({
    enabledPlugins: { 'github@x': true },
    hooks: { SessionStart: [{ hooks: [{ command: 'verbose-update' }] }] },
  }))
  fs.mkdirSync(path.join(repo, 'plugins'), { recursive: true })
  fs.writeFileSync(path.join(repo, 'plugins', 'plugins.json'), JSON.stringify({
    plugins: ['github@x'], recommended: {}, manual: [],
  }))

  const report = audit(project, { home, repoRoot: repo })
  assert.equal(report.schema_version, 1)
  assert.equal(report.measurement, 'estimate')
  assert.equal(report.tools.claude.indexed, 1)
  assert.equal(report.tools.cursor.indexed, 1)
  assert.equal(report.instructions[0].file, 'AGENTS.md')
  assert.equal(report.plugins.enabled, 1)
  assert.equal(report.hooks.session_start, 1)
  assert.ok(report.standing_context.estimated_tokens > 0)
})

test('audit tolerates a project with no tool artifacts', () => {
  const report = audit(tmp(), { home: tmp(), repoRoot: tmp() })
  assert.equal(report.standing_context.estimated_tokens, 0)
  assert.equal(report.tools.claude.indexed, 0)
  assert.equal(report.plugins.enabled, 0)
})
