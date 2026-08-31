'use strict'

const { spawnSync } = require('child_process')
const path = require('path')
const { isWindows, installDir } = require('./platform')
const { bootstrap } = require('./bootstrap')
const { kickDashboard, dashboardStartedMessage, dashboardStartInstructions } = require('./dashboard')

function run(args) {
  const startDashboard = args.includes('--dashboard')
  const filteredArgs = args.filter(arg => arg !== '--dashboard' && arg !== '--no-dashboard')
  bootstrap()
  const projectPath = filteredArgs[0] || process.cwd()
  if (isWindows) {
    require('./adapters/windows').initProjectWindows(installDir, projectPath)
  } else {
    const result = spawnSync('bash', [path.join(installDir, 'install-project.sh'), projectPath], { stdio: 'inherit' })
    if (result.status !== 0) process.exit(result.status ?? 1)
  }
  if (startDashboard) {
    if (kickDashboard()) {
      console.log(dashboardStartedMessage())
    } else {
      console.log(dashboardStartInstructions())
    }
  }
}

module.exports = { run }
