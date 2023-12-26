#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

script_dir="$(dirname "$(realpath "$script_path")")"

source "${script_dir}/.profile"

# From nrfutil completion install
[[ -r "${HOME}/.nrfutil/share/nrfutil-completion/scripts/zsh/setup.zsh" ]] && . "${HOME}/.nrfutil/share/nrfutil-completion/scripts/zsh/setup.zsh"

# export PATH="/opt/homebrew/bin:$PATH"

# add_to_path=(
#     "/home/$USER/.local/bin"
#     "/usr"
#     "/usr/local"
#     "/opt/homebrew/opt/binutils/bin"
# )
# for p in ${add_to_path[@]}; do
#     if [ ! -d "$p" ]; then
#     #     echo "Skipping ${p}"
#         continue
#     fi
#     export PATH="${p}:${PATH}"
# done

#===============================================================================
# Mac OSX
#===============================================================================

# iTerm2 integration
test -e "${HOME}/.iterm2_shell_integration.zsh" && source "${HOME}/.iterm2_shell_integration.zsh" || true

# # use GNU grep
export PATH="/opt/homebrew/opt/grep/libexec/gnubin:$PATH"
# export PATH="/usr/local/opt/grep/libexec/gnubin:$PATH"