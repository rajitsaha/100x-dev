'use strict'

// Round-3 review regressions.
//
// The central correction: a platform can accumulate MORE THAN ONE removal obligation.
// Installing directly (we own settings entries) and later installing through the pack's
// own CLI (which writes files we do not track) are independent mutations. Collapsing
// them to a single ranked status discards one of them, so obligations are now a set.

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

function setup() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pko-'))
  fs.writeFileSync(path.join(dir, 'settings.json'), '{}')
  return { dir, settingsFile: path.join(dir, 'settings.json'), log: path.join(dir, 'commands.log') }
}

function run(ctx, argv, opts = {}) {
  const env = { ...process.env, PRISM_PACKS_WHICH: JSON.stringify(opts.which || { databricks: false }) }
  env.PRISM_PACKS_RUNNER_LOG = ctx.log
  if (opts.failOn) env.PRISM_PACKS_RUNNER_FAIL = opts.failOn
  const r = spawnSync('python3', [
    SCRIPT, ...argv, '--settings', ctx.settingsFile, '--project', ctx.dir,
    '--packs', opts.registry || REGISTRY, '--json',
  ], { encoding: 'utf8', env })
  if (!opts.allowFailure) assert.equal(r.status, 0, r.stderr)
  let messages = []
  try { messages = JSON.parse(r.stdout).messages || [] } catch { /* non-JSON */ }
  return { status: r.status, messages }
}

const entryOf = (ctx) =>
  JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8')).packs.databricks
const commands = (ctx) =>
  fs.existsSync(ctx.log) && fs.readFileSync(ctx.log, 'utf8').trim()
    ? fs.readFileSync(ctx.log, 'utf8').trim().split('\n') : []

// --- Finding 1: independent obligations must both survive -------------------------

test('a direct install followed by a CLI install keeps BOTH obligations', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: false } })
  run(ctx, ['add', 'databricks'], { which: { databricks: true } })

  const obligations = entryOf(ctx).platforms['claude-code']
  assert.ok(Array.isArray(obligations), 'obligations are a set, not a single ranked status')
  assert.ok(obligations.includes('installed'), 'we still own settings entries')
  assert.ok(obligations.includes('cli'), 'the upstream CLI also wrote files')
})

test('removal honours both obligations: reverses ours AND reports the CLI', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: false } })
  run(ctx, ['add', 'databricks'], { which: { databricks: true } })

  const out = run(ctx, ['remove', 'databricks'], { which: { databricks: true } })
  const settings = JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
  assert.equal(PLUGIN in settings.enabledPlugins, false, 'our entries reversed')
  assert.ok(
    out.messages.some((m) => m.startsWith('claude-code:') && /upstream tooling/.test(m)),
    'the CLI obligation is still reported, not swallowed by the direct-install one',
  )
})

// --- Finding 2: a multi-command removal must not repeat completed commands ---------

test('retrying a partly-failed removal resumes instead of repeating', () => {
  const ctx = setup()
  const registry = path.join(ctx.dir, 'multi.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  data.packs.databricks.install.codex.uninstall = ['codex step-one', 'codex step-two']
  fs.writeFileSync(registry, JSON.stringify(data))

  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: true }, registry })
  fs.writeFileSync(ctx.log, '')

  // step-one succeeds, step-two fails.
  run(ctx, ['remove', 'databricks'], {
    which: { databricks: false, codex: true }, registry,
    failOn: 'codex step-two', allowFailure: true,
  })
  assert.deepEqual(commands(ctx), ['codex step-one', 'codex step-two'])

  // Retry must NOT re-run step-one.
  fs.writeFileSync(ctx.log, '')
  run(ctx, ['remove', 'databricks'], { which: { databricks: false, codex: true }, registry })
  assert.deepEqual(commands(ctx), ['codex step-two'], 'resumes at the failed command')
})

// --- Finding 3: nested wrong-shape state must not be discarded --------------------

function fakeHome(state, settings) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pko-'))
  const claude = path.join(home, '.claude')
  fs.mkdirSync(claude, { recursive: true })
  fs.writeFileSync(path.join(claude, 'settings.json'), JSON.stringify(settings))
  fs.writeFileSync(path.join(claude, '.100xprism-packs.json'), JSON.stringify(state))
  return { home, claude }
}

test('uninstall keeps state when packs is the wrong shape', () => {
  const { home, claude } = fakeHome({ schema: 1, packs: [] }, { enabledPlugins: { [PLUGIN]: true } })
  assert.equal(cleanManagedPacks(home).removed, 0)
  assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')),
    'a state file we could not interpret is not evidence that nothing is owned')
})

