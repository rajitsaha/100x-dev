#!/usr/bin/env bash
set -e

INSTALL_DIR="$HOME/100x-dev"

if [ -d "$INSTALL_DIR/.git" ]; then
  echo "100x-dev already installed — pulling latest..."
  git -C "$INSTALL_DIR" pull --rebase origin main --quiet \
    || { echo "Error: git pull failed. Check your network or resolve any conflicts in $INSTALL_DIR."; exit 1; }
else
  echo "Installing 100x-dev..."
  git clone https://github.com/rajitsaha/100x-dev.git "$INSTALL_DIR" --quiet \
    || { echo "Error: git clone failed. Check your network and try again."; exit 1; }
fi

exec bash "$INSTALL_DIR/install.sh" "$@"
