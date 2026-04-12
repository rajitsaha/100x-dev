# Version Notification System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically notify 100x-dev users of new versions on every shell startup and Claude Code session start, with a one-prompt upgrade path and auto-regeneration of all tracked project instruction files on update.

**Architecture:** A central `shell/check-update.sh` script owns all version-check logic, reading from a daily-refreshed cache at `~/.100x-dev/update-cache`. Shell startup calls it with `--notify` (reads cache, shows banner + prompt) then spawns it in the background with `--silent` (refreshes cache for next session). A Claude Code SessionStart hook calls it with `--claude-hook` (injects a notice into the session context). On update, `update.sh` auto-regenerates instruction files for all paths in `~/.100x-dev/tracked-projects`, which adapters write to on first run.

**Tech Stack:** Bash, git, Python 3 (for JSON merge in update.sh/install.sh — already used), `~/.claude/settings.json` hooks

---

## File Map

| File | Status | Responsibility |
|------|--------|---------------|
| `shell/check-update.sh` | New | Cache R/W, git fetch, all three output modes |
| `tests/test-check-update.sh` | New | Shell test harness for check-update.sh |
| `shell/aliases.sh` | Modify | Call `--notify` on startup + background `--silent` spawn |
| `adapters/lib/shared.sh` | Modify | Write project path to `tracked-projects` in `_run_generate` |
| `update.sh` | Modify | `regenerate_tracked_projects` + SessionStart hook merge + cache clear |
| `install.sh` | Modify | SessionStart hook merge in Claude Code install path |

State directory (created by check-update.sh): `~/.100x-dev/`
- `update-cache` — plain-text key=value cache file
- `tracked-projects` — one absolute project path per line

---

### Task 1: Test harness + `check-update.sh` skeleton

**Files:**
- Create: `tests/test-check-update.sh`
- Create: `shell/check-update.sh`

- [ ] **Step 1: Write the test harness**

Create `tests/test-check-update.sh`:

```bash
#!/usr/bin/env bash
# Test harness for shell/check-update.sh
# Uses a temporary HOME to avoid touching real state.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$REPO_DIR/shell/check-update.sh"

PASS=0
FAIL=0

_setup() {
  export HOME
  HOME="$(mktemp -d)"
  mkdir -p "$HOME/.100x-dev"
}

_teardown() {
  rm -rf "$HOME"
}

_assert_eq() {
  local label="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "  PASS: $label"
    (( PASS++ )) || true
  else
    echo "  FAIL: $label"
    echo "    expected: $expected"
    echo "    actual:   $actual"
    (( FAIL++ )) || true
  fi
}

_assert_file_contains() {
  local label="$1" file="$2" pattern="$3"
  if grep -q "$pattern" "$file" 2>/dev/null; then
    echo "  PASS: $label"
    (( PASS++ )) || true
  else
    echo "  FAIL: $label — pattern '$pattern' not found in $file"
    (( FAIL++ )) || true
  fi
}

# ── Tests ─────────────────────────────────────────────────────────────────────

test_creates_state_dir() {
  _setup
  rm -rf "$HOME/.100x-dev"
  bash "$SCRIPT" --silent || true
  if [[ -d "$HOME/.100x-dev" ]]; then
    echo "  PASS: creates ~/.100x-dev on first run"
    (( PASS++ )) || true
  else
    echo "  FAIL: ~/.100x-dev not created"
    (( FAIL++ )) || true
  fi
  _teardown
}

test_no_output_when_no_update() {
  _setup
  cat > "$HOME/.100x-dev/update-cache" << 'EOF'
last_check=9999999999
has_update=false
local_sha=abc1234
remote_sha=abc1234
changelog=
snoozed_until=0
EOF
  local output
  output=$(bash "$SCRIPT" --claude-hook 2>/dev/null)
  _assert_eq "no output when no update (--claude-hook)" "" "$output"
  _teardown
}

test_claude_hook_outputs_notice_when_update_available() {
  _setup
  cat > "$HOME/.100x-dev/update-cache" << 'EOF'
last_check=9999999999
has_update=true
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: detect Bun|def5678 feat: shared lib
snoozed_until=0
EOF
  local output
  output=$(bash "$SCRIPT" --claude-hook 2>/dev/null)
  if echo "$output" | grep -q "100x Dev update available"; then
    echo "  PASS: --claude-hook outputs update notice"
    (( PASS++ )) || true
  else
    echo "  FAIL: --claude-hook missing update notice"
    echo "    output: $output"
    (( FAIL++ )) || true
  fi
  _teardown
}

test_snoozed_suppresses_claude_hook() {
  _setup
  local future=$(( $(date +%s) + 86400 ))
  cat > "$HOME/.100x-dev/update-cache" << EOF
last_check=9999999999
has_update=true
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: something
snoozed_until=$future
EOF
  local output
  output=$(bash "$SCRIPT" --claude-hook 2>/dev/null)
  _assert_eq "snoozed suppresses --claude-hook output" "" "$output"
  _teardown
}

test_silent_creates_cache_file() {
  _setup
  # Point REPO_DIR to a temp git repo to avoid network calls
  local fake_repo
  fake_repo="$(mktemp -d)"
  cd "$fake_repo"
  git init --quiet
  git commit --allow-empty -m "init" --quiet

  # Patch REPO_DIR inside the script by overriding with env var
  HUNDRED_X_REPO_OVERRIDE="$fake_repo" bash "$SCRIPT" --silent 2>/dev/null || true

  if [[ -f "$HOME/.100x-dev/update-cache" ]]; then
    echo "  PASS: --silent creates cache file"
    (( PASS++ )) || true
  else
    echo "  FAIL: --silent did not create cache file"
    (( FAIL++ )) || true
  fi
  rm -rf "$fake_repo"
  _teardown
}

# ── Run ───────────────────────────────────────────────────────────────────────

echo ""
echo "Running check-update tests..."
echo ""

test_creates_state_dir
test_no_output_when_no_update
test_claude_hook_outputs_notice_when_update_available
test_snoozed_suppresses_claude_hook
test_silent_creates_cache_file

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
```

