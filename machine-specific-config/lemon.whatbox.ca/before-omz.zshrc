#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

script_dir="$(dirname "$(realpath "$script_path")")"

source "${script_dir}/.profile"

# export PATH="/opt/homebrew/bin:$PATH"

add_to_path=(
    "${HOME}/.local/bin"
)

for p in ${add_to_path[@]}; do
    if [ ! -d "$p" ]; then
    #     echo "Skipping ${p}"
        continue
    fi
    export PATH="${p}:${PATH}"
done

# Initialize Brew
eval "$("${BREW_PREFIX}"/bin/brew shellenv)"