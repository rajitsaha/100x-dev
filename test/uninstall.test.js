'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
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

test('cleanShellStartup removes only 100x startup entries', () => {
  const home = tmpHome()
  const zshrc = path.join(home, '.zshrc')
  const bashProfile = path.join(home, '.bash_profile')

  fs.writeFileSync(zshrc, [
    'export KEEP=1',
    '# 100xPrism aliases',
    'source /Users/me/100xprism/shell/aliases.sh',
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
