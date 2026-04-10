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

# ── Install workflows ───────────────────────────────────────────────────────

install_workflows() {
  if [ "$TOOL_CLAUDE" = true ]; then
    source "$REPO_DIR/adapters/claude-code.sh"
    install_global
  fi

  local need_project_path=false
  for tool in CURSOR CODEX WINDSURF COPILOT GEMINI ANTIGRAVITY; do
    eval "val=\$TOOL_$tool"
    [ "$val" = true ] && need_project_path=true && break
  done

  if [ "$need_project_path" = true ]; then
    echo ""
    read -rp "  Project path for generated files (default: current directory): " PROJECT_PATH
    PROJECT_PATH="${PROJECT_PATH:-.}"

    [ "$TOOL_CURSOR" = true ]      && bash "$REPO_DIR/adapters/cursor.sh" "$PROJECT_PATH"
    [ "$TOOL_CODEX" = true ]       && bash "$REPO_DIR/adapters/codex.sh" "$PROJECT_PATH"
    [ "$TOOL_WINDSURF" = true ]    && bash "$REPO_DIR/adapters/windsurf.sh" "$PROJECT_PATH"
    [ "$TOOL_COPILOT" = true ]     && bash "$REPO_DIR/adapters/copilot.sh" "$PROJECT_PATH"
    [ "$TOOL_GEMINI" = true ]      && bash "$REPO_DIR/adapters/gemini.sh" "$PROJECT_PATH"
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
