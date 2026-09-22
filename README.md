# Dotfiles

Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).

## Quick Setup (New Machine)

**One-liner** (installs chezmoi, clones repo, applies dotfiles):

```bash
sh -c "$(curl -fsLS get.chezmoi.io)" -- init --apply lmnotran/dotfiles
```

Or if you already have the repo cloned:

```bash
./script/bootstrap
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

Generates per-machine SSH and GPG keys locally and uploads the public keys to the matching GitHub account. Private keys never leave the machine.

### How It Works

1. **BWS_ACCESS_TOKEN** — Stored in Bitwarden vault, fetched on first `secrets` call
2. **Secret UUIDs** — Stored in `script/load-secrets` (safe to commit)
3. **Actual secrets** — Fetched at runtime via `bws`, never stored locally

## Other Scripts

### Tooling tests

Run the managed CLI helper tests without GitHub/Jira credentials:

```bash
uv run --with-requirements requirements-tooling-test.txt python -m pytest tests/tooling --disable-socket --strict-markers
```

The suite covers all helpers under `chezmoi/dot_local/bin`: Actions log anchors
and timings, CI sampling, PR/review body editing, Jira rendering/payloads, context
nudges, and sandbox commands. External command boundaries are mocked or isolated
in disposable fixtures; tests do not push commits, edit live issues, install
dotfiles, or run interactive agents. See `tests/tooling/README.md` for coverage.

The **Tooling tests** workflow runs on Python 3.11 and 3.13 when helpers, tests,
test dependencies, or the workflow change. It also supports manual dispatch and
uploads JUnit results. The existing dotfiles deployment workflow remains separate.
This suite does not exercise machine bootstrap, secret loading, calendar
integrations, or the Docker services.

### Allure reports

Each tooling-test matrix job uploads `allure-results-<version>` and the generated
Allure 3 HTML as `allure-report-<version>`, including failed-test reports when
results exist. Python versions have separate reports to avoid treating matrix
runs as retries.

With uv and Node.js 24 installed:

```bash
uv run --with-requirements requirements-tooling-test.txt python -m pytest tests/tooling --disable-socket --alluredir=allure-results --clean-alluredir
npx --yes allure@3 generate allure-results --output allure-report --report-name dotfiles
uv run python -m http.server 8080 --bind 127.0.0.1 --directory allure-report
```

Use a fresh report output directory for each generation and browse
`http://127.0.0.1:8080/`. Reports currently contain one run, not persistent history.
Bao publishing is pending deployment access and the public/private access policy;
the planned route is `https://bao.segfault.rip/allure/dotfiles/<python-version>/`.
The existing SSH pattern lives in `bill-split/docs/deploying.md`; its GitHub secrets
are not shared with this repo. No server configuration is changed by this workflow.

| Script | Description |
|--------|-------------|
| `script/setup-keys` | Generate per-machine SSH/GPG keys and upload public keys to GitHub |
| `script/load-secrets` | Load secrets from Bitwarden Secrets Manager |

## Devcontainer Setup

To automatically apply dotfiles when opening any VS Code devcontainer, add to your VS Code `settings.json`:

```json
...
  "dotfiles.repository": "lmnotran/dotfiles",
  "dotfiles.targetPath": "~/repos/dotfiles",
  "dotfiles.installCommand": "sh -c \"$(curl -fsLS get.chezmoi.io)\" -- init --source ~/repos/dotfiles --apply",
...
```

This uses VS Code's built-in dotfiles support — it clones the repo once, then chezmoi uses that clone directly.
