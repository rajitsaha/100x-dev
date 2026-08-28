'use strict'

// `100xprism slim` — shrink the always-on footprint of an install and of every
// project it has touched.
//
// Three levers, all reversible:
//   1. user-scope skills mode  (~/.100xprism/config.json "skills")
//        which modules earn a permanent slot in the session skill index
//   2. per-project profiles    (<project>/.100xprism.json "profiles")
//        which modules earn a rule/skill in THIS repo
//   3. an advisory report on oversized instruction files
//
// Nothing here deletes a user's own content. Generated artifacts are re-emitted
// from modules/, and the instruction-file check only reports.

const fs = require('fs')
const os = require('os')
const path = require('path')
const { spawnSync } = require('child_process')

const { installDir, isWindows, trackedProjectsFile } = require('./platform')

const MODES = ['all', 'profile', 'must']
const DEFAULT_MODE = 'must'
const PROJECT_CONFIG = '.100xprism.json'
// Roughly the point past which an instruction file is carrying reference material
// that belongs in docs/ behind a router. ~1200 tokens at the usual 4 chars/token.
const INSTRUCTION_BUDGET_BYTES = 5000
const INSTRUCTION_FILES = ['CLAUDE.md', 'AGENTS.md', '.cursorrules']

function configPath() {
  return path.join(os.homedir(), '.100xprism', 'config.json')
}

// `installDir` is the conventional ~/100xprism checkout, but slim also has to work
// when run straight out of a package (npm -g, a clone, a test). Fall back to this
// file's own package root rather than silently doing nothing.
function resolveInstallDir() {
  const candidates = [installDir, path.resolve(__dirname, '..')]
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'adapters', 'lib', 'modules.py'))) return dir
  }
  return installDir
}

function modulesPy() {
  return path.join(resolveInstallDir(), 'adapters', 'lib', 'modules.py')
}

// Never swallow a failed emit: a slim that quietly no-ops looks identical to one
// that worked, and the user would only find out from a token bill.
function runPython(args, label) {
  const r = spawnSync('python3', args, { encoding: 'utf8' })
  if (r.status !== 0) {
    console.error(`  ✗ ${label} failed: ${(r.stderr || r.error?.message || '').trim().split('\n')[0]}`)
    return null
  }
  return r.stdout
}

function readJson(file, fallback = {}) {
  try {
    return JSON.parse(fs.readFileSync(file, 'utf8'))
  } catch {
    return fallback
  }
}

function writeUserMode(mode) {
  const file = configPath()
  fs.mkdirSync(path.dirname(file), { recursive: true })
  const cfg = readJson(file)
  cfg.skills = mode
  fs.writeFileSync(file, JSON.stringify(cfg, null, 2) + '\n')
  return file
}

// Delegates detection to the adapter so the rules live in exactly one place.
function detectProfiles(projectPath) {
  if (isWindows) {
    return require('./adapters/windows').detectProfiles(projectPath)
  }
  const out = runPython([modulesPy(), 'detect-profiles', projectPath], 'profile detection')
  if (out === null) return ['core']
  try {
    return JSON.parse(out).profiles
  } catch {
    return ['core']
  }
}

function writeProjectProfiles(projectPath, profiles) {
  const file = path.join(projectPath, PROJECT_CONFIG)
  const cfg = readJson(file)
  cfg.profiles = profiles
  cfg._comment =
    'Written by `100xprism slim`. Controls which modules are installed into this ' +
    'repo. Use ["all"] to install everything again, or add/remove profiles by hand.'
  fs.writeFileSync(file, JSON.stringify(cfg, null, 2) + '\n')
  return file
}

// Re-emit only the adapters this project already uses, so slim never introduces
// a tool the user did not opt into.
function reemitProject(projectPath) {
  const emitted = []
  const root = resolveInstallDir()
  const hasCursor = fs.existsSync(path.join(projectPath, '.cursor', 'rules'))
  const hasCodex = fs.existsSync(path.join(projectPath, '.agents', 'skills'))
  const hasPi = fs.existsSync(path.join(projectPath, '.pi', 'skills'))

  if (isWindows) {
    const win = require('./adapters/windows')
    const modulesDir = path.join(root, 'modules')
    if (hasCursor) { win.emitCursorRules(modulesDir, projectPath); emitted.push('cursor') }
    if (hasCodex) {
      win.emitCodexProject(modulesDir, projectPath, path.join(root, 'hooks'))
      emitted.push('codex')
    }
    if (hasPi && runPython([modulesPy(), 'emit-pi', projectPath], 'pi emit') !== null) {
      emitted.push('pi')
    }
    return emitted
  }
  if (hasCursor && runPython([modulesPy(), 'emit-cursor', projectPath], 'cursor emit') !== null) {
    emitted.push('cursor')
  }
  if (hasCodex && runPython([modulesPy(), 'emit-codex', projectPath], 'codex emit') !== null) {
    emitted.push('codex')
  }
  if (hasPi && runPython([modulesPy(), 'emit-pi', projectPath], 'pi emit') !== null) {
    emitted.push('pi')
  }
  return emitted
}

