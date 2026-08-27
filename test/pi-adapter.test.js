'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { execFileSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const MODULES_PY = path.join(REPO, 'adapters', 'lib', 'modules.py')

function makeTmpDir(prefix = '100x-pi-') {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix))
}

function emitPi(projectDir, env = {}) {
  return execFileSync('python3', [MODULES_PY, 'emit-pi', projectDir], {
    cwd: REPO,
    encoding: 'utf8',
    env: { ...process.env, ...env },
  })
}

test('emit-pi defaults to must-have skills plus resolver even in a code repo', () => {
  const tmp = makeTmpDir()
  // Mark as a code repo so detect_profiles includes code
  fs.writeFileSync(path.join(tmp, 'package.json'), '{"name":"t"}\n')
  emitPi(tmp)

  const manifest = JSON.parse(
    fs.readFileSync(path.join(tmp, '.pi', '.100xprism-pi-manifest.json'), 'utf8'),
  )
  assert.ok(manifest.skills.length < 68, `expected <68 skills, got ${manifest.skills.length}`)
  assert.ok(manifest.skills.includes('gate'))
  assert.ok(manifest.skills.includes('100x-resolver'), 'resolver catalog skill required')
  assert.ok(manifest.skills.length < 20, `lean default should stay small, got ${manifest.skills.length}`)
  assert.ok(manifest.catalog.length > 0)
  assert.ok(fs.existsSync(path.join(tmp, '.pi', 'skills', 'gate', 'SKILL.md')))
  assert.ok(!fs.existsSync(path.join(tmp, '.pi', 'skills', 'copywriting', 'SKILL.md')))
  const generic = fs.readFileSync(path.join(tmp, '.pi', 'prompts', '100x.md'), 'utf8')
  assert.match(generic, /100x-resolver/)
  assert.match(generic, /ARGUMENTS/)
})

test('emit-pi respects profiles all', () => {
  const tmp = makeTmpDir()
  fs.writeFileSync(path.join(tmp, '.100xprism.json'), JSON.stringify({ profiles: ['all'] }))
  emitPi(tmp)
  const manifest = JSON.parse(
    fs.readFileSync(path.join(tmp, '.pi', '.100xprism-pi-manifest.json'), 'utf8'),
  )
  assert.equal(manifest.skills.length, 68)
  assert.equal(manifest.catalog.length, 0)
  assert.equal(manifest.profiles, null)
})

test('emit-pi leaves existing AGENTS.md alone', () => {
  const tmp = makeTmpDir()
  fs.writeFileSync(path.join(tmp, 'AGENTS.md'), '# keep me\n')
  emitPi(tmp)
  assert.equal(fs.readFileSync(path.join(tmp, 'AGENTS.md'), 'utf8'), '# keep me\n')
})

test('emit-pi writes AGENTS.md when missing', () => {
  const tmp = makeTmpDir()
  emitPi(tmp)
  const agents = fs.readFileSync(path.join(tmp, 'AGENTS.md'), 'utf8')
  assert.match(agents, /100x Dev for Pi/)
  assert.match(agents, /\/skill:gate/)
})

test('emit-pi-package writes must-only tree under pi/', () => {
  execFileSync('python3', [MODULES_PY, 'emit-pi-package'], { cwd: REPO, encoding: 'utf8' })
  const manifest = JSON.parse(
    fs.readFileSync(path.join(REPO, 'pi', '.100xprism-pi-manifest.json'), 'utf8'),
  )
  assert.deepEqual(manifest.profiles, [])
  assert.ok(manifest.skills.length < 20)
  assert.ok(fs.existsSync(path.join(REPO, 'pi', 'extensions', 'gate-secret.ts')))
  assert.ok(fs.existsSync(path.join(REPO, 'pi', 'extensions', 'retention.ts')))
  const pkg = JSON.parse(fs.readFileSync(path.join(REPO, 'package.json'), 'utf8'))
  assert.deepEqual(pkg.pi.extensions, [], 'Pi extensions remain available but are opt-in')
})

test('Pi enforcement extension fails closed when a hook is unavailable or errors', () => {
  const source = fs.readFileSync(path.join(REPO, 'pi', 'extensions', 'gate-secret.ts'), 'utf8')
  assert.match(source, /hook unavailable/)
  assert.match(source, /result\.status !== 0/)
  assert.match(source, /block: true, reason: `100xprism hook unavailable/)
})
