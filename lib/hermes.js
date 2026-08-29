'use strict'

const { spawnSync } = require('child_process')
const path = require('path')
const { installDir } = require('./platform')
const { bootstrap } = require('./bootstrap')

// Hermes/OpenClaw skills are global (like Claude Code's) with no per-project
// artifact, so — unlike `init` — this never takes a project path. `install`
// and `update` already call this automatically whenever Hermes is detected
// on the machine (see adapters/lib/shared.sh _hermes_installed); this command
// exists for the case where a user installs Hermes *after* 100xprism and
// wants the skills without waiting for the next `100xprism update`.
function run() {
  bootstrap()
  const result = spawnSync('bash', [path.join(installDir, 'adapters', 'hermes.sh')], { stdio: 'inherit' })
  if (result.status !== 0) process.exit(result.status ?? 1)
}

module.exports = { run }
