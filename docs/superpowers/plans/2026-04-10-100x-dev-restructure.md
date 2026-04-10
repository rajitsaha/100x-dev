# 100x-dev Multi-Tool Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure `claude-dev-setup` into `100x-dev`, a universal AI coding tool workflow system supporting Claude Code, Cursor, Codex, Windsurf, Copilot CLI, Gemini CLI, and Antigravity.

**Architecture:** Move `commands/` to `workflows/`, strip tool-specific references, add an `adapters/` layer with one shell script per tool that delivers workflows in the target format. A multi-tool `install.sh` orchestrates everything.

**Tech Stack:** Bash (adapters, installer), Markdown (workflows, templates, README)

---

## File Structure

**Create:**
- `workflows/` — moved from `commands/`, all 13 workflow files + `db-engines/`
- `adapters/claude-code.sh` — global install to `~/.claude/commands/` + plugins
- `adapters/cursor.sh` — generates `.cursorrules`
- `adapters/codex.sh` — generates `AGENTS.md`
- `adapters/windsurf.sh` — generates `.windsurfrules`
- `adapters/copilot.sh` — generates `.github/copilot-instructions.md`
- `adapters/gemini.sh` — generates `GEMINI.md`
- `adapters/antigravity.sh` — generates `ANTIGRAVITY.md`
- `plugins/plugins.json` — moved from root
- `shell/aliases.sh` — renamed from `shell/claude-aliases.sh`
- `install.sh` — rewritten multi-tool installer
- `update.sh` — rebranded
- `README.md` — rewritten

**Modify:**
- All 13 workflow files: remove `$ARGUMENTS`, update cross-refs, genericize `CLAUDE.md` references
- All 4 templates: genericize header
- `shell/aliases.sh`: rebrand aliases

**Delete (after move):**
- `commands/` directory (replaced by `workflows/`)
- `plugins.json` (moved to `plugins/plugins.json`)
- `shell/claude-aliases.sh` (replaced by `shell/aliases.sh`)

---

### Task 1: Create directory structure and move files

**Files:**
- Create: `workflows/`, `workflows/db-engines/`, `adapters/`, `plugins/`
- Move: `commands/*.md` → `workflows/*.md`
- Move: `commands/db-engines/*.md` → `workflows/db-engines/*.md`
- Move: `plugins.json` → `plugins/plugins.json`

- [ ] **Step 1: Create new directories**

```bash
mkdir -p workflows/db-engines adapters plugins
```

- [ ] **Step 2: Move command files to workflows**

```bash
git mv commands/gate.md workflows/gate.md
git mv commands/test.md workflows/test.md
git mv commands/commit.md workflows/commit.md
git mv commands/push.md workflows/push.md
git mv commands/launch.md workflows/launch.md
git mv commands/lint.md workflows/lint.md
git mv commands/security.md workflows/security.md
git mv commands/docs.md workflows/docs.md
git mv commands/issue.md workflows/issue.md
git mv commands/architect.md workflows/architect.md
git mv commands/cloud-security.md workflows/cloud-security.md
git mv commands/enterprise-design.md workflows/enterprise-design.md
git mv commands/db.md workflows/db.md
```

- [ ] **Step 3: Move db-engines**

```bash
git mv commands/db-engines/postgres.md workflows/db-engines/postgres.md
git mv commands/db-engines/snowflake.md workflows/db-engines/snowflake.md
git mv commands/db-engines/databricks.md workflows/db-engines/databricks.md
git mv commands/db-engines/athena.md workflows/db-engines/athena.md
git mv commands/db-engines/presto.md workflows/db-engines/presto.md
git mv commands/db-engines/oracle.md workflows/db-engines/oracle.md
git mv commands/db-engines/cloud-sql.md workflows/db-engines/cloud-sql.md
```

- [ ] **Step 4: Move plugins.json**

```bash
git mv plugins.json plugins/plugins.json
```

- [ ] **Step 5: Remove empty commands directory**

```bash
rmdir commands/db-engines commands
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: move commands/ to workflows/, plugins.json to plugins/"
```

---

### Task 2: Genericize workflow files — remove $ARGUMENTS

Remove the `$ARGUMENTS` line from the end of workflow files. The Claude Code adapter will re-add it during installation.

**Files:**
- Modify: `workflows/commit.md` (has `$ARGUMENTS` somewhere in the file)
- Modify: `workflows/push.md` (last line)
- Modify: `workflows/security.md` (has `$ARGUMENTS`)
- Modify: `workflows/issue.md` (has `$ARGUMENTS`)
- Modify: `workflows/architect.md` (last line)
- Modify: `workflows/cloud-security.md` (last line)
- Modify: `workflows/enterprise-design.md` (last line)
- Modify: `workflows/db.md` (last line)

Note: `gate.md`, `test.md`, `launch.md`, `lint.md`, `docs.md` do NOT have `$ARGUMENTS`.

- [ ] **Step 1: Remove $ARGUMENTS from all 8 files**

For each file, remove the line containing only `$ARGUMENTS`. In most files it's the very last line.

Files and what to remove:
- `workflows/push.md`: delete last line `$ARGUMENTS`
- `workflows/architect.md`: delete last line `$ARGUMENTS`
- `workflows/cloud-security.md`: delete last line `$ARGUMENTS`
- `workflows/enterprise-design.md`: delete last line `$ARGUMENTS`
- `workflows/db.md`: delete last line `$ARGUMENTS`
- `workflows/security.md`: find and delete the `$ARGUMENTS` line
- `workflows/commit.md`: find and delete the `$ARGUMENTS` line
- `workflows/issue.md`: find and delete the `$ARGUMENTS` line

