'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const {
  emitClaudeModules,
  scaffoldClaudeMd,
  mergePluginsJson,
  emitCursorRules,
  pruneDeprecatedArtifacts,
  pruneTrackedProjects,
  emitCodexProject,
  addTrackedProject,
} = require('../lib/adapters/windows')

function makeTmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), '100x-test-'))
}

// Build a fake modules/ dir: each entry is { slug, frontmatter, body }.
function fakeModules(dir, mods) {
  for (const m of mods) {
    const md = path.join(dir, m.slug)
    fs.mkdirSync(md, { recursive: true })
    const fm = Object.entries(m.fm || {}).map(([k, v]) => `${k}: ${v}`).join('\n')
    fs.writeFileSync(path.join(md, 'SKILL.md'), `---\n${fm}\n---\n\n${m.body || 'body'}\n`)
  }
}

test('emitClaudeModules writes skills + slash aliases from modules/', () => {
  const modulesDir = makeTmpDir(), skills = makeTmpDir(), commands = makeTmpDir()
  fakeModules(modulesDir, [
    { slug: 'gate', fm: { name: 'gate', description: 'Quality gate.', slash_command: '/gate' } },
    { slug: 'copywriting', fm: { name: 'copywriting', description: 'Write copy.' } }, // no slash
    { slug: '_lib', fm: {}, body: '' }, // shared-ref dir — but has SKILL.md here; skip via missing? keep simple
  ])
  // _lib in the real repo has no SKILL.md; emulate that:
  fs.rmSync(path.join(modulesDir, '_lib', 'SKILL.md'))

  const r = emitClaudeModules(modulesDir, skills, commands)
  assert.equal(r.skills, 2, 'two real modules emitted, _lib skipped')
  assert.ok(fs.existsSync(path.join(skills, 'gate', 'SKILL.md')))
  assert.ok(fs.existsSync(path.join(skills, 'gate', '.100xprism-generated')), 'marker written')
  assert.ok(fs.existsSync(path.join(commands, 'gate.md')), 'slash alias written')
  assert.ok(!fs.existsSync(path.join(commands, 'copywriting.md')), 'no alias without slash_command')
  const manifest = JSON.parse(fs.readFileSync(path.join(skills, '.100xprism-manifest.json'), 'utf8'))
  assert.deepEqual(manifest.skills, ['copywriting', 'gate'])
  assert.deepEqual(manifest.commands, ['gate'])
})

test('emitClaudeModules prunes removed modules but keeps user-authored skills/commands', () => {
  const modulesDir = makeTmpDir(), skills = makeTmpDir(), commands = makeTmpDir()
  fakeModules(modulesDir, [{ slug: 'gate', fm: { name: 'gate', description: 'Quality gate.', slash_command: '/gate' } }])

  // Pre-existing: a merged-away module (in REMOVED_MODULES, no marker), a user skill, a user command.
  fs.mkdirSync(path.join(skills, 'systems-architect'))
  fs.writeFileSync(path.join(skills, 'systems-architect', 'SKILL.md'), 'old')
  fs.mkdirSync(path.join(skills, 'my-skill'))
  fs.writeFileSync(path.join(skills, 'my-skill', 'SKILL.md'), 'mine')
  fs.writeFileSync(path.join(commands, 'my-cmd.md'), 'mine')

  const r = emitClaudeModules(modulesDir, skills, commands)
  assert.ok(r.prunedSkills >= 1)
  assert.ok(!fs.existsSync(path.join(skills, 'systems-architect')), 'removed module pruned')
  assert.ok(fs.existsSync(path.join(skills, 'my-skill')), 'user skill kept')
  assert.ok(fs.existsSync(path.join(commands, 'my-cmd.md')), 'user command kept')

  // A future-removed module tracked only via manifest/marker is pruned on re-run.
  fs.mkdirSync(path.join(skills, 'ghost'))
  fs.writeFileSync(path.join(skills, 'ghost', 'SKILL.md'), 'x')
  fs.writeFileSync(path.join(skills, 'ghost', '.100xprism-generated'), 'gen')
  emitClaudeModules(modulesDir, skills, commands)
  assert.ok(!fs.existsSync(path.join(skills, 'ghost')), 'marker-tagged orphan pruned')
})

