# If you come from bash you might have to change your $PATH.
# export PATH=$HOME/bin:/usr/local/bin:$PATH
export TERM="xterm-256color"
# Path to your oh-my-zsh installation.
export ZSH="${HOME}/.oh-my-zsh"

# Set name of the theme to load --- if set to "random", it will
# load a random theme each time oh-my-zsh is loaded, in which case,
# to know which specific one was loaded, run: echo $RANDOM_THEME
# See https://github.com/ohmyzsh/ohmyzsh/wiki/Themes
#ZSH_THEME="robbyrussell"

ZSH_THEME="agnoster"

#ZSH_THEME="powerlevel9k/powerlevel9k"

# Set list of themes to pick from when loading at random
# Setting this variable when ZSH_THEME=random will cause zsh to load
# a theme from this variable instead of looking in ~/.oh-my-zsh/themes/
# If set to an empty array, this variable will have no effect.
# ZSH_THEME_RANDOM_CANDIDATES=( "robbyrussell" "agnoster" )

# Uncomment the following line to use case-sensitive completion.
# CASE_SENSITIVE="true"

# Uncomment the following line to use hyphen-insensitive completion.
# Case-sensitive completion must be off. _ and - will be interchangeable.
# HYPHEN_INSENSITIVE="true"

# Uncomment the following line to disable bi-weekly auto-update checks.
# DISABLE_AUTO_UPDATE="true"

# Uncomment the following line to automatically update without prompting.
# DISABLE_UPDATE_PROMPT="true"

# Uncomment the following line to change how often to auto-update (in days).
# export UPDATE_ZSH_DAYS=13

# Uncomment the following line if pasting URLs and other text is messed up.
# DISABLE_MAGIC_FUNCTIONS=true

# Uncomment the following line to disable colors in ls.
# DISABLE_LS_COLORS="true"

# Uncomment the following line to disable auto-setting terminal title.
# DISABLE_AUTO_TITLE="true"

# Uncomment the following line to enable command auto-correction.
# ENABLE_CORRECTION="true"

# Uncomment the following line to display red dots whilst waiting for completion.
# COMPLETION_WAITING_DOTS="true"

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
# HIST_STAMPS="mm/dd/yyyy"

# Would you like to use another custom folder than $ZSH/custom?
# ZSH_CUSTOM=/path/to/new-custom-folder

# Which plugins would you like to load?
# Standard plugins can be found in ~/.oh-my-zsh/plugins/*
# Custom plugins may be added to ~/.oh-my-zsh/custom/plugins/
# Example format: plugins=(rails git textmate ruby lighthouse)
# Add wisely, as too many plugins slow down shell startup.
plugins=(iterm2 git ssh-agent tmux fzf )

source $ZSH/oh-my-zsh.sh

# User configuration

# export MANPATH="/usr/local/man:$MANPATH"

# You may need to manually set your language environment
# export LANG=en_US.UTF-8

# Preferred editor for local and remote sessions
# if [[ -n $SSH_CONNECTION ]]; then
#   export EDITOR='vim'
# else
#   export EDITOR='mvim'
# fi

# Compilation flags
# export ARCHFLAGS="-arch x86_64"

# Set personal aliases, overriding those provided by oh-my-zsh libs,
# plugins, and themes. Aliases can be placed here, though oh-my-zsh
# users are encouraged to define aliases within the ZSH_CUSTOM folder.
# For a full list of active aliases, run `alias`.
#
# Example aliases
# alias zshconfig="mate ~/.zshrc"
# alias ohmyzsh="mate ~/.oh-my-zsh"
export PATH="/usr/local/opt/llvm/bin:$PATH"
#export LDFLAGS='-L/usr/local/opt/llvm/lib -Wl,-rpath,/usr/local/opt/llvm/lib'
export PATH="/usr/local/opt/grep/libexec/gnubin:$PATH"

test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh" || true
#source ~/.power9krc

# ensure you compile 32bit binaries on a 64bit machine
export E_CC='gcc -m32a'
export E_CPP='g++ -m32'
export E_LD='ld -m32'
export JAVA_HOME=/Library/Java/JavaVirtualMachines/amazon-corretto-8.jdk/Contents/Home
export META_UTIL_PATH=/Users/matran/repos/super

#PATH and PYTHONPATH lead to the directory where your meta_util.py file is
export PATH=$PATH:$SUPER
export PYTHONPATH=$PYTHONPATH:$SUPER

# Add SEGGER JLink to path
export PATH=$PATH:/Applications/SEGGER/JLink/

# Add run-clang-tidy to path
export PATH=$PATH:/usr/local/Cellar/llvm@9/9.0.1_2/share/clang/

#export ZSH_TMUX_ITERM2=true
export ZSH_TMUX_UNICODE=true

# UC CLI
export JAVA11_HOME=/Library/Java/JavaVirtualMachines/amazon-corretto-11.jdk/Contents/Home/
export PATH=$PATH:/Users/matran/repos/sl/uc_cli_$(hostname)

export TOOLCHAIN_DIR_OSX=/usr/local/Cellar/arm-none-eabi-gcc/9-2019-q4-major
export ARM_GCC_DIR=/usr/local/Cellar/arm-none-eabi-gcc/9-2019-q4-major
export ARM_GCC_DIR_OSX=/usr/local/Cellar/arm-none-eabi-gcc/9-2019-q4-major

source ~/.bash_profile

export PATH=$PATH:/Applications/Commander.app/Contents/MacOS/
function gi() { curl -sLw n https://www.toptal.com/developers/gitignore/api/$@ ;}

export SUPER=~/repos/sl/super
export OPENTHREAD_REPO_PATH=~/repos/openthread
export LMNOTRAN_DOTFILES=~/repos/dotfiles
source $LMNOTRAN_DOTFILES/lmnotran.profile
export USERID=`id -u $USER`

# export PATH="/usr/local/opt/python@3.9/Frameworks/Python.framework/Versions/3.9/bin:$PATH"

export TCM_SIMPLICITYCOMMANDER=`which commander`
export PYENV_ROOT="$HOME/.pyenv"
export PATH="/usr/local/Cellar/m4/1.4.18/bin:$PATH"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
export DOCKER_BUILDKIT=0
