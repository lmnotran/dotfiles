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
