#!/bin/bash

# https://gitlab.dto.lego.com/-/user_settings/personal_access_tokens
export GITLAB_PERSONAL_ACCESS_TOKEN="REDACTED_GITLAB_TOKEN"
export CI_JOB_TOKEN="${GITLAB_PERSONAL_ACCESS_TOKEN}"

export GITHUB_TOKEN="REDACTED_GITHUB_PAT"
export GHCR_TOKEN="REDACTED_GHCR_TOKEN"