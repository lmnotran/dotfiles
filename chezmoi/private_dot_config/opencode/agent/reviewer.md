---
description: Second-opinion review of a diff or PR by GPT-6.2 Sol, a different model family from the session's Claude. Read-only. Use it when Mason asks for a second opinion, or to cross-check a review that ran on Claude.
mode: subagent
model: github-copilot/gpt-6.2-sol#high
# Skills write scratch files to /tmp/opencode, and OpenCode's own scratch folder is
# $TMPDIR/opencode. macOS may check either path with /private in front.
permissions:
  - action: edit
    resource: "*"
    effect: deny
  - action: edit
    resource: "/tmp/opencode/**"
    effect: allow
  - action: edit
    resource: "/private/tmp/opencode/**"
    effect: allow
  - action: edit
    resource: "/var/folders/*/T/opencode/**"
    effect: allow
  - action: edit
    resource: "/private/var/folders/*/T/opencode/**"
    effect: allow
  - action: subagent
    resource: "*"
    effect: deny
---
