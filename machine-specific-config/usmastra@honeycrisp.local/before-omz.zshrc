#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

script_dir="$(dirname "$(realpath "$script_path")")"

source "${script_dir}/.profile"

export BREW_PREFIX="${HOME}/repos/brew/"
export PATH="${BREW_PREFIX}/bin:$PATH"

add_to_path=(
    "${HOME}/.local/bin"
    "${BREW_PREFIX}/opt/binutils/bin"
)
for p in ${add_to_path[@]}; do
    if [ ! -d "$p" ]; then
    #     echo "Skipping ${p}"
        continue
    fi
    export PATH="${p}:${PATH}"
done

#===============================================================================
# Mac OSX
#===============================================================================

# iTerm2 integration
test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh" || true

export PATH="/opt/homebrew/opt/grep/libexec/gnubin:$PATH"