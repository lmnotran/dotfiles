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
# oh-my-zsh plugins
#===============================================================================

# Which plugins would you like to load?
# Standard plugins can be found in $ZSH/plugins/
# Custom plugins may be added to $ZSH_CUSTOM/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(
    git
    fzf
    # Built-in
    ssh-agent
    colored-man-pages
    zsh-autosuggestions
    pyenv
    # fast-syntax-highlighting
    iterm2
)

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
