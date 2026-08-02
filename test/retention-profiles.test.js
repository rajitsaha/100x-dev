'use strict'

// Covers the routed-index work: retention classes, per-project profiles, the
// generated resolver catalog, and `100xprism slim`.
//
// The load-bearing property throughout is that FILTERING IS OPT-IN — an emit into
// a directory with no `.100xprism.json` and no env override must produce byte-for-byte
// what it produced before any of this existed. Several tests assert exactly that.

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const MODULES_PY = path.join(REPO, 'adapters', 'lib', 'modules.py')
const win = require('../lib/adapters/windows')
const slim = require('../lib/slim')

function tmp(prefix = '100x-ret-') {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix))
}

function py(args, env = {}) {
  const r = spawnSync('python3', [MODULES_PY, ...args], {
    encoding: 'utf8',
    env: { ...process.env, ...env },
  })
  assert.equal(r.status, 0, r.stderr)
  return r.stdout
}

function countRules(project) {
  const dir = path.join(project, '.cursor', 'rules')
  return fs.existsSync(dir) ? fs.readdirSync(dir).filter(f => f.endsWith('.mdc')).length : 0
}

// ── retention derivation ─────────────────────────────────────────────────────

test('retention: must-have modules outrank their category', () => {
  const mods = JSON.parse(py(['list']))
  const bySlug = Object.fromEntries(mods.map(m => [m.slug, m]))
  for (const slug of ['gate', 'commit', 'push', 'test', 'release', 'pair-loop']) {
    assert.equal(bySlug[slug].retention, 'must', `${slug} must be a must-have`)
  }
})

test('retention: advice-shaped categories become resolver-only', () => {
  const mods = JSON.parse(py(['list']))
  for (const m of mods) {
    if (['marketing', 'design'].includes(m.category) && !m.slash_command) {
      assert.equal(m.retention, 'resolver', `${m.slug} should be catalog-only`)
    }
  }
})

test('retention: owning a slash command always keeps a real skill', () => {
  // A user can type the command, so it has to resolve — even for a category that
  // is otherwise routed. enterprise-design is the live example.
  const mods = JSON.parse(py(['list']))
  for (const m of mods) {
    if (m.slash_command) {
      assert.notEqual(m.retention, 'resolver', `${m.slug} owns ${m.slash_command}`)
    }
  }
})

test('retention: frontmatter can override the derived class', () => {
  assert.equal(win.retentionOf({ retention: 'resolver' }, 'gate', 'quality', '/gate'), 'resolver')
  assert.equal(win.retentionOf({ retention: 'must' }, 'copywriting', 'marketing', ''), 'must')
  assert.equal(win.retentionOf({ retention: 'nonsense' }, 'copywriting', 'marketing', ''), 'resolver')
})

test('retention: python and node derive identically for every module', () => {
  const fromPy = JSON.parse(py(['list']))
  const fromJs = win.listModules(path.join(REPO, 'modules'))
  const jsBySlug = Object.fromEntries(fromJs.map(m => [m.slug, m]))
  assert.equal(fromPy.length, fromJs.length)
  for (const m of fromPy) {
    assert.equal(jsBySlug[m.slug].retention, m.retention, `${m.slug} retention parity`)
    assert.deepEqual(jsBySlug[m.slug].profiles, m.profiles, `${m.slug} profiles parity`)
  }
})

// ── profile detection ────────────────────────────────────────────────────────

test('detectProfiles classifies a backend repo', () => {
  const p = tmp()
  fs.writeFileSync(path.join(p, 'pyproject.toml'), '[project]\n')
  fs.mkdirSync(path.join(p, 'terraform'))
  assert.deepEqual(win.detectProfiles(p), ['core', 'code', 'data'])
})

test('detectProfiles falls back to growth for a bare content directory', () => {
  // Otherwise a docs/marketing repo with no build manifest would end up with
  // nothing but the must-haves, silently losing the modules it actually wants.
  const p = tmp()
  assert.deepEqual(win.detectProfiles(p), ['core', 'growth'])
})

test('detectProfiles agrees across python and node', () => {
  const p = tmp()
  fs.writeFileSync(path.join(p, 'package.json'), '{}')
  fs.mkdirSync(path.join(p, 'content'))
  const fromPy = JSON.parse(py(['detect-profiles', p])).profiles
  assert.deepEqual(win.detectProfiles(p), fromPy)
})

