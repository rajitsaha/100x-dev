'use strict'

const { spawnSync } = require('child_process')
const path = require('path')

const repoRoot = path.join(__dirname, '..')

function runPythonScript(script, args = []) {
  const result = spawnSync('python3', [path.join(repoRoot, 'scripts', script), ...args], {
    stdio: 'inherit',
  })
  if (result.status !== 0) process.exit(result.status ?? 1)
}

function runDashboard(args = []) {
  runPythonScript('token-dashboard.py', args)
}

function runValue(args = []) {
  runPythonScript('value-report.py', args)
}

module.exports = { runDashboard, runValue }
