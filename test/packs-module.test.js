'use strict'

// Verifies modules/pack/SKILL.md is a well-formed on-demand slash-command module that
// delegates to adapters/lib/packs.py, routes arguments through a validated case
// statement, and quotes them.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SKILL = path.join(REPO, 'modules', 'pack', 'SKILL.md')
const read = () => fs.readFileSync(SKILL, 'utf8')

test('frontmatter declares the expected routing', () => {
  const text = read()
  assert.match(text, /^---\n/)
  for (const line of ['name: pack', 'tier: on-demand', 'model: haiku', 'slash_command: /pack']) {
    assert.ok(text.includes(`\n${line}\n`), `frontmatter has "${line}"`)
  }
})

test('delegates to the helper rather than reimplementing install logic', () => {
  const text = read()
  assert.match(text, /adapters\/lib\/packs\.py/)
  assert.ok(!/enabledPlugins/.test(text), 'must not touch settings.json directly')
})

test('routes every subcommand through an explicit case statement', () => {
  const text = read()
  // Each supported invocation must appear as a case arm that assigns SUB.
  for (const [arm, sub] of [['""', 'status'], ['detect', 'detect'], ['add', 'add'], ['remove', 'remove']]) {
    const pattern = new RegExp(`${arm}\\)[^\\n]*SUB=["']?${sub}`)
    assert.match(text, pattern, `case arm ${arm} assigns SUB=${sub}`)
  }
  assert.match(text, /\*\)/, 'has a default arm that rejects unknown input')
})

test('quotes the slug when invoking the helper', () => {
  const text = read()
  assert.ok(!/\$SLUG(?!")/.test(text.replace(/"\$SLUG"/g, '')), 'SLUG is always quoted')
  assert.match(text, /"\$SLUG"/)
})

test('resolves the helper for npm-global installs too', () => {
  assert.match(read(), /npm root -g/)
})

test('trigger-overlap check still passes in strict mode', () => {
  const r = spawnSync('python3', [path.join(REPO, 'scripts', 'trigger-overlap.py'), '--strict'], {
    cwd: REPO, encoding: 'utf8',
  })
  assert.equal(r.status, 0, r.stdout + r.stderr)
})
