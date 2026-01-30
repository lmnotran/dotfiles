#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# ─────────────────────────────────────────────────────────────────────────────
# Colors
# ─────────────────────────────────────────────────────────────────────────────

if [[ -t 1 ]]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
    BOLD='\033[1m'
    RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' CYAN='' BOLD='' RESET=''
fi

log()      { echo -e "${CYAN}[bootstrap]${RESET} $*"; }
log_step() { echo -e "${BOLD}${BLUE}==>${RESET} ${BOLD}$*${RESET}"; }
log_ok()   { echo -e "${GREEN}✓${RESET} $*"; }
log_warn() { echo -e "${YELLOW}⚠${RESET} $*"; }
log_err()  { echo -e "${RED}✗${RESET} $*" >&2; }

# ─────────────────────────────────────────────────────────────────────────────

log_step "Ensuring GNU Stow is installed"
if ! command -v stow >/dev/null 2>&1; then
  if [[ "$OSTYPE" == darwin* ]]; then
    if command -v brew >/dev/null 2>&1; then
      brew install stow
    else
      log_err "Homebrew not found; install it from https://brew.sh and re-run"
      exit 1
    fi
  else
    log_err "Please install GNU Stow using your package manager."
    exit 1
  fi
else
  log_ok "stow is installed"
fi

TARGET=${TARGET:-$HOME}
PACKAGES=${PACKAGES:-"zsh bin"}

# Fix legacy absolute symlink for ~/.zshrc pointing to repo root .zshrc
LEGACY_ZSHRC_TARGET="$TARGET/.zshrc"
if [[ -L "$LEGACY_ZSHRC_TARGET" ]]; then
  CURRENT_LINK="$(readlink "$LEGACY_ZSHRC_TARGET" || true)"
  if [[ "$CURRENT_LINK" == "$PWD/.zshrc" ]]; then
    log_warn "Detected legacy symlink: $LEGACY_ZSHRC_TARGET -> $CURRENT_LINK"
    read -r -p "Replace it with a stow-managed link now? [y/N] " fix
    if [[ "${fix:-}" =~ ^[Yy]$ ]]; then
      rm -v "$LEGACY_ZSHRC_TARGET"
    else
      log "Leaving legacy symlink in place; stow will likely conflict."
    fi
  fi
fi

log_step "Dry run (preview)"
make dry-run TARGET="$TARGET" PACKAGES="$PACKAGES"

read -r -p "Apply these changes? [y/N] " ans
if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
  make stow TARGET="$TARGET" PACKAGES="$PACKAGES"
  log_ok "Done!"
else
  log_warn "Aborted."
fi