// ── opt-in guarantee ─────────────────────────────────────────────────────────

test('emit-cursor with no project config emits every module (unchanged behaviour)', () => {
  const p = tmp()
  py(['emit-cursor', p])
  const sourceCount = fs.readdirSync(path.join(REPO, 'modules'))
    .filter(n => fs.existsSync(path.join(REPO, 'modules', n, 'SKILL.md'))).length
  assert.equal(countRules(p), sourceCount, 'no config ⇒ no filtering')
  assert.ok(!fs.existsSync(path.join(p, '.cursor', '100xprism-catalog')), 'no catalog dir')
  assert.ok(!fs.existsSync(path.join(p, '.cursor', 'rules', '100x-resolver.mdc')))
})

test('emit-cursor honours a project config and parks the rest in the catalog', () => {
  const p = tmp()
  fs.writeFileSync(path.join(p, '.100xprism.json'), JSON.stringify({ profiles: ['core', 'code'] }))
  py(['emit-cursor', p])

  const all = JSON.parse(py(['list']))
  const rules = fs.readdirSync(path.join(p, '.cursor', 'rules')).filter(f => f.endsWith('.mdc'))
  assert.ok(rules.length < all.length, 'filtered')
  assert.ok(rules.includes('100x-resolver.mdc'), 'resolver rule written')
  assert.ok(rules.includes('gate.mdc'), 'must-have kept regardless of profile')
  assert.ok(!rules.includes('copywriting.mdc'), 'catalog module removed from the index')

  const catalogBody = path.join(p, '.cursor', '100xprism-catalog', 'copywriting', 'SKILL.md')
  assert.ok(fs.existsSync(catalogBody), 'catalog body still on disk')
})

test('profiles: ["all"] is an explicit opt-out that restores every rule', () => {
  const p = tmp()
  fs.writeFileSync(path.join(p, '.100xprism.json'), JSON.stringify({ profiles: ['all'] }))
  py(['emit-cursor', p])
  const sourceCount = fs.readdirSync(path.join(REPO, 'modules'))
    .filter(n => fs.existsSync(path.join(REPO, 'modules', n, 'SKILL.md'))).length
  assert.equal(countRules(p), sourceCount)
})

test('PRISM_PROFILES overrides the project config', () => {
  const p = tmp()
  fs.writeFileSync(path.join(p, '.100xprism.json'), JSON.stringify({ profiles: ['core'] }))
  py(['emit-cursor', p], { PRISM_PROFILES: 'all' })
  const sourceCount = fs.readdirSync(path.join(REPO, 'modules'))
    .filter(n => fs.existsSync(path.join(REPO, 'modules', n, 'SKILL.md'))).length
  assert.equal(countRules(p), sourceCount, 'env "all" wins over a narrow config')
})

// ── resolver ─────────────────────────────────────────────────────────────────

test('every resolver row points at a file that exists', () => {
  // A catalog row is worthless if the path does not resolve — this is the single
  // most important property of the whole routed-index design.
  const p = tmp()
  fs.writeFileSync(path.join(p, '.100xprism.json'), JSON.stringify({ profiles: ['core'] }))
  py(['emit-cursor', p])

  const resolver = fs.readFileSync(path.join(p, '.cursor', 'rules', '100x-resolver.mdc'), 'utf8')
  const rows = [...resolver.matchAll(/^\| `([^`]+)` \| .* \| `([^`]+)` \|$/gm)]
  assert.ok(rows.length > 20, `expected a populated catalog, got ${rows.length} rows`)
  for (const [, slug, target] of rows) {
    assert.ok(fs.existsSync(path.join(p, target)), `${slug}: ${target} must exist`)
  }
})

