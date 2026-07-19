'use strict'

const fs = require('fs')
const os = require('os')
const path = require('path')
const { stopDashboard } = require('./dashboard')

const BIN_NAMES = ['100xprism', '100x-dev']
const RC_FILES = ['.zshrc', '.zprofile', '.bashrc', '.bash_profile']

function uniq(values) {
  return [...new Set(values.filter(Boolean))]
}

function exists(target) {
  try {
    fs.accessSync(target)
    return true
  } catch {
    return false
  }
}

function isSafe100xLink(linkPath, target, options = {}) {
  const name = path.basename(linkPath)
  if (!BIN_NAMES.includes(name)) return false

  const resolved = path.resolve(path.dirname(linkPath), target)
  if (!exists(resolved)) return true
  if (resolved.includes(`${path.sep}100x-dev${path.sep}`)) return true
  if (target.includes('100x-dev')) return true
  if (options.staleOnly) return false
  return target.includes('100xprism') || resolved.includes(`${path.sep}100xprism${path.sep}`)
}

function removeLink(linkPath, removed, options = {}) {
  let stat
  try {
    stat = fs.lstatSync(linkPath)
  } catch (err) {
    if (err && err.code === 'ENOENT') return
    throw err
  }

  if (!stat.isSymbolicLink()) return

  const target = fs.readlinkSync(linkPath)
  if (!isSafe100xLink(linkPath, target, options)) return

  fs.unlinkSync(linkPath)
  removed.push(`${linkPath} -> ${target}`)
}

function candidateDirs(home = os.homedir()) {
  const dirs = [
    path.dirname(process.execPath),
    process.env.npm_config_prefix ? path.join(process.env.npm_config_prefix, 'bin') : '',
    path.join(home, '.local', 'share', 'mise', 'shims'),
  ]

  const miseNodeRoot = path.join(home, '.local', 'share', 'mise', 'installs', 'node')
  try {
    for (const version of fs.readdirSync(miseNodeRoot)) {
      dirs.push(path.join(miseNodeRoot, version, 'bin'))
    }
  } catch (_) {
    // mise is optional.
  }

  return uniq(dirs)
}

function cleanRcFile(file, cleaned) {
  let before
  try {
    before = fs.readFileSync(file, 'utf8')
  } catch (err) {
    if (err && err.code === 'ENOENT') return
    throw err
  }

  const lines = before.split(/\n/)
  const kept = lines.filter(line => {
    if (line.includes('100xprism/shell/aliases.sh')) return false
    if (line.includes('100x-dev/shell/aliases.sh')) return false
    if (/^\s*#\s*100x(Prism| Dev) aliases\s*$/.test(line)) return false
    return true
  })

  const after = kept.join('\n')
  if (after !== before) {
    fs.writeFileSync(file, after)
    cleaned.push(file)
  }
}

function cleanShellStartup(home = os.homedir()) {
  const cleaned = []
  for (const rc of RC_FILES) cleanRcFile(path.join(home, rc), cleaned)
  return cleaned
}

function cleanClaudeSessionHooks(home = os.homedir()) {
  const settingsFile = path.join(home, '.claude', 'settings.json')
  let settings
  try {
    settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  } catch (err) {
    if (err && err.code === 'ENOENT') return { file: settingsFile, removed: 0 }
    throw err
  }

  const sessionStart = settings && settings.hooks && settings.hooks.SessionStart
  if (!Array.isArray(sessionStart)) return { file: settingsFile, removed: 0 }

  let removed = 0
  for (const entry of sessionStart) {
    if (!Array.isArray(entry.hooks)) continue
    const before = entry.hooks.length
    entry.hooks = entry.hooks.filter(hook => {
      const command = String((hook && hook.command) || '')
      return !command.includes('100xprism/shell/check-update.sh') &&
        !command.includes('100x-dev/shell/check-update.sh')
    })
    removed += before - entry.hooks.length
  }
  settings.hooks.SessionStart = sessionStart.filter(entry => Array.isArray(entry.hooks) && entry.hooks.length)
  if (removed) fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + '\n')

  return { file: settingsFile, removed }
}

function removeCommandLinks(home = os.homedir(), options = {}) {
  const removed = []
  for (const dir of candidateDirs(home)) {
    for (const name of BIN_NAMES) removeLink(path.join(dir, name), removed, options)
  }
  return removed
}

function preinstallCleanup() {
  const dashboard = stopDashboard()
  const links = removeCommandLinks(os.homedir(), { staleOnly: true })
  const startupFiles = cleanShellStartup()
  const hookCleanup = cleanClaudeSessionHooks()

  const actions = []
  if (dashboard.stopped) actions.push(`stopped dashboard process ${dashboard.pid}`)
  if (links.length) actions.push(`removed ${links.length} stale command link(s)`)
  if (startupFiles.length) actions.push(`cleaned ${startupFiles.length} shell startup file(s)`)
  if (hookCleanup.removed) actions.push(`removed ${hookCleanup.removed} Claude SessionStart hook(s)`)
  if (actions.length) console.log(`Pre-install cleanup: ${actions.join('; ')}.`)
  return { dashboard, links, startupFiles, hookCleanup }
}

function run(_args = []) {
  const dashboard = stopDashboard()
  if (dashboard.stopped) {
    console.log(`Stopped token dashboard process ${dashboard.pid}.`)
  }

  const links = removeCommandLinks()
  if (links.length) {
    console.log('Removed 100xprism command symlinks:')
    for (const item of links) console.log(`  - ${item}`)
  }

  const startupFiles = cleanShellStartup()
  if (startupFiles.length) {
    console.log('Removed 100xprism shell-startup entries from:')
    for (const file of startupFiles) console.log(`  - ${file}`)
  }

  const hookCleanup = cleanClaudeSessionHooks()
  if (hookCleanup.removed) {
    console.log(`Removed ${hookCleanup.removed} Claude SessionStart update-check hook(s) from ${hookCleanup.file}.`)
  }

  if (!dashboard.stopped && !links.length && !startupFiles.length && !hookCleanup.removed) {
    console.log('No 100xprism dashboard, command symlinks, or shell-startup entries found.')
  }

  console.log('If you use mise, run: mise reshim node')
}

if (require.main === module) run(process.argv.slice(2))

module.exports = {
  run,
  candidateDirs,
  cleanClaudeSessionHooks,
  cleanShellStartup,
  isSafe100xLink,
  preinstallCleanup,
  removeCommandLinks,
}
