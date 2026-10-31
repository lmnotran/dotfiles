# AI Agent Guidelines

Context and rules for AI assistants working on this repository.

## Critical Rules

### Git Operations
- **NEVER force push without explicit user confirmation.** Show the command and wait for approval before running:
  - `git push --force` / `git push -f`
  - `git push --force-with-lease`
  - `git filter-repo` / `git filter-branch`
  - Any history-rewriting operations
- **NEVER commit secrets.** Use environment variables or Bitwarden Secrets Manager.
- **Skip signing on commits you make.** Use `git commit --no-gpg-sign` and `git -c commit.gpgsign=false rebase …` for rebases.
- Signing prompts garble the terminal during agent sessions. Mason signs his own commits.
- **Leave re-signing to Mason.** `git filter-repo` and rebases drop signatures. Tell Mason which commits lost theirs.
- **Use conventional commits:** `type(scope): description`, such as `docs:`, `fix:`, `refactor:`, or `chore:`.
- **Prefer amending commits** when fixing something related to the previous commit. Use `git commit --amend` instead of a fixup commit.
- Update the commit message to cover added changes. Use separate commits for independent changes.

## Repository Structure

### Current Setup (chezmoi)
- `chezmoi/` holds managed dotfiles and CLI helpers. `.chezmoiroot` selects this subdirectory.
- Edit managed files in `chezmoi/`, not their installed copies in `$HOME`
- Go templates handle machine-specific settings. `chezmoi/.chezmoidata.toml` holds shared template data.
- `script/bootstrap` applies chezmoi from an existing clone.
- `run_once_before_01-install-deps.sh.tmpl` runs `script/install-deps`.
- `script/` holds setup and utility scripts.
- Read `tests/tooling/README.md` when changing CLI helpers. Their offline tests live in `tests/tooling/`.
- `.github/workflows/` holds dotfiles validation and tooling-test CI.
- Read `docs/openchamber.md` when installing, updating, or troubleshooting OpenChamber.
- `stow/karabiner/` holds Karabiner config. Use the Stow targets in `Makefile` to apply it.

## Secrets Management

- Secrets are stored in **Bitwarden Secrets Manager**
- `script/load-secrets` fetches secrets by UUID and prints shell export statements
- The UUIDs in `load-secrets` are safe to commit (they're references, not values)
- The `secrets` shell function evaluates the exports from `script/load-secrets`

## User Preferences

- Owner: Mason Tran
- Primary machines: allston-st (Linux), various macOS and Linux hosts
- Work detection: username starts with `usmastra` or `username@hostname` is listed in `chezmoi/.chezmoidata.toml`
- Shell: zsh with antidote plugin manager
- Editor: neovim (or VS Code in VS Code terminal)

### Maintenance Philosophy
- **Minimize maintenance overhead.** This is a personal dotfiles repo.
- **Avoid version pinning.** Use the latest stable tools.
- **No Dependabot or Renovate.** The notifications aren't worth it for a single-user repo.
- **Prefer simplicity.** Choose straightforward solutions over clever abstractions.

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

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues via `gh`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, and `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Use the single-context layout with a root `GLOSSARY.md` and `docs/adr/`. See `docs/agents/domain.md`.