- [ ] **Step 2: Verify no $ARGUMENTS remain**

Run: `grep -r '\$ARGUMENTS' workflows/`
Expected: no output

- [ ] **Step 3: Commit**

```bash
git add workflows/
git commit -m "refactor: remove \$ARGUMENTS from workflow files (adapter handles it)"
```

---

### Task 3: Genericize workflow files — update cross-references

Change `/slash` command references to tool-agnostic language.

**Files:**
- Modify: `workflows/gate.md` — line 9: `Invoke `/test`` → `Run the **test** workflow`
- Modify: `workflows/commit.md` — references to `/gate`
- Modify: `workflows/push.md` — references to `/gate`
- Modify: `workflows/launch.md` — references to `/test`, `/lint`, `/security`, `/commit`, `/push`
- Modify: `workflows/docs.md` — references to `/test`, `/lint`
- Modify: `workflows/issue.md` — reference to `/gate` in acceptance criteria

- [ ] **Step 1: Update gate.md**

Change:
```
Invoke `/test`. Run ALL test layers (unit, integration, E2E if configured).
```
To:
```
Run the **test** workflow. Run ALL test layers (unit, integration, E2E if configured).
```

Also change:
```
Invoke `/security`. Scan all package managers found in this project.
```
To:
```
Run the **security** workflow. Scan all package managers found in this project.
```

Also change:
```
Invoke `/cloud-security`. Run the full cloud security and data privacy scan.
```
To:
```
Run the **cloud-security** workflow. Run the full cloud security and data privacy scan.
```

- [ ] **Step 2: Update commit.md**

Change all references like `Run /gate` or `Invoke /gate` to `Run the **gate** workflow`.

- [ ] **Step 3: Update push.md**

Change all references like `Run /gate` or `Invoke /gate` to `Run the **gate** workflow`.

- [ ] **Step 4: Update launch.md**

Change all `/test`, `/lint`, `/security`, `/commit`, `/push` references to `the **test** workflow`, `the **lint** workflow`, etc.

- [ ] **Step 5: Update docs.md**

Change `/test` and `/lint` references to `the **test** workflow` and `the **lint** workflow`.

- [ ] **Step 6: Update issue.md**

Change `/gate` reference in acceptance criteria to `the **gate** workflow`.

- [ ] **Step 7: Verify no /slash cross-refs remain (except as workflow titles)**

Run: `grep -n 'Invoke `/\|Run /[a-z]' workflows/*.md`
Expected: no output (title lines like `# /gate —` are fine, those are just names)

- [ ] **Step 8: Commit**

```bash
git add workflows/
git commit -m "refactor: replace slash-command cross-references with tool-agnostic language"
```

---

### Task 4: Genericize workflow files — CLAUDE.md references

Replace `CLAUDE.md` references in workflows with multi-file detection so workflows work regardless of which tool's instruction file is present.

**Strategy:** In bash code blocks, use a detection snippet. In prose, say "project instruction file (CLAUDE.md, AGENTS.md, .cursorrules, or equivalent)".

**Files to modify (those referencing CLAUDE.md):**
- `workflows/gate.md` (lines 117-118)
- `workflows/launch.md` (lines 43, 112, 114, 143, 148-149)
- `workflows/commit.md` (lines 42, 48)
- `workflows/push.md` (line 72)
- `workflows/security.md` (lines 21, 23)
- `workflows/docs.md` (lines 26, 62, 65, 77)
- `workflows/architect.md` (lines 17, 21)
- `workflows/enterprise-design.md` (line 20)
- `workflows/cloud-security.md` (lines 17, 27)
- `workflows/db.md` (lines 4, 38, 47, 54, 79)

**Detection snippet** to use in bash code blocks:

```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
```

- [ ] **Step 1: Update gate.md**

In Gate 5 cloud detection, replace:
```bash
if grep -qE "gcloud|GCP_PROJECT|GOOGLE_CLOUD_PROJECT|Cloud Run|Cloud SQL|Firebase" \
  "$PROJECT_ROOT/CLAUDE.md" "$PROJECT_ROOT/.env.example" 2>/dev/null; then
```
With:
```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done

if grep -qE "gcloud|GCP_PROJECT|GOOGLE_CLOUD_PROJECT|Cloud Run|Cloud SQL|Firebase" \
  "$INSTRUCTION_FILE" "$PROJECT_ROOT/.env.example" 2>/dev/null; then
```

- [ ] **Step 2: Update db.md**

Replace the CLAUDE.md config reading logic. Change line 4 prose:
```
Reads connection config from CLAUDE.md (project-level) or ~/.claude/db-connections.json (global registry).
```
To:
```
Reads connection config from the project instruction file (CLAUDE.md, AGENTS.md, .cursorrules, or equivalent) or ~/.claude/db-connections.json (global registry).
```

Replace the bash detection (around line 38):
```bash
CLAUDE_MD="$(git rev-parse --show-toplevel 2>/dev/null)/CLAUDE.md"
```
With:
```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
```

Update all subsequent references from `$CLAUDE_MD` to `$INSTRUCTION_FILE`.

Replace the error message (around line 54):
```
echo "No DB config found in CLAUDE.md. Available connections:"
```
With:
```
echo "No DB config found in project instruction file. Available connections:"
```

Replace the help text (around line 79):
```
echo "  Option 1: Add a '## Database' section to CLAUDE.md"
```
With:
```
echo "  Option 1: Add a '## Database' section to your project instruction file"
```

- [ ] **Step 3: Update launch.md**

