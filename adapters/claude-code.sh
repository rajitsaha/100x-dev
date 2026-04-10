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
    cp "$f" "$COMMANDS_DIR/$(basename "$f")"
    echo "" >> "$COMMANDS_DIR/$(basename "$f")"
    echo '$ARGUMENTS' >> "$COMMANDS_DIR/$(basename "$f")"
    count=$((count + 1))
  done

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

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  case "${1:-}" in
    --plugins) install_plugins ;;
    *) install_global ;;
  esac
fi