test('resolver trades many descriptions for one', () => {
  const p = tmp()
  fs.writeFileSync(path.join(p, '.100xprism.json'), JSON.stringify({ profiles: ['core'] }))
  py(['emit-cursor', p])
  const resolver = fs.readFileSync(path.join(p, '.cursor', 'rules', '100x-resolver.mdc'), 'utf8')
  const description = resolver.split('\n').find(l => l.startsWith('description:'))
  const rows = [...resolver.matchAll(/^\| `[^`]+` \|/gm)].length
  assert.ok(description.length < 400, 'the one standing cost stays small')
  assert.ok(rows >= 30, `one description now covers ${rows} modules`)
})

// ── user-scope skills modes ──────────────────────────────────────────────────

test('skills mode splits the user-scope index and always keeps the must-haves', () => {
  const mods = JSON.parse(py(['list']))
  const all = win.splitByMode(mods, 'all')
  assert.equal(all.catalog.length, 0, 'default mode installs everything')
  assert.equal(all.installed.length, mods.length)

  const profile = win.splitByMode(mods, 'profile')
  const must = win.splitByMode(mods, 'must')
  assert.ok(must.installed.length < profile.installed.length)
  assert.ok(profile.installed.length < all.installed.length)

  for (const split of [profile, must]) {
    for (const slug of ['gate', 'commit', 'test', 'security']) {
      assert.ok(split.installed.some(m => m.slug === slug), `${slug} survives every mode`)
    }
  }
})

test('emit-claude-code: PRISM_SKILLS=profile routes the catalog out of the index', () => {
  const home = tmp('100x-home-')
  py(['emit-claude-code'], { HOME: home, PRISM_SKILLS: 'profile' })

  const skills = path.join(home, '.claude', 'skills')
  const installed = fs.readdirSync(skills).filter(n => fs.statSync(path.join(skills, n)).isDirectory())
  assert.ok(installed.includes('100x-resolver'), 'resolver installed')
  assert.ok(installed.includes('gate'), 'must-have installed')
  assert.ok(!installed.includes('copywriting'), 'catalog module not in the index')

  // Bodies land outside ~/.claude/skills, or Claude Code would index them anyway.
  const body = path.join(home, '.100xprism', '100xprism-catalog', 'copywriting', 'SKILL.md')
  assert.ok(fs.existsSync(body), 'catalog body parked outside the indexed tree')

  const resolver = fs.readFileSync(path.join(skills, '100x-resolver', 'SKILL.md'), 'utf8')
  assert.ok(resolver.includes(body), 'resolver points at the absolute parked path')
})

test('emit-claude-code: default mode is unchanged, and re-emitting is reversible', () => {
  const home = tmp('100x-home2-')
  py(['emit-claude-code'], { HOME: home })
  const skills = path.join(home, '.claude', 'skills')
  const full = fs.readdirSync(skills).filter(n => fs.statSync(path.join(skills, n)).isDirectory())
  assert.ok(full.includes('copywriting'), 'default installs everything')
  assert.ok(!full.includes('100x-resolver'), 'no resolver when nothing is routed')

  // Slim it, then restore — the index must come back intact, with no orphans.
  py(['emit-claude-code'], { HOME: home, PRISM_SKILLS: 'must' })
  assert.ok(!fs.existsSync(path.join(skills, 'copywriting')))
  py(['emit-claude-code'], { HOME: home, PRISM_SKILLS: 'all' })
  const restored = fs.readdirSync(skills).filter(n => fs.statSync(path.join(skills, n)).isDirectory())
  assert.deepEqual(restored.sort(), full.sort(), 'round-trip restores the exact index')
})

test('emit-claude-code: a user-authored skill survives every mode transition', () => {
  const home = tmp('100x-home3-')
  const skills = path.join(home, '.claude', 'skills')
  fs.mkdirSync(path.join(skills, 'my-own'), { recursive: true })
  fs.writeFileSync(path.join(skills, 'my-own', 'SKILL.md'), 'mine\n')
  for (const mode of ['profile', 'must', 'all']) {
    py(['emit-claude-code'], { HOME: home, PRISM_SKILLS: mode })
    assert.ok(fs.existsSync(path.join(skills, 'my-own', 'SKILL.md')), `kept under ${mode}`)
  }
})

test('an unknown PRISM_SKILLS value falls back to the safe end', () => {
  assert.equal(win.splitByMode([], 'all').catalog.length, 0)
  const prev = process.env.PRISM_SKILLS
  process.env.PRISM_SKILLS = 'wat'
  try {
    assert.equal(win.userSkillsMode(), 'all')
  } finally {
    if (prev === undefined) delete process.env.PRISM_SKILLS
    else process.env.PRISM_SKILLS = prev
  }
})

// ── slim ─────────────────────────────────────────────────────────────────────

test('slim resolves an install dir it can actually run from', () => {
  const dir = slim.resolveInstallDir()
  assert.ok(fs.existsSync(path.join(dir, 'adapters', 'lib', 'modules.py')))
})

test('slim flags instruction files that are too big to re-send every turn', () => {
  const p = tmp()
  fs.writeFileSync(path.join(p, 'CLAUDE.md'), 'x'.repeat(slim.INSTRUCTION_BUDGET_BYTES + 1))
  fs.writeFileSync(path.join(p, 'AGENTS.md'), 'small')
  const flagged = slim.oversizedInstructionFiles(p).map(f => f.name)
  assert.deepEqual(flagged, ['CLAUDE.md'])
})

// ── scaffold parity ──────────────────────────────────────────────────────────

test('the bash and JS CLAUDE.md scaffolds do not drift', { skip: process.platform === 'win32' }, () => {
  // The scaffold is duplicated in adapters/claude-code.sh and windows.js because
  // Windows has no bash. Only the JS copy had a test, so the two could drift
  // silently — this compares the real output of both.
  const fromBash = tmp('100x-sh-')
  const r = spawnSync('bash', ['-c',
    `source "${path.join(REPO, 'adapters', 'claude-code.sh')}" 2>/dev/null; ` +
    `install_project "${fromBash}" >/dev/null 2>&1`], { encoding: 'utf8' })
  assert.equal(r.status, 0, r.stderr)

  const fromJs = tmp('100x-js-')
  win.scaffoldClaudeMd(fromJs)

  const strip = dir => fs.readFileSync(path.join(dir, 'CLAUDE.md'), 'utf8')
    .split('\n').slice(1).join('\n')  // line 1 carries the project name
  assert.equal(strip(fromBash), strip(fromJs), 'CLAUDE.md scaffolds must match')

  const yml = dir => fs.readFileSync(path.join(dir, '.claude', '100xprism.yml'), 'utf8')
  assert.equal(yml(fromBash), yml(fromJs), '100xprism.yml scaffolds must match')
})

test('the scaffolded config survives the anchored grep the modules use', () => {
  // /db does `grep -q "^engine:"`. An indented key would be invisible, so the
  // uncommented form of every documented key has to sit at column 0.
  const p = tmp()
  win.scaffoldClaudeMd(p)
  const uncommented = fs.readFileSync(path.join(p, '.claude', '100xprism.yml'), 'utf8')
    .split('\n').map(l => l.replace(/^# /, '')).join('\n')
  for (const key of ['engine', 'connection', 'gcp_project', 'production_url',
    'health_url', 'security_exceptions']) {
    assert.match(uncommented, new RegExp(`^${key}:`, 'm'), `^${key}: must match`)
  }
})

test('config-reading modules prefer 100xprism.yml but still fall back', () => {
  // Existing repos keep their config in CLAUDE.md; the discovery order has to
  // find the new file first without dropping the old one.
  for (const slug of ['gate', 'cloud-security', 'launch', 'db']) {
    const body = fs.readFileSync(path.join(REPO, 'modules', slug, 'SKILL.md'), 'utf8')
    const line = body.split('\n').find(l => l.includes('INSTRUCTION_FILE=$('))
    assert.ok(line, `${slug}: no instruction-file discovery line`)
    assert.ok(line.indexOf('.claude/100xprism.yml') < line.indexOf('CLAUDE.md'),
      `${slug}: must check 100xprism.yml before CLAUDE.md`)
    assert.ok(line.includes('AGENTS.md') && line.includes('.cursorrules'),
      `${slug}: fallbacks must survive`)
  }
})

test('slim writes a reversible project config', () => {
  const p = tmp()
  slim.writeProjectProfiles(p, ['core', 'code'])
  const cfg = JSON.parse(fs.readFileSync(path.join(p, '.100xprism.json'), 'utf8'))
  assert.deepEqual(cfg.profiles, ['core', 'code'])
  assert.match(cfg._comment, /all/, 'the config explains how to undo itself')
})
