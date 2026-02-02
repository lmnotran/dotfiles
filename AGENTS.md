# AI Agent Guidelines

Context and rules for AI assistants working on this repository.

## Critical Rules

### Git Operations
- **NEVER force push without explicit user confirmation** — Always show the command and wait for approval before running:
  - `git push --force` / `git push -f`
  - `git push --force-with-lease`
  - `git filter-repo` / `git filter-branch`
  - Any history-rewriting operations
- **NEVER commit secrets** — Use environment variables or Bitwarden Secrets Manager

## Repository Structure

### Current Setup (GNU Stow)
- `stow/` — Dotfiles packages managed via GNU Stow (symlinked to `$HOME`)
  - `zsh/`, `git/`, `nvim/`, `tmux/`
- `machine-specific-config/` — Per-machine configs sourced at runtime by hostname
- `script/` — Setup and utility scripts
- `docker/` — Docker compose configs for self-hosted services (not dotfiles)

### Chezmoi Migration (WIP)
- `chezmoi/` — Experimental chezmoi migration on `feature/chezmoi-migration` branch
- Uses Go templates for machine-specific config (`{{ .chezmoi.hostname }}`, etc.)
- `run_once_before_*` scripts for dependency installation

## Secrets Management

- Secrets are stored in **Bitwarden Secrets Manager**
- `script/load-secrets` fetches secrets by UUID and exports them as env vars
- The UUIDs in `load-secrets` are safe to commit (they're references, not values)
- Docker compose files use `${VAR:?must be set}` pattern

## User Preferences

- Owner: Mason Tran
- Primary machines: allston-st (Linux), various macOS and Linux hosts
- Work username prefix: `usmastra`
- Shell: zsh with antidote plugin manager
- Editor: neovim (or VS Code in VS Code terminal)

### Maintenance Philosophy
- **Minimize maintenance overhead** — This is a personal dotfiles repo, not production infrastructure
- **Avoid version pinning** — Use latest stable versions of tools (chezmoi, neovim, etc.) rather than pinning specific versions
- **No Dependabot/Renovate** — Not worth the noise for a single-user repo
- **Prefer simplicity** — Choose straightforward solutions over clever abstractions

## Common Tasks

```bash
# Stow dotfiles
make stow

# Preview stow changes
make dry-run

# Setup new machine (current)
./script/setup

# Setup new machine (chezmoi - WIP)
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply lmnotran/dotfiles
```
