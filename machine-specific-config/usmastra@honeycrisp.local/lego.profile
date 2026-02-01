#!/bin/bash

# Tokens loaded from Bitwarden or environment
# Run: bw get item "Dev Tokens" | jq -r '.fields[] | "export \(.name)=\"\(.value)\""' | source /dev/stdin

export GITLAB_PERSONAL_ACCESS_TOKEN="${GITLAB_PERSONAL_ACCESS_TOKEN:-}"
export CI_JOB_TOKEN="${GITLAB_PERSONAL_ACCESS_TOKEN}"

export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
export GHCR_TOKEN="${GHCR_TOKEN:-}"