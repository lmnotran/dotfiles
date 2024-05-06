#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi
script_dir=$(dirname "${script_path}")

if command -v date > /dev/null; then
    DATE=date
elif command -v gdate > /dev/null; then
    DATE=gdata
fi
REPO_DIR="$(git -C ${script_dir} rev-parse --show-toplevel)"

export DOTFILES=$REPO_DIR
source $REPO_DIR/utils/bash_utils.sh
source $REPO_DIR/utils/network.sh
source $REPO_DIR/utils/pushover.sh
