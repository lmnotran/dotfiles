# Offline tooling tests

Run the helper tests from the dotfiles root:

```sh
uv run --with-requirements requirements-tooling-test.txt python -m pytest tests/tooling --disable-socket --strict-markers
```

Type-check the Python helpers with `script/typecheck-helpers`. CI runs it in its
own job.

CI tests Python 3.11 and 3.13. Installing dependencies may need network access
on the first run. The tests themselves need no credentials or network.
Sandbox tests also need Bash and Git on the local PATH
(`/usr/bin:/bin` in the child environment).

## Isolation

Each test uses temporary directories for its home, cache, config, and working
files. Python helpers without a `.py` extension load through `SourceFileLoader`.
Register loaded modules so dataclasses work.

Tests block real subprocess calls and Python socket connections by default.
Replace the command or API call being tested with a fake response.

Sandbox tests run the real Bash CLI in a temporary directory. They disable
system and global Git configuration and prevent Git from finding repos outside
that directory. These tests don't change Git state.

No test reads secret files, authenticates, contacts GitHub or Jira, launches
agents, or edits a user's repo.

## Coverage

| Helper and test file | What the tests check |
|---|---|
| [`gh-pr-body`](test_pr_body.py) | Section boundaries and footer preservation. Verified writes, repo selection, prose checks, and word limits. |
| [`gh-pr-create`](test_pr_create.py) | P11 title rules, prose checks, dry runs, and verified bodies. Jira links and API failures. |
| [`gh-pr-merge`](test_pr_merge.py) | Merge blockers, reason comments, admin overrides, and dry runs. Checkbox parsing and follow-up notes. |
| [`gh-pr-state`](test_pr_state.py) | Reviews, threads, checkboxes, checks, and branch protection. Unknown states and repo selection. |
| [`prose-lint`](test_prose_lint.py) | Rule matches and allowed text. Baselines, word limits, Markdown, Atlassian Document Format (ADF), and CLI exit codes. |
| [`gh-review-body`](test_review_body.py) | Review selection, pagination, payloads, stdin editing, and verified writes. |
| [`gh-run-timings`](test_run_timings.py) | Duration calculations, pagination, filters, sorting, skipped steps, and empty results. |
| [`gh-queue-times`](test_queue_times.py) | Date-window run search, deduplication, job fetches, and caching. Rate-limit retries, queue-time stats, filters, output formats, and argument errors. |
| [`gh-run-failures`](test_run_failures.py) | Error extraction, cleanup, deduplication, and failed-step links. Polling, run states, and exit codes. |
| [`gh-artifact-file`](test_artifact_file.py) | Artifact selection, pagination, file reads, and citations. Missing artifacts, invalid options, and insufficient matches. |
| [`p11-image-build`](test_p11_image_build.py) | Image discovery, parent order, tags, and build targets. Preview and builder commands. |
| [`p11-ci-local`](test_p11_ci_local.py) | Image selection, Docker mounts, command quoting, and JFrog config. Cleanup and invalid checkout errors. |
| [`ci-sample`](test_ci_sample.py) | Branch safety, cleanup previews, summaries, timing calculations, and workflow selection. |
| [`md2adf`](test_md2adf.py) | Markdown conversion, nested lists, formatting, tables, and links. File and stdin input. |
| [`jira-put-description`](test_jira_description.py) | Input validation, prose checks, dry runs, payloads, and API failures. |
| [`jira-comment`](test_jira_comment.py) | Create and edit payloads, comment IDs, prose checks, dry runs, and API failures. |
| [`jira-create`](test_jira_create.py) | Defaults, overrides, prose checks, dry runs, and response validation. |
| [`jira-search`](test_jira_search.py) | Query encoding, pagination, result limits, output formats, and API failures. |
| [`jira-view`](test_jira_view.py) | ADF rendering, missing descriptions, raw output, and API errors. |
| [`claude-context-nudge`](test_context_nudge.py) | Token totals, warning levels, saved state, invalid data, and disabled mode. Prompt wording isn't tested. |
| [`gh-step-anchor`](test_step_anchor.py) | Log matching, physical line numbers, skipped steps, and timestamps. Archive fallbacks and invalid or ambiguous logs. |
| [`sandbox`](test_sandbox.py) | Real CLI help, unknown commands, and errors outside a repo. |
| [`oc-session-purge`](test_session_purge.py) | Session selection, ID validation, dry runs, file removal, and database failures. |
| [`chamberctl`](test_chamberctl.py) | Real CLI help and unknown commands. Systemd calls aren't tested. |

The linked test files list the individual cases.

## Deliberate gaps

- No live services, authentication, remote API schema checks, or browser
  confirmation of GitHub log anchors.
- No CI collection commits, pushes, long-running polling, cleanup resets,
  amends, or force pushes. Cleanup tests use fake read responses and block writes.
- No sandbox worktree lifecycle, tmux, agents, submodules, or Jira cleanup.
- Jira input validation checks only the top-level ADF `type: doc`.
- Markdown conversion supports a subset of CommonMark.
- Not every Jira formatted metadata field or every CLI file-input variant is
  covered. Tests focus on behavior rather than line coverage.

The PR-body tests protect stdin argument intermixing on Python 3.11 as well as
newer interpreters.
