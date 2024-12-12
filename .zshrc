zmodload zsh/zprof

# Check if ~/.zshrc is a symlink

if [[ -L "${HOME}/.zshrc" ]]; then
    # If it is, resolve the symlink
    DOTFILES="$(dirname $(readlink -f "${HOME}/.zshrc"))"
else
    # Otherwise, assume it's in the same directory as this file
    DOTFILES="$(dirname $0)"
fi

export DOTFILES

#===============================================================================
# pyenv
#===============================================================================
# This needs to happen before the pyenv plugin is sourced
export PYENV_ROOT="$HOME/.pyenv"
command -v pyenv >/dev/null || export PATH="$PYENV_ROOT/bin:$PATH"
command -v pyenv >/dev/null && eval "$(pyenv init -)"

#===============================================================================
# Source machine-specific-configs (before oh-my-zsh is sourced)
#===============================================================================
MACHINE_ENV=$DOTFILES/machine-specific-config/$(hostname)/.env
[ -f $MACHINE_ENV ] && source $MACHINE_ENV

MACHINE_BEFORE_OMZ_ZSHRC=$DOTFILES/machine-specific-config/$(hostname)/before-omz.zshrc
[ -f $MACHINE_BEFORE_OMZ_ZSHRC ] && source $MACHINE_BEFORE_OMZ_ZSHRC

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
# antidote
#===============================================================================
source $DOTFILES/.antidote/antidote.zsh

antidote load

#===============================================================================
# User configuration
#===============================================================================
# Preferred editor
export EDITOR='nvim'

source $DOTFILES/git.plugin.overrides.zsh

export GPG_TTY=$(tty)

export ZSH_TMUX_UNICODE=true
export GO111MODULE=on

# Source machine-specific-configs
MACHINE_AFTER_OMZ_ZSHRC=$DOTFILES/machine-specific-config/$(hostname)/after-omz.zshrc
[ -f $MACHINE_AFTER_OMZ_ZSHRC ] && source $MACHINE_AFTER_OMZ_ZSHRC

# Work user
MACHINE_LEGO_ZSHRC=$DOTFILES/machine-specific-config/$(hostname)/lego.zshrc
[[ "$(whoami)" == "usmastra"* ]] && [ -f $MACHINE_LEGO_ZSHRC ] && source $MACHINE_LEGO_ZSHRC

# Uncomment the following line to get zprof output
# zprof