test('scaffoldClaudeMd writes CLAUDE.md with project name', () => {
  const projectDir = makeTmpDir()
  scaffoldClaudeMd(projectDir)
  const content = fs.readFileSync(path.join(projectDir, 'CLAUDE.md'), 'utf8')
  assert.ok(content.includes(path.basename(projectDir)))
  assert.ok(content.includes('## Database'))
  assert.ok(content.includes('## Rules'))
})

test('scaffoldClaudeMd skips if CLAUDE.md already exists', () => {
  const projectDir = makeTmpDir()
  fs.writeFileSync(path.join(projectDir, 'CLAUDE.md'), 'existing')
  scaffoldClaudeMd(projectDir)
  assert.equal(fs.readFileSync(path.join(projectDir, 'CLAUDE.md'), 'utf8'), 'existing')
})

test('scaffoldClaudeMd skips if .cursorrules already exists', () => {
  const projectDir = makeTmpDir()
  fs.writeFileSync(path.join(projectDir, '.cursorrules'), 'existing')
  scaffoldClaudeMd(projectDir)
  assert.ok(!fs.existsSync(path.join(projectDir, 'CLAUDE.md')))
})

test('mergePluginsJson adds plugins to settings.json', () => {
  const settingsFile = path.join(makeTmpDir(), 'settings.json')
  const pluginsFile = path.join(makeTmpDir(), 'plugins.json')
  fs.writeFileSync(settingsFile, JSON.stringify({ enabledPlugins: {} }))
  fs.writeFileSync(pluginsFile, JSON.stringify({ plugins: ['plugin-a', 'plugin-b'] }))
  mergePluginsJson(pluginsFile, settingsFile)
  const settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  assert.equal(settings.enabledPlugins['plugin-a'], true)
  assert.equal(settings.enabledPlugins['plugin-b'], true)
})

test('mergePluginsJson is idempotent', () => {
  const settingsFile = path.join(makeTmpDir(), 'settings.json')
  const pluginsFile = path.join(makeTmpDir(), 'plugins.json')
  fs.writeFileSync(settingsFile, JSON.stringify({ enabledPlugins: { 'plugin-a': true } }))
  fs.writeFileSync(pluginsFile, JSON.stringify({ plugins: ['plugin-a'] }))
  mergePluginsJson(pluginsFile, settingsFile)
  const settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  assert.equal(Object.keys(settings.enabledPlugins).length, 1)
})

test('mergePluginsJson removes a dropped managed plugin but keeps user plugins', () => {
  const settingsFile = path.join(makeTmpDir(), 'settings.json')
  const pluginsFile = path.join(makeTmpDir(), 'plugins.json')
  fs.writeFileSync(settingsFile, JSON.stringify({ enabledPlugins: { 'user-only': true } }))

  // First run: declare a + b (seed managed set, add both, remove nothing).
  fs.writeFileSync(pluginsFile, JSON.stringify({ plugins: ['plugin-a', 'plugin-b'] }))
  mergePluginsJson(pluginsFile, settingsFile)

  // Second run: drop plugin-b from plugins.json -> it should be removed.
  fs.writeFileSync(pluginsFile, JSON.stringify({ plugins: ['plugin-a'] }))
  mergePluginsJson(pluginsFile, settingsFile)

  const enabled = JSON.parse(fs.readFileSync(settingsFile, 'utf8')).enabledPlugins
  assert.equal('plugin-b' in enabled, false, 'dropped managed plugin removed')
  assert.equal(enabled['plugin-a'], true, 'still-declared plugin kept')
  assert.equal(enabled['user-only'], true, 'user-managed plugin preserved')
})

test('emitCursorRules writes one .mdc per module with tier-driven alwaysApply', () => {
  const modulesDir = makeTmpDir()
  const projectDir = makeTmpDir()
  fakeModules(modulesDir, [
    { slug: 'gate', fm: { name: 'gate', category: 'quality', tier: 'core', slash_command: '/gate', description: 'Quality gate.' }, body: 'GATE BODY' },
    { slug: 'copywriting', fm: { name: 'copywriting', category: 'marketing', tier: 'on-demand', description: 'Write copy.' }, body: 'COPY BODY' },
  ])
  const count = emitCursorRules(modulesDir, projectDir)
  assert.equal(count, 2, 'wrote a rule per module')

  const rulesDir = path.join(projectDir, '.cursor', 'rules')
  const gate = fs.readFileSync(path.join(rulesDir, 'gate.mdc'), 'utf8')
  const copy = fs.readFileSync(path.join(rulesDir, 'copywriting.mdc'), 'utf8')

  assert.match(gate, /alwaysApply: true/, 'core module is resident')
  assert.match(copy, /alwaysApply: false/, 'on-demand module is agent-requested')
  // Bodies ship in every rule file — Cursor loads them, it does not inline them
  // into an always-on blob the way the removed concat adapters did.
  assert.ok(gate.includes('GATE BODY'), 'core body present in its own rule file')
  assert.ok(copy.includes('COPY BODY'), 'on-demand body present in its own rule file')
  assert.match(gate, /generated by 100xprism/, 'carries the generation marker used for pruning')
})

