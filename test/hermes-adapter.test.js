'use strict'

// Verifies adapters/lib/modules.py `emit-hermes` writes valid Hermes/OpenClaw
// skills (~/.hermes/skills/100xprism/<slug>/SKILL.md), keeps every emitted
// description inside Hermes's always-on index budget, reconciles on re-run the
// same way emit-claude-code does, and respects `100xprism slim` (PRISM_SKILLS).

const { test } = require('node:test')
const assert = require('node:assert/strict')
const { spawnSync } = require('node:child_process')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')

const REPO = path.resolve(__dirname, '..')
const MODULES_PY = path.join(REPO, 'adapters', 'lib', 'modules.py')
const HERMES_DESC_MAX = 57

function emit(home, extraEnv = {}) {
  return spawnSync('python3', [MODULES_PY, 'emit-hermes'], {
    encoding: 'utf8',
    env: { ...process.env, HOME: home, ...extraEnv },
  })
}

function skillsDir(home) {
  return path.join(home, '.hermes', 'skills', '100xprism')
}

function readDescription(skillMdPath) {
  const text = fs.readFileSync(skillMdPath, 'utf8')
  const m = text.match(/^description:\s*(.*)$/m)
  return m ? m[1] : null
}

test('emit-hermes writes one skill per module, all within budget, none dropped', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-hermes-'))
  // PRISM_SKILLS=all: this test verifies full-catalog install + budget
  // compliance, independent of whichever mode ships as the default (v3.2
  // made 'must' the lean default; see user_skills_mode()).
  const r = emit(home, { PRISM_SKILLS: 'all' })
  assert.equal(r.status, 0, r.stderr)

  const skills = skillsDir(home)
  const sourceSlugs = fs.readdirSync(path.join(REPO, 'modules'))
    .filter((name) => fs.existsSync(path.join(REPO, 'modules', name, 'SKILL.md')))
  const emittedDirs = fs.readdirSync(skills)
    .filter((name) => fs.existsSync(path.join(skills, name, 'SKILL.md')))

  // Every source module lands as a skill (default PRISM_SKILLS=all — no filtering).
  for (const slug of sourceSlugs) {
    assert.ok(emittedDirs.includes(slug), `missing emitted skill for ${slug}`)
  }

  for (const slug of emittedDirs) {
    const skillMd = path.join(skills, slug, 'SKILL.md')
    const desc = readDescription(skillMd)
    assert.ok(desc !== null, `${slug}: no description: line found`)
    assert.ok(
      Buffer.byteLength(desc, 'utf8') <= HERMES_DESC_MAX,
      `${slug}: description exceeds ${HERMES_DESC_MAX} chars: ${JSON.stringify(desc)}`,
    )
    // Marker file lets reconciliation distinguish 100xprism's own output from
    // anything the user placed under the same category by hand.
    assert.ok(fs.existsSync(path.join(skills, slug, '.100xprism-generated')))
  }

  const manifest = JSON.parse(fs.readFileSync(path.join(skills, '.100xprism-manifest.json'), 'utf8'))
  assert.ok(manifest.skills.includes('gate'))
  assert.ok(manifest.skills.includes('copywriting'))
})

test('emit-hermes reconciles: prunes a module removed upstream, keeps hand-authored skills', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-hermes-prune-'))
  const skills = skillsDir(home)
  fs.mkdirSync(skills, { recursive: true })

  // A module merged away in this release (REMOVED_MODULES) — must prune even
  // though this simulated install predates the manifest/marker.
  fs.mkdirSync(path.join(skills, 'systems-architect'))
  fs.writeFileSync(path.join(skills, 'systems-architect', 'SKILL.md'), 'old\n')

  // A skill in a DIFFERENT category, hand-authored by the user — must never be
  // touched; emit-hermes only ever writes under skills/100xprism/.
  const otherCategory = path.join(home, '.hermes', 'skills', 'my-own-category', 'my-skill')
  fs.mkdirSync(otherCategory, { recursive: true })
  fs.writeFileSync(path.join(otherCategory, 'SKILL.md'), '---\nname: my-skill\ndescription: mine\n---\nmine\n')

  const r = emit(home)
  assert.equal(r.status, 0, r.stderr)

  assert.ok(!fs.existsSync(path.join(skills, 'systems-architect')), 'removed module pruned')
  assert.ok(fs.existsSync(path.join(otherCategory, 'SKILL.md')), 'user skill in another category kept')
  assert.ok(fs.existsSync(path.join(skills, 'gate', 'SKILL.md')), 'current module written')
})

test('emit-hermes prunes a future-removed module via manifest/marker on re-run', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-hermes-ghost-'))
  const skills = skillsDir(home)

  assert.equal(emit(home).status, 0)

  // Simulate a module present on a previous emit (marker + manifest) that no
  // longer exists upstream, without being in the hardcoded REMOVED_MODULES set.
  fs.mkdirSync(path.join(skills, 'ghost-module'))
  fs.writeFileSync(path.join(skills, 'ghost-module', 'SKILL.md'), 'x\n')
  fs.writeFileSync(path.join(skills, 'ghost-module', '.100xprism-generated'), 'gen\n')
  const mPath = path.join(skills, '.100xprism-manifest.json')
  const m = JSON.parse(fs.readFileSync(mPath, 'utf8'))
  m.skills.push('ghost-module')
  fs.writeFileSync(mPath, JSON.stringify(m))

  assert.equal(emit(home).status, 0)
  assert.ok(!fs.existsSync(path.join(skills, 'ghost-module')), 'manifest-tracked skill pruned')
})

test('emit-hermes respects PRISM_SKILLS=must and re-widening back to all', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-hermes-slim-'))
  const skills = skillsDir(home)

  let r = emit(home, { PRISM_SKILLS: 'must' })
  assert.equal(r.status, 0, r.stderr)
  let installed = fs.readdirSync(skills).filter((n) => fs.existsSync(path.join(skills, n, 'SKILL.md')))
  assert.ok(installed.includes('gate'), 'must-have module present')
  assert.ok(installed.includes('100x-resolver'), 'resolver present when a catalog exists')
  assert.ok(!installed.includes('copywriting'), 'non-must module routed to resolver, not installed')

  const resolverDesc = readDescription(path.join(skills, '100x-resolver', 'SKILL.md'))
  assert.ok(Buffer.byteLength(resolverDesc, 'utf8') <= HERMES_DESC_MAX)

  r = emit(home, { PRISM_SKILLS: 'all' })
  assert.equal(r.status, 0, r.stderr)
  installed = fs.readdirSync(skills).filter((n) => fs.existsSync(path.join(skills, n, 'SKILL.md')))
  assert.ok(installed.includes('copywriting'), 'widening back to all restores routed modules')
  assert.ok(!installed.includes('100x-resolver'), 'resolver removed once nothing is routed')
})

test('emit-hermes is idempotent: re-running with no changes yields the same skill set', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), '100x-hermes-idem-'))
  assert.equal(emit(home).status, 0)
  const skills = skillsDir(home)
  const before = fs.readdirSync(skills).sort()

  assert.equal(emit(home).status, 0)
  const after = fs.readdirSync(skills).sort()
  assert.deepEqual(before, after)
})
