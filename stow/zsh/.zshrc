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
MACHINE_BASE_DIR=$DOTFILES/machine-specific-config/$(whoami)@$(hostname -f)
MACHINE_ENV=$MACHINE_BASE_DIR/.env
[[ -f $MACHINE_ENV ]] && source $MACHINE_ENV

MACHINE_BEFORE_OMZ_ZSHRC=$MACHINE_BASE_DIR/before-omz.zshrc
[[ -f $MACHINE_BEFORE_OMZ_ZSHRC ]] && source $MACHINE_BEFORE_OMZ_ZSHRC

# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH
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
# Use VS Code only inside VS Code's integrated terminal; else fall back to nvim/vi
if [[ "$TERM_PROGRAM" == "vscode" || -n "$VSCODE_PID" || -n "$VSCODE_GIT_IPC_HANDLE" ]]; then
  if command -v code >/dev/null 2>&1; then
    export EDITOR="code --wait --reuse-window"
  else
    export EDITOR="nvim"
  fi
else
  if command -v nvim >/dev/null 2>&1; then
    export EDITOR="nvim"
  else
    export EDITOR="vi"
  fi
fi
export VISUAL="$EDITOR"
export GIT_EDITOR="$EDITOR"

source $HOME/.config/zsh/git-overrides.zsh
source $HOME/.config/zsh/aliases.zsh

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

