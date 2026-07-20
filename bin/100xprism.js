#!/usr/bin/env node
'use strict'

const HELP = `
Usage: 100xprism <command>

Commands:
  install    Clean old artifacts, then install global Claude Code setup
  init       Per-project setup — run from your project root
  update     Pull latest workflows and regenerate tracked projects
  check      Check for a newer version without applying
  uninstall  Stop dashboard and remove stale command/shell-startup links

Examples:
  npm install -g 100xprism && 100xprism install
  cd my-project && 100xprism init
  100xprism update
  100xprism install --dashboard  # optionally start dashboard after install
  100xprism uninstall
`.trimStart()

const [,, cmd, ...args] = process.argv

switch (cmd) {
  case 'install': require('../lib/install').run(args); break
  case 'init':    require('../lib/init').run(args);    break
  case 'update':  require('../lib/update').run(args);  break
  case 'check':   require('../lib/update').run(['--check-only']); break
  case 'uninstall': require('../lib/uninstall').run(args); break
  default:
    process.stdout.write(HELP)
    process.exit(cmd ? 1 : 0)
}
