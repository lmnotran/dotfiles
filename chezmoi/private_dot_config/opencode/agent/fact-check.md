---
description: Fact-checks a draft before Mason posts it, checking each claim against code, CI logs, and tickets. Read-only. Use it for write-like-mason's fact-check step.
mode: subagent
model: github-copilot/claude-opus-5.5#max
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
