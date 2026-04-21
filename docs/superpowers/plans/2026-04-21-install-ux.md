# Install UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken two-line README clone instruction with `curl | bash` (Mac/Linux) + `npm install -g 100x-dev` (all platforms), and add a `100x-dev init` command for per-project setup.

**Architecture:** A thin npm package (`bin/100x-dev.js`) dispatches to existing bash scripts on Mac/Linux and to a Node.js implementation on Windows. A new `get.sh` handles the curl|bash bootstrap with idempotent clone-or-pull. `install.sh` becomes Phase 1 only (global); per-project logic moves to a new `install-project.sh`.

**Tech Stack:** Bash (existing), Node.js 18+ (CommonJS, no external deps), npm registry for distribution.

---

## File Map

**New files:**
| File | Purpose |
|------|---------|
| `get.sh` | curl\|bash bootstrap — clone or pull `~/100x-dev`, then exec `install.sh` |
| `install-project.sh` | Phase 2: per-project setup (extracted from `install.sh`) |
| `package.json` | npm package definition |
| `.npmignore` | exclude dev/docs files from npm publish |
| `bin/100x-dev.js` | CLI entry point — parse subcommand, delegate |
| `lib/platform.js` | OS detection, home-dir path helpers |
| `lib/bootstrap.js` | ensure `~/100x-dev` exists (clone or pull) |
| `lib/install.js` | Phase 1 global: exec `install.sh` (Mac/Linux) or JS impl (Windows) |
| `lib/init.js` | Phase 2 per-project: exec `install-project.sh` (Mac/Linux) or JS (Windows) |
| `lib/update.js` | exec `update.sh` (Mac/Linux) or JS (Windows) |
| `lib/adapters/windows.js` | Windows file-copy implementations for all 6 adapters |
| `test/platform.test.js` | unit tests for `lib/platform.js` |
| `test/windows-adapters.test.js` | unit tests for `lib/adapters/windows.js` |

**Modified files:**
| File | Change |
|------|--------|
| `install.sh` | Remove per-project path prompt + adapter calls; add `100x-dev init` hint |
| `README.md` | Replace two-line clone instruction with new install commands |

---

## Task 1: Create get.sh

**Files:**
- Create: `get.sh`

- [ ] **Step 1: Write get.sh**

```bash
#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/100x-dev"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "100x-dev already installed — pulling latest..."
  git -C "$INSTALL_DIR" pull --rebase origin main --quiet
else
  echo "Installing 100x-dev..."
  git clone https://github.com/rajitsaha/100x-dev.git "$INSTALL_DIR" --quiet
fi

exec bash "$INSTALL_DIR/install.sh" "$@"
```

- [ ] **Step 2: Make executable**

```bash
chmod +x get.sh
```

- [ ] **Step 3: Validate syntax**

```bash
bash -n get.sh && echo "get.sh OK"
```

Expected: `get.sh OK`

- [ ] **Step 4: Smoke test — already-installed path**

```bash
# Run from within the repo itself (~/100x-dev already exists)
bash -c 'INSTALL_DIR=$(pwd) && [ -d "$INSTALL_DIR/.git" ] && echo "would pull" || echo "would clone"'
```

Expected: `would pull`

- [ ] **Step 5: Commit**

```bash
git add get.sh
git commit -m "feat: add get.sh — idempotent curl|bash bootstrap"
```

---

## Task 2: Extract install-project.sh + modify install.sh

**Files:**
- Create: `install-project.sh`
- Modify: `install.sh`

- [ ] **Step 1: Write install-project.sh**

