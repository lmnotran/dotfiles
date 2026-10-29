# Offline tooling tests

From the dotfiles root:

```sh
uv run --with-requirements requirements-tooling-test.txt python -m pytest tests/tooling --disable-socket --strict-markers
```

Type-check the Python helpers with `script/typecheck-helpers`. CI runs it in its
own job.

Dependencies include pytest, pytest-socket, and allure-pytest for CI reports.
CI tests Python 3.11 and 3.13.
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
| `gh-pr-body` | Nested heading boundaries, last-section footer preservation, replacement footer precedence, missing sections, normalized verified writes and mismatch rejection, `-R` repo selection, PR URLs, one-line errors outside a checkout, prose-lint gate on new text with unchanged lines skipped, `--no-lint`, missing prose-lint note, word budget on whole-body and Summary edits, skipped for other sections and with `--long` |
| `gh-pr-create` | Title format (shape, capital letter, trailing period, components from the changelog script) only in p11 repos, prose-lint and word-budget stops before the PR exists, `--long`, `--ready`, `--dry-run`, body verification that ignores the Jira footer and fails on a mismatch, numstat diff counting against the fetched base |
| `gh-pr-merge` | Squash merge when nothing is open, protection gaps (failed or pending required checks, review required, blocked, behind) that stop without `--reason` and add `--admin` with it, reason comment before the merge, unchecked boxes that need a reason but no admin, draft/closed/conflicting stops, dry run, follow-ups from ticket notes, checkbox parsing across fences and sections, required-check JSON despite nonzero exits |
| `gh-pr-state` | Text and JSON summaries: reviews on an older commit, requested users and teams, unresolved threads, unchecked boxes outside fences, required and other checks keyed by workflow and name, the stack chain or none, base rules merged from branch protection and rulesets, unreadable protection versus an unprotected branch, a failed checks call reported as unknown, repository from a PR URL, missing PR and bad arguments, `gh pr checks` JSON despite nonzero exits |
| `prose-lint` | Each rule's hit and its fine cases (TL;DR, entities, en dashes, code spans, fenced blocks, `<pre>` blocks with later line numbers kept, linked SHAs, schema hashes, footer reference lines), Markdown and ADF baselines, ADF code marks and code blocks skipped, payload unwrapping, CLI output and exit codes, word budget (Summary limit, small-diff body limit, what word counts skip including `<pre>` blocks, `--diff-lines` and its ADF rejection) |
| `gh-review-body` | Concatenated pagination JSON, latest authored nonempty review, explicit IDs, missing matches, PUT payload, verified writes/mismatch, stdin CLI editing |
| `gh-run-timings` | Duration units/rounding, attempt endpoint/pagination, JSON filtering/sorting/top, timestamp arithmetic, skipped-step table rows, wall-clock display, empty results |
| `gh-run-failures` | Error lines from pytest summaries and counts, compiler, linker, and CMake errors, Python exception lines, and `##[error]` annotations, with timestamps, ANSI codes, and workspace prefixes stripped, repeats dropped, and a line limit. Run ID or URL and `--repo` conflicts. First failed step link, cancelled jobs, `--wait` polling until done, and exit codes for failed, green, still running, and unreadable runs |
| `p11-image-build` | Image discovery from `FROM ghcr.io/lego-cpl/firmware-developer-p11-*:${ARG}` lines, parent closure order, bake targets with parent contexts, tag args and outputs, monolith tag, unknown image and unusable tags, `--print` without Docker, builder creation before bake with attestations off, `--du`/`--rm` |
| `p11-ci-local` | Image name resolution, default JFrog server from the CLI config, `docker run` mounts and env for worktrees and main checkouts, linuxbrew jf, the setup script, CI's git version fallback, command quoting, `.jfrog/` cleanup that keeps a pre-existing one, missing local image and non-p11-firmware checkout errors |
| `ci-sample` | Protected/detached branch refusal, cleanup dry-run, missing safe reset target, summary files with missing values/outlier median, job arithmetic, workflow resolution/ambiguity |
| `md2adf` | ATX headings, soft-wrapped paragraphs, mixed nested lists, fenced code, inline marks, code+link preservation, tables, quotes/rules, empty text avoidance, file/stdin CLI |
| `jira-put-description` | Invalid JSON/non-document rejection before subprocess, Markdown/ADF input, dry-run envelope, prose-lint gate with the current description as baseline, `--no-lint`, PUT endpoint, 204 success, single-request HTTP and transport failures |
| `jira-comment` | Markdown/ADF input, POST/PUT endpoint and body, strict success codes, required/matching comment IDs, dry run, prose-lint gate with the edited comment as baseline, HTTP/transport errors |
| `jira-create` | Markdown description, POST envelope, defaults and project/type/parent/assignee overrides, dry run, prose-lint gate and `--no-lint`, strict 201/key validation, HTTP/transport errors |
| `jira-search` | GET endpoint and encoded JQL/fields, token pagination, maximum count, raw issues JSON, compact/empty output, API/transport errors and repeated-token rejection |
| `jira-view` | ADF heading/list nesting/code/quote/rule/inline marks/cards/mentions/breaks, absent descriptions, raw JSON/ADF modes, non-JSON API errors |
| `claude-context-nudge` | Cache-token aggregation, latest usage, tier persistence/suppression/escalation, malformed JSON/transcript lines/state, environment fallback, disabled mode; no prompt prose assertions |
| `gh-step-anchor` | ANSI color codes removed before matching and from JSON text, in-memory attempt ZIP, matching job selection, setup/BOM/CRLF, nested markers, physical multiline numbering, skipped-step gaps, post steps, all/JSON/step filters, URL/repo arguments, ambiguous/absent/duplicate mapping, invalid ZIP. ZIP without step files: job-log split by step times across shared seconds, composite start-action/end-action markers, skipped steps, unplaceable lines, and logs that don't fit the step times. In both modes, `^` anchoring to the text after GitHub's timestamp while timestamp patterns still match. No run archive yet (HTTP 404 while the rest of the run is going) uses the job-log split, other archive errors stop with gh's message, and `gh` raises gh's own error output |
| `sandbox` | Real CLI help variants, unknown commands, repository-required error paths from a fully isolated non-repository |
| `oc-session-purge` | Subagent IDs from spawn-tool results only, database children, top-level sessions skipped unless named, dry run deletes nothing, transcript/state/scan-dir removal, failed database delete exit code, ID validation |
| `chamberctl` | Real CLI help variants and unknown commands; no systemd calls |

## Deliberate gaps

- No live-service integration, authentication, remote API schema guarantees, or
  GitHub browser confirmation of anchors.
- No CI collection commits/pushes, long-running polling, real cleanup reset/amend,
  or force pushes. Cleanup safety and preview are tested with reads mocked and
  mutations blocked.
- No sandbox worktree lifecycle, tmux, agents, submodules, or Jira cleanup.
- Jira ADF input validation checks only the top-level `type: doc`, not the full
  ADF schema. Markdown conversion supports the documented subset, not all CommonMark.
- Not every Jira formatted metadata field or every CLI file-input variant is
  covered. Tests target contracts rather than line coverage or implementation
  internals.

The PR-body tests protect stdin argument intermixing on Python 3.11 as well as
newer interpreters. Anchor tests cover the existing `gh-step-anchor` fix.
