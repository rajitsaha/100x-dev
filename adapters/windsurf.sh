#!/usr/bin/env bash
set -e

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

# Windsurf has a tight rules file size limit, so we emit index-only mode
# (one line per module) instead of full bodies.
install_project() {
  _run_concat "${1:-.}" ".windsurfrules" "Windsurf" "index"
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_project "${1:-.}"
fi
