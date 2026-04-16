# shellcheck shell=bash
# 100x Dev shortcuts
# Source this file from ~/.zshrc or ~/.bashrc:
#   source ~/100x-dev/shell/aliases.sh

# Launch Claude
alias cc='claude'
alias ccc='claude --continue'

# Setup management
# shellcheck disable=SC2139
alias 100x-update="$HOME/100x-dev/update.sh"
# shellcheck disable=SC2139
alias 100x-check="$HOME/100x-dev/update.sh --check-only"

# ── Version check ─────────────────────────────────────────────────────────────
# On shell startup: read cached update status (no network) + prompt if available.
# Then kick off a background cache refresh for next session.
if [[ -x "$HOME/100x-dev/shell/check-update.sh" ]]; then
  bash "$HOME/100x-dev/shell/check-update.sh" --notify
  ("$HOME/100x-dev/shell/check-update.sh" --silent &) 2>/dev/null
fi
