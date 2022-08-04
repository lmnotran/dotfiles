#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

script_dir="$(dirname $(realpath $script_path))"
repo_dir="$(dirname $script_dir)"

ln -s ${repo_dir}/.tmux.conf ~

git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
