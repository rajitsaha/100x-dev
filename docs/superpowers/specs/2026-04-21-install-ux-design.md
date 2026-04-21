# Install UX Redesign — Design Spec

**Date:** 2026-04-21  
**Status:** Approved

---

## Problem

The current install instruction has three friction points:

1. `git clone` fails silently if `~/100x-dev` already exists — no idempotency
2. `cd ~/100x-dev && ./install.sh` runs from the wrong directory, then immediately asks "what's your project path?" — confusing mental model
3. No named command for adding 100x-dev to a new project later — users must re-run the full TUI

Windows users have no supported install path at all (bash scripts won't run natively).

---

## Mental Model

Two explicit phases with named commands:

```
Phase 1 — Global (once per machine)
  Clone ~/100x-dev, install workflows to ~/.claude/commands/, add shell aliases

Phase 2 — Per-project (once per project, run from project root)
  Write .cursorrules / AGENTS.md / GEMINI.md etc., scaffold CLAUDE.md
```

---

## User-Facing Install Flow

### Mac / Linux

```bash
# Phase 1 — one time
curl -fsSL https://raw.githubusercontent.com/rajitsaha/100x-dev/main/get.sh | bash

# Phase 2 — once per project
cd my-project
100x-dev init
```

### Windows (and universal)

```bash
# Phase 1 — one time
npm install -g 100x-dev
100x-dev install

# Phase 2 — once per project
cd my-project
100x-dev init
```

### Ongoing

```bash
100x-dev update     # pull latest, regenerate all tracked projects
100x-dev check      # check for newer version without applying
```

---

## Architecture

### npm package (`100x-dev` on npm registry)

A thin dispatcher — does not duplicate the bash scripts. Provides the cross-platform `100x-dev` CLI.

```
package root
├── bin/
│   └── 100x-dev.js      # CLI entry point — parses subcommand, delegates
├── lib/
│   ├── bootstrap.js     # ensure ~/100x-dev exists (clone or pull)
│   ├── install.js       # Phase 1: exec install.sh (Mac/Linux) or JS impl (Windows)
│   ├── init.js          # Phase 2: exec install-project.sh (Mac/Linux) or JS impl (Windows)
│   ├── update.js        # exec update.sh (Mac/Linux) or JS impl (Windows)
│   └── platform.js      # OS detection, home dir resolution, path helpers
└── package.json
```

**Mac/Linux path:** bootstrap.js ensures `~/100x-dev` → exec the appropriate `.sh` script  
**Windows path:** bootstrap.js clones repo → Node.js `fs`/`path`/`os` copies files, writes JSON config directly (no bash)

The Windows JS implementation mirrors the bash adapter logic: copy `.md` files to the right locations and write/merge JSON settings. No new logic — just a JS translation of what the bash scripts already do.

### git repo (`~/100x-dev`)

Three changes to existing shell scripts:

| File | Change |
|------|--------|
| `get.sh` | **New.** curl\|bash bootstrap: clone if absent, pull if present, exec install.sh |
| `install.sh` | **Modified.** Phase 1 only — remove per-project path prompt (that moves to install-project.sh) |
| `install-project.sh` | **New.** Extracted Phase 2 logic from install.sh. Accepts project path as arg, defaults to `$PWD` |
| `update.sh` | Unchanged |
| `adapters/*` | Unchanged |
| `workflows/*` | Unchanged |

---

## `get.sh` (new file)

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

---

## `install.sh` changes

Remove the `need_project_path` block and the `install_project "$PROJECT_PATH"` call from `install_workflows()`. The global install no longer prompts for a project path.

After global install completes, print:

```
✓ Done! Run  cd <your-project> && 100x-dev init  to set up a project.
```

---

## `install-project.sh` (new file)

Accepts optional `$1` as project path (defaults to `$PWD`). Contains the current per-project logic from `install.sh`:

- Prompt which tools to set up for this project
- Run the relevant adapter scripts with the project path
- Register the project in `~/.100x-dev/tracked-projects`

`100x-dev init` calls this with `$PWD` as the default, so `cd my-project && 100x-dev init` Just Works.

---

## CLI Subcommands (`bin/100x-dev.js`)

| Command | What it does |
|---------|-------------|
| `100x-dev install` | bootstrap.js + Phase 1 (global) |
| `100x-dev init [path]` | Phase 2 for `path` or `$PWD` |
| `100x-dev update` | git pull + regenerate tracked projects |
| `100x-dev check` | check for updates, print notice, exit |

`100x-dev` with no args prints help.

---

## platform.js

Detects OS and resolves install-dir paths:

```js
const os = require('os')
const path = require('path')

const isWindows = process.platform === 'win32'
const home = os.homedir()
const installDir = path.join(home, '100x-dev')
const claudeCommandsDir = path.join(home, '.claude', 'commands')
const claudeSettingsFile = path.join(home, '.claude', 'settings.json')

module.exports = { isWindows, home, installDir, claudeCommandsDir, claudeSettingsFile }
```

---

## Windows Implementation Notes

All six adapters need a JS equivalent. Each one is a simple file write — no novel logic:

| Adapter | Operation |
|---------|-----------|
| claude-code | Copy `workflows/*.md` → `%USERPROFILE%\.claude\commands\`, merge `settings.json` |
| cursor | Concatenate workflows → `<project>/.cursorrules` |
| codex | Concatenate workflows → `<project>/AGENTS.md` |
| windsurf | Concatenate workflows → `<project>/.windsurfrules` |
| copilot | Concatenate workflows → `<project>/.github/copilot-instructions.md` |
| gemini | Concatenate workflows → `<project>/GEMINI.md` |

Common utilities:
- **File copies:** `fs.cpSync(src, dest, { recursive: true })`
- **JSON merge (plugins, hooks):** read → mutate → write (mirrors the Python block in install.sh)
- **Shell aliases:** not applicable on Windows — `100x-dev` npm bin covers the CLI surface; `cc`/`ccc` Bash aliases are skipped
- **Project path default:** `process.cwd()` — running `100x-dev init` from the project root Just Works

---

## README changes

Replace the current two-line clone instruction with:

```markdown
## Install

**Mac / Linux**
\`\`\`bash
curl -fsSL https://raw.githubusercontent.com/rajitsaha/100x-dev/main/get.sh | bash
\`\`\`

**Windows**
\`\`\`bash
npm install -g 100x-dev && 100x-dev install
\`\`\`

**Add to a project** (all platforms, run from project root)
\`\`\`bash
100x-dev init
\`\`\`
```

---

## Out of Scope

- Homebrew tap (future, after npm is proven)
- Auto-detecting existing projects on first install
- GUI / TUI redesign beyond what's needed to split phases
- Windows MSI installer
