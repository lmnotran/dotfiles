zmodload zsh/zprof

#===============================================================================
# Lmno dotfiles
#===============================================================================
# TODO: Make this detect where the dotfiles actually are by following the symlink
export LMNOTRAN_DOTFILES=~/repos/dotfiles
source $LMNOTRAN_DOTFILES/lmnotran.profile

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

MACHINE_BEFORE_OMZ_ZSHRC=$LMNOTRAN_DOTFILES/machine-specific-config/$(hostname)/before-omz.zshrc
[ -f $MACHINE_BEFORE_OMZ_ZSHRC ] && source $MACHINE_BEFORE_OMZ_ZSHRC

export TERM="xterm-256color"

#===============================================================================
# oh-my-zsh configuration
#===============================================================================
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Settings for available settings

# Path to your oh-my-zsh installation.
export ZSH="${HOME}/.oh-my-zsh"

# Set name of the theme to load
#   See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
export ZSH_THEME="spaceship"
export SPACESHIP_CONFIG="$DOTFILES/.spaceship.zsh"

# Uncomment the following line to display red dots whilst waiting for completion.
COMPLETION_WAITING_DOTS="true"

# Uncomment the following line if you want to disable marking untracked files
# under VCS as dirty. This makes repository status check for large repositories
# much, much faster.
# DISABLE_UNTRACKED_FILES_DIRTY="true"

# Uncomment the following line if you want to change the command execution time
# stamp shown in the history command output.
# You can set one of the optional three formats:
# "mm/dd/yyyy"|"dd.mm.yyyy"|"yyyy-mm-dd"
# or set a custom format using the strftime function format specifications,
# see 'man strftime' for details.
HIST_STAMPS="yyyy-mm-dd"


#===============================================================================
# antigen
#===============================================================================
ANTIGEN_LOG=$DOTFILES/antigen.log
source $DOTFILES/antigen.zsh

# Load oh-my-zsh library.
antigen use oh-my-zsh

# Load bundles from the default repo (oh-my-zsh).
antigen bundle autojump
antigen bundle command-not-found
antigen bundle docker
antigen bundle git
antigen bundle pip

# Load bundles from external repos.
antigen bundle zsh-users/zsh-autosuggestions
antigen bundle zdharma-continuum/fast-syntax-highlighting

# Load the theme.
antigen theme spaceship

# Tell Antigen that you're done.
antigen apply


#===============================================================================
# oh-my-zsh plugins
#===============================================================================

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(
    # Built-in
    ssh-agent
    colored-man-pages
)

plugins_to_check=(
    git
    fzf
    pyenv
)
# Check if the commands in plugins_to_check exist and if they do, append them to the list of plugins
for plugin in ${plugins_to_check[@]}; do
    command -v $plugin >/dev/null && plugins+=($plugin)
done

# Add any machine-specific plugins
machine_specific_plugins=$LMNOTRAN_DOTFILES/machine-specific-config/$(hostname)/plugins.zsh
[ -f $machine_specific_plugins ] && source $machine_specific_plugins

bindkey '^ ' autosuggest-accept

# Source oh-my-zsh
[ -f $ZSH/oh-my-zsh.sh ] && source $ZSH/oh-my-zsh.sh


#===============================================================================
# User configuration
#===============================================================================
# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor
export EDITOR='nvim'

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"
#
source $DOTFILES/git.plugin.overrides.zsh

export QT_GRAPHICSSYSTEM=native
export GPG_TTY=$(tty)

#export ZSH_TMUX_ITERM2=true
export ZSH_TMUX_UNICODE=true
export GO111MODULE=on

# Source machine-specific-configs
MACHINE_AFTER_OMZ_ZSHRC=$LMNOTRAN_DOTFILES/machine-specific-config/$(hostname)/after-omz.zshrc
[ -f $MACHINE_AFTER_OMZ_ZSHRC ] && source $MACHINE_AFTER_OMZ_ZSHRC

# Work user
MACHINE_LEGO_ZSHRC=$LMNOTRAN_DOTFILES/machine-specific-config/$(hostname)/lego.zshrc
[[ "$(whoami)" == "usmastra"* ]] && [ -f $MACHINE_LEGO_ZSHRC ] && source $MACHINE_LEGO_ZSHRC