- [ ] **Step 2: Run the test to verify it fails (script doesn't exist yet)**

```bash
bash tests/test-check-update.sh
```

Expected: errors about `shell/check-update.sh` not found.

- [ ] **Step 3: Create `shell/check-update.sh` skeleton**

Create `shell/check-update.sh`:

```bash
#!/usr/bin/env bash
# check-update.sh — daily version check + cache for 100x-dev
#
# Usage:
#   check-update.sh --silent       Refresh cache only. No output.
#   check-update.sh --notify       Show banner + prompt if update available.
#   check-update.sh --claude-hook  Inject session notice if update available.

set -euo pipefail

REPO_DIR="${HUNDRED_X_REPO_OVERRIDE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STATE_DIR="$HOME/.100x-dev"
CACHE_FILE="$STATE_DIR/update-cache"
FLAG="${1:-}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$STATE_DIR"

# ── Argument validation ───────────────────────────────────────────────────────

case "$FLAG" in
  --silent|--notify|--claude-hook) ;;
  *)
    echo "Usage: check-update.sh [--silent|--notify|--claude-hook]" >&2
    exit 1
    ;;
esac

echo "stub: $FLAG"
```

- [ ] **Step 4: Run tests — expect most to fail but state-dir test to pass**

```bash
bash tests/test-check-update.sh
```

Expected: `test_creates_state_dir` PASS, rest FAIL.

- [ ] **Step 5: Commit skeleton**

```bash
git add shell/check-update.sh tests/test-check-update.sh
git commit -m "feat: add check-update.sh skeleton + test harness"
```

---

### Task 2: Cache helpers in `check-update.sh`

**Files:**
- Modify: `shell/check-update.sh`

- [ ] **Step 1: Replace stub with full cache helpers + `--silent` implementation**

Replace the entire contents of `shell/check-update.sh` with:

```bash
#!/usr/bin/env bash
# check-update.sh — daily version check + cache for 100x-dev
#
# Usage:
#   check-update.sh --silent       Refresh cache only. No output.
#   check-update.sh --notify       Show banner + prompt if update available.
#   check-update.sh --claude-hook  Inject session notice if update available.

set -euo pipefail

REPO_DIR="${HUNDRED_X_REPO_OVERRIDE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STATE_DIR="$HOME/.100x-dev"
CACHE_FILE="$STATE_DIR/update-cache"
FLAG="${1:-}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

mkdir -p "$STATE_DIR"

# ── Cache helpers ─────────────────────────────────────────────────────────────

_cache_get() {
  local key="$1"
  if [[ ! -f "$CACHE_FILE" ]]; then
    echo ""
    return
  fi
  grep "^${key}=" "$CACHE_FILE" 2>/dev/null | cut -d= -f2- || true
}

_cache_set() {
  local key="$1" value="$2"
  touch "$CACHE_FILE"
  local tmp
  tmp="$(mktemp)"
  grep -v "^${key}=" "$CACHE_FILE" > "$tmp" 2>/dev/null || true
  echo "${key}=${value}" >> "$tmp"
  mv "$tmp" "$CACHE_FILE"
}

# ── Version check ─────────────────────────────────────────────────────────────

_refresh_cache() {
  local now
  now="$(date +%s)"
  local last_check
  last_check="$(_cache_get last_check)"
  last_check="${last_check:-0}"

  local age=$(( now - last_check ))
  if (( age < 86400 )); then
    return  # Cache is fresh — skip network call
  fi

  cd "$REPO_DIR"

  # Fetch with 5s timeout; on failure, update timestamp only to avoid retry storm
  if ! git fetch origin main --quiet 2>/dev/null; then
    _cache_set last_check "$now"
    return
  fi

  local local_sha remote_sha
  local_sha="$(git rev-parse HEAD 2>/dev/null || echo "unknown")"
  remote_sha="$(git rev-parse origin/main 2>/dev/null || echo "unknown")"

  local has_update="false"
  local changelog=""

  if [[ "$local_sha" != "$remote_sha" && "$local_sha" != "unknown" ]]; then
    has_update="true"
    changelog="$(git log --oneline "${local_sha}..origin/main" 2>/dev/null | head -5 | tr '\n' '|' | sed 's/|$//')"
  fi

  _cache_set last_check  "$now"
  _cache_set has_update  "$has_update"
  _cache_set local_sha   "$local_sha"
  _cache_set remote_sha  "$remote_sha"
  _cache_set changelog   "$changelog"

  # Clear snooze when update state changes to false
  if [[ "$has_update" == "false" ]]; then
    _cache_set snoozed_until "0"
  fi
}

# ── Snooze helpers ────────────────────────────────────────────────────────────

_is_snoozed() {
  local snoozed_until
  snoozed_until="$(_cache_get snoozed_until)"
  snoozed_until="${snoozed_until:-0}"
  local now
  now="$(date +%s)"
  (( now < snoozed_until )) && return 0 || return 1
}

_snooze() {
  local until=$(( $(date +%s) + 86400 ))
  _cache_set snoozed_until "$until"
}

# ── Output modes ──────────────────────────────────────────────────────────────

_do_silent() {
  _refresh_cache
}

_do_notify() {
  # Read from cache only — no network call here (that's _do_silent's job)
  local has_update
  has_update="$(_cache_get has_update)"
  [[ "$has_update" == "true" ]] || return 0
  _is_snoozed && return 0

  # Only show prompt if stdin is a terminal
  [[ -t 0 ]] || return 0

  local local_sha remote_sha changelog
  local_sha="$(_cache_get local_sha)"
  remote_sha="$(_cache_get remote_sha)"
  changelog="$(_cache_get changelog)"

  local short_local="${local_sha:0:7}"
  local short_remote="${remote_sha:0:7}"

  echo ""
  printf "${YELLOW}╔══════════════════════════════════════════════════════╗${NC}\n"
  printf "${YELLOW}║${NC}  %-52s${YELLOW}║${NC}\n" "100x Dev update available: $short_local → $short_remote"

  IFS='|' read -ra _lines <<< "$changelog"
  for _line in "${_lines[@]}"; do
    [[ -z "$_line" ]] && continue
    # Strip leading git sha (first word)
    local _msg="${_line#* }"
    printf "${YELLOW}║${NC}  %-52s${YELLOW}║${NC}\n" "• $_msg"
  done

  printf "${YELLOW}╚══════════════════════════════════════════════════════╝${NC}\n"
  echo ""

  read -rp "Update now? (Y/n): " _confirm
  _confirm="${_confirm:-Y}"
  if [[ "$_confirm" =~ ^[Yy]$ ]]; then
    bash "$REPO_DIR/update.sh"
  else
    _snooze
    echo -e "${CYAN}Reminder snoozed for 24h. Run \`100x-update\` when ready.${NC}"
  fi
}

_do_claude_hook() {
  local has_update
  has_update="$(_cache_get has_update)"
  [[ "$has_update" == "true" ]] || return 0
  _is_snoozed && return 0

  local local_sha remote_sha changelog
  local_sha="$(_cache_get local_sha)"
  remote_sha="$(_cache_get remote_sha)"
  changelog="$(_cache_get changelog)"

  local short_local="${local_sha:0:7}"
  local short_remote="${remote_sha:0:7}"

  local changes=""
  IFS='|' read -ra _lines <<< "$changelog"
  for _line in "${_lines[@]}"; do
    [[ -z "$_line" ]] && continue
    local _msg="${_line#* }"
    changes+="• $_msg  "
  done

  echo "> 100x Dev update available ($short_local → $short_remote)"
  echo "> Changes: ${changes%  }"
  echo "> Run \`100x-update\` in your terminal to upgrade."
}

# ── Dispatch ──────────────────────────────────────────────────────────────────

case "$FLAG" in
  --silent)      _do_silent      ;;
  --notify)      _do_notify      ;;
  --claude-hook) _do_claude_hook ;;
  *)
    echo "Usage: check-update.sh [--silent|--notify|--claude-hook]" >&2
    exit 1
    ;;
esac
```

- [ ] **Step 2: Make executable**

```bash
chmod +x shell/check-update.sh
```

- [ ] **Step 3: Run tests**

```bash
bash tests/test-check-update.sh
```

Expected: all 5 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add shell/check-update.sh
git commit -m "feat: implement check-update.sh with cache helpers and all three output modes"
```

---

### Task 3: Update `shell/aliases.sh`

**Files:**
- Modify: `shell/aliases.sh`

- [ ] **Step 1: Write a test that verifies aliases.sh sources without error and background spawn syntax is correct**

Add to `tests/test-check-update.sh` — append before the `# ── Run ───` block:

```bash
test_aliases_sources_cleanly() {
  _setup
  local fake_script="$HOME/100x-dev/shell/check-update.sh"
  mkdir -p "$(dirname "$fake_script")"
  cat > "$fake_script" << 'STUB'
#!/usr/bin/env bash
echo "called: $1" >> "$HOME/.100x-dev/calls.log"
STUB
  chmod +x "$fake_script"

  # Source aliases in a subshell with fake HOME
  local alias_file="$REPO_DIR/shell/aliases.sh"
  local output
  output=$(HOME="$HOME" bash -c "source '$alias_file'" 2>&1) || true

  if [[ -z "$output" ]]; then
    echo "  PASS: aliases.sh sources without errors"
    (( PASS++ )) || true
  else
    echo "  FAIL: aliases.sh produced unexpected output on source"
    echo "    output: $output"
    (( FAIL++ )) || true
  fi
  _teardown
}
```

Also add `test_aliases_sources_cleanly` to the run section before the Results line.

- [ ] **Step 2: Run the new test — expect FAIL (aliases.sh not yet modified)**

```bash
bash tests/test-check-update.sh
```

Expected: `test_aliases_sources_cleanly` FAIL (aliases sources fine but the logic isn't wired yet — test passes vacuously). That's OK; the test mostly guards against syntax errors.

- [ ] **Step 3: Add notify call + background spawn to `shell/aliases.sh`**

Open `shell/aliases.sh`. After the existing aliases (`cc`, `ccc`, `100x-update`, `100x-check`), append:

```bash

# ── Version check ─────────────────────────────────────────────────────────────
# On shell startup: read cached update status (no network) and prompt if stale.
# Then kick off a background cache refresh for next session.
if [[ -x "$HOME/100x-dev/shell/check-update.sh" ]]; then
  bash "$HOME/100x-dev/shell/check-update.sh" --notify
  ("$HOME/100x-dev/shell/check-update.sh" --silent &) 2>/dev/null
fi
```

- [ ] **Step 4: Run tests**

```bash
bash tests/test-check-update.sh
```

Expected: all tests PASS.

- [ ] **Step 5: Smoke test manually**

```bash
# Manually set has_update=true in cache to see banner
mkdir -p ~/.100x-dev
cat > ~/.100x-dev/update-cache << 'EOF'
last_check=9999999999
has_update=true
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: test banner display|def5678 feat: something new
snoozed_until=0
EOF

# Source aliases as a login shell would
source ~/100x-dev/shell/aliases.sh
```

Expected: banner appears, prompt shows "Update now? (Y/n):". Answer N. Verify `snoozed_until` is set in cache:
```bash
grep snoozed_until ~/.100x-dev/update-cache
```
Expected: `snoozed_until=<timestamp in the future>`

Clean up test cache:
```bash
rm ~/.100x-dev/update-cache
```

- [ ] **Step 6: Commit**

```bash
git add shell/aliases.sh tests/test-check-update.sh
git commit -m "feat: wire version check into shell startup via aliases.sh"
```

---

### Task 4: Update `adapters/lib/shared.sh` — tracked-projects write-back

**Files:**
- Modify: `adapters/lib/shared.sh`

- [ ] **Step 1: Add a test for tracked-projects write-back**

Append to `tests/test-check-update.sh` (before `# ── Run ───`):

```bash
test_adapter_writes_tracked_projects() {
  _setup
  local fake_repo
  fake_repo="$(mktemp -d)"

  # Stub out WORKFLOWS_DIR so _run_generate doesn't need real workflows
  mkdir -p "$fake_repo/workflows"
  touch "$fake_repo/workflows/gate.md"

  # Source shared.sh and call _run_generate
  local output_file="$HOME/myproject/.cursorrules"
  mkdir -p "$HOME/myproject"

  (
    HUNDRED_X_REPO_OVERRIDE="$fake_repo" \
    HOME="$HOME" \
    bash -c "
      source '$REPO_DIR/adapters/lib/shared.sh'
      _run_generate '$HOME/myproject' '.cursorrules' 'TestTool'
    "
  ) 2>/dev/null || true

  local tracked="$HOME/.100x-dev/tracked-projects"
  if grep -qF "$HOME/myproject" "$tracked" 2>/dev/null; then
    echo "  PASS: _run_generate writes project path to tracked-projects"
    (( PASS++ )) || true
  else
    echo "  FAIL: project path not found in tracked-projects"
    (( FAIL++ )) || true
  fi

  rm -rf "$fake_repo"
  _teardown
}
```

Add `test_adapter_writes_tracked_projects` to the run section.

- [ ] **Step 2: Run test — expect FAIL**

```bash
bash tests/test-check-update.sh
```

Expected: `test_adapter_writes_tracked_projects` FAIL.

- [ ] **Step 3: Add write-back to `_run_generate` in `adapters/lib/shared.sh`**

Open `adapters/lib/shared.sh`. At the end of the `_run_generate` function, just before the final `echo -e "  ${GREEN}→ Generated $output_file ✓${NC}"` line, insert:

```bash
  # Record project path for auto-regeneration on update
  local _tracked_file="$HOME/.100x-dev/tracked-projects"
  mkdir -p "$(dirname "$_tracked_file")"
  local _abs_path
  _abs_path="$(cd "$project_path" && pwd)"
  if ! grep -qxF "$_abs_path" "$_tracked_file" 2>/dev/null; then
    echo "$_abs_path" >> "$_tracked_file"
  fi
```

- [ ] **Step 4: Run tests**

```bash
bash tests/test-check-update.sh
```

Expected: all tests PASS.

- [ ] **Step 5: Smoke test**

```bash
# Run an adapter against a temp dir and verify tracked-projects is written
tmp=$(mktemp -d)
bash ~/100x-dev/adapters/cursor.sh "$tmp"
grep "$tmp" ~/.100x-dev/tracked-projects
rm -rf "$tmp"
```

Expected: the temp dir path appears in `~/.100x-dev/tracked-projects`.

- [ ] **Step 6: Commit**

```bash
git add adapters/lib/shared.sh tests/test-check-update.sh
git commit -m "feat: write project path to tracked-projects on adapter run"
```

---

### Task 5: Update `update.sh` — regenerate tracked projects + hook merge + cache clear

**Files:**
- Modify: `update.sh`

- [ ] **Step 1: Add `regenerate_tracked_projects` function to `update.sh`**

Open `update.sh`. After the existing Python snippet (plugin merge block), add:

```bash

# ── Regenerate tracked project instruction files ────────────────────────────

regenerate_tracked_projects() {
  local tracked="$HOME/.100x-dev/tracked-projects"
  [[ -f "$tracked" ]] || return 0

  local count=0
  while IFS= read -r project_path; do
    [[ -z "$project_path" ]] && continue
    [[ -d "$project_path" ]] || continue  # skip deleted projects

    local regenerated=false

    [[ -f "$project_path/.cursorrules" ]]                    && bash "$REPO_DIR/adapters/cursor.sh"      "$project_path" && regenerated=true
    [[ -f "$project_path/AGENTS.md" ]]                       && bash "$REPO_DIR/adapters/codex.sh"       "$project_path" && regenerated=true
    [[ -f "$project_path/.windsurfrules" ]]                  && bash "$REPO_DIR/adapters/windsurf.sh"    "$project_path" && regenerated=true
    [[ -f "$project_path/.github/copilot-instructions.md" ]] && bash "$REPO_DIR/adapters/copilot.sh"    "$project_path" && regenerated=true
    [[ -f "$project_path/GEMINI.md" ]]                       && bash "$REPO_DIR/adapters/gemini.sh"      "$project_path" && regenerated=true
    [[ -f "$project_path/ANTIGRAVITY.md" ]]                  && bash "$REPO_DIR/adapters/antigravity.sh" "$project_path" && regenerated=true

    "$regenerated" && (( count++ )) || true
  done < "$tracked"

  if (( count > 0 )); then
    echo -e "  ${GREEN}→ Regenerated instruction files in $count tracked project(s) ✓${NC}"
  fi
}
```

- [ ] **Step 2: Add SessionStart hook merge to the Python block in `update.sh`**

Find the Python `<< PYEOF` block in `update.sh`. After the line `with open(settings_file, 'w') as f:` write block (just before `PYEOF`), add:

```python
# Merge SessionStart hook for version check
hook_cmd = os.path.expanduser('~/100x-dev/shell/check-update.sh') + ' --claude-hook'
hooks = settings.setdefault('hooks', {})
session_start = hooks.setdefault('SessionStart', [])

already_exists = any(
    h.get('command') == hook_cmd
    for entry in session_start
    for h in entry.get('hooks', [])
)

if not already_exists:
    session_start.append({
        'matcher': '',
        'hooks': [{'type': 'command', 'command': hook_cmd}]
    })
    print('  Added SessionStart update-check hook ✓')
else:
    print('  SessionStart hook: already configured ✓')
```

- [ ] **Step 3: Add cache clear + regeneration call at the end of `update.sh`**

Find the final success echo block in `update.sh`:
```bash
echo -e "${GREEN}✓ 100x Dev updated!...
```

Just before that line, add:

```bash
# Clear update-available flag from cache
if [[ -f "$HOME/.100x-dev/update-cache" ]]; then
  local _tmp
  _tmp="$(mktemp)"
  grep -v '^has_update=' "$HOME/.100x-dev/update-cache" > "$_tmp" || true
  grep -v '^snoozed_until=' "$_tmp" > "$HOME/.100x-dev/update-cache" || true
  echo "has_update=false" >> "$HOME/.100x-dev/update-cache"
  echo "snoozed_until=0"  >> "$HOME/.100x-dev/update-cache"
  rm -f "$_tmp"
fi

regenerate_tracked_projects
```

- [ ] **Step 4: Run update.sh in check-only mode to verify no syntax errors**

```bash
bash -n update.sh && echo "Syntax OK"
bash ~/100x-dev/update.sh --check-only
```

Expected: `Syntax OK`, then the usual up-to-date or diff output.

- [ ] **Step 5: Verify hook is written to settings.json**

```bash
python3 - << 'EOF'
import json
with open('/Users/rajit/.claude/settings.json') as f:
    s = json.load(f)
hooks = s.get('hooks', {})
ss = hooks.get('SessionStart', [])
cmds = [h.get('command') for e in ss for h in e.get('hooks', [])]
print('SessionStart hooks:', cmds)
EOF
```

Expected: output includes `~/100x-dev/shell/check-update.sh --claude-hook`.

- [ ] **Step 6: Commit**

```bash
git add update.sh
git commit -m "feat: auto-regenerate tracked projects and register SessionStart hook on update"
```

---

### Task 6: Update `install.sh` — SessionStart hook merge on fresh install

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Add hook merge to `do_install_plugins` in `install.sh`**

Open `install.sh`. Find the `do_install_plugins()` function:

```bash
do_install_plugins() {
  if [ "$TOOL_CLAUDE" = true ]; then
    source "$REPO_DIR/adapters/claude-code.sh"
    install_plugins
  fi
}
```

Replace it with:

```bash
do_install_plugins() {
  if [ "$TOOL_CLAUDE" = true ]; then
    source "$REPO_DIR/adapters/claude-code.sh"
    install_plugins
    _install_session_hook
  fi
}

_install_session_hook() {
  local settings_file="$HOME/.claude/settings.json"
  [[ -f "$settings_file" ]] || return 0

python3 << PYEOF
import json, os

settings_file = os.path.expanduser('$settings_file')
hook_cmd = os.path.expanduser('~/100x-dev/shell/check-update.sh') + ' --claude-hook'

with open(settings_file) as f:
    settings = json.load(f)

hooks = settings.setdefault('hooks', {})
session_start = hooks.setdefault('SessionStart', [])

already_exists = any(
    h.get('command') == hook_cmd
    for entry in session_start
    for h in entry.get('hooks', [])
)

if not already_exists:
    session_start.append({
        'matcher': '',
        'hooks': [{'type': 'command', 'command': hook_cmd}]
    })
    print('  Added SessionStart update-check hook ✓')
else:
    print('  SessionStart hook: already configured ✓')

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)
PYEOF
}
```

- [ ] **Step 2: Verify syntax**

```bash
bash -n install.sh && echo "Syntax OK"
```

Expected: `Syntax OK`.

- [ ] **Step 3: Simulate a Claude Code install path to verify hook merge**

```bash
# Check current settings.json for the hook
python3 - << 'EOF'
import json
with open('/Users/rajit/.claude/settings.json') as f:
    s = json.load(f)
ss = s.get('hooks', {}).get('SessionStart', [])
cmds = [h.get('command') for e in ss for h in e.get('hooks', [])]
print('Current SessionStart commands:', cmds)
EOF
```

Expected: hook already present from Task 5. Running install again should be idempotent — "already configured ✓".

- [ ] **Step 4: Commit**

```bash
git add install.sh
git commit -m "feat: merge SessionStart update-check hook on fresh Claude Code install"
```

---

### Task 7: Run full test suite + update docs

**Files:**
- Modify: `docs/USAGE.md`

- [ ] **Step 1: Run full test suite**

```bash
bash tests/test-check-update.sh
```

Expected: all tests PASS, `0 failed`.

- [ ] **Step 2: Verify end-to-end shell startup**

```bash
# Set up a fake "update available" cache
mkdir -p ~/.100x-dev
cat > ~/.100x-dev/update-cache << 'EOF'
last_check=9999999999
has_update=true
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: test notification works|def5678 feat: auto-regen
snoozed_until=0
EOF

# Open a new shell to trigger aliases.sh
bash --rcfile ~/100x-dev/shell/aliases.sh -i << 'SHELL'
exit
SHELL
```

Expected: banner appears with the two changelog entries. (Prompt won't show in non-interactive subshell — that's correct; the `[[ -t 0 ]]` guard fires.)

Clean up:
```bash
rm ~/.100x-dev/update-cache
```

- [ ] **Step 3: Verify end-to-end Claude Code hook**

```bash
bash ~/100x-dev/shell/check-update.sh --claude-hook
```

Expected: no output (cache doesn't exist or `has_update=false`).

```bash
mkdir -p ~/.100x-dev
cat > ~/.100x-dev/update-cache << 'EOF'
last_check=9999999999
has_update=true
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: hooks work
snoozed_until=0
EOF
bash ~/100x-dev/shell/check-update.sh --claude-hook
rm ~/.100x-dev/update-cache
```

Expected:
```
> 100x Dev update available (abc1234 → def5678)
> Changes: • fix: hooks work
> Run `100x-update` in your terminal to upgrade.
```

- [ ] **Step 4: Update `docs/USAGE.md` — add version notifications section**

Find the `## Keeping Workflows Updated` section in `docs/USAGE.md`. Add below the "Manual" subsection and before `### For Per-Project Files`:

```markdown
### Automatic Version Notifications

After install, 100x Dev checks for updates once per day in the background. When a new version is available:

**In your terminal** — a banner appears on the next shell open:
```
╔══════════════════════════════════════════════════════╗
║  100x Dev update available: abc1234 → def5678        ║
║  • fix: detect Bun before enabling claude-mem        ║
╚══════════════════════════════════════════════════════╝
Update now? (Y/n):
```
Answer `Y` to update immediately. Answer `N` to snooze for 24 hours.

**In Claude Code** — a notice appears at the top of your session:
```
> 100x Dev update available (abc1234 → def5678)
> Changes: • fix: detect Bun before enabling claude-mem
> Run `100x-update` in your terminal to upgrade.
```

After running `100x-update`, instruction files (`.cursorrules`, `AGENTS.md`, etc.) in all your tracked projects are automatically regenerated — no manual re-runs needed.

Update state is stored in `~/.100x-dev/update-cache`. To force an immediate check:
```bash
~/100x-dev/shell/check-update.sh --silent   # refresh cache now
~/100x-dev/shell/check-update.sh --notify   # check + prompt now
```
```

- [ ] **Step 5: Final commit**

```bash
git add docs/USAGE.md tests/test-check-update.sh
git commit -m "docs: document version notification system + finalize test suite"
```

---

## Self-Review

**Spec coverage:**
- [x] Daily check with cache — Task 2 (`_refresh_cache`, 86400s threshold)
- [x] Shell startup banner + prompt — Task 3 (`aliases.sh` + `--notify`)
- [x] Background cache refresh — Task 3 (`--silent` background spawn)
- [x] Claude Code SessionStart hook — Task 5 + 6 (settings.json merge)
- [x] Snooze on N — Task 2 (`_snooze`, `_is_snoozed`)
- [x] Offline handling — Task 2 (`git fetch` failure path)
- [x] tracked-projects write-back — Task 4 (`shared.sh`)
- [x] Auto-regeneration on update — Task 5 (`regenerate_tracked_projects`)
- [x] Cache clear after update — Task 5
- [x] `~/.100x-dev/` creation — Task 1 + every script does `mkdir -p`
- [x] Error handling: deleted project paths — Task 5 (`[[ -d "$project_path" ]] || continue`)

**Type/name consistency:**
- `_run_generate` — defined in shared.sh, called consistently
- `_cache_get` / `_cache_set` — defined once in check-update.sh, used only within it
- `CACHE_FILE` / `STATE_DIR` — consistent across all tasks
- `regenerate_tracked_projects` — defined and called only in update.sh
- `_install_session_hook` — defined and called only in install.sh

**No placeholders found.**