This contains the per-project tool selection and adapter dispatch extracted from `install.sh`. Accepts optional `$1` project path, defaulting to `$PWD`.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$(cd "${1:-$PWD}" && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════╗"
echo "║    100x Dev — Project Setup          ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  Project: $PROJECT_PATH"
echo ""

TOOL_CLAUDE=false
TOOL_CURSOR=false
TOOL_CODEX=false
TOOL_WINDSURF=false
TOOL_COPILOT=false
TOOL_GEMINI=false
TOOL_ANTIGRAVITY=false

select_tools() {
  echo "Which AI coding tools do you use in this project?"
  echo "  (Enter numbers to toggle, then press Enter with no input to confirm)"
  echo ""

  while true; do
    echo "  [$([ "$TOOL_CLAUDE" = true ] && echo "x" || echo " ")] 1) Claude Code"
    echo "  [$([ "$TOOL_CURSOR" = true ] && echo "x" || echo " ")] 2) Cursor"
    echo "  [$([ "$TOOL_CODEX" = true ] && echo "x" || echo " ")] 3) Codex (OpenAI)"
    echo "  [$([ "$TOOL_WINDSURF" = true ] && echo "x" || echo " ")] 4) Windsurf"
    echo "  [$([ "$TOOL_COPILOT" = true ] && echo "x" || echo " ")] 5) Copilot CLI"
    echo "  [$([ "$TOOL_GEMINI" = true ] && echo "x" || echo " ")] 6) Gemini CLI"
    echo "  [$([ "$TOOL_ANTIGRAVITY" = true ] && echo "x" || echo " ")] 7) Antigravity"
    echo ""
    read -rp "  Toggle (1-7) or press Enter to confirm: " choice
    case "$choice" in
      1) TOOL_CLAUDE=$([ "$TOOL_CLAUDE" = true ] && echo false || echo true) ;;
      2) TOOL_CURSOR=$([ "$TOOL_CURSOR" = true ] && echo false || echo true) ;;
      3) TOOL_CODEX=$([ "$TOOL_CODEX" = true ] && echo false || echo true) ;;
      4) TOOL_WINDSURF=$([ "$TOOL_WINDSURF" = true ] && echo false || echo true) ;;
      5) TOOL_COPILOT=$([ "$TOOL_COPILOT" = true ] && echo false || echo true) ;;
      6) TOOL_GEMINI=$([ "$TOOL_GEMINI" = true ] && echo false || echo true) ;;
      7) TOOL_ANTIGRAVITY=$([ "$TOOL_ANTIGRAVITY" = true ] && echo false || echo true) ;;
      "") break ;;
      *) echo "  Invalid choice. Enter 1-7." ;;
    esac
    echo ""
  done

  if [ "$TOOL_CLAUDE" = false ] && [ "$TOOL_CURSOR" = false ] && [ "$TOOL_CODEX" = false ] && \
     [ "$TOOL_WINDSURF" = false ] && [ "$TOOL_COPILOT" = false ] && [ "$TOOL_GEMINI" = false ] && \
     [ "$TOOL_ANTIGRAVITY" = false ]; then
    echo -e "  ${YELLOW}No tools selected. Please select at least one.${NC}"
    echo ""
    select_tools
  fi
}

select_tools

if [ "$TOOL_CLAUDE" = true ]; then
  source "$REPO_DIR/adapters/claude-code.sh"
  install_project "$PROJECT_PATH"
fi

[ "$TOOL_CURSOR" = true ]      && bash "$REPO_DIR/adapters/cursor.sh"      "$PROJECT_PATH"
[ "$TOOL_CODEX" = true ]       && bash "$REPO_DIR/adapters/codex.sh"       "$PROJECT_PATH"
[ "$TOOL_WINDSURF" = true ]    && bash "$REPO_DIR/adapters/windsurf.sh"    "$PROJECT_PATH"
[ "$TOOL_COPILOT" = true ]     && bash "$REPO_DIR/adapters/copilot.sh"     "$PROJECT_PATH"
[ "$TOOL_GEMINI" = true ]      && bash "$REPO_DIR/adapters/gemini.sh"      "$PROJECT_PATH"
[ "$TOOL_ANTIGRAVITY" = true ] && bash "$REPO_DIR/adapters/antigravity.sh" "$PROJECT_PATH"

