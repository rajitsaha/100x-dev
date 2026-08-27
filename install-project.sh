#!/usr/bin/env bash
set -euo pipefail

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
TOOL_PI=false

select_tools() {
  echo "Which AI coding tools do you use in this project?"
  echo "  (Enter numbers to toggle, then press Enter with no input to confirm)"
  echo ""

  while true; do
    echo "  [$([ "$TOOL_CLAUDE" = true ] && echo "x" || echo " ")] 1) Claude Code"
    echo "  [$([ "$TOOL_CURSOR" = true ] && echo "x" || echo " ")] 2) Cursor"
    echo "  [$([ "$TOOL_CODEX" = true ] && echo "x" || echo " ")] 3) Codex (OpenAI)"
    echo "  [$([ "$TOOL_PI" = true ] && echo "x" || echo " ")] 4) Pi"
    echo ""
    read -rp "  Toggle (1-4) or press Enter to confirm: " choice || true
    case "$choice" in
      1) TOOL_CLAUDE=$([ "$TOOL_CLAUDE" = true ] && echo false || echo true) ;;
      2) TOOL_CURSOR=$([ "$TOOL_CURSOR" = true ] && echo false || echo true) ;;
      3) TOOL_CODEX=$([ "$TOOL_CODEX" = true ] && echo false || echo true) ;;
      4) TOOL_PI=$([ "$TOOL_PI" = true ] && echo false || echo true) ;;
      "") break ;;
      *) echo "  Invalid choice. Enter 1-4." ;;
    esac
    echo ""
  done

  if [ "$TOOL_CLAUDE" = false ] && [ "$TOOL_CURSOR" = false ] && [ "$TOOL_CODEX" = false ] && [ "$TOOL_PI" = false ]; then
    echo -e "  ${YELLOW}No tools selected. Exiting.${NC}"
    exit 1
  fi
}

select_tools

if [ "$TOOL_CLAUDE" = true ]; then
  source "$REPO_DIR/adapters/claude-code.sh"
  install_project "$PROJECT_PATH"
fi

[ "$TOOL_CURSOR" = true ] && bash "$REPO_DIR/adapters/cursor.sh" "$PROJECT_PATH"
[ "$TOOL_CODEX" = true ]  && bash "$REPO_DIR/adapters/codex.sh"  "$PROJECT_PATH"
[ "$TOOL_PI" = true ]     && bash "$REPO_DIR/adapters/pi.sh"     "$PROJECT_PATH"

# Prune artifacts from tools dropped in v3.0.0. This is the path that reaches
# repos `update` cannot see — ones cloned fresh, or set up on another machine,
# so they were never added to ~/.100xprism/tracked-projects.
# shellcheck disable=SC1091
source "$REPO_DIR/adapters/lib/deprecated.sh"
prune_deprecated_artifacts "$PROJECT_PATH"
if (( PRUNED_COUNT > 0 )); then
  echo ""
  echo -e "  ${YELLOW}→ Removed $PRUNED_COUNT file(s) from tools dropped in v3.0.0${NC}"
  echo -e "  ${CYAN}   Usually committed — review with 'git status' and commit the deletions.${NC}"
fi

echo ""
echo -e "${GREEN}✓ Project set up!${NC}"
echo -e "${CYAN}  Run 100xprism update any time to pull latest workflows.${NC}"
echo ""
