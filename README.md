# Dotfiles

Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).

## Quick Setup (New Machine)

**One-liner** (installs chezmoi, clones repo, applies dotfiles):

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply lmnotran/dotfiles
```

Or if you already have the repo cloned:

```bash
./script/setup
```

That's it! Restart your terminal and you're good to go.

## What Gets Installed

The `run_once_before_01-install-deps.sh` script automatically installs:

### Packages
- **Linux (apt):** `zsh`, `git`, `neovim`, `fzf`, `ripgrep`, `fd-find`, `tmux`, `htop`, `curl`, `wget`, `make`
- **Linux (brew):** `lazygit`, `pyenv`, `bitwarden-cli`
- **macOS (brew):** All of the above

### Tools (cloned on-demand)
- [antidote](https://github.com/mattmc3/antidote) — zsh plugin manager → `~/.local/share/antidote`
- [gpakosz/.tmux](https://github.com/gpakosz/.tmux) — tmux config framework → `~/.tmux`

### Managed Dotfiles
| File | Description |
|------|-------------|
| `~/.zshrc` | Zsh config (templated per-machine) |
| `~/.zsh_plugins.txt` | Antidote plugin list |
| `~/.config/zsh/` | Aliases, git overrides |
| `~/.config/nvim/` | Neovim config |
| `~/.gitconfig` | Git config |
| `~/.tmux.conf` | Tmux config (sources gpakosz/.tmux) |
| `~/.tmux.conf.local` | Tmux customizations |
| `~/.profile` | Pyenv for bash shells |
| `~/.spaceshiprc.zsh` | Spaceship prompt config |

## Common Commands

```bash
chezmoi diff              # Preview pending changes
chezmoi apply             # Apply changes
chezmoi edit ~/.zshrc     # Edit a managed file
chezmoi cd                # Jump to source directory
chezmoi update            # Pull latest and apply
```

## Adding New Dotfiles

```bash
chezmoi add ~/.some-config    # Add a file to chezmoi
chezmoi edit ~/.some-config   # Edit and apply
```

Files are stored in `chezmoi/` with special naming:
- `dot_` prefix → `.` (e.g., `dot_zshrc` → `.zshrc`)
- `.tmpl` suffix → Go template (for machine-specific config)
- `private_` prefix → 0600 permissions

## Machine-Specific Config

Machine-specific settings are handled via Go templates in `dot_zshrc.tmpl`:

```bash
{{- if eq .chezmoi.hostname "bigboi" }}
umask 002
{{- end }}

{{- if eq .chezmoi.os "darwin" }}
# macOS-specific
{{- end }}
```

Available variables: `.chezmoi.hostname`, `.chezmoi.os`, `.chezmoi.username`

## Secrets Management

Secrets are managed separately from dotfiles using [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/).

### Runtime Secrets (for Docker)

Docker compose files use `${VAR:?must be set}` pattern. Load secrets before running containers:

```bash
# Load secrets for a profile
secrets docker        # cloudflare, paperless, pihole, mariadb
secrets lego          # GHCR_TOKEN, GITHUB_TOKEN
secrets all           # everything

# Then run your containers
docker compose up -d
```

Available profiles: `cloudflare`, `paperless`, `pihole`, `mariadb`, `aviationstack`, `lego`, `docker`, `all`

### SSH/GPG Keys (one-time setup)

```bash
./script/setup-keys
```

Downloads SSH and GPG keys from Bitwarden vault attachments.

### How It Works

1. **BWS_ACCESS_TOKEN** — Stored in Bitwarden vault, fetched on first `secrets` call
2. **Secret UUIDs** — Stored in `script/load-secrets` (safe to commit)
3. **Actual secrets** — Fetched at runtime via `bws`, never stored locally

## Other Scripts

| Script | Description |
|--------|-------------|
| `script/setup-keys` | Download SSH/GPG keys from Bitwarden |
| `script/load-secrets` | Load secrets from Bitwarden Secrets Manager |