echo ""
echo -e "${GREEN}✓ Project set up!${NC}"
echo -e "${CYAN}  Run 100x-dev update any time to pull latest workflows.${NC}"
echo ""
```

- [ ] **Step 2: Make install-project.sh executable**

```bash
chmod +x install-project.sh
```

- [ ] **Step 3: Modify install.sh — replace install_workflows()**

Find the `install_workflows()` function (lines 107–134 of install.sh). Replace the entire function body with the version below that only handles the global Claude Code install:

```bash
install_workflows() {
  if [ "$TOOL_CLAUDE" = true ]; then
    source "$REPO_DIR/adapters/claude-code.sh"
    install_global
  fi
}
```

- [ ] **Step 4: Modify install.sh — update the completion message**

Find the completion block at the bottom:

```bash
echo ""
echo "──────────────────────────────────────"
echo -e "${GREEN}✓ Done!${NC}"
[ "$TOOL_CLAUDE" = true ] && echo -e "${CYAN}  Claude Code: restart to load workflows. Run /reload-plugins for plugins.${NC}"
echo ""
```

Replace with:

```bash
echo ""
echo "──────────────────────────────────────"
echo -e "${GREEN}✓ Done!${NC}"
[ "$TOOL_CLAUDE" = true ] && echo -e "${CYAN}  Claude Code: restart to load workflows. Run /reload-plugins for plugins.${NC}"
echo -e "${CYAN}  Next: cd into a project and run  100x-dev init  to set it up.${NC}"
echo ""
```

- [ ] **Step 5: Validate bash syntax**

```bash
bash -n install.sh && echo "install.sh OK"
bash -n install-project.sh && echo "install-project.sh OK"
```

Expected: both print OK.

- [ ] **Step 6: Commit**

```bash
git add install.sh install-project.sh
git commit -m "feat: extract install-project.sh — split global and per-project install phases"
```

---

## Task 3: npm package scaffolding + lib/platform.js

**Files:**
- Create: `package.json`
- Create: `.npmignore`
- Create: `lib/platform.js`
- Create: `test/platform.test.js`

- [ ] **Step 1: Write package.json**

```json
{
  "name": "100x-dev",
  "version": "1.3.1",
  "description": "24 slash commands. Quality gates on every commit. Works with any AI coding tool.",
  "bin": {
    "100x-dev": "./bin/100x-dev.js"
  },
  "files": [
    "bin/",
    "lib/",
    "workflows/",
    "plugins/",
    "templates/",
    "shell/",
    "adapters/",
    "get.sh",
    "install.sh",
    "install-project.sh",
    "update.sh",
    "VERSION"
  ],
  "engines": {
    "node": ">=18.0.0"
  },
  "keywords": [
    "claude-code", "cursor", "codex", "ai-coding", "developer-workflow", "slash-commands"
  ],
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/rajitsaha/100x-dev.git"
  },
  "homepage": "https://github.com/rajitsaha/100x-dev"
}
```

- [ ] **Step 2: Write .npmignore**

```
docs/
test/
.github/
*.bak
.DS_Store
```

- [ ] **Step 3: Create lib directory and write lib/platform.js**

```bash
mkdir -p lib
```

```js
'use strict'

const os = require('os')
const path = require('path')

const isWindows = process.platform === 'win32'
const isMac = process.platform === 'darwin'
const isLinux = process.platform === 'linux'
const home = os.homedir()

const installDir = path.join(home, '100x-dev')
const claudeDir = path.join(home, '.claude')
const claudeCommandsDir = path.join(claudeDir, 'commands')
const claudeSettingsFile = path.join(claudeDir, 'settings.json')
const trackedProjectsFile = path.join(home, '.100x-dev', 'tracked-projects')

module.exports = {
  isWindows, isMac, isLinux,
  home, installDir,
  claudeDir, claudeCommandsDir, claudeSettingsFile,
  trackedProjectsFile,
}
```

- [ ] **Step 4: Create test directory and write test/platform.test.js**

```bash
mkdir -p test
```

```js
'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const os = require('os')
const path = require('path')
const platform = require('../lib/platform')

test('home resolves to os.homedir()', () => {
  assert.equal(platform.home, os.homedir())
})

test('installDir is ~/100x-dev', () => {
  assert.equal(platform.installDir, path.join(os.homedir(), '100x-dev'))
})

test('claudeCommandsDir is ~/.claude/commands', () => {
  assert.equal(platform.claudeCommandsDir, path.join(os.homedir(), '.claude', 'commands'))
})

test('claudeSettingsFile is ~/.claude/settings.json', () => {
  assert.equal(platform.claudeSettingsFile, path.join(os.homedir(), '.claude', 'settings.json'))
})

test('trackedProjectsFile is ~/.100x-dev/tracked-projects', () => {
  assert.equal(platform.trackedProjectsFile, path.join(os.homedir(), '.100x-dev', 'tracked-projects'))
})
```

- [ ] **Step 5: Run tests**

```bash
node --test test/platform.test.js
```

Expected: 5 passing tests.

- [ ] **Step 6: Commit**

```bash
git add package.json .npmignore lib/platform.js test/platform.test.js
git commit -m "feat: add npm package scaffold and lib/platform.js"
```

---

## Task 4: lib/bootstrap.js

**Files:**
- Create: `lib/bootstrap.js`

- [ ] **Step 1: Write lib/bootstrap.js**

Uses `spawnSync` with argument arrays (not string interpolation) to avoid shell injection.

```js
'use strict'

const { spawnSync } = require('child_process')
const fs = require('fs')
const path = require('path')
const { installDir } = require('./platform')

const REPO_URL = 'https://github.com/rajitsaha/100x-dev.git'

