# shellcheck shell=bash
# 100xPrism shortcuts
# Source this file manually when you want aliases in the current terminal:
#   source ~/100xprism/shell/aliases.sh

# Launch Claude
alias cc='claude'
alias ccc='claude --continue'

# Setup management
# shellcheck disable=SC2139
alias 100xprism="node $HOME/100xprism/bin/100xprism.js"
# shellcheck disable=SC2139
alias 100x-update="$HOME/100xprism/update.sh"
# shellcheck disable=SC2139
alias 100x-check="$HOME/100xprism/update.sh --check-only"

# Token usage — one machine-wide dashboard (all sessions & repos); auto-opens the
# URL, and relaunching from any session just opens the already-running one.
# shellcheck disable=SC2139
alias 100x-tokens="100xprism tokens"
# What shipped (value, to read next to token cost) — defaults to the current repo.
# shellcheck disable=SC2139
alias 100x-value="100xprism value"
