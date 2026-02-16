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
- **Always sign commits** — Use `git commit -S` for all commits
- **Re-sign after filter-repo** — After using `git filter-repo`, re-sign affected commits with `git rebase --committer-date-is-author-date --exec 'git commit --amend --no-edit -S' <base>`
- **Use conventional commits** — Format: `type(scope): description` (e.g., `docs:`, `fix:`, `refactor:`, `chore:`)
- **Prefer amending commits** — When fixing something related to the previous commit, use `git commit --amend` to keep history clean rather than creating fixup commits. Update the commit message if needed to reflect the newly added changes. Logically independent changes should always be separate commits.

## Repository Structure

### Current Setup (GNU Stow)
- `stow/` — Dotfiles packages managed via GNU Stow (symlinked to `$HOME`)
  - `zsh/`, `git/`, `nvim/`, `tmux/`
- `machine-specific-config/` — Per-machine configs sourced at runtime by hostname
- `script/` — Setup and utility scripts
- `docker/` — Docker compose configs for self-hosted services (not dotfiles)

### Chezmoi Setup
- `chezmoi/` — Dotfiles source directory (specified via `.chezmoiroot`)
- Uses Go templates for machine-specific config (`{{ .chezmoi.hostname }}`, etc.)
- `run_once_before_*` scripts delegate to `script/install-deps`
- One-liner setup: `sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply lmnotran/dotfiles`

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
# Setup new machine (one-liner)
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply lmnotran/dotfiles

# Update dotfiles
chezmoi update

# Preview changes
chezmoi diff

# Re-run install-deps manually
./script/install-deps
```