test('uninstall keeps state when enabledPlugins is the wrong shape', () => {
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: { platforms: { 'claude-code': ['installed'] },
      owned: { plugins: [PLUGIN], marketplace: MARKET }, uninstall: {} } } },
    { enabledPlugins: [], extraKnownMarketplaces: {} },
  )
  assert.equal(cleanManagedPacks(home).removed, 0)
  assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')), 'state kept')
})

test('uninstall skips a malformed pack entry AND keeps the state file', () => {
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: 'not-an-object' } },
    { enabledPlugins: { [PLUGIN]: true } },
  )
  assert.equal(cleanManagedPacks(home).removed, 0)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))
  assert.equal(settings.enabledPlugins[PLUGIN], true, 'nothing removed on a record we cannot read')
  // The earlier version of this test asserted only the settings and so passed
  // vacuously: the state file was deleted anyway, losing the ownership record.
  assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')),
    'a record we could not interpret is not a record we may discard')
})

test('uninstall refuses a pack entry whose owned.plugins is not an array', () => {
  // `plugins` as a string would otherwise be iterated character by character, deleting
  // single-letter keys from enabledPlugins.
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: {
      platforms: { 'claude-code': ['installed'] },
      owned: { plugins: 'abc', marketplace: MARKET },
      uninstall: {},
    } } },
    { enabledPlugins: { a: true, b: true, [PLUGIN]: true }, extraKnownMarketplaces: { [MARKET]: {} } },
  )
  assert.equal(cleanManagedPacks(home).removed, 0)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))
  assert.equal(settings.enabledPlugins.a, true, 'characters were not treated as plugin keys')
  assert.equal(settings.enabledPlugins.b, true)
  assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')), 'state kept')
})

test('uninstall refuses a pack entry whose owned.marketplace is not a string', () => {
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: {
      platforms: { 'claude-code': ['installed'] },
      owned: { plugins: [], marketplace: { nested: true } },
      uninstall: {},
    } } },
    { enabledPlugins: {}, extraKnownMarketplaces: { [MARKET]: {} } },
  )
  assert.equal(cleanManagedPacks(home).removed, 0)
  assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')), 'state kept')
})

// --- The Python path needs the SAME nested-shape guard as lib/uninstall.js --------

function withState(state, settings) {
  const ctx = setup()
  fs.writeFileSync(path.join(ctx.dir, '.100xprism-packs.json'), JSON.stringify(state))
  fs.writeFileSync(ctx.settingsFile, JSON.stringify(settings))
  return ctx
}

test('remove refuses a state whose owned.plugins is not an array', () => {
  // Iterating a string yields characters, which would pop single-letter plugin keys.
  const ctx = withState(
    { schema: 1, packs: { databricks: {
      platforms: { 'claude-code': ['installed'] },
      owned: { plugins: 'abc', marketplace: MARKET }, uninstall: {},
    } } },
    { enabledPlugins: { a: true, b: true }, extraKnownMarketplaces: { [MARKET]: {} } },
  )
  const r = run(ctx, ['remove', 'databricks'], { allowFailure: true })
  assert.notEqual(r.status, 0, 'refuses rather than acting on a record it cannot trust')
  const settings = JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
  assert.equal(settings.enabledPlugins.a, true, 'unrelated keys survive')
  assert.equal(settings.enabledPlugins.b, true)
})

test('add refuses a state with a non-object pack record', () => {
  const ctx = withState({ schema: 1, packs: { databricks: 'nope' } }, {})
  const r = run(ctx, ['add', 'databricks'], { allowFailure: true })
  assert.notEqual(r.status, 0)
  assert.match(
    JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8')).packs.databricks,
    /nope/, 'the unreadable record is preserved, not overwritten',
  )
})

test('sync refuses a state whose packs is not an object', () => {
  const ctx = withState({ schema: 1, packs: [] }, {})
  const r = run(ctx, ['sync'], { allowFailure: true })
  assert.notEqual(r.status, 0)
  assert.deepEqual(
    JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8')).packs, [],
    'left intact for the user to fix',
  )
})

