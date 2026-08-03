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

  try {
    fs.unlinkSync(linkPath)
    removed.push(`${linkPath} -> ${target}`)
  } catch (err) {
    const detail = err && err.message ? `: ${err.message}` : ''
    console.warn(`Warning: could not remove stale command link ${linkPath}${detail}`)
  }
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
    if (/DEV_100X_HOME.*shell\/aliases\.sh/.test(line)) return false
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
    const detail = err && err.message ? `: ${err.message}` : ''
    console.warn(`Warning: could not clean Claude SessionStart hooks in ${settingsFile}${detail}`)
    return { file: settingsFile, removed: 0, warning: detail.slice(2) || 'unknown error' }
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

// Reverse pack entries 100xprism recorded inserting. Packs installed by an upstream
// CLI are left alone — we did not write those files and do not know what else that
// CLI put there. Ownership comes from the state record, never from the registry.
function cleanManagedPacks(home = os.homedir()) {
  const claudeDir = path.join(home, '.claude')
  const stateFile = path.join(claudeDir, '.100xprism-packs.json')
  const settingsFile = path.join(claudeDir, 'settings.json')

  let state
  try {
    state = JSON.parse(fs.readFileSync(stateFile, 'utf8'))
  } catch (err) {
    if (!err || err.code !== 'ENOENT') {
      console.warn(`Warning: could not read ${stateFile}: ${err.message}`)
    }
    return { file: settingsFile, removed: 0 }
  }

  let settings
  try {
    settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  } catch (err) {
    if (err && err.code === 'ENOENT') {
      fs.rmSync(stateFile, { force: true })
      return { file: settingsFile, removed: 0 }
    }
    // Malformed settings: leave BOTH files alone so the user can recover.
    console.warn(`Warning: ${settingsFile} could not be parsed — leaving pack entries in place.`)
    return { file: settingsFile, removed: 0 }
  }

  const enabled = settings.enabledPlugins || {}
  const marketplaces = settings.extraKnownMarketplaces || {}
  let removed = 0

  for (const entry of Object.values(state.packs || {})) {
    if ((entry.platforms || {})['claude-code'] !== 'installed') continue
    const owned = entry.owned || {}
    for (const plugin of owned.plugins || []) {
      // `delete` returns true even for absent keys, so check ownership explicitly.
      if (Object.prototype.hasOwnProperty.call(enabled, plugin)) {
        delete enabled[plugin]
        removed += 1
      }
    }
    const name = owned.marketplace
    if (name && !Object.keys(enabled).some(p => p.split('@').pop() === name)) {
      delete marketplaces[name]
    }
  }

  if (removed) {
    settings.enabledPlugins = enabled
    settings.extraKnownMarketplaces = marketplaces
    fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2) + '\n')
  }
  fs.rmSync(stateFile, { force: true })
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

function cleanSessionHooksOnly() {
  const hookCleanup = cleanClaudeSessionHooks()
  if (hookCleanup.removed) {
    console.log(`Removed ${hookCleanup.removed} Claude SessionStart update-check hook(s) from ${hookCleanup.file}.`)
  }
  return hookCleanup
}

function run(args = []) {
  const dashboard = stopDashboard()
  if (dashboard.stopped) {
    console.log(`Stopped token dashboard process ${dashboard.pid}.`)
  }

  const removeLiveLinks = args.includes('--remove-live-links')
  const links = removeCommandLinks(os.homedir(), { staleOnly: !removeLiveLinks })
  if (links.length) {
    console.log('Removed 100xprism command symlinks:')
    for (const item of links) console.log(`  - ${item}`)
  }

  const startupFiles = cleanShellStartup()
  if (startupFiles.length) {
    console.log('Removed 100xprism shell-startup entries from:')
    for (const file of startupFiles) console.log(`  - ${file}`)
  }

  const hookCleanup = cleanSessionHooksOnly()

  // Uninstall only — never from preinstallCleanup(). install.sh runs preinstall
  // cleanup before installing plugins, so clearing pack state there would uninstall
  // every opted-in pack on each install.
  const packCleanup = cleanManagedPacks()
  if (packCleanup.removed) {
    console.log(`Removed ${packCleanup.removed} 100xprism-managed pack plugin(s) from ${packCleanup.file}.`)
    console.log('Packs installed by an upstream CLI were left in place — remove those with their own tooling.')
  }

  if (!dashboard.stopped && !links.length && !startupFiles.length && !hookCleanup.removed && !packCleanup.removed) {
    console.log('No 100xprism dashboard, command symlinks, or shell-startup entries found.')
  }

  if (links.some(item => item.includes(`${path.sep}mise${path.sep}`))) {
    console.log('Run `mise reshim node` to refresh mise command shims.')
  }
}

if (require.main === module) {
  const args = process.argv.slice(2)
  if (args.includes('--preinstall-cleanup')) preinstallCleanup()
  else if (args.includes('--hooks-only')) cleanSessionHooksOnly()
  else run(args)
}

module.exports = {
  run,
  candidateDirs,
  cleanClaudeSessionHooks,
  cleanManagedPacks,
  cleanSessionHooksOnly,
  cleanShellStartup,
  isSafe100xLink,
  preinstallCleanup,
  removeCommandLinks,
}