// Regression: the stale-rule fixture used to be hand-written with the marker on
// line 5, while the real emitter puts it on line 7 — so the test passed against a
// file the emitter never produces, and pruning was broken in production for every
// removed module. This test now prunes REAL emitter output: generate, drop a
// module, re-emit, and require the orphan to be gone.
test('emitCursorRules prunes real generated rules for modules that disappeared', () => {
  const modulesDir = makeTmpDir()
  const projectDir = makeTmpDir()
  const rulesDir = path.join(projectDir, '.cursor', 'rules')

  fakeModules(modulesDir, [
    { slug: 'gate', fm: { name: 'gate', category: 'quality', tier: 'core', slash_command: '/gate', description: 'Quality gate.' }, body: 'GATE BODY' },
    { slug: 'copywriting', fm: { name: 'copywriting', category: 'marketing', tier: 'on-demand', description: 'Write copy.' }, body: 'COPY BODY' },
  ])
  emitCursorRules(modulesDir, projectDir)
  assert.ok(fs.existsSync(path.join(rulesDir, 'copywriting.mdc')), 'precondition: rule was generated')

  // Guard the exact off-by-one that caused the bug: the marker must fall inside
  // the window the pruner actually scans.
  const generated = fs.readFileSync(path.join(rulesDir, 'copywriting.mdc'), 'utf8')
  const markerLine = generated.split('\n').findIndex(l => l.includes('generated by 100xprism')) + 1
  assert.ok(markerLine > 0, 'generated rule carries the marker')
  assert.ok(markerLine <= 10, `marker on line ${markerLine} must be within the 10-line prune window`)

  // The module goes away upstream; a user-authored rule sits alongside it.
  fs.rmSync(path.join(modulesDir, 'copywriting'), { recursive: true })
  fs.writeFileSync(path.join(rulesDir, 'mine.mdc'), '---\ndescription: hand written\n---\n\nmy own rule\n')
  emitCursorRules(modulesDir, projectDir)

  assert.ok(!fs.existsSync(path.join(rulesDir, 'copywriting.mdc')), 'orphaned generated rule removed')
  assert.ok(fs.existsSync(path.join(rulesDir, 'mine.mdc')), 'user-authored rule preserved')
  assert.ok(fs.existsSync(path.join(rulesDir, 'gate.mdc')), 'current module still written')
})

