#!/bin/bash

# https://gitlab.dto.lego.com/-/user_settings/personal_access_tokens
export GITLAB_PERSONAL_ACCESS_TOKEN="REDACTED_GITLAB_TOKEN"
export CI_JOB_TOKEN="${GITLAB_PERSONAL_ACCESS_TOKEN}"