function bootstrap() {
  const gitDir = path.join(installDir, '.git')

  if (fs.existsSync(gitDir)) {
    console.log('100x-dev already installed — pulling latest...')
    const result = spawnSync('git', ['-C', installDir, 'pull', '--rebase', 'origin', 'main', '--quiet'], { stdio: 'inherit' })
    if (result.status !== 0) {
      console.error('git pull failed')
      process.exit(result.status ?? 1)
    }
  } else {
    console.log('Installing 100x-dev...')
    fs.mkdirSync(path.dirname(installDir), { recursive: true })
    const result = spawnSync('git', ['clone', REPO_URL, installDir, '--quiet'], { stdio: 'inherit' })
    if (result.status !== 0) {
      console.error('git clone failed')
      process.exit(result.status ?? 1)
    }
  }
}

module.exports = { bootstrap }
```

- [ ] **Step 2: Verify syntax**

```bash
node -e "require('./lib/bootstrap')" && echo "bootstrap.js OK"
```

Expected: `bootstrap.js OK`

- [ ] **Step 3: Commit**

```bash
git add lib/bootstrap.js
git commit -m "feat: add lib/bootstrap.js — clone or pull ~/100x-dev"
```

---

## Task 5: bin/100x-dev.js

**Files:**
- Create: `bin/100x-dev.js`

- [ ] **Step 1: Create bin directory**

```bash
mkdir -p bin
```

- [ ] **Step 2: Write bin/100x-dev.js**

```js
#!/usr/bin/env node
'use strict'

const HELP = `
Usage: 100x-dev <command>

Commands:
  install    Global setup — copy workflows to ~/.claude/commands/, install plugins
  init       Per-project setup — run from your project root
  update     Pull latest workflows and regenerate tracked projects
  check      Check for a newer version without applying

Examples:
  npm install -g 100x-dev && 100x-dev install
  cd my-project && 100x-dev init
  100x-dev update
`.trimStart()

const [,, cmd, ...args] = process.argv

switch (cmd) {
  case 'install': require('../lib/install').run(args); break
  case 'init':    require('../lib/init').run(args);    break
  case 'update':  require('../lib/update').run(args);  break
  case 'check':   require('../lib/update').run(['--check-only']); break
  default:
    process.stdout.write(HELP)
    process.exit(cmd ? 1 : 0)
}
```

- [ ] **Step 3: Make executable**

```bash
chmod +x bin/100x-dev.js
```

- [ ] **Step 4: Verify help output**

```bash
node bin/100x-dev.js
```

Expected: usage text showing `install`, `init`, `update`, `check`.

- [ ] **Step 5: Verify unknown command exits 1**

```bash
node bin/100x-dev.js foobar; echo "exit: $?"
```

Expected: `exit: 1`

- [ ] **Step 6: Commit**

```bash
git add bin/100x-dev.js
git commit -m "feat: add bin/100x-dev.js CLI entry point"
```

---

## Task 6: lib/install.js, lib/init.js, lib/update.js

**Files:**
- Create: `lib/install.js`
- Create: `lib/init.js`
- Create: `lib/update.js`

- [ ] **Step 1: Write lib/install.js**

```js
'use strict'

const { spawnSync } = require('child_process')
const path = require('path')
const { isWindows, installDir } = require('./platform')
const { bootstrap } = require('./bootstrap')

function run(_args) {
  bootstrap()
  if (isWindows) {
    require('./adapters/windows').installGlobalWindows(installDir)
  } else {
    const result = spawnSync('bash', [path.join(installDir, 'install.sh')], { stdio: 'inherit' })
    if (result.status !== 0) process.exit(result.status ?? 1)
  }
}

module.exports = { run }
```

- [ ] **Step 2: Write lib/init.js**

```js
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
```

- [ ] **Step 3: Write lib/update.js**

```js
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
```

- [ ] **Step 4: Verify all three load cleanly**

```bash
node -e "require('./lib/install'); require('./lib/init'); require('./lib/update')" && echo "all OK"
```

Expected: `all OK`

- [ ] **Step 5: Commit**

```bash
git add lib/install.js lib/init.js lib/update.js
git commit -m "feat: add lib/install.js, lib/init.js, lib/update.js"
```

---

## Task 7: lib/adapters/windows.js

**Files:**
- Create: `lib/adapters/windows.js`
- Create: `test/windows-adapters.test.js`

The workflow concatenation order matches `adapters/lib/shared.sh` line 64:
`gate test commit push pr branch launch lint security docs issue architect cloud-security enterprise-design db fix spec grill techdebt context query orchestrate update-claude`

- [ ] **Step 1: Write test/windows-adapters.test.js**

```js
'use strict'

