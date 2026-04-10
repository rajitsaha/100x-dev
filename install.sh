#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
TEMPLATES_DIR="$HOME/claude-templates"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo "╔══════════════════════════════════════╗"
echo "║     Claude Dev Setup — Installer     ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ── Component selection ──────────────────────────────────────────────────────

select_components() {
  local install_commands=true
  local install_plugins=true
  local install_shell=true
  local install_templates=true

  echo "What would you like to install?"
  echo "  (Enter component numbers to toggle, then press Enter with no input to confirm)"
  echo ""

  while true; do
    echo "  [$([ "$install_commands" = true ] && echo "x" || echo " ")] 1) Commands    — /launch, /commit, /push, /test, /security, ..."
    echo "  [$([ "$install_plugins" = true ] && echo "x" || echo " ")] 2) Plugins     — superpowers, stripe, hookify, pr-review-toolkit, ..."
    echo "  [$([ "$install_shell" = true ] && echo "x" || echo " ")] 3) Shell       — aliases + shortcuts (cc, ccc, claude-update, ...)"
    echo "  [$([ "$install_templates" = true ] && echo "x" || echo " ")] 4) Templates  — CLAUDE.md starters (node, python, docker)"
    echo ""
    read -rp "  Toggle (1-4) or press Enter to confirm: " choice

    case "$choice" in
      1) install_commands=$([ "$install_commands" = true ] && echo false || echo true) ;;
      2) install_plugins=$([ "$install_plugins" = true ] && echo false || echo true) ;;
      3) install_shell=$([ "$install_shell" = true ] && echo false || echo true) ;;
      4) install_templates=$([ "$install_templates" = true ] && echo false || echo true) ;;
      "") break ;;
      *) echo "  Invalid choice. Enter 1, 2, 3, or 4." ;;
    esac
    echo ""
  done

  INSTALL_COMMANDS=$install_commands
  INSTALL_PLUGINS=$install_plugins
  INSTALL_SHELL=$install_shell
  INSTALL_TEMPLATES=$install_templates
}

# ── Installers ───────────────────────────────────────────────────────────────

install_commands() {
  echo ""
  echo "Installing Commands..."
  mkdir -p "$COMMANDS_DIR"

  if [ -d "$COMMANDS_DIR" ] && [ "$(ls -A "$COMMANDS_DIR" 2>/dev/null)" ]; then
    BACKUP="$CLAUDE_DIR/commands.bak.$(date +%Y%m%d_%H%M%S)"
    cp -r "$COMMANDS_DIR" "$BACKUP"
    echo -e "  ${YELLOW}→ Backed up existing commands to $(basename "$BACKUP")${NC}"
  fi

  count=0
  for f in "$REPO_DIR/commands/"*.md; do
    cp "$f" "$COMMANDS_DIR/"
    count=$((count + 1))
  done
  echo -e "  ${GREEN}→ Copied $count commands to ~/.claude/commands/ ✓${NC}"
  echo -e "  ${CYAN}→ Restart Claude Code to load new commands${NC}"
}

install_plugins() {
  echo ""
  echo "Installing Plugins..."
  mkdir -p "$CLAUDE_DIR"

  PLUGINS_FILE="$REPO_DIR/plugins.json"

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

  if [ -f "$SETTINGS_FILE" ]; then
    : # file exists, python will read it
  else
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

install_shell() {
  echo ""
  echo "Installing Shell aliases..."

  SOURCE_LINE="source $REPO_DIR/shell/claude-aliases.sh"

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

  if grep -qF "$SOURCE_LINE" "$RC_FILE" 2>/dev/null; then
    echo -e "  ${YELLOW}→ Already sourced in ~/${RC_FILE##*/} (no change)${NC}"
  else
    echo "" >> "$RC_FILE"
    echo "# Claude Code aliases" >> "$RC_FILE"
    echo "$SOURCE_LINE" >> "$RC_FILE"
    echo -e "  ${GREEN}→ Added source line to ~/${RC_FILE##*/} ($SHELL_NAME) ✓${NC}"
  fi

  echo -e "  ${CYAN}→ Run: source ~/${RC_FILE##*/}  to activate now${NC}"
}

install_templates() {
  echo ""
  echo "Installing Templates..."
  mkdir -p "$TEMPLATES_DIR"

  count=0
  for f in "$REPO_DIR/templates/"*.md; do
    cp "$f" "$TEMPLATES_DIR/"
    count=$((count + 1))
  done

  echo -e "  ${GREEN}→ Copied $count templates to ~/claude-templates/ ✓${NC}"
  echo -e "  ${CYAN}→ Copy the relevant template into your project as CLAUDE.md${NC}"
}

# ── Main ─────────────────────────────────────────────────────────────────────

select_components

echo ""
echo "──────────────────────────────────────"

[ "$INSTALL_COMMANDS" = true ]  && install_commands
[ "$INSTALL_PLUGINS" = true ]   && install_plugins
[ "$INSTALL_SHELL" = true ]     && install_shell
[ "$INSTALL_TEMPLATES" = true ] && install_templates

echo ""
echo "──────────────────────────────────────"
echo -e "${GREEN}✓ Done! Restart Claude Code to load all changes.${NC}"
echo ""
