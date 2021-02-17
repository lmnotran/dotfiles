#!/bin/zsh

REPO_DIR=$(dirname "$0")
DOTFILES_SILABS_DIR=$REPO_DIR/silabs
source $REPO_DIR/utils/bash_utils.sh
source $REPO_DIR/utils/network.sh
source $REPO_DIR/silabs/env.profile
source $REPO_DIR/silabs/silabs.profile
