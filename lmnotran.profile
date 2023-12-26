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
                                                                                timeraaaaa=$(($($DATE +%s%N)/1000000))
REPO_DIR="$(git -C ${script_dir} rev-parse --show-toplevel)"
                                                                                nowaaaaa=$(($($DATE +%s%N)/1000000))
                                                                                elapsedaaaaa=$(($nowaaaaa-$timeraaaaa))
                                                                                # echo $elapsedaaaaa":" REPO_DIR

export DOTFILES=$REPO_DIR
                                                                                timeraaaaa=$(($($DATE +%s%N)/1000000))
source $REPO_DIR/utils/bash_utils.sh
                                                                                nowaaaaa=$(($($DATE +%s%N)/1000000))
                                                                                elapsedaaaaa=$(($nowaaaaa-$timeraaaaa))
                                                                                # echo $elapsedaaaaa":" source $REPO_DIR/utils/bash_utils.sh
                                                                                timeraaaaa=$(($($DATE +%s%N)/1000000))
source $REPO_DIR/utils/network.sh
                                                                                nowaaaaa=$(($($DATE +%s%N)/1000000))
                                                                                elapsedaaaaa=$(($nowaaaaa-$timeraaaaa))
                                                                                # echo $elapsedaaaaa":" source $REPO_DIR/utils/network.sh
                                                                                timeraaaaa=$(($($DATE +%s%N)/1000000))
source $REPO_DIR/utils/pushover.sh
                                                                                nowaaaaa=$(($($DATE +%s%N)/1000000))
                                                                                elapsedaaaaa=$(($nowaaaaa-$timeraaaaa))
                                                                                # echo $elapsedaaaaa":" source $REPO_DIR/utils/pushover.sh
