# Custom aliases

# Load secrets from Bitwarden Secrets Manager
# Usage: secrets <profile> [profile2] [profile3] ...
secrets() {
    local output
    for profile in "$@"; do
        output="$(~/repos/dotfiles/script/load-secrets "$profile")" || return 1
        eval "$output"
    done
}

#===============================================================================
# Git overrides
#===============================================================================

# Override OMZ's gpristine alias with an interactive version
if whence -w gpristine | grep "alias" > /dev/null; then
    unalias gpristine
fi

function gpristine()
{
    echo ">>> git status"
    git status
    echo

    # Ask if the user wants to proceed with the reset
    read -q "REPLY?Do you want to proceed with the reset? (y/n) "
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        git reset --hard
    fi
    echo

    # Dry-run a "git clean" and prompt if the user wants to proceed with the clean
    cmd="git clean -dx  \
            -e .vscode/ \
            -e .devcontainer/ \
    "
    echo ">>> "$cmd
    output=$(eval $cmd -n)
    if [[ $output ]]; then
        echo
        read -q "REPLY?Do you want to proceed with the clean? (y/n) "
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]
        then
            eval $cmd -f
        fi
    else
        echo "Nothing to clean"
    fi

}

alias gs='git status'
alias gsu='git submodule update'