const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('fs')
const os = require('os')
const path = require('path')
const {
  copyWorkflowsToClaudeCommands,
  scaffoldClaudeMd,
  mergePluginsJson,
  generateCombinedWorkflows,
  addTrackedProject,
} = require('../lib/adapters/windows')

function makeTmpDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), '100x-test-'))
}

test('copyWorkflowsToClaudeCommands copies .md files and appends $ARGUMENTS', () => {
  const src = makeTmpDir()
  const dst = makeTmpDir()
  fs.writeFileSync(path.join(src, 'gate.md'), '# Gate\ncontent')
  copyWorkflowsToClaudeCommands(src, dst)
  const content = fs.readFileSync(path.join(dst, 'gate.md'), 'utf8')
  assert.ok(content.includes('# Gate'))
  assert.ok(content.includes('$ARGUMENTS'))
})

test('copyWorkflowsToClaudeCommands copies db-engines subdir', () => {
  const src = makeTmpDir()
  const dst = makeTmpDir()
  const dbDir = path.join(src, 'db-engines')
  fs.mkdirSync(dbDir)
  fs.writeFileSync(path.join(dbDir, 'postgres.md'), '# Postgres')
  copyWorkflowsToClaudeCommands(src, dst)
  assert.ok(fs.existsSync(path.join(dst, 'db-engines', 'postgres.md')))
})

test('scaffoldClaudeMd writes CLAUDE.md with project name', () => {
  const projectDir = makeTmpDir()
  scaffoldClaudeMd(projectDir)
  const content = fs.readFileSync(path.join(projectDir, 'CLAUDE.md'), 'utf8')
  assert.ok(content.includes(path.basename(projectDir)))
  assert.ok(content.includes('## Database'))
  assert.ok(content.includes('## Rules'))
})

test('scaffoldClaudeMd skips if CLAUDE.md already exists', () => {
  const projectDir = makeTmpDir()
  fs.writeFileSync(path.join(projectDir, 'CLAUDE.md'), 'existing')
  scaffoldClaudeMd(projectDir)
  assert.equal(fs.readFileSync(path.join(projectDir, 'CLAUDE.md'), 'utf8'), 'existing')
})

test('scaffoldClaudeMd skips if .cursorrules already exists', () => {
  const projectDir = makeTmpDir()
  fs.writeFileSync(path.join(projectDir, '.cursorrules'), 'existing')
  scaffoldClaudeMd(projectDir)
  assert.ok(!fs.existsSync(path.join(projectDir, 'CLAUDE.md')))
})

test('mergePluginsJson adds plugins to settings.json', () => {
  const settingsFile = path.join(makeTmpDir(), 'settings.json')
  const pluginsFile = path.join(makeTmpDir(), 'plugins.json')
  fs.writeFileSync(settingsFile, JSON.stringify({ enabledPlugins: {} }))
  fs.writeFileSync(pluginsFile, JSON.stringify({ plugins: ['plugin-a', 'plugin-b'] }))
  mergePluginsJson(pluginsFile, settingsFile)
  const settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  assert.equal(settings.enabledPlugins['plugin-a'], true)
  assert.equal(settings.enabledPlugins['plugin-b'], true)
})

test('mergePluginsJson is idempotent', () => {
  const settingsFile = path.join(makeTmpDir(), 'settings.json')
  const pluginsFile = path.join(makeTmpDir(), 'plugins.json')
  fs.writeFileSync(settingsFile, JSON.stringify({ enabledPlugins: { 'plugin-a': true } }))
  fs.writeFileSync(pluginsFile, JSON.stringify({ plugins: ['plugin-a'] }))
  mergePluginsJson(pluginsFile, settingsFile)
  const settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  assert.equal(Object.keys(settings.enabledPlugins).length, 1)
})

test('generateCombinedWorkflows concatenates gate before commit', () => {
  const workflowsDir = makeTmpDir()
  fs.writeFileSync(path.join(workflowsDir, 'gate.md'), '# Gate')
  fs.writeFileSync(path.join(workflowsDir, 'commit.md'), '# Commit')
  const result = generateCombinedWorkflows(workflowsDir)
  assert.ok(result.indexOf('# Gate') < result.indexOf('# Commit'))
})

