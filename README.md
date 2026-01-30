# Dotfiles

Personal dotfiles managed with [GNU Stow](https://www.gnu.org/software/stow/).

## Quick Setup (New Machine)

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/dotfiles.git ~/repos/dotfiles
cd ~/repos/dotfiles

# Run setup (installs deps, stows configs, sets zsh as default shell)
./script/setup
```

That's it! Restart your terminal and you're good to go.

## What Gets Installed

### Packages (via apt on Linux, brew on macOS)
- `zsh`, `git`, `stow`, `fzf`, `htop`, `curl`, `wget`, `make`
- `lazygit`, `pyenv` (via brew on all platforms)

### Stowed Configs
| Package | What it configures |
|---------|-------------------|
| `zsh`   | `.zshrc`, zsh plugins (antidote) |
| `bin`   | Personal scripts in `~/bin` |
| `git`   | `.gitconfig` |
| `nvim`  | Neovim config |
| `tmux`  | `.tmux.conf` (sources gpakosz/.tmux submodule) |

## Manual Commands

```bash
# Preview what setup would do
./script/setup --dry-run

# Just install dependencies
./script/install-deps

# Just stow configs
make stow PACKAGES="zsh bin git nvim tmux"

# Unstow (remove symlinks)
make unstow PACKAGES="zsh"

# See all make targets
make help
```

## Adding New Configs

1. Create a folder under `stow/` (e.g., `stow/tmux/`)
2. Mirror the home directory structure inside it:
   ```
   stow/tmux/.tmux.conf        → ~/.tmux.conf
   stow/tmux/.config/tmux/...  → ~/.config/tmux/...
   ```
3. Add the package name to `PACKAGES` in `script/setup`
4. Run `make stow PACKAGES="tmux"`

## Machine-Specific Config

Machine-specific zsh configs live in `machine-specific-config/<hostname>/`:
- `before-omz.zshrc` - Sourced before plugins
- `after-omz.zshrc` - Sourced after plugins

These are automatically loaded based on `$HOST`.
