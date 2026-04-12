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
  trap '_teardown' EXIT
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
  if grep -qF "$pattern" "$file" 2>/dev/null; then
    echo "  PASS: $label"
    (( PASS++ )) || true
  else
    echo "  FAIL: $label — pattern '$pattern' not found in $file"
    (( FAIL++ )) || true
  fi
}

_make_cache() {
  # _make_cache <home_dir> [has_update] [snoozed_until]
  local home_dir="${1:-$HOME}"
  local has_update="${2:-false}"
  local snoozed_until="${3:-0}"
  mkdir -p "$home_dir/.100x-dev"
  cat > "$home_dir/.100x-dev/update-cache" << EOF
last_check=9999999999
has_update=$has_update
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: detect Bun|def5678 feat: shared lib
snoozed_until=$snoozed_until
EOF
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
  _make_cache "$HOME" false
  local output
  output=$(bash "$SCRIPT" --claude-hook 2>/dev/null)
  _assert_eq "no output when no update (--claude-hook)" "" "$output"
  _teardown
}

test_claude_hook_outputs_notice_when_update_available() {
  _setup
  _make_cache "$HOME" true
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
  _make_cache "$HOME" true "$(( $(date +%s) + 86400 ))"
  local output
  output=$(bash "$SCRIPT" --claude-hook 2>/dev/null)
  _assert_eq "snoozed suppresses --claude-hook output" "" "$output"
  _teardown
}

test_silent_creates_cache_file() {
  _setup
  # Point REPO_DIR to a temp git repo to avoid real network calls
  local fake_repo
  fake_repo="$(mktemp -d)"
  cd "$fake_repo"
  git init --quiet
  git commit --allow-empty -m "init" --quiet

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

test_invalid_flag_exits_nonzero() {
  _setup
  local exit_code=0
  bash "$SCRIPT" --invalid-flag 2>/dev/null || exit_code=$?
  if (( exit_code != 0 )); then
    echo "  PASS: invalid flag exits non-zero"
    (( PASS++ )) || true
  else
    echo "  FAIL: invalid flag should exit non-zero"
    (( FAIL++ )) || true
  fi
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
test_invalid_flag_exits_nonzero

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
