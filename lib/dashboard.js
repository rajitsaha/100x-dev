'use strict'

const fs = require('fs')
const os = require('os')
const { spawn, spawnSync } = require('child_process')
const path = require('path')
const { installDir } = require('./platform')

const PID_FILE = path.join(os.homedir(), '.100xprism', 'token-dashboard.pid')

function dashboardScript() {
  return path.join(installDir, 'scripts', 'token-dashboard.py')
}

function kickDashboard() {
  if (process.env.PRISM_NO_DASHBOARD) return false
  try {
    const script = dashboardScript()
    const p = spawn('python3', [script, '--ensure-daemon'], {
      detached: true, stdio: 'ignore'
    })
    p.unref()
    return true
  } catch (_) {
    return false
  }
}

function commandForPid(pid) {
  const result = spawnSync('ps', ['-p', String(pid), '-o', 'command='], { encoding: 'utf8' })
  return result.status === 0 ? result.stdout.trim() : ''
}

function readOwnedDashboardPid() {
  let record
  try {
    record = JSON.parse(fs.readFileSync(PID_FILE, 'utf8'))
  } catch (_) {
    return null
  }

  const pid = Number(record.pid)
  if (!Number.isInteger(pid) || pid <= 0 || pid === process.pid) return null

  const expected = path.resolve(record.script || dashboardScript())
  const command = commandForPid(pid)
  if (!command || !command.includes('token-dashboard.py')) return null
  if (!command.includes(expected) && !command.includes(path.resolve(dashboardScript()))) return null

  return pid
}

function sleep(milliseconds) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, milliseconds)
}

function waitForExit(pid, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      process.kill(pid, 0)
    } catch (err) {
      if (err && err.code === 'ESRCH') return true
      throw err
    }
    sleep(25)
  }
  return false
}

function stopDashboard() {
  const pid = readOwnedDashboardPid()
  if (!pid) return { stopped: false, reason: 'not running' }

  try {
    process.kill(pid, 'SIGTERM')
  } catch (err) {
    if (err && err.code !== 'ESRCH') throw err
  }

  let exited = waitForExit(pid, 1500)
  if (!exited) {
    try {
      process.kill(pid, 'SIGKILL')
      exited = waitForExit(pid, 500)
    } catch (err) {
      if (err && err.code !== 'ESRCH') throw err
      exited = true
    }
  }

  try {
    fs.rmSync(PID_FILE, { force: true })
  } catch (_) {
    // best effort
  }

  return { stopped: true, pid, exited }
}

module.exports = { kickDashboard, stopDashboard, PID_FILE }
