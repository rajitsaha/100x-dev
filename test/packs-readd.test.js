'use strict'

// Regression suite for the re-review findings on PR #103.
//
// Root cause behind both: removal decided what to reverse from the `platforms` status
// label rather than from the ownership record. `owned` is the truth of what we actually
// inserted, so a status change on re-add must never be able to strand it.

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

function setup() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkra-'))
  const settingsFile = path.join(dir, 'settings.json')
  fs.writeFileSync(settingsFile, '{}')
  return { dir, settingsFile, log: path.join(dir, 'commands.log') }
}

function run(ctx, argv, opts = {}) {
  const env = { ...process.env, PRISM_PACKS_WHICH: JSON.stringify(opts.which || { databricks: false }) }
  env.PRISM_PACKS_RUNNER_LOG = ctx.log
  if (opts.failOn) env.PRISM_PACKS_RUNNER_FAIL = opts.failOn
  const r = spawnSync('python3', [
    SCRIPT, ...argv,
    '--settings', ctx.settingsFile, '--project', ctx.dir, '--packs', REGISTRY, '--json',
  ], { encoding: 'utf8', env })
  if (!opts.allowFailure) assert.equal(r.status, 0, r.stderr)
  let messages = []
  try { messages = JSON.parse(r.stdout).messages || [] } catch { /* non-JSON */ }
  return { status: r.status, messages }
}

const settingsOf = (ctx) => JSON.parse(fs.readFileSync(ctx.settingsFile, 'utf8'))
const statePath = (ctx) => path.join(ctx.dir, '.100xprism-packs.json')
const entryOf = (ctx) => JSON.parse(fs.readFileSync(statePath(ctx), 'utf8')).packs.databricks

// --- Finding 1: re-add must not downgrade a platform we already mutated -----------

test('re-add does not downgrade an installed platform to unavailable', () => {
  const ctx = setup()
  // First add: codex partially installs (a real mutation happened).
  run(ctx, ['add', 'databricks'], {
    which: { databricks: false, codex: true },
    failOn: 'codex plugin add databricks',
  })
  assert.equal(entryOf(ctx).platforms.codex, 'installed')

  // Second add with the codex binary now absent — must NOT forget the mutation.
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: false } })
  assert.equal(entryOf(ctx).platforms.codex, 'installed',
    'a recorded mutation cannot be downgraded by a later failed attempt')

  const out = run(ctx, ['remove', 'databricks'], { which: { databricks: false, codex: false } })
  assert.ok(out.messages.some((m) => m.startsWith('codex:')), 'codex still gets a removal transition')
})

// --- Finding 2: a CLI re-add must not orphan Claude entries we inserted ------------

test('remove reverses owned Claude entries even after the platform flips to cli', () => {
  const ctx = setup()
  // First add via the per-platform path: we insert the plugin and own it.
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: false } })
  assert.deepEqual(entryOf(ctx).owned.plugins, [PLUGIN])
  assert.equal(settingsOf(ctx).enabledPlugins[PLUGIN], true)

  // Second add, now with the Databricks CLI available — the CLI path marks
  // every platform `cli`, including claude-code.
  run(ctx, ['add', 'databricks'], { which: { databricks: true } })

  run(ctx, ['remove', 'databricks'], { which: { databricks: true } })
  const settings = settingsOf(ctx)
  assert.equal(PLUGIN in settings.enabledPlugins, false,
    'the plugin we inserted is reversed from the ownership record, whatever the status says')
  assert.equal(MARKET in (settings.extraKnownMarketplaces || {}), false, 'marketplace too')
})

test('ownership survives a per-platform to cli transition in state', () => {
  const ctx = setup()
  run(ctx, ['add', 'databricks'], { which: { databricks: false, codex: false } })
  run(ctx, ['add', 'databricks'], { which: { databricks: true } })
  assert.deepEqual(entryOf(ctx).owned.plugins, [PLUGIN], 'ownership record preserved across paths')
})

// --- Failed removal must checkpoint what it already reversed ----------------------

test('a failed removal records the transitions it completed before failing', () => {
  const ctx = setup()
  const registry = path.join(ctx.dir, 'with-uninstall.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  data.packs.databricks.install.codex.uninstall = ['codex plugin remove databricks']
  fs.writeFileSync(registry, JSON.stringify(data))

  const withReg = (argv, opts) => {
    const env = { ...process.env, PRISM_PACKS_WHICH: JSON.stringify(opts.which) }
    env.PRISM_PACKS_RUNNER_LOG = ctx.log
    if (opts.failOn) env.PRISM_PACKS_RUNNER_FAIL = opts.failOn
    return spawnSync('python3', [
      SCRIPT, ...argv, '--settings', ctx.settingsFile, '--project', ctx.dir,
      '--packs', registry, '--json',
    ], { encoding: 'utf8', env })
  }

  withReg(['add', 'databricks'], { which: { databricks: false, codex: true } })
  // claude-code sorts before codex, so Claude is reversed first, then codex fails.
  const r = withReg(['remove', 'databricks'], {
    which: { databricks: false, codex: true },
    failOn: 'codex plugin remove databricks',
  })
  assert.notEqual(r.status, 0, 'failed removal exits non-zero')

  const entry = entryOf(ctx)
  assert.deepEqual(entry.owned.plugins, [],
    'Claude entries were already reversed — the record must not claim we still own them')
  assert.equal(entry.owned.marketplace, null)
  assert.equal(entry.platforms['claude-code'], undefined,
    'a completed transition is dropped so a retry does not repeat it')
  assert.equal(entry.platforms.codex, 'installed', 'the failed platform is still owed')
})

// --- Finding 3: do not claim an install when nothing was installed ----------------

test('add reports honestly when no platform could be installed', () => {
  const ctx = setup()
  // No claude-code block reachable, no binaries: nothing happens anywhere.
  const registry = path.join(ctx.dir, 'nothing.json')
  const data = JSON.parse(fs.readFileSync(REGISTRY, 'utf8'))
  delete data.packs.databricks.install['claude-code']
  delete data.packs.databricks.install.cursor
  fs.writeFileSync(registry, JSON.stringify(data))

  const r = spawnSync('python3', [
    SCRIPT, 'add', 'databricks',
    '--settings', ctx.settingsFile, '--project', ctx.dir, '--packs', registry, '--json',
  ], {
    encoding: 'utf8',
    env: { ...process.env, PRISM_PACKS_WHICH: '{"databricks":false,"codex":false}' },
  })
  assert.notEqual(r.status, 0, 'installing nothing is not a success')
  assert.equal(fs.existsSync(statePath(ctx)), false, 'no state recorded for a no-op install')
})
