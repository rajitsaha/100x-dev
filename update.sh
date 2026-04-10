#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
COMMANDS_DIR="$CLAUDE_DIR/commands"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
CHECK_ONLY=false

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

[ "$1" = "--check-only" ] && CHECK_ONLY=true

echo ""
echo "Checking for updates..."

cd "$REPO_DIR"

git fetch origin main --quiet 2>/dev/null

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  echo -e "${GREEN}✓ Already up to date.${NC}"
  echo ""
  exit 0
fi

CHANGES=$(git log --oneline "$LOCAL..$REMOTE" 2>/dev/null)
LOCAL_SHORT=$(git rev-parse --short HEAD)
REMOTE_SHORT=$(git rev-parse --short origin/main)

echo ""
echo "  Current version:  $LOCAL_SHORT ($(git log -1 --format='%ar' HEAD))"
echo "  Latest version:   $REMOTE_SHORT ($(git log -1 --format='%ar' origin/main))"
echo ""
echo "Changes:"
echo "$CHANGES" | sed 's/^/  • /'
echo ""

if [ "$CHECK_ONLY" = true ]; then
  echo -e "${CYAN}Run '~/claude-dev-setup/update.sh' to apply updates.${NC}"
  echo ""
  exit 0
fi

read -rp "Apply updates? (Y/n): " confirm
confirm=${confirm:-Y}

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
  echo "Skipped."
  exit 0
fi

echo ""

git pull origin main --quiet
echo -e "  ${GREEN}→ Pulled latest ✓${NC}"

if [ -d "$COMMANDS_DIR" ] && [ "$(ls -A "$COMMANDS_DIR" 2>/dev/null)" ]; then
  BACKUP="$CLAUDE_DIR/commands.bak.$(date +%Y%m%d_%H%M%S)"
  cp -r "$COMMANDS_DIR" "$BACKUP"
  echo -e "  ${YELLOW}→ Backed up commands to $(basename "$BACKUP")${NC}"
fi

count=0
for f in "$REPO_DIR/commands/"*.md; do
  cp "$f" "$COMMANDS_DIR/"
  count=$((count + 1))
done

# Update db-engines subdirectory
if [ -d "$REPO_DIR/commands/db-engines" ]; then
  mkdir -p "$COMMANDS_DIR/db-engines"
  cp "$REPO_DIR/commands/db-engines/"*.md "$COMMANDS_DIR/db-engines/"
  echo -e "  ${GREEN}→ Updated db-engines/ ($(ls "$REPO_DIR/commands/db-engines/"*.md | wc -l | tr -d ' ') engine files) ✓${NC}"
fi

echo -e "  ${GREEN}→ Updated $count commands ✓${NC}"

python3 << PYEOF
import json, os

plugins_file = os.path.join('$REPO_DIR', 'plugins.json')
settings_file = '$SETTINGS_FILE'

with open(plugins_file) as f:
    repo_data = json.load(f)

with open(settings_file) as f:
    settings = json.load(f)

new_plugins = repo_data.get('plugins', [])
enabled = settings.get('enabledPlugins', {})
added = 0
for p in new_plugins:
    if p not in enabled:
        enabled[p] = True
        added += 1

settings['enabledPlugins'] = enabled

extra = repo_data.get('extraKnownMarketplaces', {})
settings.setdefault('extraKnownMarketplaces', {}).update(extra)

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)

if added > 0:
    print(f'  Added {added} new plugin(s) to settings.json ✓')
else:
    print('  Plugins: already up to date ✓')
PYEOF

echo -e "  ${CYAN}→ Shell aliases auto-updated (sourced file)${NC}"
echo ""
echo -e "${GREEN}✓ Updated! Run /reload-plugins in Claude Code to activate new plugins.${NC}"
echo ""
echo -e "${CYAN}Tip: Add this to your crontab to get notified weekly:${NC}"
echo "  0 9 * * 1 $REPO_DIR/update.sh --check-only"
echo ""