Replace prose references:
- "Read `CLAUDE.md` or `README.md` for health endpoint" → "Read the project instruction file or `README.md` for health endpoint"
- "Read `CLAUDE.md` for health endpoint URLs" → "Read the project instruction file for health endpoint URLs"
- "Update CLAUDE.md (if features changed)" → "Update project instruction file (if features changed)"

Replace bash:
```bash
grep -E "https?://[^ ]*/health" "$PROJECT_ROOT/CLAUDE.md" 2>/dev/null | head -3
```
With:
```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
grep -E "https?://[^ ]*/health" "$INSTRUCTION_FILE" 2>/dev/null | head -3
```

Replace git add lines:
```bash
git diff --name-only ROADMAP.md CLAUDE.md AGENT.md 2>/dev/null | grep -q . && \
  git add ROADMAP.md CLAUDE.md AGENT.md 2>/dev/null && \
```
With:
```bash
git diff --name-only ROADMAP.md CLAUDE.md AGENTS.md .cursorrules .windsurfrules GEMINI.md 2>/dev/null | grep -q . && \
  git add ROADMAP.md CLAUDE.md AGENTS.md .cursorrules .windsurfrules GEMINI.md 2>/dev/null && \
```

- [ ] **Step 4: Update security.md**

Replace prose:
```
Read CLAUDE.md for any documented known exceptions before determining what is blocking:
```
With:
```
Read the project instruction file for any documented known exceptions before determining what is blocking:
```

Replace bash:
```bash
grep -A3 -i "known exception\|security exception\|audit exception" "$PROJECT_ROOT/CLAUDE.md" 2>/dev/null | head -30
```
With:
```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
grep -A3 -i "known exception\|security exception\|audit exception" "$INSTRUCTION_FILE" 2>/dev/null | head -30
```

- [ ] **Step 5: Update commit.md**

Replace prose references:
- "API reference doc (README, CLAUDE.md, or `docs/`)" → "API reference doc (README, project instruction file, or `docs/`)"
- "Read the project's `CLAUDE.md` for specific doc file paths" → "Read the project instruction file for specific doc file paths"

- [ ] **Step 6: Update push.md**

Replace:
```
Check health endpoints listed in the project's `CLAUDE.md` or `README`
```
With:
```
Check health endpoints listed in the project instruction file or `README`
```

- [ ] **Step 7: Update docs.md**

Replace prose:
```
Read this project's `CLAUDE.md` (or equivalent) to understand which doc files exist
```
With:
```
Read the project instruction file (CLAUDE.md, AGENTS.md, .cursorrules, or equivalent) to understand which doc files exist
```

Replace bash that greps/iterates over CLAUDE.md:
```bash
grep -rn '\[.*\](\.\.' docs/ README.md CLAUDE.md 2>/dev/null | head -20 || true
```
With:
```bash
grep -rn '\[.*\](\.\.' docs/ README.md CLAUDE.md AGENTS.md .cursorrules .windsurfrules GEMINI.md 2>/dev/null | head -20 || true
```

```bash
for f in docs/*.md README.md CLAUDE.md ARCHITECTURE.md 2>/dev/null; do
```
With:
```bash
for f in docs/*.md README.md CLAUDE.md AGENTS.md .cursorrules ARCHITECTURE.md 2>/dev/null; do
```

```bash
git add docs/ README.md CLAUDE.md AGENT.md ROADMAP.md ARCHITECTURE.md 2>/dev/null
```
With:
```bash
git add docs/ README.md CLAUDE.md AGENTS.md .cursorrules .windsurfrules GEMINI.md ROADMAP.md ARCHITECTURE.md 2>/dev/null
```

- [ ] **Step 8: Update architect.md**

Replace prose:
```
Read the project's `CLAUDE.md` and relevant source files to understand:
```
With:
```
Read the project instruction file and relevant source files to understand:
```

Replace bash:
```bash
cat "$PROJECT_ROOT/CLAUDE.md" 2>/dev/null | head -100
```
With:
```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
cat "$INSTRUCTION_FILE" 2>/dev/null | head -100
```

- [ ] **Step 9: Update enterprise-design.md**

Replace bash:
```bash
cat "$PROJECT_ROOT/CLAUDE.md" 2>/dev/null | head -150
```
With:
```bash
# Detect project instruction file
INSTRUCTION_FILE=""
for f in CLAUDE.md AGENTS.md .cursorrules .windsurfrules .github/copilot-instructions.md GEMINI.md; do
  [ -f "$PROJECT_ROOT/$f" ] && INSTRUCTION_FILE="$PROJECT_ROOT/$f" && break
done
cat "$INSTRUCTION_FILE" 2>/dev/null | head -150
```

- [ ] **Step 10: Update cloud-security.md**

Replace bash (around line 17):
```bash
  CLAUDE.md .env.example terraform/ 2>/dev/null \
```
With:
```bash
  CLAUDE.md AGENTS.md .cursorrules .windsurfrules GEMINI.md .env.example terraform/ 2>/dev/null \
```

Replace prose:
```
Also read the project's `CLAUDE.md` to identify all GCP projects.
```
With:
```
Also read the project instruction file to identify all GCP projects.
```

- [ ] **Step 11: Verify changes are consistent**

Run: `grep -rn 'CLAUDE\.md' workflows/*.md`
Expected: Only hits in generic file detection loops (the `for f in CLAUDE.md AGENTS.md ...` lines) or git add lists. No standalone `CLAUDE.md` references.

- [ ] **Step 12: Commit**

```bash
git add workflows/
git commit -m "refactor: genericize CLAUDE.md references for multi-tool support"
```

---

### Task 5: Update templates

**Files:**
- Modify: `templates/node-fullstack.md`
- Modify: `templates/node-frontend.md`
- Modify: `templates/python-api.md`
- Modify: `templates/docker-compose.md`

