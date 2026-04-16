#!/usr/bin/env bash
set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
WORKFLOWS_DIR="$CLAUDE_DIR/commands"
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
while IFS= read -r line; do echo "  • $line"; done <<< "$CHANGES"
echo ""

if [ "$CHECK_ONLY" = true ]; then
  echo -e "${CYAN}Run '~/100x-dev/update.sh' to apply updates.${NC}"
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

if [ -d "$WORKFLOWS_DIR" ] && [ "$(ls -A "$WORKFLOWS_DIR" 2>/dev/null)" ]; then
  BACKUP="$CLAUDE_DIR/commands.bak.$(date +%Y%m%d_%H%M%S)"
  cp -r "$WORKFLOWS_DIR" "$BACKUP"
  echo -e "  ${YELLOW}→ Backed up workflows to $(basename "$BACKUP")${NC}"
fi

count=0
for f in "$REPO_DIR/workflows/"*.md; do
  cp "$f" "$WORKFLOWS_DIR/"
  count=$((count + 1))
done

# Update db-engines subdirectory
if [ -d "$REPO_DIR/workflows/db-engines" ]; then
  mkdir -p "$WORKFLOWS_DIR/db-engines"
  cp "$REPO_DIR/workflows/db-engines/"*.md "$WORKFLOWS_DIR/db-engines/"
  echo -e "  ${GREEN}→ Updated db-engines/ ($(find "$REPO_DIR/workflows/db-engines/" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ') engine files) ✓${NC}"
fi

echo -e "  ${GREEN}→ Updated $count workflows ✓${NC}"

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

with open(settings_file, 'w') as f:
    json.dump(settings, f, indent=2)

if added > 0:
    print(f'  Added {added} new plugin(s) to settings.json ✓')
else:
    print('  Plugins: already up to date ✓')
PYEOF

echo -e "  ${CYAN}→ Shell aliases auto-updated (sourced file)${NC}"

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

# Clear update-available flag from cache so banner stops showing
if [[ -f "$HOME/.100x-dev/update-cache" ]]; then
  _tmp="$(mktemp)"
  grep -v '^has_update=' "$HOME/.100x-dev/update-cache" > "$_tmp" 2>/dev/null || true
  grep -v '^snoozed_until=' "$_tmp" >> /dev/null || true
  mv "$_tmp" "$HOME/.100x-dev/update-cache"
  echo "has_update=false"  >> "$HOME/.100x-dev/update-cache"
  echo "snoozed_until=0"   >> "$HOME/.100x-dev/update-cache"
fi

regenerate_tracked_projects

echo ""
NEW_VERSION="$(cat "$REPO_DIR/VERSION" 2>/dev/null | tr -d '[:space:]')"
echo -e "${GREEN}✓ 100x Dev updated to v${NEW_VERSION}! Note: if using Claude Code, run /reload-plugins to activate new plugins.${NC}"
echo ""
echo -e "${CYAN}Tip: Add this to your crontab to get notified weekly:${NC}"
echo "  0 9 * * 1 $REPO_DIR/update.sh --check-only"
echo ""