test('addTrackedProject writes path to file', () => {
  const trackedFile = path.join(makeTmpDir(), 'tracked-projects')
  addTrackedProject('/some/project', trackedFile)
  assert.ok(fs.readFileSync(trackedFile, 'utf8').includes('/some/project'))
})

test('addTrackedProject is idempotent', () => {
  const trackedFile = path.join(makeTmpDir(), 'tracked-projects')
  addTrackedProject('/some/project', trackedFile)
  addTrackedProject('/some/project', trackedFile)
  const lines = fs.readFileSync(trackedFile, 'utf8').trim().split('\n')
  assert.equal(lines.filter(l => l === '/some/project').length, 1)
})
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
node --test test/windows-adapters.test.js 2>&1 | head -3
```

Expected: `Cannot find module '../lib/adapters/windows'`

- [ ] **Step 3: Create lib/adapters directory**

```bash
mkdir -p lib/adapters
```

- [ ] **Step 4: Write lib/adapters/windows.js**

```js
'use strict'

const fs = require('fs')
const path = require('path')
const { spawnSync } = require('child_process')

const WORKFLOW_ORDER = [
  'gate', 'test', 'commit', 'push', 'pr', 'branch', 'launch', 'lint',
  'security', 'docs', 'issue', 'architect', 'cloud-security',
  'enterprise-design', 'db', 'fix', 'spec', 'grill', 'techdebt',
  'context', 'query', 'orchestrate', 'update-claude',
]

function copyWorkflowsToClaudeCommands(workflowsDir, commandsDir) {
  fs.mkdirSync(commandsDir, { recursive: true })
  for (const file of fs.readdirSync(workflowsDir).filter(f => f.endsWith('.md'))) {
    const content = fs.readFileSync(path.join(workflowsDir, file), 'utf8')
    fs.writeFileSync(path.join(commandsDir, file), content + '\n$ARGUMENTS\n')
  }
  const dbEnginesDir = path.join(workflowsDir, 'db-engines')
  if (fs.existsSync(dbEnginesDir)) {
    const dstDbDir = path.join(commandsDir, 'db-engines')
    fs.mkdirSync(dstDbDir, { recursive: true })
    for (const file of fs.readdirSync(dbEnginesDir).filter(f => f.endsWith('.md'))) {
      fs.copyFileSync(path.join(dbEnginesDir, file), path.join(dstDbDir, file))
    }
  }
}

function scaffoldClaudeMd(projectPath) {
  const existing = [
    'CLAUDE.md', 'AGENTS.md', '.cursorrules', '.windsurfrules', 'GEMINI.md',
    path.join('.github', 'copilot-instructions.md'),
  ]
  if (existing.some(f => fs.existsSync(path.join(projectPath, f)))) return

  const projectName = path.basename(path.resolve(projectPath))
  fs.writeFileSync(path.join(projectPath, 'CLAUDE.md'), `# ${projectName} — Project Instructions

<!-- Generated by 100x-dev. Fill in the sections below so workflows like /db, /gate, /launch have project context. -->

## Project

<!-- Describe what this project does in 2-3 sentences. Used by /architect and /enterprise-design. -->
description: TODO

## Database

<!-- Used by /db and /query. Remove if not applicable. -->
# engine: postgres
# connection: default
# connections:
#   default:
#     host: localhost
#     port: 5432
#     name: mydb
#     user: myuser
#     auth: env:DB_PASSWORD

## Cloud (GCP)

<!-- Used by /gate, /cloud-security, /launch. Remove if not on GCP. -->
# gcp_project: my-gcp-project
# cloud_run_service: my-service
# region: us-central1

## Production

<!-- Used by /launch and /push for health checks and smoke tests. -->
# production_url: https://example.com
# health_url: https://example.com/health

## Security Exceptions

# security_exceptions:
#   - CVE-2023-XXXX: false positive in test dependency

## Rules

<!-- Add project-specific rules for Claude here. /update-claude appends to this section. -->
`)
  console.log(`  → Scaffolded CLAUDE.md in ${projectPath} ✓`)
}

function mergePluginsJson(pluginsFile, settingsFile) {
  if (!fs.existsSync(settingsFile)) {
    fs.mkdirSync(path.dirname(settingsFile), { recursive: true })
    fs.writeFileSync(settingsFile, '{}')
  }
  const pluginsData = JSON.parse(fs.readFileSync(pluginsFile, 'utf8'))
  const settings = JSON.parse(fs.readFileSync(settingsFile, 'utf8'))
  const enabled = settings.enabledPlugins || {}
  for (const p of (pluginsData.plugins || [])) {
    if (!(p in enabled)) enabled[p] = true
  }
  settings.enabledPlugins = enabled
  settings.extraKnownMarketplaces = {
    ...settings.extraKnownMarketplaces,
    ...(pluginsData.extraKnownMarketplaces || {}),
  }
  fs.writeFileSync(settingsFile, JSON.stringify(settings, null, 2))
}