- [ ] **Step 1: Update all 4 template headers**

Change the first line of each template from:
```markdown
# CLAUDE.md — [Project Name]
```
To:
```markdown
# [Project Name] — Project Instructions
```

- [ ] **Step 2: Commit**

```bash
git add templates/
git commit -m "refactor: genericize template headers for multi-tool support"
```

---

### Task 6: Rename and rebrand shell aliases

**Files:**
- Create: `shell/aliases.sh`
- Delete: `shell/claude-aliases.sh`

- [ ] **Step 1: Create new aliases file**

Write `shell/aliases.sh`:

```bash
# 100x Dev shortcuts
# Source this file from ~/.zshrc or ~/.bashrc:
#   source ~/100x-dev/shell/aliases.sh

# Launch Claude
alias cc='claude'
alias ccc='claude --continue'

# Setup management
alias 100x-update="$HOME/100x-dev/update.sh"
alias 100x-check="$HOME/100x-dev/update.sh --check-only"
```

- [ ] **Step 2: Remove old aliases file**

```bash
git rm shell/claude-aliases.sh
git add shell/aliases.sh
```

- [ ] **Step 3: Commit**

```bash
git commit -m "refactor: rebrand shell aliases from claude-* to 100x-*"
```

---

### Task 7: Write adapters

**Files:**
- Create: `adapters/claude-code.sh`
- Create: `adapters/cursor.sh`
- Create: `adapters/codex.sh`
- Create: `adapters/windsurf.sh`
- Create: `adapters/copilot.sh`
- Create: `adapters/gemini.sh`
- Create: `adapters/antigravity.sh`

- [ ] **Step 1: Write adapters/claude-code.sh**

This adapter copies workflow files to `~/.claude/commands/`, appends `$ARGUMENTS` to each, and optionally installs plugins.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

install_global() {
  echo ""
  echo "Installing workflows for Claude Code..."
  mkdir -p "$COMMANDS_DIR"

  if [ -d "$COMMANDS_DIR" ] && [ "$(ls -A "$COMMANDS_DIR" 2>/dev/null)" ]; then
    BACKUP="$CLAUDE_DIR/commands.bak.$(date +%Y%m%d_%H%M%S)"
    cp -r "$COMMANDS_DIR" "$BACKUP"
    echo -e "  ${YELLOW}→ Backed up existing commands to $(basename "$BACKUP")${NC}"
  fi

  count=0
  for f in "$WORKFLOWS_DIR/"*.md; do
    # Copy and append $ARGUMENTS for Claude Code
    cp "$f" "$COMMANDS_DIR/$(basename "$f")"
    echo "" >> "$COMMANDS_DIR/$(basename "$f")"
    echo '$ARGUMENTS' >> "$COMMANDS_DIR/$(basename "$f")"
    count=$((count + 1))
  done

  # Copy db-engines subdirectory
  if [ -d "$WORKFLOWS_DIR/db-engines" ]; then
    mkdir -p "$COMMANDS_DIR/db-engines"
    for f in "$WORKFLOWS_DIR/db-engines/"*.md; do
      cp "$f" "$COMMANDS_DIR/db-engines/"
    done
    engine_count=$(ls "$WORKFLOWS_DIR/db-engines/"*.md 2>/dev/null | wc -l | tr -d ' ')
    echo -e "  ${GREEN}→ Copied db-engines/ ($engine_count engine files) ✓${NC}"
  fi

  echo -e "  ${GREEN}→ Copied $count workflows to ~/.claude/commands/ ✓${NC}"
  echo -e "  ${CYAN}→ Restart Claude Code to load new commands${NC}"
}

install_plugins() {
  echo ""
  echo "Installing plugins for Claude Code..."
  mkdir -p "$CLAUDE_DIR"

  PLUGINS_FILE="$REPO_DIR/plugins/plugins.json"

  new_plugins=$(python3 -c "
import json
with open('$PLUGINS_FILE') as f:
    data = json.load(f)
print(json.dumps(data.get('plugins', [])))
")

  extra_marketplaces=$(python3 -c "
import json
with open('$PLUGINS_FILE') as f:
    data = json.load(f)
print(json.dumps(data.get('extraKnownMarketplaces', {})))
")

  if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{}' > "$SETTINGS_FILE"
  fi

  python3 << PYEOF
import json

with open('$SETTINGS_FILE', 'r') as f:
    settings = json.load(f)

new_plugins = $new_plugins
extra_marketplaces = $extra_marketplaces

enabled = settings.get('enabledPlugins', {})
added = 0
for p in new_plugins:
    if p not in enabled:
        enabled[p] = True
        added += 1

settings['enabledPlugins'] = enabled

existing_marketplaces = settings.get('extraKnownMarketplaces', {})
existing_marketplaces.update(extra_marketplaces)
settings['extraKnownMarketplaces'] = existing_marketplaces

with open('$SETTINGS_FILE', 'w') as f:
    json.dump(settings, f, indent=2)

print(f'  Added {added} new plugins ({len(enabled)} total)')
PYEOF

  echo -e "  ${GREEN}→ Plugins merged into ~/.claude/settings.json ✓${NC}"
  echo -e "  ${CYAN}→ Run /reload-plugins in Claude Code to activate${NC}"
}

# When sourced by install.sh, functions are available
# When run directly:
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "${1:-}" in
    --plugins) install_plugins ;;
    *) install_global ;;
  esac
