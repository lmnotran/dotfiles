# Managed via GNU Stow (package: zsh)
# This file was migrated from the repo root `.zshrc` and now computes DOTFILES
# based on its own location under `stow/zsh/.zshrc`.

setopt EXTENDED_GLOB

# Resolve absolute path to this file even when sourced
local __this_file=${(%):-%N}
local __this_path=${__this_file:A}

# Repo directory: .../dotfiles (this file lives at dotfiles/stow/zsh/.zshrc)
local DOTFILES_DIR=${__this_path:h:h:h}
export DOTFILES=$DOTFILES_DIR

# ---------------------------------------------------------------------------
# Begin: original configuration migrated from repo root .zshrc
# ---------------------------------------------------------------------------

# zmodload zsh/zprof


#===============================================================================
# pyenv
#===============================================================================
# pyenv must be before plugins
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
command -v pyenv >/dev/null && eval "$(pyenv init -)"

#===============================================================================
# Source machine-specific-configs (before plugin manager is sourced)
#===============================================================================
MACHINE_ENV=$DOTFILES/machine-specific-config/$(hostname)/.env
[[ -f $MACHINE_ENV ]] && source $MACHINE_ENV

MACHINE_BEFORE_OMZ_ZSHRC=$DOTFILES/machine-specific-config/$(hostname)/before-omz.zshrc
[[ -f $MACHINE_BEFORE_OMZ_ZSHRC ]] && source $MACHINE_BEFORE_OMZ_ZSHRC

export TERM="xterm-256color"

#===============================================================================
# oh-my-zsh configuration
#===============================================================================
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Settings for available settings

# Uncomment the following line to display red dots whilst waiting for completion.
COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
HIST_STAMPS="yyyy-mm-dd"


#===============================================================================
# antidote plugin manager
#===============================================================================
if [[ -r $DOTFILES/.antidote/antidote.zsh ]]; then
  source $DOTFILES/.antidote/antidote.zsh
  antidote load
fi


#===============================================================================
# User configuration
#===============================================================================
# Preferred editor
#   If inside of vscode, use code, else check for nvim, else vim
if [[ "$TERM_PROGRAM" == "vscode" ]]; then
    export VISUAL='code --wait --reuse-window'
elif command -v nvim >/dev/null; then
    export VISUAL='nvim'
else
    export VISUAL='vim'
fi
export EDITOR="$VISUAL"

source $DOTFILES/git.plugin.overrides.zsh

export GPG_TTY=$(tty)
export ZSH_TMUX_UNICODE=true
export GO111MODULE=on

# Source machine-specific-configs
MACHINE_AFTER_OMZ_ZSHRC=$DOTFILES/machine-specific-config/$(hostname)/after-omz.zshrc
[[ -f $MACHINE_AFTER_OMZ_ZSHRC ]] && source $MACHINE_AFTER_OMZ_ZSHRC

# Work user
MACHINE_LEGO_ZSHRC=$DOTFILES/machine-specific-config/$(hostname)/lego.zshrc
[[ "$(whoami)" == "usmastra"* ]] && [[ -f $MACHINE_LEGO_ZSHRC ]] && source $MACHINE_LEGO_ZSHRC

# Optional: local overrides outside of git
[[ -r $HOME/.zshrc.local ]] && source $HOME/.zshrc.local

# zprof diagnostics
# zprof

# ---------------------------------------------------------------------------
# End: original configuration
# ---------------------------------------------------------------------------