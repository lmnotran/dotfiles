#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

repo_dir="$(dirname $(realpath $script_path))"

source ${repo_dir}/utils/bash_utils.sh

ln -s ${repo_dir}/.tmux.conf ~

gitCloneOrPull ~/.tmux/plugins/tpm https://github.com/tmux-plugins/tpm
