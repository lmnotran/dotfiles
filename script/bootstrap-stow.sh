#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "[bootstrap] Ensuring GNU Stow is installed..."
if ! command -v stow >/dev/null 2>&1; then
  if [[ "$OSTYPE" == darwin* ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install stow
    else
      echo "Homebrew not found; install it from https://brew.sh and re-run" >&2
      exit 1
    fi
  else
    echo "Please install GNU Stow using your package manager." >&2
    exit 1
  fi
fi

TARGET=${TARGET:-$HOME}
PACKAGES=${PACKAGES:-"zsh bin"}

# Fix legacy absolute symlink for ~/.zshrc pointing to repo root .zshrc
LEGACY_ZSHRC_TARGET="$TARGET/.zshrc"
if [[ -L "$LEGACY_ZSHRC_TARGET" ]]; then
  CURRENT_LINK="$(readlink "$LEGACY_ZSHRC_TARGET" || true)"
  if [[ "$CURRENT_LINK" == "$PWD/.zshrc" ]]; then
    echo "[bootstrap] Detected legacy symlink: $LEGACY_ZSHRC_TARGET -> $CURRENT_LINK"
    read -r -p "Replace it with a stow-managed link now? [y/N] " fix
    if [[ "${fix:-}" =~ ^[Yy]$ ]]; then
      rm -v "$LEGACY_ZSHRC_TARGET"
    else
      echo "[bootstrap] Leaving legacy symlink in place; stow will likely conflict."
    fi
  fi
fi

echo "[bootstrap] Dry run (preview):"
make dry-run TARGET="$TARGET" PACKAGES="$PACKAGES"

read -r -p "Apply these changes? [y/N] " ans
if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
  make stow TARGET="$TARGET" PACKAGES="$PACKAGES"
  echo "[bootstrap] Done."
else
  echo "[bootstrap] Aborted."
fi