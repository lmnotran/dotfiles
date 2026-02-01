#
# Aliases
# (sorted alphabetically by command)
# (order should follow README)
# (in some cases force the alisas order to match README, like for example gke and gk)
#

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