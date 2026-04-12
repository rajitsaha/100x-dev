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
