# Stow-managed dotfiles

This repo uses GNU Stow to manage symlinks for your dotfiles. Packages live in `stow/<pkg>` with the directory layout mirroring your `$HOME`.

Contents:
- `stow/zsh/.zshrc` – minimal bootstrap that sources repo config and host-specific files.
- `stow/bin/.local/bin/dotfiles` – helper to cd into this repo.
- `Makefile` – easy stow/unstow/dry-run targets.
- `script/bootstrap-stow.sh` – install stow (macOS Homebrew) and apply packages.

Quickstart:
1. Preview what would change:
   - make dry-run
2. Apply zsh and bin packages:
   - make stow PACKAGES="zsh bin"
3. Unstow if needed:
   - make unstow PACKAGES="zsh bin"

Notes:
- To adopt existing files in $HOME into the repo, use `make restow` (uses `stow --adopt`). Review git changes afterward.
- Host-specific files can be placed under `machine-specific-config/<hostname>/before-omz.zshrc` and `after-omz.zshrc`.