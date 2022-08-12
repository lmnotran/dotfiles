#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

REPO_DIR="$(dirname "$(realpath "$script_path")")"
# echo REPO_DIR = "${REPO_DIR}"

export DOTFILES=$REPO_DIR
source $REPO_DIR/utils/bash_utils.sh
source $REPO_DIR/utils/network.sh
source $REPO_DIR/utils/pushover.sh
