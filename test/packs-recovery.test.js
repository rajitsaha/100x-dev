'use strict'

// Regression suite for the review findings on PR #103. Each test names the failure it
// pins down: state that gets silently discarded after a partial install, a registry-drop
// sync, or a failed uninstall — and config shapes that must never be overwritten.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const SCRIPT = path.join(REPO, 'adapters', 'lib', 'packs.py')
const REGISTRY = path.join(REPO, 'packs', 'packs.json')
const { cleanManagedPacks } = require('../lib/uninstall.js')
const PLUGIN = 'databricks@databricks-agent-skills'
const MARKET = 'databricks-agent-skills'

function setup(settings = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkr-'))
  const settingsFile = path.join(dir, 'settings.json')
  fs.writeFileSync(settingsFile, typeof settings === 'string' ? settings : JSON.stringify(settings))
  return { dir, settingsFile, log: path.join(dir, 'commands.log') }
}

function run(ctx, argv, opts = {}) {
  const env = { ...process.env, PRISM_PACKS_WHICH: JSON.stringify(opts.which || { databricks: false }) }
  if (!opts.noLog) env.PRISM_PACKS_RUNNER_LOG = ctx.log
  if (opts.failOn) env.PRISM_PACKS_RUNNER_FAIL = opts.failOn
  const r = spawnSync('python3', [
    SCRIPT, ...argv,
    '--settings', ctx.settingsFile, '--project', ctx.dir,
    '--packs', opts.registry || REGISTRY, '--json',
  ], { encoding: 'utf8', env })
  if (!opts.allowFailure) assert.equal(r.status, 0, r.stderr)
  // Expose the helper's JSON payload alongside the raw spawn result.
  let messages = []
  try { messages = JSON.parse(r.stdout).messages || [] } catch { /* non-JSON output */ }
  return { status: r.status, stdout: r.stdout, stderr: r.stderr, messages }
}

const stateOf = (ctx) => JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8'))
const settingsOf = (ctx) => JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
const emptyRegistry = (ctx) => {
  const p = path.join(ctx.dir, 'empty.json')
  fs.writeFileSync(p, JSON.stringify({ schema: 1, packs: {} }))
  return p
}

// --- Finding 1: partial shell install must stay removable ------------------------

test('a partially-completed shell install is recorded as installed, not unavailable', () => {
  const ctx = setup()
  // First codex command succeeds, second fails: the marketplace-add already mutated
  // the user's system, so the platform MUST carry a removal transition.
  const out = run(ctx, ['add', 'databricks'], {
    which: { databricks: false, codex: true },
    failOn: 'codex plugin add databricks',
  })
  assert.deepEqual(stateOf(ctx).packs.databricks.platforms.codex, ['installed'],
    'a mutation happened, so it must be reversible')
  assert.ok(out.messages.some((m) => m.includes('partially')), 'the partial state is reported')
})

// --- Finding 2: sync prune must run the full removal path -------------------------

test('sync prune runs every removal transition, not just claude-code', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: true } })
  const out = run(ctx, ['sync'], { which: { databricks: false, codex: true }, registry: emptyRegistry(ctx) })

  assert.ok(out.messages.some((m) => m.startsWith('codex:')), 'codex obligation surfaced')
  assert.ok(out.messages.some((m) => m.startsWith('cursor:')), 'cursor obligation surfaced')
  assert.equal(PLUGIN in settingsOf(ctx).enabledPlugins, false, 'claude entries still reversed')
})

test('sync prune of a cli-installed pack does not claim it was removed', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { which: { databricks: true } })
  const out = run(ctx, ['sync'], { which: { databricks: true }, registry: emptyRegistry(ctx) })
  assert.ok(
    out.messages.some((m) => /upstream tooling/.test(m)),
    'a CLI install is not something sync can remove — say so',
  )
})

// --- Finding 3: a failed uninstall must keep the state needed to retry -------------

test('a failed inverse command keeps the pack state for a retry', () => {
  const ctx = setup()
  const registry = path.join(ctx.dir, 'with-uninstall.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  data.packs.databricks.install.codex.uninstall = ['codex plugin remove databricks']
  fs.writeFileSync(registry, JSON.stringify(data))

  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: true }, registry })
  const r = run(ctx, ['remove', 'databricks'], {
    which: { databricks: false, codex: true },
    registry,
    failOn: 'codex plugin remove databricks',
    allowFailure: true,
  })
  assert.notEqual(r.status, 0, 'a failed removal is not a success')
  assert.ok('databricks' in stateOf(ctx).packs, 'state kept so the user can retry')
})

// --- Finding 4: valid-but-wrong-shape settings must not be replaced ----------------

