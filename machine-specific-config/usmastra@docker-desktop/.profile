#!/bin/bash

if [[ -n ${BASH_SOURCE[0]} ]]; then
    script_path="${BASH_SOURCE[0]}"
else
    script_path="$0"
fi

script_dir="$(dirname "$(realpath "$script_path")")"

source "${script_dir}/lego.profile"

#===============================================================================
# constants
#===============================================================================
export TOOLCHAIN_DIR="~/toolchain"

#===============================================================================
# PATH modifications
#===============================================================================
