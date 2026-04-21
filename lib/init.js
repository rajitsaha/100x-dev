'use strict'

const { spawnSync } = require('child_process')
const path = require('path')
const { isWindows, installDir } = require('./platform')
const { bootstrap } = require('./bootstrap')

function run(args) {
  bootstrap()
  const projectPath = args[0] || process.cwd()
  if (isWindows) {
    require('./adapters/windows').initProjectWindows(installDir, projectPath)
  } else {
    const result = spawnSync('bash', [path.join(installDir, 'install-project.sh'), projectPath], { stdio: 'inherit' })
    if (result.status !== 0) process.exit(result.status ?? 1)
  }
}

module.exports = { run }