function generateCombinedWorkflows(workflowsDir) {
  const lines = [
    '# 100x Dev Workflows',
    '# Generated by 100x-dev (https://github.com/rajitsaha/100x-dev)',
    '',
  ]
  for (const name of WORKFLOW_ORDER) {
    const file = path.join(workflowsDir, `${name}.md`)
    if (fs.existsSync(file)) {
      lines.push('---', '', fs.readFileSync(file, 'utf8').trimEnd(), '')
    }
  }
  return lines.join('\n')
}

function addTrackedProject(projectPath, trackedFile) {
  fs.mkdirSync(path.dirname(trackedFile), { recursive: true })
  const existing = fs.existsSync(trackedFile)
    ? fs.readFileSync(trackedFile, 'utf8').split('\n').filter(Boolean)
    : []
  if (!existing.includes(projectPath)) {
    fs.appendFileSync(trackedFile, projectPath + '\n')
  }
}

function writeAdapter(content, outputFile) {
  fs.mkdirSync(path.dirname(outputFile), { recursive: true })
  fs.writeFileSync(outputFile, content)
  console.log(`  → Generated ${outputFile} ✓`)
}

function installGlobalWindows(installDir) {
  const { claudeCommandsDir, claudeSettingsFile } = require('../platform')
  copyWorkflowsToClaudeCommands(path.join(installDir, 'workflows'), claudeCommandsDir)
  mergePluginsJson(path.join(installDir, 'plugins', 'plugins.json'), claudeSettingsFile)
  console.log('✓ Workflows installed to ~/.claude/commands/')
  console.log('✓ Plugins merged into ~/.claude/settings.json')
  console.log('\nNext: cd into a project and run  100x-dev init  to set it up.')
}

function initProjectWindows(installDir, projectPath) {
  const { trackedProjectsFile } = require('../platform')
  const workflowsDir = path.join(installDir, 'workflows')
  const absProject = path.resolve(projectPath)
  const readline = require('readline')
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout })

  console.log('\n100x Dev — Project Setup')
  console.log(`  Project: ${absProject}\n`)

  const tools = [
    { label: 'Claude Code (CLAUDE.md scaffold)', key: 'claude' },
    { label: 'Cursor (.cursorrules)', key: 'cursor' },
    { label: 'Codex (AGENTS.md)', key: 'codex' },
    { label: 'Windsurf (.windsurfrules)', key: 'windsurf' },
    { label: 'Copilot CLI (.github/copilot-instructions.md)', key: 'copilot' },
    { label: 'Gemini CLI (GEMINI.md)', key: 'gemini' },
    { label: 'Antigravity (ANTIGRAVITY.md)', key: 'antigravity' },
  ]
  const selected = {}

  function promptNext(idx) {
    if (idx >= tools.length) {
      rl.close()
      applyAdapters()
      return
    }
    rl.question(`  Set up ${tools[idx].label}? [y/N] `, ans => {
      selected[tools[idx].key] = /^y$/i.test(ans.trim())
      promptNext(idx + 1)
    })
  }

  function applyAdapters() {
    const combined = generateCombinedWorkflows(workflowsDir)
    if (selected.claude)      scaffoldClaudeMd(absProject)
    if (selected.cursor)      writeAdapter(combined, path.join(absProject, '.cursorrules'))
    if (selected.codex)       writeAdapter(combined, path.join(absProject, 'AGENTS.md'))
    if (selected.windsurf)    writeAdapter(combined, path.join(absProject, '.windsurfrules'))
    if (selected.copilot)     writeAdapter(combined, path.join(absProject, '.github', 'copilot-instructions.md'))
    if (selected.gemini)      writeAdapter(combined, path.join(absProject, 'GEMINI.md'))
    if (selected.antigravity) writeAdapter(combined, path.join(absProject, 'ANTIGRAVITY.md'))
    addTrackedProject(absProject, trackedProjectsFile)
    console.log('\n✓ Project set up!')
  }

  promptNext(0)
}