for (const shape of ['[]', 'null', '"a string"', '42']) {
  test(`refuses to overwrite settings.json containing ${shape}`, () => {
    const ctx = setup(shape)
    const r = run(ctx, ['add', 'databricks'], { allowFailure: true })
    assert.notEqual(r.status, 0)
    assert.equal(fs.readFileSync(ctx.settingsFile, 'utf8'), shape, 'file untouched')
  })
}

// --- Finding 6: malformed pack state must not be silently discarded ----------------

test('refuses to overwrite an unreadable pack state file', () => {
  const ctx = setup()
  const state = path.join(ctx.dir, '.100xprism-packs.json')
  fs.writeFileSync(state, '{ not json')
  const r = run(ctx, ['add', 'databricks'], { allowFailure: true })
  assert.notEqual(r.status, 0)
  assert.equal(fs.readFileSync(state, 'utf8'), '{ not json', 'ownership records preserved')
})

// --- Finding 7: detect must print nothing when nothing matched --------------------

test('detect prints nothing when no pack matches', () => {
  const ctx = setup()
  const r = spawnSync('python3', [
    SCRIPT, 'detect', '--settings', ctx.settingsFile, '--project', ctx.dir, '--packs', REGISTRY,
  ], { encoding: 'utf8', env: { ...process.env, DATABRICKS_HOST: '' } })
  assert.equal(r.status, 0, r.stderr)
  assert.equal(r.stdout.trim(), '', 'empty output keeps install.sh from showing an empty section')
})

// --- Finding 5: marketplace-only cleanup must be persisted ------------------------

test('uninstall persists a marketplace-only removal', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkr-'))
  const claude = path.join(home, '.claude')
  fs.mkdirSync(claude, { recursive: true })
  // We claimed the marketplace but not the plugin (the user already had it listed).
  fs.writeFileSync(path.join(claude, '.100xprism-packs.json'), JSON.stringify({
    schema: 1,
    packs: {
      databricks: {
        platforms: { 'claude-code': ['installed'] },
        owned: { plugins: [], marketplace: MARKET },
        uninstall: {},
      },
    },
  }))
  fs.writeFileSync(path.join(claude, 'settings.json'), JSON.stringify({
    enabledPlugins: {}, extraKnownMarketplaces: { [MARKET]: {} },
  }))

  cleanManagedPacks(home)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))
  assert.equal(MARKET in settings.extraKnownMarketplaces, false,
    'marketplace removal written to disk, not just in memory')
})

// --- uninstall must apply the same shape guard as packs.py -------------------------

for (const shape of ['[]', 'null', '"a string"', '42']) {
  test(`uninstall refuses to act on settings.json containing ${shape}`, () => {
    const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkr-'))
    const claude = path.join(home, '.claude')
    fs.mkdirSync(claude, { recursive: true })
    fs.writeFileSync(path.join(claude, 'settings.json'), shape)
    fs.writeFileSync(path.join(claude, '.100xprism-packs.json'), JSON.stringify({
      schema: 1,
      packs: {
        databricks: {
          platforms: { 'claude-code': ['installed'] },
          owned: { plugins: [PLUGIN], marketplace: MARKET },
          uninstall: {},
        },
      },
    }))

    // Must not throw, must not rewrite, must not discard the ownership record.
    const result = cleanManagedPacks(home)
    assert.equal(result.removed, 0)
    assert.equal(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'), shape, 'untouched')
    assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')), 'state kept for recovery')
  })
}

test('uninstall ignores a pack state file of the wrong shape', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkr-'))
  const claude = path.join(home, '.claude')
  fs.mkdirSync(claude, { recursive: true })
  fs.writeFileSync(path.join(claude, 'settings.json'), JSON.stringify({ enabledPlugins: {} }))
  fs.writeFileSync(path.join(claude, '.100xprism-packs.json'), '[]')
  assert.equal(cleanManagedPacks(home).removed, 0, 'no crash')
})

// --- Detection really is read-only ------------------------------------------------

test('detect writes nothing at all', () => {
  const ctx = setup({ enabledPlugins: { keep: true } })
  const before = fs.readFileSync(ctx.settingsFile, 'utf8')
  run(ctx, ['detect'], {})
  assert.equal(fs.readFileSync(ctx.settingsFile, 'utf8'), before, 'settings untouched')
  assert.equal(fs.existsSync(path.join(ctx.dir, '.100xprism-packs.json')), false, 'no state written')
  assert.equal(fs.existsSync(ctx.log), false, 'no commands run')
})

// --- Ownership: a pre-enabled plugin is not claimed -------------------------------

test('a plugin the user already enabled is not claimed and survives removal', () => {
  const ctx = setup({ enabledPlugins: { [PLUGIN]: true } })
  run(ctx, ['add', 'databricks'])
  assert.deepEqual(stateOf(ctx).packs.databricks.owned.plugins, [], 'not claimed')
  run(ctx, ['remove', 'databricks'])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], true, 'user entry survives')
})
