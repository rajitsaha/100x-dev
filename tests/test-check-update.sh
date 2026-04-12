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
  if grep -q "$pattern" "$file" 2>/dev/null; then
    echo "  PASS: $label"
    (( PASS++ )) || true
  else
    echo "  FAIL: $label — pattern '$pattern' not found in $file"
    (( FAIL++ )) || true
  fi
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
  cat > "$HOME/.100x-dev/update-cache" << 'EOF'
last_check=9999999999
has_update=false
local_sha=abc1234
remote_sha=abc1234
changelog=
snoozed_until=0
EOF
  local output
  output=$(bash "$SCRIPT" --claude-hook 2>/dev/null)
  _assert_eq "no output when no update (--claude-hook)" "" "$output"
  _teardown
}

test_claude_hook_outputs_notice_when_update_available() {
  _setup
  cat > "$HOME/.100x-dev/update-cache" << 'EOF'
last_check=9999999999
has_update=true
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: detect Bun|def5678 feat: shared lib
snoozed_until=0
EOF
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
  local future=$(( $(date +%s) + 86400 ))
  cat > "$HOME/.100x-dev/update-cache" << EOF
last_check=9999999999
has_update=true
local_sha=abc1234abc
remote_sha=def5678def
changelog=abc1234 fix: something
snoozed_until=$future
EOF
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

# ── Run ───────────────────────────────────────────────────────────────────────

echo ""
echo "Running check-update tests..."
echo ""

test_creates_state_dir
test_no_output_when_no_update
test_claude_hook_outputs_notice_when_update_available
test_snoozed_suppresses_claude_hook
test_silent_creates_cache_file

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
