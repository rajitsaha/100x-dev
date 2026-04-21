'use strict'

const { spawnSync } = require('child_process')
const fs = require('fs')
const path = require('path')
const { isWindows, installDir } = require('./platform')

function run(args) {
  const checkOnly = args.includes('--check-only')

  if (!fs.existsSync(installDir)) {
    console.error('100x-dev is not installed. Run: 100x-dev install')
    process.exit(1)
  }

  if (isWindows) {
    require('./adapters/windows').updateWindows(installDir, checkOnly)
  } else {
    const script = path.join(installDir, 'update.sh')
    const scriptArgs = checkOnly ? ['--check-only'] : []
    const result = spawnSync('bash', [script, ...scriptArgs], { stdio: 'inherit' })
    if (result.status !== 0) process.exit(result.status ?? 1)
  }
}

module.exports = { run }
