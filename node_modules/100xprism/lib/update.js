'use strict'

const { spawnSync } = require('child_process')
const fs = require('fs')
const path = require('path')
const { isWindows, installDir } = require('./platform')
const { migrateLegacy } = require('./migrate')
const { kickDashboard, dashboardStartedMessage, dashboardStartInstructions } = require('./dashboard')

function run(args) {
  const checkOnly = args.includes('--check-only')
  const startDashboard = args.includes('--dashboard')

  migrateLegacy()

  if (!fs.existsSync(installDir)) {
    console.error('100xprism is not installed. Run: 100xprism install')
    process.exit(1)
  }

  if (isWindows) {
    require('./adapters/windows').updateWindows(installDir, checkOnly)
  } else {
    const script = path.join(installDir, 'update.sh')
    const scriptArgs = checkOnly ? ['--check-only'] : []
    const result = spawnSync('bash', [script, ...scriptArgs], { stdio: 'inherit' })
    // update.sh exits non-zero when per-project reconciliation was incomplete,
    // even though the global update itself succeeded. Record that for the caller
    // via exitCode rather than exiting here, so `--dashboard` still starts —
    // a project-level failure should not withhold the rest of the command.
    if (result.status !== 0) process.exitCode = result.status ?? 1
  }

  if (!checkOnly && startDashboard) {
    if (kickDashboard()) {
      console.log(dashboardStartedMessage())
    } else {
      console.log(dashboardStartInstructions())
    }
  }
}

module.exports = { run }
