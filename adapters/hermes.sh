#!/usr/bin/env bash
set -e

# shellcheck disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/lib/shared.sh"

install_global() {
  _run_hermes
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  install_global
fi
