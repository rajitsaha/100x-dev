'use strict'

// Verifies the install resolution order in adapters/lib/packs.py — prefer the pack's
// own multi-agent CLI, else per-platform blocks — and that every recorded platform
// status has a defined removal transition.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')
const REGISTRY = path.join(REPO, 'packs', 'packs.json')

function setup() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pki-'))
  fs.writeFileSync(path.join(dir, 'settings.json'), '{}')
  return { dir, settingsFile: path.join(dir, 'settings.json'), log: path.join(dir, 'commands.log') }
}

function run(ctx, argv, whichMap, registry) {
  const r = spawnSync('python3', [
    SCRIPT, ...argv,
    '--settings', ctx.settingsFile, '--project', ctx.dir,
    '--packs', registry || REGISTRY, '--json',
  ], {
    encoding: 'utf8',
    env: { ...process.env, PRISM_PACKS_WHICH: JSON.stringify(whichMap), PRISM_PACKS_RUNNER_LOG: ctx.log },
  })
  assert.equal(r.status, 0, r.stderr)
  return JSON.parse(r.stdout)
}

const commands = (ctx) =>
  fs.existsSync(ctx.log) && fs.readFileSync(ctx.log, 'utf8').trim()
    ? fs.readFileSync(ctx.log, 'utf8').trim().split('\n')
    : []
const platforms = (ctx) =>
  JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8')).packs.databricks.platforms

test('prefers the pack CLI when its binary is present', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { databricks: true })
  assert.deepEqual(commands(ctx), ['databricks aitools install'])
  assert.deepEqual(platforms(ctx), { 'claude-code': 'cli', cursor: 'cli', codex: 'cli' })
})

test('falls back to per-platform blocks when the CLI binary is missing', () => {
  const ctx = setup()
  const out = run(ctx, ['add', 'databricks'], { databricks: false, codex: true })
  assert.deepEqual(commands(ctx), [
    'codex plugin marketplace add databricks/databricks-agent-skills',
    'codex plugin add databricks',
  ])
  const p = platforms(ctx)
  assert.equal(p['claude-code'], 'installed', 'claude handled in-process')
  assert.equal(p.codex, 'installed')
  assert.equal(p.cursor, 'manual', 'cursor has no shell installer')
  assert.ok(out.messages.some((m) => m.includes('/add-plugin databricks')), 'prints the cursor command')
})

test('reports a platform as unavailable when its binary is missing', () => {
  const ctx = setup()
  const out = run(ctx, ['add', 'databricks'], { databricks: false, codex: false })
  assert.equal(platforms(ctx).codex, 'unavailable')
  assert.ok(out.messages.some((m) => m.includes('docs.databricks.com')), 'prints the hint')
})

test('removing a shell-installed platform prints guidance when no inverse is declared', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { databricks: false, codex: true })
  const out = run(ctx, ['remove', 'databricks'], { databricks: false, codex: true })
  assert.ok(
    out.messages.some((m) => m.startsWith('codex:') && /no uninstall command/i.test(m)),
    'codex installed-state is not silently forgotten',
  )
})

test('removing a shell-installed platform runs a declared inverse command', () => {
  const ctx = setup()
  const registry = path.join(ctx.dir, 'with-uninstall.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  data.packs.databricks.install.codex.uninstall = ['codex plugin remove databricks']
  fs.writeFileSync(registry, JSON.stringify(data))

  run(ctx, ['add', 'databricks'], { databricks: false, codex: true }, registry)
  fs.writeFileSync(ctx.log, '')
  run(ctx, ['remove', 'databricks'], { databricks: false, codex: true }, registry)
  assert.deepEqual(commands(ctx), ['codex plugin remove databricks'])
})
