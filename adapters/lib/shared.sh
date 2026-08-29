#!/usr/bin/env bash
# shared.sh — common logic for all 100xprism adapter scripts.
# Source this file; do not execute directly.
#
# All adapters dispatch to adapters/lib/modules.py for module reading and
# rendering. Adapters here provide thin shell wrappers + per-tool output paths.

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$_LIB_DIR/../.." && pwd)"
MODULES_PY="$_LIB_DIR/modules.py"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# _run_cursor <project_path>
# Cursor supports per-rule files with description-based auto-trigger, so we
# write one .cursor/rules/<slug>.mdc per module.
_run_cursor() {
  local project_path="$1"
  echo ""
  echo "Generating .cursor/rules/ for Cursor..."
  python3 "$MODULES_PY" emit-cursor "$project_path"
  _track_project "$project_path"
  echo -e "  ${GREEN}→ Generated .cursor/rules/ in $project_path ✓${NC}"
}

# _run_codex <project_path>
# Codex supports repo-scoped skills and hooks, so we keep AGENTS.md compact and
# emit full module bodies into .agents/skills for progressive loading.
_run_codex() {
  local project_path="$1"
  echo ""
  echo "Generating Codex project artifacts..."
  python3 "$MODULES_PY" emit-codex "$project_path"
  _track_project "$project_path"
  echo -e "  ${GREEN}→ Generated AGENTS.md, .agents/skills/, and .codex/hooks.json in $project_path ✓${NC}"
  echo -e "  ${YELLOW}→ In Codex, run /hooks to review and trust generated hooks.${NC}"
}

# _run_pi <project_path>
# Pi indexes every discovered skill description, so retention is ON by default.
_run_pi() {
  local project_path="$1"
  echo ""
  echo "Generating .pi/ for Pi (retention on by default)..."
  python3 "$MODULES_PY" emit-pi "$project_path"
  _track_project "$project_path"
  echo -e "  ${GREEN}→ Generated .pi/skills/ in $project_path ✓${NC}"
}

# _hermes_installed
# Detects whether this machine actually has Hermes/OpenClaw, so install/update
# only ever create ~/.hermes/skills for users who use it — never for everyone.
# A prior 100xprism run (~/.hermes/skills/100xprism/) also counts, so once a
# user has opted in (or the hermes CLI later goes away) reconciliation keeps
# working instead of orphaning the skills it wrote.
_hermes_installed() {
  [ -d "$HOME/.hermes" ] && return 0
  command -v hermes >/dev/null 2>&1 && return 0
  return 1
}

# _run_hermes
# Hermes/OpenClaw skills are global (like Claude Code's), not per-project — one
# ~/.hermes/skills/100xprism/<slug>/SKILL.md per module, reconciled on every run.
# There is no per-project artifact to generate, so this does not call
# _track_project the way the per-project adapters do.
_run_hermes() {
  echo ""
  echo "Installing modules for Hermes/OpenClaw..."
  python3 "$MODULES_PY" emit-hermes
  echo -e "  ${GREEN}→ Modules installed to ~/.hermes/skills/${YELLOW}100xprism${GREEN}/ ✓${NC}"
  echo -e "  ${CYAN}→ Restart Hermes (or start a new session) to load new/updated skills${NC}"
}

_track_project() {
  local project_path="$1"
  local _tracked_file="$HOME/.100xprism/tracked-projects"
  mkdir -p "$(dirname "$_tracked_file")"
  local _abs_path
  _abs_path="$(cd "$project_path" && pwd)"
  if ! grep -qxF "$_abs_path" "$_tracked_file" 2>/dev/null; then
    echo "$_abs_path" >> "$_tracked_file"
  fi
}