function oversizedInstructionFiles(projectPath) {
  const out = []
  for (const name of INSTRUCTION_FILES) {
    const file = path.join(projectPath, name)
    try {
      const { size } = fs.statSync(file)
      if (size > INSTRUCTION_BUDGET_BYTES) out.push({ name, size })
    } catch { /* absent — nothing to report */ }
  }
  return out
}

function trackedProjects() {
  try {
    return fs.readFileSync(trackedProjectsFile, 'utf8')
      .split('\n').map(s => s.trim()).filter(p => p && fs.existsSync(p))
  } catch {
    return []
  }
}

function slimProject(projectPath, { dryRun, mode = DEFAULT_MODE }) {
  const profiles = mode === 'all' ? ['all'] : mode === 'profile' ? detectProfiles(projectPath) : []
  const profileLabel = profiles.length ? profiles.join(', ') : 'must only'
  const existing = readJson(path.join(projectPath, PROJECT_CONFIG)).profiles
  const hasExistingProfiles = existing != null && !(Array.isArray(existing) && existing.length === 0)
  const label = path.basename(projectPath)

  if (hasExistingProfiles) {
    console.log(`  ${label}: profiles already set (${[].concat(existing).join(', ')}) — left alone`)
  } else if (dryRun) {
    console.log(`  ${label}: would set profiles → ${profileLabel}`)
  } else {
    writeProjectProfiles(projectPath, profiles)
    const emitted = reemitProject(projectPath)
    console.log(`  ${label}: profiles → ${profileLabel}` +
      (emitted.length ? ` (re-emitted ${emitted.join(', ')})` : ''))
  }

  for (const f of oversizedInstructionFiles(projectPath)) {
    console.log(`     ⚠ ${f.name} is ${(f.size / 1024).toFixed(1)}KB (~${Math.round(f.size / 4)} tokens) ` +
      're-sent every turn — move reference material into docs/ and leave a router table.')
  }
}

function run(args) {
  const dryRun = args.includes('--dry-run')
  const allProjects = args.includes('--all-projects')
  const modeArg = args.find(a => a.startsWith('--skills='))
  const mode = modeArg ? modeArg.split('=')[1] : DEFAULT_MODE
  const positional = args.filter(a => !a.startsWith('-'))

  if (!MODES.includes(mode)) {
    console.error(`Unknown --skills mode '${mode}'. Expected one of: ${MODES.join(', ')}`)
    process.exit(2)
  }

  console.log(`\n100xprism optimize${dryRun ? ' (dry run)' : ''}\n`)

  // 1. User-scope skills mode, then re-emit so it takes effect immediately.
  if (dryRun) {
    console.log(`  would set user skills mode → ${mode}`)
  } else {
    const file = writeUserMode(mode)
    console.log(`  user skills mode → ${mode}  (${file})`)
    if (isWindows) {
      require('./adapters/windows').installGlobalWindows(resolveInstallDir())
    } else {
      const out = runPython([modulesPy(), 'emit-claude-code'], 'user-scope skill emit')
      if (out) console.log(`  ${out.trim()}`)
    }
  }

  // 2. Per-project profiles.
  const targets = positional.length ? positional.map(p => path.resolve(p))
    : allProjects ? trackedProjects()
      : [process.cwd()]

  if (targets.length) {
    console.log(`\n  Projects (${targets.length}):`)
    for (const t of targets) slimProject(t, { dryRun, mode })
  }

  console.log('\n  Undo: `100xprism optimize --skills=all`, or set "profiles": ["all"] in a ' +
    `project's ${PROJECT_CONFIG}.`)
  console.log('  See what changed: `100xprism tokens --print`\n')
}

module.exports = {
  run,
  resolveInstallDir,
  detectProfiles,
  writeUserMode,
  writeProjectProfiles,
  oversizedInstructionFiles,
  trackedProjects,
  slimProject,
  MODES,
  DEFAULT_MODE,
  INSTRUCTION_BUDGET_BYTES,
}