function updateWindows(installDir, checkOnly) {
  const fetchResult = spawnSync('git', ['-C', installDir, 'fetch', 'origin', 'main', '--quiet'], { stdio: 'inherit' })
  if (fetchResult.status !== 0) { console.error('git fetch failed'); process.exit(1) }

  const local  = spawnSync('git', ['-C', installDir, 'rev-parse', 'HEAD']).stdout.toString().trim()
  const remote = spawnSync('git', ['-C', installDir, 'rev-parse', 'origin/main']).stdout.toString().trim()

  if (local === remote) { console.log('✓ Already up to date.'); return }

  if (checkOnly) { console.log('Update available. Run: 100x-dev update'); return }

  const pullResult = spawnSync('git', ['-C', installDir, 'pull', '--rebase', 'origin', 'main', '--quiet'], { stdio: 'inherit' })
  if (pullResult.status !== 0) { console.error('git pull failed'); process.exit(1) }

  installGlobalWindows(installDir)
  console.log('✓ 100x-dev updated!')
}

module.exports = {
  copyWorkflowsToClaudeCommands,
  scaffoldClaudeMd,
  mergePluginsJson,
  generateCombinedWorkflows,
  addTrackedProject,
  installGlobalWindows,
  initProjectWindows,
  updateWindows,
}
```

- [ ] **Step 5: Run tests**

```bash
node --test test/windows-adapters.test.js
```

Expected: all 10 tests pass.

- [ ] **Step 6: Run all tests together**

```bash
node --test test/platform.test.js test/windows-adapters.test.js
```

Expected: 15 tests passing, 0 failing.

- [ ] **Step 7: Commit**

```bash
git add lib/adapters/windows.js test/windows-adapters.test.js
git commit -m "feat: add lib/adapters/windows.js with full test coverage"
```

---

## Task 8: Update README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the install block**

Find:
```markdown
```bash
git clone https://github.com/rajitsaha/100x-dev.git ~/100x-dev
cd ~/100x-dev && ./install.sh
```
```

Replace with:
````markdown
```bash
# Mac / Linux
curl -fsSL https://raw.githubusercontent.com/rajitsaha/100x-dev/main/get.sh | bash

# Windows (or anywhere Node.js is installed)
npm install -g 100x-dev && 100x-dev install
```

Run once per machine. Then to add 100x-dev to a project:

```bash
cd my-project && 100x-dev init
```
````

- [ ] **Step 2: Update the manual update reference**

Find:
```markdown
**Manual**: `~/100x-dev/update.sh` to update, `~/100x-dev/update.sh --check-only` to check.
```

Replace with:
```markdown
**Manual**: `100x-dev update` to update, `100x-dev check` to check.
```

- [ ] **Step 3: Verify README has no broken markdown**

```bash
grep -c '```' README.md
```

Expected: an even number (balanced fences).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: update README with new install instructions"
```

---

## Task 9: Publish to npm

- [ ] **Step 1: Check if package name is available**

```bash
npm view 100x-dev 2>&1 | head -3
```

If name is taken, update `package.json` `name` to `@rajitsaha/100x-dev` and update the help text in `bin/100x-dev.js`.

- [ ] **Step 2: Dry-run to verify included files**

```bash
npm pack --dry-run 2>&1 | grep -E '^\s+(bin|lib|workflows|plugins|shell|adapters|get\.sh|install)'
```

Expected: all the above directories and files appear. `test/` and `docs/` should NOT appear.

- [ ] **Step 3: Login to npm**

```bash
npm login
```

- [ ] **Step 4: Publish**

```bash
npm publish --access public
```

- [ ] **Step 5: Verify end-to-end**

```bash
npm install -g 100x-dev
100x-dev
```

Expected: help text prints with all four subcommands.

- [ ] **Step 6: Tag the release**

```bash
git commit --allow-empty -m "chore: publish v1.3.1 to npm"
git tag npm-v1.3.1
git push origin main --tags
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|-----------------|------|
| `get.sh` idempotent curl\|bash bootstrap | Task 1 |
| `install.sh` Phase 1 only, no project-path prompt | Task 2 |
| `install-project.sh` Phase 2, defaults to `$PWD` | Task 2 |
| `package.json` npm package definition | Task 3 |
| `lib/platform.js` with unit tests | Task 3 |
| `lib/bootstrap.js` clone/pull with `spawnSync` arrays | Task 4 |
| `bin/100x-dev.js` with install/init/update/check | Task 5 |
| `lib/install.js`, `lib/init.js`, `lib/update.js` | Task 6 |
| All 6 Windows adapter implementations + tests | Task 7 |
| README updated | Task 8 |
| npm publish | Task 9 |

All spec requirements covered.
