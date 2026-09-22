# Offline tooling tests

From the dotfiles root:

```sh
uv run --with-requirements requirements-tooling-test.txt python -m pytest tests/tooling --disable-socket --strict-markers
```

Dependencies are pytest and pytest-socket. CI tests Python 3.11 and 3.13.
Installing dependencies may need network access on the first run; the
tests themselves require no credentials or network. Sandbox tests also require
Bash and Git on the local PATH (`/usr/bin:/bin` in the child environment).

## Isolation

Each test gets temporary HOME, cache, config, working and temporary directories.
Extensionless Python helpers load through `SourceFileLoader`; module registration
supports dataclasses. Real subprocess entry points and Python socket connections
are blocked by default. Tests explicitly replace narrow command/API boundaries.
Sandbox alone runs the actual Bash CLI with a sanitized environment, disabled
system/global Git configuration, and a repository-discovery ceiling inside its
temporary directory. These cases perform no Git mutations. No test reads secret
files, authenticates, contacts GitHub/Jira, launches agents, or edits a user's repo.

## Coverage

| Helper | Behavioral coverage |
|---|---|
| `gh-pr-body` | Nested heading boundaries, last-section footer preservation, replacement footer precedence, missing sections, normalized verified writes and mismatch rejection |
| `gh-review-body` | Concatenated pagination JSON, latest authored nonempty review, explicit IDs, missing matches, PUT payload, verified writes/mismatch, stdin CLI editing |
| `gh-run-timings` | Duration units/rounding, attempt endpoint/pagination, JSON filtering/sorting/top, timestamp arithmetic, skipped-step table rows, wall-clock display, empty results |
| `ci-sample` | Protected/detached branch refusal, cleanup dry-run, missing safe reset target, summary files with missing values/outlier median, job arithmetic, workflow resolution/ambiguity |
| `jira-put-description` | Invalid JSON/non-document rejection before subprocess, description envelope, PUT endpoint, 204 success and non-204 failure |
| `jira-view` | ADF heading/list nesting/code/quote/rule/inline marks/cards/mentions/breaks, absent descriptions, raw JSON/ADF modes, non-JSON API errors |
| `claude-context-nudge` | Cache-token aggregation, latest usage, tier persistence/suppression/escalation, malformed JSON/transcript lines/state, environment fallback, disabled mode; no prompt prose assertions |
| `gh-step-anchor` | In-memory attempt ZIP, matching job selection, setup/BOM/CRLF, nested markers, physical multiline numbering, skipped-step gaps, post steps, all/JSON/step filters, URL/repo arguments, ambiguous/absent/duplicate mapping, invalid ZIP |
| `sandbox` | Real CLI help variants, unknown commands, repository-required error paths from a fully isolated non-repository |

## Deliberate gaps

- No live-service integration, authentication, remote API schema guarantees, or
  GitHub browser confirmation of anchors.
- No CI collection commits/pushes, long-running polling, real cleanup reset/amend,
  or force pushes. Cleanup safety and preview are tested with reads mocked and
  mutations blocked.
- No sandbox worktree lifecycle, tmux, agents, submodules, or Jira cleanup.
- Jira description validation currently checks only the top-level `type: doc`,
  not the full ADF schema. Its non-204 path repeats the PUT to retrieve an error
  body; the test mocks this existing behavior and does not endorse retry safety.
- Not every Jira formatted metadata field or every CLI file-input variant is
  covered. Tests target contracts rather than line coverage or implementation
  internals.

The PR-body tests protect stdin argument intermixing on Python 3.11 as well as
newer interpreters. Anchor tests cover the existing `gh-step-anchor` fix.
