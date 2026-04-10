# Custom aliases

# Unlock Bitwarden vault and export session
# Usage: bwunlock
bwunlock() {
    if ! command -v bw &>/dev/null; then
        echo "✗ bw CLI not installed" >&2
        return 1
    fi

    local status
    status="$(bw status 2>/dev/null | grep -o '"status":"[^"]*"' | cut -d'"' -f4)"

    if [[ "$status" == "unauthenticated" ]]; then
        echo "Not logged in. Logging in..."
        bw login || return 1
    fi

    export BW_SESSION="$(bw unlock --raw)" && echo "✓ Vault unlocked"
}

# Authenticate with Bitwarden Secrets Manager
# Usage: bwsauth
bwsauth() {
    if [[ -z "${BW_SESSION:-}" ]]; then
        echo "Bitwarden vault is locked. Unlocking..."
        bwunlock || return 1
    fi

    local bws_token
    bws_token="$(bw get password 'BWS Access Token')"
    if [[ -n "$bws_token" ]]; then
        export BWS_ACCESS_TOKEN="$bws_token"
        echo "✓ BWS authenticated"
    else
        echo "✗ Failed to get BWS Access Token from vault" >&2
        return 1
    fi
}

# Load secrets from Bitwarden Secrets Manager
# Usage: secrets <profile> [profile2] [profile3] ...
secrets() {
    # Unlock vault if needed
    if [[ -z "${BW_SESSION:-}" ]]; then
        echo "Bitwarden vault is locked. Unlocking..."
        bwunlock || return 1
    fi

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
