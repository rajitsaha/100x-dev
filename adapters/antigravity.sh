#!/usr/bin/env bash
set -e

source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

install_project() {
  _run_generate "${1:-.}" "ANTIGRAVITY.md" "Antigravity" \
    "Note: Antigravity adapter is provisional — update when format is confirmed."
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
