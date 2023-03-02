#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

repo_dir="$(dirname $(realpath $script_path))"

source ${repo_dir}/utils/bash_utils.sh

TMUX_CONFIG_ROOT=${repo_dir}/.tmux

# Make sure submodule is initialized
git -C ${repo_dir} submodule update --init --recursive .tmux

ln -s -f ${TMUX_CONFIG_ROOT}/.tmux.conf ~/.tmux.conf

# Create host-specific dotfiles folder
mkdir -p ${repo_dir}/$(hostname)/

# Copy .tmux.conf.local into host-specific dotfiles and create a symlink in ~
cp ${TMUX_CONFIG_ROOT}/.tmux.conf.local ${repo_dir}/$(hostname)/.tmux.conf.local
ln -s -f ${repo_dir}/$(hostname)/.tmux.conf.local ~/.tmux.conf.local
