#!/bin/bash


if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

script_dir="$(dirname "$(realpath "$script_path")")"
repo_dir="$(dirname "$script_dir")"

if test -n "$ZSH_VERSION"; then
  PROFILE_SHELL=zsh
elif test -n "$BASH_VERSION"; then
  PROFILE_SHELL=bash
fi

echo "(script_path) = $script_path"
echo "(PROFILE_SHELL) = $PROFILE_SHELL"

echo "(BASH_SOURCE) = $BASH_SOURCE"
echo "(0) = $0"
echo "(1) = $1"
echo "(2) = $2"
echo "(3) = $3"
echo "(4) = $4"
echo "(0) = $0"
echo "(pwd) = $(pwd)"
echo "script_dir = $script_dir"
echo "repo_dir = $repo_dir"