#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

repo_dir="$(dirname "$(realpath "$script_path")")"

plugins=(
    zsh-autosuggestions
    zsh-syntax-highlighting
)

source ${repo_dir}/utils/bash_utils.sh

for plugin in ${plugins[@]}; do
    plugin_repo=${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/${plugin}
    gitCloneOrPull $plugin_repo https://github.com/zsh-users/${plugin}
done

# Fix perms
# compaudit | xargs chmod g-w,o-w

if [[ "$OSTYPE" == "darwin"* ]]; then
    # Mac OSX

    # Install brew
    command -v brew || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    brew install coreutils grep fzf

    /opt/homebrew/opt/fzf/install

fi

if [ -f $ZSH/plugins/git/git.plugin.zsh ] && [ ! -f $ZSH/plugins/git/patched ]; then
    git -C $ZSH apply $repo_dir/patches/gs-alias.patch
    touch $ZSH/plugins/git/patched
fi