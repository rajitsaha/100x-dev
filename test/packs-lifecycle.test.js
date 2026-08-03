'use strict'

// Verifies uninstall reverses only 100xprism-managed pack entries, counts real
// removals, preserves unreadable settings, and never deletes third-party skill files.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const uninstall = require('../lib/uninstall.js')
const { cleanManagedPacks, preinstallCleanup } = uninstall
const PLUGIN = 'databricks@databricks-agent-skills'
const MARKET = 'databricks-agent-skills'

function fakeHome(state, settings) {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkl-'))
  const claude = path.join(home, '.claude')
  fs.mkdirSync(path.join(claude, 'skills', 'databricks-core'), { recursive: true })
  fs.writeFileSync(path.join(claude, 'skills', 'databricks-core', 'SKILL.md'), '# upstream')
  fs.writeFileSync(
    path.join(claude, 'settings.json'),
    typeof settings === 'string' ? settings : JSON.stringify(settings),
  )
  if (state) fs.writeFileSync(path.join(claude, '.100xprism-packs.json'), JSON.stringify(state))
  return { home, claude }
}

const managedState = (owned) => ({
  schema: 1,
  packs: { databricks: { platforms: { 'claude-code': 'installed' }, owned, uninstall: {} } },
})

test('removes owned plugins and the state file', () => {
  const { home, claude } = fakeHome(
    managedState({ plugins: [PLUGIN], marketplace: MARKET }),
    { enabledPlugins: { [PLUGIN]: true, 'user-only@m': true }, extraKnownMarketplaces: { [MARKET]: {} } },
  )
  const result = cleanManagedPacks(home)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))

  assert.equal(result.removed, 1)
  assert.equal(PLUGIN in settings.enabledPlugins, false)
  assert.equal(settings.enabledPlugins['user-only@m'], true, 'user plugin preserved')
  assert.equal(MARKET in settings.extraKnownMarketplaces, false)
  assert.equal(fs.existsSync(path.join(claude, '.100xprism-packs.json')), false)
})

test('counts only plugins that were actually present', () => {
  // The owned record names a plugin that is no longer in settings — a bare `delete`
  // returns true for absent keys, so a naive counter would over-report here.
  const { home } = fakeHome(managedState({ plugins: [PLUGIN], marketplace: null }), { enabledPlugins: {} })
  assert.equal(cleanManagedPacks(home).removed, 0)
})

test('does not touch a plugin we never claimed', () => {
  const { home, claude } = fakeHome(
    managedState({ plugins: [], marketplace: null }),
    { enabledPlugins: { [PLUGIN]: false } },
  )
  cleanManagedPacks(home)
  const settings = JSON.parse(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'))
  assert.equal(settings.enabledPlugins[PLUGIN], false, 'user-disabled entry survives')
})

test('preserves an unreadable settings.json and keeps the state file for recovery', () => {
  const { home, claude } = fakeHome(managedState({ plugins: [PLUGIN], marketplace: MARKET }), '{ broken')
  const result = cleanManagedPacks(home)
  assert.equal(result.removed, 0)
  assert.equal(fs.readFileSync(path.join(claude, 'settings.json'), 'utf8'), '{ broken', 'untouched')
  assert.ok(fs.existsSync(path.join(claude, '.100xprism-packs.json')), 'state kept for recovery')
})

test('never deletes third-party skill files', () => {
  const { home, claude } = fakeHome(
    { schema: 1, packs: { databricks: { platforms: { 'claude-code': 'cli' }, owned: {}, uninstall: {} } } },
    { enabledPlugins: {} },
  )
  cleanManagedPacks(home)
  assert.ok(
    fs.existsSync(path.join(claude, 'skills', 'databricks-core', 'SKILL.md')),
    'CLI-installed skills left on disk',
  )
})

test('is a no-op when no packs were ever installed', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-pkl-'))
  assert.equal(cleanManagedPacks(home).removed, 0)
})

test('preinstallCleanup does not clear pack state', () => {
  // install.sh runs preinstall cleanup BEFORE installing plugins; clearing pack state
  // there would uninstall every opted-in pack on each install.
  assert.ok(!/cleanManagedPacks/.test(preinstallCleanup.toString()), 'not wired into preinstall')
})