test('the stricter guard still accepts sparse legacy state', () => {
  // A record written by an earlier version: single-string platform value, and no
  // `owned` or `uninstall` keys at all. Validation must accept it, not reject the user.
  const ctx = withState(
    { schema: 1, packs: { databricks: { platforms: { cursor: 'manual' } } } },
    { enabledPlugins: {} },
  )
  const out = run(ctx, ['remove', 'databricks'])
  assert.equal(out.status, 0, 'sparse legacy state is legitimate')
  assert.ok(out.messages.some((m) => m.startsWith('cursor:')), 'its obligation is still honoured')
})

// --- Re-add must not resurrect uninstall commands that already succeeded ----------

test('re-add does not restore checkpointed uninstall commands for an untouched platform', () => {
  const ctx = setup()
  const registry = path.join(ctx.dir, 'multi.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  data.packs.databricks.install.codex.uninstall = ['codex step-one', 'codex step-two']
  fs.writeFileSync(registry, JSON.stringify(data))

  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: true }, registry })
  // step-one succeeds, step-two fails -> the record keeps only step-two.
  run(ctx, ['remove', 'databricks'], {
    which: { databricks: false, codex: true }, registry,
    failOn: 'codex step-two', allowFailure: true,
  })
  assert.deepEqual(entryOf(ctx).uninstall.codex, ['codex step-two'], 'checkpointed')

  // Re-add via the CLI path: codex gains a `cli` obligation but is NOT reinstalled
  // through its commands, so its checkpointed remainder must survive.
  run(ctx, ['add', 'databricks'], { which: { databricks: true }, registry })
  assert.deepEqual(entryOf(ctx).uninstall.codex, ['codex step-two'],
    'a completed command must not be resurrected by an unrelated re-add')
})

test('re-add DOES restore the full command list for a platform it reinstalls', () => {
  const ctx = setup()
  const registry = path.join(ctx.dir, 'multi.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  data.packs.databricks.install.codex.uninstall = ['codex step-one', 'codex step-two']
  fs.writeFileSync(registry, JSON.stringify(data))

  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: true }, registry })
  run(ctx, ['remove', 'databricks'], {
    which: { databricks: false, codex: true }, registry,
    failOn: 'codex step-two', allowFailure: true,
  })
  // Re-installing codex through its own commands genuinely re-creates what step-one
  // undid, so the full inverse list applies again.
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: true }, registry })
  assert.deepEqual(entryOf(ctx).uninstall.codex, ['codex step-one', 'codex step-two'],
    'a genuine reinstall restores the full inverse')
})

// --- Obligations must render as text, not as a Python list repr -------------------

test('status renders obligations readably', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: false } })
  run(ctx, ['add', 'databricks'], { which: { databricks: true } })

  const r = spawnSync('python3', [
    SCRIPT, 'status', '--settings', ctx.settingsFile, '--project', ctx.dir, '--packs', REGISTRY,
  ], { encoding: 'utf8', env: { ...process.env, DATABRICKS_HOST: '' } })
  assert.equal(r.status, 0, r.stderr)
  assert.ok(!/\[|'/.test(r.stdout), `no list repr leaked into user output:\n${r.stdout}`)
  assert.match(r.stdout, /claude-code=installed\+cli/)
})

// --- Finding 4: writes must be atomic ---------------------------------------------

test('a write leaves no partial file behind', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'])
  // Both files must be complete, parseable JSON after a normal run.
  JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
  JSON.parse(fs.readFileSync(path.join(ctx.dir, '.100xprism-packs.json'), 'utf8'))
  // No temp artifacts left in the directory.
  const strays = fs.readdirSync(ctx.dir).filter((f) => f.includes('.tmp'))
  assert.deepEqual(strays, [], 'atomic replace cleans up after itself')
})

// --- Legacy state written by an earlier version must still load -------------------

test('a legacy string status is understood as a single obligation', () => {
  const ctx = setup()
  fs.writeFileSync(path.join(ctx.dir, '.100xprism-packs.json'), JSON.stringify({
    schema: 1,
    packs: {
      databricks: {
        platforms: { 'claude-code': 'installed', cursor: 'manual' },
        owned: { plugins: [PLUGIN], marketplace: MARKET },
        uninstall: {},
      },
    },
  }))
  fs.writeFileSync(ctx.settingsFile, JSON.stringify({
    enabledPlugins: { [PLUGIN]: true }, extraKnownMarketplaces: { [MARKET]: {} },
  }))

  const out = run(ctx, ['remove', 'databricks'])
  const settings = JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
  assert.equal(PLUGIN in settings.enabledPlugins, false, 'legacy record still reversible')
  assert.ok(out.messages.some((m) => m.startsWith('cursor:')), 'legacy manual status still reported')
})
