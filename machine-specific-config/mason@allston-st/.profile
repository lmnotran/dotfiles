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
export ARM_GCC_DIR="/Applications/ArmGNUToolchain/13.3.rel1/arm-none-eabi/"

#===============================================================================
# PATH modifications
#===============================================================================

# ARM GNU toolchain
export PATH="$PATH:$ARM_GCC_DIR/bin"

# Load brew
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv zsh)"