test('emitCodexProject emits Codex-native repo skills and portable hooks', () => {
  const modulesDir = makeTmpDir()
  const projectDir = makeTmpDir()
  const hooksDir = makeTmpDir()
  fakeModules(modulesDir, [
    { slug: 'gate', fm: { name: 'gate', category: 'quality', tier: 'core', slash_command: '/gate', description: 'Quality gate.' }, body: 'GATE BODY' },
    { slug: 'copywriting', fm: { name: 'copywriting', category: 'marketing', tier: 'on-demand', description: 'Write copy.' }, body: 'COPY BODY' },
  ])
  fs.writeFileSync(path.join(hooksDir, 'hooks.manifest.json'), JSON.stringify({
    hooks: [{
      id: 'gate-on-commit',
      event: 'PreToolUse',
      matcher: 'Bash',
      script: 'pretooluse-gate.py',
      default: true,
      description: 'Block git commit/push unless /gate passed.',
    }],
  }))

  const r = emitCodexProject(modulesDir, projectDir, hooksDir)

  assert.equal(r.skills, 2)
  assert.ok(fs.existsSync(path.join(projectDir, 'AGENTS.md')))
  assert.ok(fs.existsSync(path.join(projectDir, '.agents', 'skills', 'gate', 'SKILL.md')))
  const hooksText = fs.readFileSync(path.join(projectDir, '.codex', 'hooks.json'), 'utf8')
  assert.match(hooksText, /\.codex\/100xprism-hooks\/run-hook\.py/)
  assert.doesNotMatch(hooksText, new RegExp(modulesDir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  assert.ok(fs.existsSync(path.join(projectDir, '.codex', '100xprism-hooks', 'run-hook.py')))
})

test('Windows and Python Codex emitters write the same hook wrapper template', () => {
  const repo = path.join(__dirname, '..')
  const modulesDir = path.join(repo, 'modules')
  const projectDir = makeTmpDir()
  const pyProjectDir = makeTmpDir()
  const hooksDir = path.join(repo, 'hooks')

  emitCodexProject(modulesDir, projectDir, hooksDir)
  require('node:child_process').execFileSync(
    'python3',
    [path.join(repo, 'adapters', 'lib', 'modules.py'), 'emit-codex', pyProjectDir],
    { cwd: repo, encoding: 'utf8' },
  )

  const jsWrapper = fs.readFileSync(path.join(projectDir, '.codex', '100xprism-hooks', 'run-hook.py'), 'utf8')
  const pyWrapper = fs.readFileSync(path.join(pyProjectDir, '.codex', '100xprism-hooks', 'run-hook.py'), 'utf8')
  assert.equal(jsWrapper, pyWrapper)
})

test('addTrackedProject writes path to file', () => {
  const trackedFile = path.join(makeTmpDir(), 'tracked-projects')
  addTrackedProject('/some/project', trackedFile)
  assert.ok(fs.readFileSync(trackedFile, 'utf8').includes('/some/project'))
})

test('addTrackedProject is idempotent', () => {
  const trackedFile = path.join(makeTmpDir(), 'tracked-projects')
  addTrackedProject('/some/project', trackedFile)
  addTrackedProject('/some/project', trackedFile)
  const lines = fs.readFileSync(trackedFile, 'utf8').trim().split('\n')
  assert.equal(lines.filter(l => l === '/some/project').length, 1)
})

// The native-Windows path never runs adapters/lib/deprecated.sh, so the JS mirror
// must enforce the same three guarantees. Without these, the CHANGELOG's
// "migration is automatic" claim is false on Windows.
test('pruneDeprecatedArtifacts mirrors the shell guarantees on Windows', () => {
  const project = makeTmpDir()
  const backupRoot = makeTmpDir()
  const header = '# 100x Dev — Modules\n# Generated by 100xprism\n\nbody\n'

  fs.writeFileSync(path.join(project, '.windsurfrules'), header)
  fs.writeFileSync(path.join(project, 'GEMINI.md'), '# hand written, not ours\n')
  fs.writeFileSync(path.join(project, 'CLAUDE.md'), '# supported tool\n')

  const r = pruneDeprecatedArtifacts(project, backupRoot)

  assert.equal(r.removed, 1, 'only the generated artifact was removed')
  assert.equal(r.failed, 0)
  assert.ok(!fs.existsSync(path.join(project, '.windsurfrules')), 'generated file removed')
  assert.ok(fs.existsSync(path.join(project, 'GEMINI.md')), 'hand-written file preserved')
  assert.ok(fs.existsSync(path.join(project, 'CLAUDE.md')), 'supported tool untouched')

  const backup = path.join(backupRoot, path.basename(fs.realpathSync(project)), '.windsurfrules')
  assert.ok(fs.existsSync(backup), 'removal was backed up first')
  assert.equal(fs.readFileSync(backup, 'utf8'), header, 'backup is byte-identical')
})

test('pruneTrackedProjects walks every registered project', () => {
  const a = makeTmpDir(), b = makeTmpDir(), gone = path.join(makeTmpDir(), 'deleted')
  const backupRoot = makeTmpDir()
  const header = '# 100x Dev\n# Generated by 100xprism\n\nbody\n'
  fs.writeFileSync(path.join(a, 'GEMINI.md'), header)
  fs.writeFileSync(path.join(b, 'ANTIGRAVITY.md'), header)

  const trackedFile = path.join(makeTmpDir(), 'tracked-projects')
  fs.writeFileSync(trackedFile, `${a}\n${gone}\n\n${b}\n`)

  const r = pruneTrackedProjects(trackedFile, backupRoot)

  assert.equal(r.removed, 2, 'pruned across both live projects')
  assert.equal(r.projects, 2)
  assert.equal(r.failed, 0, 'a deleted/blank tracked path is skipped, not counted as failure')
})
