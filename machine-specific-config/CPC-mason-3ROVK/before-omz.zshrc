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

# Add local bin to PATH
add_to_path=(
    "$HOME/.local/bin"
)
for p in ${add_to_path[@]}; do
    # Skip if the directory does not exist
    if [ ! -d "$p" ]; then
        continue
    fi
    export PATH="${p}:${PATH}"
done
