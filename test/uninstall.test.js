'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { cleanClaudeSessionHooks, cleanShellStartup, isSafe100xLink, removeCommandLinks } = require('../lib/uninstall')

function tmpHome() {
  return fs.mkdtempSync(path.join(os.tmpdir(), '100xprism-uninstall-'))
}

test('isSafe100xLink only allows exact 100x command symlinks', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), '100xprism-links-'))
  assert.equal(
    isSafe100xLink(path.join(dir, '100xprism'), '/Users/me/100xprism/bin/100xprism.js'),
    true,
  )
  assert.equal(
    isSafe100xLink(path.join(dir, '100x-dev'), '/missing/target'),
    true,
  )
  assert.equal(
    isSafe100xLink(path.join(dir, 'node'), '/Users/me/100xprism/bin/100xprism.js'),
    false,
  )
  assert.equal(
    isSafe100xLink(path.join(dir, '100xprism'), process.execPath),
    false,
  )
})

test('stale-only command cleanup preserves live npm links', () => {
  const home = tmpHome()
  const binDir = path.join(home, '.local', 'share', 'mise', 'installs', 'node', '24.0.0', 'bin')
  fs.mkdirSync(binDir, { recursive: true })
  const liveTarget = path.join(home, '.local', 'share', 'mise', 'installs', 'node', '24.0.0', 'lib', 'node_modules', '100xprism', 'bin', '100xprism.js')
  fs.mkdirSync(path.dirname(liveTarget), { recursive: true })
  fs.writeFileSync(liveTarget, '#!/usr/bin/env node\n')

  const liveLink = path.join(binDir, '100xprism')
  const staleLink = path.join(binDir, '100x-dev')
  fs.symlinkSync('../lib/node_modules/100xprism/bin/100xprism.js', liveLink)
  fs.symlinkSync('/Users/me/100x-dev/bin/100xprism.js', staleLink)

  const removed = removeCommandLinks(home, { staleOnly: true })
  assert.equal(fs.existsSync(liveLink), true)
  assert.equal(fs.existsSync(staleLink), false)
  assert.equal(removed.length, 1)
})

test('command cleanup warns instead of aborting on an unwritable bin directory', { skip: process.platform === 'win32' }, () => {
  const home = tmpHome()
  const binDir = path.join(home, '.local', 'share', 'mise', 'installs', 'node', '24.0.0', 'bin')
  fs.mkdirSync(binDir, { recursive: true })
  const link = path.join(binDir, '100x-dev')
  fs.symlinkSync('/missing/100x-dev/bin/100xprism.js', link)
  fs.chmodSync(binDir, 0o555)

  const warnings = []
  const originalWarn = console.warn
  console.warn = message => warnings.push(message)
  try {
    assert.doesNotThrow(() => removeCommandLinks(home, { staleOnly: true }))
    assert.equal(fs.lstatSync(link).isSymbolicLink(), true)
  } finally {
    console.warn = originalWarn
    fs.chmodSync(binDir, 0o755)
  }

  assert.equal(warnings.length, 1)
  assert.match(warnings[0], /could not remove stale command link/)
})

test('CLI cleanup preserves a healthy launcher', () => {
  const home = tmpHome()
  const binDir = path.join(home, '.local', 'share', 'mise', 'installs', 'node', '24.0.0', 'bin')
  const target = path.join(home, '.local', 'share', 'mise', 'installs', 'node', '24.0.0', 'lib', 'node_modules', '100xprism', 'bin', '100xprism.js')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.mkdirSync(binDir, { recursive: true })
  fs.writeFileSync(target, '#!/usr/bin/env node\n')
  const link = path.join(binDir, '100xprism')
  fs.symlinkSync('../lib/node_modules/100xprism/bin/100xprism.js', link)

  execFileSync(process.execPath, [path.join(__dirname, '..', 'lib', 'uninstall.js')], {
    env: { ...process.env, HOME: home, npm_config_prefix: '' },
    stdio: 'pipe',
  })

  assert.equal(fs.existsSync(link), true)
})

