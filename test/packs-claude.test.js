'use strict'

// Verifies adapters/lib/packs.py reconciles settings.json for the claude-code
// platform with per-entry ownership: it removes only what it inserted, survives a
// pack being dropped from the registry, and refuses to overwrite unreadable config.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')
const REGISTRY = path.join(REPO, 'packs', 'packs.json')
const PLUGIN = 'databricks@databricks-agent-skills'
const MARKET = 'databricks-agent-skills'

function setup(settings = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkc-'))
  const settingsFile = path.join(dir, 'settings.json')
  fs.writeFileSync(settingsFile, typeof settings === 'string' ? settings : JSON.stringify(settings))
  return { dir, settingsFile, project: dir }
}

function run(ctx, argv, opts = {}) {
  const r = spawnSync('python3', [
    SCRIPT, ...argv,
    '--settings', ctx.settingsFile,
    '--project', ctx.project,
    '--packs', opts.registry || REGISTRY,
  ], {
    encoding: 'utf8',
    // Force the per-platform path; Task 4 covers the CLI path.
    env: { ...process.env, PRISM_PACKS_WHICH: '{"databricks": false}' },
  })
  if (!opts.allowFailure) assert.equal(r.status, 0, r.stderr)
  return r
}

const settingsOf = (ctx) => JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
const stateFile = (ctx) => path.join(ctx.dir, '.100xprism-packs.json')
const stateOf = (ctx) => JSON.parse(fs.readFileSync(stateFile(ctx), 'utf8'))

test('add wires the marketplace, enables the plugin, and records ownership', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const s = settingsOf(ctx)
  assert.equal(s.enabledPlugins[PLUGIN], true)
  assert.ok(s.extraKnownMarketplaces[MARKET])

  const entry = stateOf(ctx).packs.databricks
  assert.deepEqual(entry.platforms['claude-code'], ['installed'])
  assert.deepEqual(entry.owned.plugins, [PLUGIN])
  assert.equal(entry.owned.marketplace, MARKET)
})

test('add is idempotent and does not lose the ownership record', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const first = settingsOf(ctx)
  run(ctx, ['add', 'databricks'])
  assert.deepEqual(settingsOf(ctx), first)
  // Second add inserts nothing; the record from the first must survive.
  assert.deepEqual(stateOf(ctx).packs.databricks.owned.plugins, [PLUGIN])
})

test('a plugin the user already disabled is neither flipped nor owned nor removed', () => {
  const ctx = setup({ enabledPlugins: { [PLUGIN]: false } })
  run(ctx, ['add', 'databricks'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], false, 'not flipped')
  assert.deepEqual(stateOf(ctx).packs.databricks.owned.plugins, [], 'not claimed')

  run(ctx, ['remove', 'databricks'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], false, 'user entry survives removal')
})

test('a marketplace the user already had is not claimed and not removed', () => {
  const ctx = setup({ extraKnownMarketplaces: { [MARKET]: { source: { source: 'github', repo: 'u/x' } } } })
  run(ctx, ['add', 'databricks'])
  assert.equal(stateOf(ctx).packs.databricks.owned.marketplace, null, 'not claimed')
  assert.deepEqual(
    settingsOf(ctx).extraKnownMarketplaces[MARKET].source.repo, 'u/x', 'not overwritten')

  run(ctx, ['remove', 'databricks'])
  assert.ok(settingsOf(ctx).extraKnownMarketplaces[MARKET], 'user marketplace survives')
})

test('remove reverses only what we inserted', () => {
  const ctx = setup({ enabledPlugins: { 'user-only@m': true } })
  run(ctx, ['add', 'databricks'])
  run(ctx, ['remove', 'databricks'])
  const s = settingsOf(ctx)
  assert.equal(PLUGIN in s.enabledPlugins, false, 'our plugin removed')
  assert.equal(s.enabledPlugins['user-only@m'], true, 'user plugin preserved')
  assert.equal(MARKET in (s.extraKnownMarketplaces || {}), false)
  assert.equal('databricks' in stateOf(ctx).packs, false)
})

test('remove keeps a marketplace another enabled plugin still needs', () => {
  const ctx = setup({ enabledPlugins: { 'other@databricks-agent-skills': true } })
  run(ctx, ['add', 'databricks'])
  run(ctx, ['remove', 'databricks'])
  assert.ok(settingsOf(ctx).extraKnownMarketplaces[MARKET], 'marketplace still in use')
})

test('remove still works after the pack is dropped from the registry', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  const empty = path.join(ctx.dir, 'empty-packs.json')
  fs.writeFileSync(empty, JSON.stringify({ schema: 1, packs: {} }))

  run(ctx, ['remove', 'databricks'], { registry: empty })
  assert.equal(PLUGIN in settingsOf(ctx).enabledPlugins, false, 'reversed from the state record')
  assert.equal('databricks' in stateOf(ctx).packs, false)
})

test('sync re-applies an opted-in pack and prunes one no longer declared', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])

  const s = settingsOf(ctx)
  delete s.enabledPlugins[PLUGIN]
  fs.writeFileSync(ctx.settingsFile, JSON.stringify(s))
  run(ctx, ['sync'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], true, 're-applied')

  const empty = path.join(ctx.dir, 'empty-packs.json')
  fs.writeFileSync(empty, JSON.stringify({ schema: 1, packs: {} }))
  run(ctx, ['sync'], { registry: empty })
  assert.equal(PLUGIN in settingsOf(ctx).enabledPlugins, false, 'pruned')
})

test('refuses to overwrite an unreadable settings.json', () => {
  const ctx = setup('{ this is not json')
  const r = run(ctx, ['add', 'databricks'], { allowFailure: true })
  assert.notEqual(r.status, 0)
  assert.match(r.stderr, /refusing to rewrite/)
  assert.equal(fs.readFileSync(ctx.settingsFile, 'utf8'), '{ this is not json', 'file untouched')
})

test('add rejects an unknown slug', () => {
  const ctx = setup()
  const r = run(ctx, ['add', 'nope'], { allowFailure: true })
  assert.equal(r.status, 1)
  assert.match(r.stderr, /unknown pack 'nope'/)
})
