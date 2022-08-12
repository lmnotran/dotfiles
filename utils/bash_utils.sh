#!/bin/bash

function contains() {
    list=$1
    x=$2
    [[ $list =~ (^|[[:space:]])$x($|[[:space:]]) ]] && exit 0 || exit 1
}

function gitCloneOrPull() {
    local repo_dir=$1
    local repo_url=${2:-}
    if [ ! -d $repo_dir ]; then
        git clone $repo_url $repo_dir
    else
        echo "'${repo_dir}' exists. Pulling..."
        git -C $repo_dir pull
    fi
}