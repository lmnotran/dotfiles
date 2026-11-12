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

Restart your terminal after setup.

## What Gets Installed

The [chezmoi setup hook](chezmoi/run_once_before_01-install-deps.sh.tmpl) runs
[`script/install-deps`](script/install-deps) to install packages and tools.

### Packages

On Linux, packages are installed with apt and Homebrew extras. On macOS,
Homebrew installs the base packages and extras, and pip installs the Cocoa
bindings used by macOS tooling. See the package arrays in
[`script/install-deps`](script/install-deps) for the current lists.

### Tools

Setup clones these tools if they aren't installed:

| Tool | Purpose | Location |
|------|---------|----------|
| [antidote](https://github.com/mattmc3/antidote) | Zsh plugin manager | `~/.local/share/antidote` |
| [gpakosz/.tmux](https://github.com/gpakosz/.tmux) | Tmux config framework | `~/.tmux` |

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

Karabiner is managed with Stow under [`stow/karabiner/`](stow/karabiner/),
using the targets in [`Makefile`](Makefile).

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

Machine-specific settings are handled via Go templates, including
[`chezmoi/dot_zshrc.tmpl`](chezmoi/dot_zshrc.tmpl):

```bash
{{- if eq .chezmoi.hostname "bigboi" }}
umask 002
{{- end }}

{{- if eq .chezmoi.os "darwin" }}
# macOS-specific
{{- end }}
```

Available variables: `.chezmoi.hostname`, `.chezmoi.os`, `.chezmoi.username`

Work configuration is selected when the username starts with `usmastra` or
`username@hostname` appears in
[`chezmoi/.chezmoidata.toml`](chezmoi/.chezmoidata.toml).

### Work-only files

Anything that names the employer, its services or internal hosts lives in a
private repo, `lmnotran/work-dotfiles`. On work machines, `chezmoi apply`
clones it to `~/repos/work-dotfiles` and runs its `install`, which links its
helpers into `~/.local/bin`. The work Git email, the `script/setup-keys`
values and `~/.config/jira/env` come from it too.

The `jira-*` helpers and `alfred-jira` read `JIRA_BASE_URL`,
`JIRA_DEFAULT_PROJECT` and `JIRA_ACCOUNT_ID` from the environment or from
`~/.config/jira/env` (`KEY=value` lines). They authenticate with `~/.netrc`.

[`script/check-public`](script/check-public) keeps work-only words out of this
repo. It reads a deny list from the private repo, or from the
`PUBLIC_DENYLIST` secret in CI. On work machines, the `.githooks/` hooks run it
on each commit.

## Secrets Management

Secrets are managed separately from dotfiles using [Bitwarden Secrets Manager](https://bitwarden.com/products/secrets-manager/).

### Runtime Secrets

Load a profile into the current shell before running tools that need it:

```bash
# Load secrets for a profile
secrets docker        # cloudflare, paperless, pihole, mariadb
secrets work          # GHCR_TOKEN, GITHUB_TOKEN
secrets jira          # Jira credentials
secrets all           # everything
```

See [`script/load-secrets`](script/load-secrets) for all available profiles.

### SSH/GPG Keys (one-time setup)

```bash
./script/setup-keys
```

This generates SSH and GPG keys for the machine and uploads the public keys
to the matching GitHub account. Private keys stay on the machine.

### How It Works

1. `secrets` fetches `BWS_ACCESS_TOKEN` from the Bitwarden vault when needed.
2. `script/load-secrets` uses the secret UUIDs to fetch values with `bws`. UUIDs are references, so they're safe to commit.
3. `secrets` exports the values into the current shell. Keep those values out of Git.

## OpenChamber Service

OpenChamber is the web UI for OpenCode. On allston-st, it runs as the systemd
user service `openchamber.service`. Control it with `chamberctl`.

To install it on a Linux machine:

```bash
./script/install-openchamber
```

See [docs/openchamber.md](docs/openchamber.md) for what it installs, how to update OpenChamber, and gotchas.

## Other Scripts

### Tooling tests

Run the CLI helper tests without GitHub or Jira credentials:

```bash
uv run --with-requirements requirements-tooling-test.txt python -m pytest tests/tooling --disable-socket --strict-markers
```

The suite tests helpers in [`chezmoi/dot_local/bin/`](chezmoi/dot_local/bin/).
Tests use fake command responses or temporary directories. They don't push
commits, edit live issues, install dotfiles, or launch agents.

See [`tests/tooling/README.md`](tests/tooling/README.md) for coverage and gaps.
Type-check the Python helpers with
[`script/typecheck-helpers`](script/typecheck-helpers).

| Workflow | Checks |
|----------|--------|
| **Tooling tests** | Helper tests on Python 3.11 and 3.13, plus mypy type checks. Uploads JUnit results. |
| **Dotfiles CI** | Shell scripts, chezmoi apply, Zsh, Neovim, tmux, and the dependency installer's dry run. |
| **Public check** | Tracked files and new commits against the private deny list. Prints only where a match is. |

All workflows support manual runs. Their
[workflow files](.github/workflows/) define which changes trigger them.

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

| Script | Description |
|--------|-------------|
| `script/setup-keys` | Generate per-machine SSH/GPG keys and upload public keys to GitHub |
| `script/load-secrets` | Load secrets from Bitwarden Secrets Manager |
| `script/install-openchamber` | Install OpenChamber as the systemd user service `openchamber.service` |

## Devcontainer Setup

To automatically apply dotfiles when opening any VS Code devcontainer, add to your VS Code `settings.json`:

```json
...
  "dotfiles.repository": "lmnotran/dotfiles",
  "dotfiles.targetPath": "~/repos/dotfiles",
  "dotfiles.installCommand": "sh -c \"$(curl -fsLS get.chezmoi.io)\" -- init --source ~/repos/dotfiles --apply",
...
```

VS Code clones the repo once. Chezmoi applies dotfiles from that clone.