fi
```

- [ ] **Step 2: Write adapters/cursor.sh**

This adapter concatenates all workflows into a single `.cursorrules` file.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

GREEN='\033[0;32m'
NC='\033[0m'

install_project() {
  local project_path="${1:-.}"
  local output_file="$project_path/.cursorrules"

  echo ""
  echo "Generating .cursorrules for Cursor..."

  {
    echo "# 100x Dev Workflows"
    echo "# Generated by 100x-dev (https://github.com/rajitsaha/100x-dev)"
    echo "# Regenerate: run install.sh or adapters/cursor.sh <project-path>"
    echo ""

    for f in gate test commit push launch lint security docs issue architect cloud-security enterprise-design db; do
      if [ -f "$WORKFLOWS_DIR/$f.md" ]; then
        echo "---"
        echo ""
        cat "$WORKFLOWS_DIR/$f.md"
        echo ""
      fi
    done
  } > "$output_file"

  echo -e "  ${GREEN}→ Generated $output_file ✓${NC}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
```

- [ ] **Step 3: Write adapters/codex.sh**

Same pattern as cursor.sh but outputs `AGENTS.md`.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

GREEN='\033[0;32m'
NC='\033[0m'

install_project() {
  local project_path="${1:-.}"
  local output_file="$project_path/AGENTS.md"

  echo ""
  echo "Generating AGENTS.md for Codex..."

  {
    echo "# 100x Dev Workflows"
    echo "# Generated by 100x-dev (https://github.com/rajitsaha/100x-dev)"
    echo "# Regenerate: run install.sh or adapters/codex.sh <project-path>"
    echo ""

    for f in gate test commit push launch lint security docs issue architect cloud-security enterprise-design db; do
      if [ -f "$WORKFLOWS_DIR/$f.md" ]; then
        echo "---"
        echo ""
        cat "$WORKFLOWS_DIR/$f.md"
        echo ""
      fi
    done
  } > "$output_file"

  echo -e "  ${GREEN}→ Generated $output_file ✓${NC}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
```

- [ ] **Step 4: Write adapters/windsurf.sh**

Same pattern, outputs `.windsurfrules`.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

GREEN='\033[0;32m'
NC='\033[0m'

install_project() {
  local project_path="${1:-.}"
  local output_file="$project_path/.windsurfrules"

  echo ""
  echo "Generating .windsurfrules for Windsurf..."

  {
    echo "# 100x Dev Workflows"
    echo "# Generated by 100x-dev (https://github.com/rajitsaha/100x-dev)"
    echo "# Regenerate: run install.sh or adapters/windsurf.sh <project-path>"
    echo ""

    for f in gate test commit push launch lint security docs issue architect cloud-security enterprise-design db; do
      if [ -f "$WORKFLOWS_DIR/$f.md" ]; then
        echo "---"
        echo ""
        cat "$WORKFLOWS_DIR/$f.md"
        echo ""
      fi
    done
  } > "$output_file"

  echo -e "  ${GREEN}→ Generated $output_file ✓${NC}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
```

- [ ] **Step 5: Write adapters/copilot.sh**

Same pattern, outputs `.github/copilot-instructions.md`.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

GREEN='\033[0;32m'
NC='\033[0m'

install_project() {
  local project_path="${1:-.}"
  mkdir -p "$project_path/.github"
  local output_file="$project_path/.github/copilot-instructions.md"

  echo ""
  echo "Generating copilot-instructions.md for GitHub Copilot..."

  {
    echo "# 100x Dev Workflows"
    echo "# Generated by 100x-dev (https://github.com/rajitsaha/100x-dev)"
    echo "# Regenerate: run install.sh or adapters/copilot.sh <project-path>"
    echo ""

    for f in gate test commit push launch lint security docs issue architect cloud-security enterprise-design db; do
      if [ -f "$WORKFLOWS_DIR/$f.md" ]; then
        echo "---"
        echo ""
        cat "$WORKFLOWS_DIR/$f.md"
        echo ""
      fi
    done
  } > "$output_file"

  echo -e "  ${GREEN}→ Generated $output_file ✓${NC}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
```

- [ ] **Step 6: Write adapters/gemini.sh**

Same pattern, outputs `GEMINI.md`.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

GREEN='\033[0;32m'
NC='\033[0m'

install_project() {
  local project_path="${1:-.}"
  local output_file="$project_path/GEMINI.md"

  echo ""
  echo "Generating GEMINI.md for Gemini CLI..."

  {
    echo "# 100x Dev Workflows"
    echo "# Generated by 100x-dev (https://github.com/rajitsaha/100x-dev)"
    echo "# Regenerate: run install.sh or adapters/gemini.sh <project-path>"
    echo ""

    for f in gate test commit push launch lint security docs issue architect cloud-security enterprise-design db; do
      if [ -f "$WORKFLOWS_DIR/$f.md" ]; then
        echo "---"
        echo ""
        cat "$WORKFLOWS_DIR/$f.md"
        echo ""
      fi
    done
  } > "$output_file"

  echo -e "  ${GREEN}→ Generated $output_file ✓${NC}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
```

- [ ] **Step 7: Write adapters/antigravity.sh**

Placeholder adapter. Outputs `ANTIGRAVITY.md` using same concatenation pattern.

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

install_project() {
  local project_path="${1:-.}"
  local output_file="$project_path/ANTIGRAVITY.md"

  echo ""
  echo -e "${YELLOW}Note: Antigravity adapter is provisional — update when format is confirmed.${NC}"
  echo "Generating ANTIGRAVITY.md..."

  {
    echo "# 100x Dev Workflows"
    echo "# Generated by 100x-dev (https://github.com/rajitsaha/100x-dev)"
    echo "# Regenerate: run install.sh or adapters/antigravity.sh <project-path>"
    echo ""

    for f in gate test commit push launch lint security docs issue architect cloud-security enterprise-design db; do
      if [ -f "$WORKFLOWS_DIR/$f.md" ]; then
        echo "---"
        echo ""
        cat "$WORKFLOWS_DIR/$f.md"
        echo ""
      fi
    done
  } > "$output_file"

  echo -e "  ${GREEN}→ Generated $output_file ✓${NC}"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
```

- [ ] **Step 8: Make all adapters executable**

```bash
chmod +x adapters/*.sh
```

- [ ] **Step 9: Commit**

```bash
git add adapters/
git commit -m "feat: add adapters for 7 AI coding tools"
```

---

### Task 8: Rewrite install.sh

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Write new install.sh**

```bash
#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES_DIR="$HOME/100x-templates"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════╗"
echo "║      100x Dev Setup — Installer      ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Tool selection ──────────────────────────────────────────────────────────

TOOL_CLAUDE=false
TOOL_CURSOR=false
TOOL_CODEX=false
TOOL_WINDSURF=false
TOOL_COPILOT=false
TOOL_GEMINI=false
TOOL_ANTIGRAVITY=false

select_tools() {
  echo "Which AI coding tools do you use?"
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

  # Check at least one tool selected
  if [ "$TOOL_CLAUDE" = false ] && [ "$TOOL_CURSOR" = false ] && [ "$TOOL_CODEX" = false ] && \
     [ "$TOOL_WINDSURF" = false ] && [ "$TOOL_COPILOT" = false ] && [ "$TOOL_GEMINI" = false ] && \
     [ "$TOOL_ANTIGRAVITY" = false ]; then
    echo -e "  ${YELLOW}No tools selected. Please select at least one.${NC}"
    echo ""
    select_tools
  fi
}

# ── Component selection ─────────────────────────────────────────────────────

INSTALL_WORKFLOWS=true
INSTALL_PLUGINS=true
INSTALL_SHELL=true
INSTALL_TEMPLATES=true

select_components() {
  echo ""
  echo "What would you like to install?"
  echo "  (Enter numbers to toggle, then press Enter with no input to confirm)"
  echo ""

  while true; do
    echo "  [$([ "$INSTALL_WORKFLOWS" = true ] && echo "x" || echo " ")] 1) Workflows    — gate, test, commit, push, launch, lint, security, ..."
    if [ "$TOOL_CLAUDE" = true ]; then
      echo "  [$([ "$INSTALL_PLUGINS" = true ] && echo "x" || echo " ")] 2) Plugins      — Claude Code only: superpowers, stripe, hookify, ..."
    fi
    echo "  [$([ "$INSTALL_SHELL" = true ] && echo "x" || echo " ")] 3) Shell        — aliases + shortcuts (cc, ccc, 100x-update, ...)"
    echo "  [$([ "$INSTALL_TEMPLATES" = true ] && echo "x" || echo " ")] 4) Templates   — project starters (node, python, docker)"
    echo ""
    read -rp "  Toggle (1-4) or press Enter to confirm: " choice

    case "$choice" in
      1) INSTALL_WORKFLOWS=$([ "$INSTALL_WORKFLOWS" = true ] && echo false || echo true) ;;
      2) [ "$TOOL_CLAUDE" = true ] && INSTALL_PLUGINS=$([ "$INSTALL_PLUGINS" = true ] && echo false || echo true) ;;
      3) INSTALL_SHELL=$([ "$INSTALL_SHELL" = true ] && echo false || echo true) ;;
      4) INSTALL_TEMPLATES=$([ "$INSTALL_TEMPLATES" = true ] && echo false || echo true) ;;
      "") break ;;
      *) echo "  Invalid choice." ;;
    esac
    echo ""
  done
}

# ── Project path for non-global tools ───────────────────────────────────────

ask_project_path() {
  local tool_name="$1"
  echo ""
  read -rp "  Project path for $tool_name (default: current directory): " project_path
  echo "${project_path:-.}"
}

# ── Install workflows ───────────────────────────────────────────────────────

install_workflows() {
  # Claude Code: global install
  if [ "$TOOL_CLAUDE" = true ]; then
    source "$REPO_DIR/adapters/claude-code.sh"
    install_global
  fi

  # Project-level tools: ask for path once if multiple selected
  local need_project_path=false
  for tool in CURSOR CODEX WINDSURF COPILOT GEMINI ANTIGRAVITY; do
    eval "val=\$TOOL_$tool"
    [ "$val" = true ] && need_project_path=true && break
  done

  if [ "$need_project_path" = true ]; then
    echo ""
    read -rp "  Project path for generated files (default: current directory): " PROJECT_PATH
    PROJECT_PATH="${PROJECT_PATH:-.}"

    [ "$TOOL_CURSOR" = true ] && bash "$REPO_DIR/adapters/cursor.sh" "$PROJECT_PATH"
    [ "$TOOL_CODEX" = true ] && bash "$REPO_DIR/adapters/codex.sh" "$PROJECT_PATH"
    [ "$TOOL_WINDSURF" = true ] && bash "$REPO_DIR/adapters/windsurf.sh" "$PROJECT_PATH"
    [ "$TOOL_COPILOT" = true ] && bash "$REPO_DIR/adapters/copilot.sh" "$PROJECT_PATH"
    [ "$TOOL_GEMINI" = true ] && bash "$REPO_DIR/adapters/gemini.sh" "$PROJECT_PATH"
    [ "$TOOL_ANTIGRAVITY" = true ] && bash "$REPO_DIR/adapters/antigravity.sh" "$PROJECT_PATH"
  fi
}

# ── Install plugins (Claude Code only) ──────────────────────────────────────

do_install_plugins() {
  if [ "$TOOL_CLAUDE" = true ]; then
    source "$REPO_DIR/adapters/claude-code.sh"
    install_plugins
  fi
}

# ── Install shell aliases ───────────────────────────────────────────────────

install_shell() {
  echo ""
  echo "Installing shell aliases..."

  SOURCE_LINE="source $REPO_DIR/shell/aliases.sh"

  if [ -f "$HOME/.zshrc" ]; then
    RC_FILE="$HOME/.zshrc"
    SHELL_NAME="zsh"
  elif [ -f "$HOME/.bashrc" ]; then
    RC_FILE="$HOME/.bashrc"
    SHELL_NAME="bash"
  else
    RC_FILE="$HOME/.bashrc"
    SHELL_NAME="bash"
    touch "$RC_FILE"
  fi

  # Remove old claude-dev-setup source line if present
  if grep -qF "claude-dev-setup/shell/claude-aliases.sh" "$RC_FILE" 2>/dev/null; then
    grep -v "claude-dev-setup/shell/claude-aliases.sh" "$RC_FILE" > "$RC_FILE.tmp" && mv "$RC_FILE.tmp" "$RC_FILE"
    echo -e "  ${YELLOW}→ Removed old claude-dev-setup alias line${NC}"
  fi

  if grep -qF "$SOURCE_LINE" "$RC_FILE" 2>/dev/null; then
    echo -e "  ${YELLOW}→ Already sourced in ~/${RC_FILE##*/} (no change)${NC}"
  else
    echo "" >> "$RC_FILE"
    echo "# 100x Dev aliases" >> "$RC_FILE"
    echo "$SOURCE_LINE" >> "$RC_FILE"
    echo -e "  ${GREEN}→ Added source line to ~/${RC_FILE##*/} ($SHELL_NAME) ✓${NC}"
  fi

  echo -e "  ${CYAN}→ Run: source ~/${RC_FILE##*/}  to activate now${NC}"
}

# ── Install templates ───────────────────────────────────────────────────────

install_templates() {
  echo ""
  echo "Installing templates..."
  mkdir -p "$TEMPLATES_DIR"

  count=0
  for f in "$REPO_DIR/templates/"*.md; do
    cp "$f" "$TEMPLATES_DIR/"
    count=$((count + 1))
  done

  echo -e "  ${GREEN}→ Copied $count templates to ~/100x-templates/ ✓${NC}"
  echo ""
  echo "  Copy a template into your project and rename for your tool:"
  echo "    Claude Code  →  CLAUDE.md"
  echo "    Cursor       →  .cursorrules"
  echo "    Codex        →  AGENTS.md"
  echo "    Windsurf     →  .windsurfrules"
  echo "    Copilot      →  .github/copilot-instructions.md"
  echo "    Gemini CLI   →  GEMINI.md"
}

# ── Main ─────────────────────────────────────────────────────────────────────

select_tools
select_components

echo ""
echo "──────────────────────────────────────"

[ "$INSTALL_WORKFLOWS" = true ] && install_workflows
[ "$INSTALL_PLUGINS" = true ] && [ "$TOOL_CLAUDE" = true ] && do_install_plugins
[ "$INSTALL_SHELL" = true ] && install_shell
[ "$INSTALL_TEMPLATES" = true ] && install_templates

echo ""
echo "──────────────────────────────────────"
echo -e "${GREEN}✓ Done!${NC}"
[ "$TOOL_CLAUDE" = true ] && echo -e "${CYAN}  Claude Code: restart to load workflows. Run /reload-plugins for plugins.${NC}"
echo ""
```

- [ ] **Step 2: Commit**

```bash
git add install.sh
git commit -m "feat: rewrite install.sh as multi-tool installer"
```

---

### Task 9: Update update.sh

**Files:**
- Modify: `update.sh`

- [ ] **Step 1: Read current update.sh and rebrand**

Replace all references:
- `claude-dev-setup` → `100x-dev`
- `Claude Code` → `100x Dev`
- `claude-check` → `100x-check`
- `claude-update` → `100x-update`
- `commands/` → `workflows/`
- `/reload-plugins` reference → note it's Claude Code specific

Keep the core logic (git pull, re-run install) the same.

- [ ] **Step 2: Commit**

```bash
git add update.sh
git commit -m "refactor: rebrand update.sh for 100x-dev"
```

---

### Task 10: Write README.md

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write new README**

```markdown
# 100x Dev

Production-grade AI development workflows for every coding tool.

Works with **Claude Code**, **Cursor**, **Codex**, **Windsurf**, **Copilot CLI**, **Gemini CLI**, and **Antigravity**.

## Quick Start

​```bash
git clone https://github.com/rajitsaha/100x-dev.git ~/100x-dev
cd ~/100x-dev
./install.sh
​```

The installer asks which tools you use and which components to install.

## What You Get

| Workflow | What it does |
|----------|-------------|
| **gate** | Pre-commit quality gate — tests, security, build, Docker, cloud security |
| **test** | Run all test layers (unit → integration → E2E), loop until ≥95% coverage |
| **commit** | Gate → stage → conventional commit |
| **push** | Gate → push → monitor CI/CD → verify production |
| **launch** | Full release pipeline: Docker → test → lint → security → build → commit → push |
| **lint** | Auto-detect linting stack, fix all errors, zero tolerance |
| **security** | Vulnerability scanner + secret audit |
| **docs** | Detect code changes, update corresponding docs |
| **issue** | Investigate and create detailed GitHub issues |
| **architect** | Cloud, data & SaaS architecture advisor |
| **cloud-security** | Cloud security & data privacy scan |
| **enterprise-design** | Enterprise design & systems architecture |
| **db** | Universal database access — 7 engines |

### Database engines

| Engine | Connection method |
|--------|-----------------|
| `cloud-sql` | GCP Cloud SQL via temporary public IP |
| `postgres` | Direct TCP — PostgreSQL, Supabase |
| `snowflake` | Snowflake via snowsql or Python connector |
| `databricks` | Databricks SQL warehouse |
| `athena` | AWS Athena via boto3 |
| `presto` | Presto / Trino via Python client |
| `oracle` | Oracle via cx_Oracle or sqlplus |

## Supported Tools

| Tool | Install type | Project file |
|------|-------------|-------------|
| Claude Code | Global (`~/.claude/commands/`) | CLAUDE.md |
| Cursor | Project | .cursorrules |
| Codex (OpenAI) | Project | AGENTS.md |
| Windsurf | Project | .windsurfrules |
| Copilot CLI | Project | .github/copilot-instructions.md |
| Gemini CLI | Project | GEMINI.md |
| Antigravity | Project | ANTIGRAVITY.md |

**Global install** copies each workflow as a separate file — available in all your projects.

**Project install** generates a single instruction file containing all workflows — add it to your project repo.

## Templates

Project instruction file starters for common stacks:

​```bash
# Copy a template and rename for your tool
cp ~/100x-templates/node-fullstack.md ./CLAUDE.md      # Claude Code
cp ~/100x-templates/node-fullstack.md ./.cursorrules    # Cursor
cp ~/100x-templates/node-fullstack.md ./AGENTS.md       # Codex
​```

Available: `node-fullstack`, `node-frontend`, `python-api`, `docker-compose`

## Plugins (Claude Code)

14 curated plugins installed into Claude Code's settings:

superpowers, frontend-design, stripe, hookify, pr-review-toolkit, code-review, playwright, firecrawl, github, remember, skill-creator, code-simplifier, security-guidance, brightdata

Only installed when you select Claude Code + Plugins during setup.

## Shell Aliases

| Alias | What it does |
|-------|-------------|
| `cc` | Launch Claude Code in current directory |
| `ccc` | Continue last Claude Code session |
| `100x-update` | Pull and apply latest setup |
| `100x-check` | Check for updates without applying |

## Update

​```bash
100x-check        # Check for updates
100x-update       # Pull and apply
​```

## Add Your Own Tool

Write an adapter script in `adapters/`:

​```bash
#!/usr/bin/env bash
# adapters/my-tool.sh
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORKFLOWS_DIR="$REPO_DIR/workflows"

install_project() {
  local project_path="${1:-.}"
  local output_file="$project_path/.my-tool-config"

  {
    echo "# 100x Dev Workflows"
    for f in "$WORKFLOWS_DIR/"*.md; do
      echo "---"
      cat "$f"
    done
  } > "$output_file"
}

install_project "${1:-.}"
​```

Then add it to `install.sh`'s tool selection. PRs welcome!

## Philosophy

- **No skips** — quality gates are mandatory
- **95% coverage** — not aspirational, enforced
- **Auto-fix first** — lint and security fixes applied automatically
- **Loop until clean** — tests re-run until all thresholds met
- **Tool-agnostic** — same workflows, any AI coding tool
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for 100x-dev multi-tool positioning"
```

---

### Task 11: Final cleanup and verification

- [ ] **Step 1: Verify no stale references**

```bash
# Should find no hits outside of detection loops
grep -rn 'claude-dev-setup' . --include='*.sh' --include='*.md' | grep -v docs/superpowers | grep -v '.git/'

# Should find no standalone CLAUDE.md refs in workflows (only in detection loops)
grep -n 'CLAUDE\.md' workflows/*.md | grep -v 'for f in' | grep -v 'CLAUDE.md AGENTS.md' | grep -v 'CLAUDE.md,'

# Should find no $ARGUMENTS in workflows
grep -rn '\$ARGUMENTS' workflows/
```

- [ ] **Step 2: Verify all adapter scripts are executable**

```bash
ls -la adapters/*.sh
```

- [ ] **Step 3: Verify directory structure matches spec**

```bash
find . -not -path './.git/*' -not -path './docs/*' -not -name '.git' | sort
```

Expected structure:
```
.
./adapters
./adapters/antigravity.sh
./adapters/claude-code.sh
./adapters/codex.sh
./adapters/copilot.sh
./adapters/cursor.sh
./adapters/gemini.sh
./adapters/windsurf.sh
./install.sh
./plugins
./plugins/plugins.json
./README.md
./shell
./shell/aliases.sh
./templates
./templates/docker-compose.md
./templates/node-frontend.md
./templates/node-fullstack.md
./templates/python-api.md
./update.sh
./workflows
./workflows/architect.md
./workflows/cloud-security.md
./workflows/commit.md
./workflows/db-engines
./workflows/db-engines/athena.md
./workflows/db-engines/cloud-sql.md
./workflows/db-engines/databricks.md
./workflows/db-engines/oracle.md
./workflows/db-engines/postgres.md
./workflows/db-engines/presto.md
./workflows/db-engines/snowflake.md
./workflows/db.md
./workflows/docs.md
./workflows/enterprise-design.md
./workflows/gate.md
./workflows/issue.md
./workflows/launch.md
./workflows/lint.md
./workflows/push.md
./workflows/security.md
./workflows/test.md
```

- [ ] **Step 4: Final commit (if any fixups needed)**

```bash
git add -A
git status
# Only commit if there are changes
git diff --cached --quiet || git commit -m "chore: final cleanup for 100x-dev restructure"
```
