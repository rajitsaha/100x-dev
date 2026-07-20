'use strict'

const { spawnSync } = require('child_process')
const path = require('path')
const { isWindows, installDir } = require('./platform')
const { bootstrap } = require('./bootstrap')
const { kickDashboard } = require('./dashboard')

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
    kickDashboard()
    console.log('📊 Token + value dashboard → http://127.0.0.1:8787')
  }
}

module.exports = { run }