test('npm preuninstall cleanup removes a healthy package launcher', () => {
  const home = tmpHome()
  const prefix = path.join(home, 'npm')
  const target = path.join(prefix, 'lib', 'node_modules', '100xprism', 'bin', '100xprism.js')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.mkdirSync(path.join(prefix, 'bin'), { recursive: true })
  fs.writeFileSync(target, '#!/usr/bin/env node\n')
  const link = path.join(prefix, 'bin', '100xprism')
  fs.symlinkSync('../lib/node_modules/100xprism/bin/100xprism.js', link)

  execFileSync(process.execPath, [path.join(__dirname, '..', 'lib', 'uninstall.js'), '--remove-live-links'], {
    env: { ...process.env, HOME: home, npm_config_prefix: prefix },
    stdio: 'pipe',
  })

  assert.equal(fs.existsSync(link), false)
})

test('cleanShellStartup removes only 100x startup entries', () => {
  const home = tmpHome()
  const zshrc = path.join(home, '.zshrc')
  const bashProfile = path.join(home, '.bash_profile')

  fs.writeFileSync(zshrc, [
    'export KEEP=1',
    '# 100xPrism aliases',
    'source /Users/me/100xprism/shell/aliases.sh',
    '[ -f "$DEV_100X_HOME/shell/aliases.sh" ] && source "$DEV_100X_HOME/shell/aliases.sh"',
    'alias mine=true',
    '',
  ].join('\n'))
  fs.writeFileSync(bashProfile, [
    '# 100x Dev aliases',
    'source /Users/me/100x-dev/shell/aliases.sh',
    'export KEEP_BASH=1',
    '',
  ].join('\n'))

  const cleaned = cleanShellStartup(home).map(file => path.basename(file)).sort()
  assert.deepEqual(cleaned, ['.bash_profile', '.zshrc'])
  assert.equal(fs.readFileSync(zshrc, 'utf8'), 'export KEEP=1\nalias mine=true\n')
  assert.equal(fs.readFileSync(bashProfile, 'utf8'), 'export KEEP_BASH=1\n')
})

test('cleanClaudeSessionHooks removes 100x update-check hooks only', () => {
  const home = tmpHome()
  const claude = path.join(home, '.claude')
  fs.mkdirSync(claude, { recursive: true })
  const settings = path.join(claude, 'settings.json')
  fs.writeFileSync(settings, JSON.stringify({
    hooks: {
      SessionStart: [
        {
          matcher: '',
          hooks: [
            { type: 'command', command: '$HOME/100xprism/shell/check-update.sh --claude-hook' },
            { type: 'command', command: 'echo keep' },
          ],
        },
        {
          matcher: '',
          hooks: [
            { type: 'command', command: '$HOME/100x-dev/shell/check-update.sh --claude-hook' },
          ],
        },
      ],
    },
  }, null, 2))

  const result = cleanClaudeSessionHooks(home)
  assert.equal(result.removed, 2)
  const after = JSON.parse(fs.readFileSync(settings, 'utf8'))
  assert.deepEqual(after.hooks.SessionStart, [
    { matcher: '', hooks: [{ type: 'command', command: 'echo keep' }] },
  ])
})

test('cleanClaudeSessionHooks warns and preserves malformed settings', () => {
  const home = tmpHome()
  const claude = path.join(home, '.claude')
  fs.mkdirSync(claude, { recursive: true })
  const settings = path.join(claude, 'settings.json')
  const malformed = '{ "hooks": '
  fs.writeFileSync(settings, malformed)

  const warnings = []
  const originalWarn = console.warn
  console.warn = message => warnings.push(message)
  try {
    const result = cleanClaudeSessionHooks(home)
    assert.equal(result.removed, 0)
    assert.match(result.warning, /JSON/)
  } finally {
    console.warn = originalWarn
  }

  assert.equal(fs.readFileSync(settings, 'utf8'), malformed)
  assert.equal(warnings.length, 1)
  assert.match(warnings[0], /could not clean Claude SessionStart hooks/)
})

test('cleanClaudeSessionHooks does not rewrite settings without matching hooks', () => {
  const home = tmpHome()
  const claude = path.join(home, '.claude')
  fs.mkdirSync(claude, { recursive: true })
  const settings = path.join(claude, 'settings.json')
  const original = '{\n  "enabledPlugins": {"keep": true}\n}\n'
  fs.writeFileSync(settings, original)

  const result = cleanClaudeSessionHooks(home)

  assert.equal(result.removed, 0)
  assert.equal(fs.readFileSync(settings, 'utf8'), original)
})
