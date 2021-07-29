#!/bin/zsh

REPO_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
export DOTFILES=$REPO_DIR
export DOTFILES_prev_DIR=$REPO_DIR/prev
source $REPO_DIR/utils/bash_utils.sh
source $REPO_DIR/utils/network.sh
source $REPO_DIR/prev/env.profile
source $REPO_DIR/prev/prev.profile
