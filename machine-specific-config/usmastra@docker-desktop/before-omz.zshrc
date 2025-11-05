#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

script_dir="$(dirname "$(realpath "$script_path")")"

source "${script_dir}/.profile"

# Add Homebrew to PATH
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"

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
