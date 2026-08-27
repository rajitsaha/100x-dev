#!/usr/bin/env bash
# adapters/pi.sh — emit retention-filtered Pi project artifacts into .pi/
set -euo pipefail
_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/lib" && pwd)"
# shellcheck disable=SC1091
source "$_LIB_DIR/shared.sh"

PROJECT_PATH="$(cd "${1:-$PWD}" && pwd)"
echo ""
echo "Generating .pi/ skills for Pi (retention on)..."
python3 "$MODULES_PY" emit-pi "$PROJECT_PATH"
_track_project "$PROJECT_PATH"
echo -e "  ${GREEN}→ Generated .pi/skills/ (+ prompts, catalog) in $PROJECT_PATH ✓${NC}"
echo -e "  ${YELLOW}→ Install the package with: pi install git:github.com/rajitsaha/100xprism${NC}"
echo -e "  ${YELLOW}→ Or point Pi at this repo; trust the project when prompted.${NC}"
