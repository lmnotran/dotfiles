# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

## Conventions

- **Create an issue**: `gh issue create --title "..." --body "..."`. Use a heredoc for multi-line bodies.
- **Read an issue**: `gh issue view <number> --comments`. Use JSON output when you need to filter comments or inspect labels.
- **List issues**: `gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'` with appropriate `--label` and `--state` filters.
- **Comment on an issue**: `gh issue comment <number> --body "..."`
- **Apply / remove labels**: `gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **Close**: `gh issue close <number> --comment "..."`

Run `gh` inside the clone to use its remote. Check `git remote -v` if the repo is unclear.

## Pull requests as a triage surface

**PRs as a request surface: no.** `/triage` reads this flag. Set it to `yes` to treat external pull requests (PRs) as feature requests.

When set to `yes`, PRs run through the same labels and states as issues, using the `gh pr` equivalents:

- **Read a PR**: `gh pr view <number> --comments` and `gh pr diff <number>` for the diff.
- **List PRs**: `gh pr list --state open --json number,title,body,labels,author,authorAssociation,comments`.
- Keep authors whose `authorAssociation` is `CONTRIBUTOR`, `FIRST_TIME_CONTRIBUTOR`, or `NONE`. Exclude `OWNER`, `MEMBER`, and `COLLABORATOR`.
- **Comment**: `gh pr comment`.
- **Change labels**: `gh pr edit --add-label` or `--remove-label`.
- **Close**: `gh pr close`.

GitHub shares numbers across issues and PRs. A bare `#42` may be either.
Try `gh pr view 42`, then `gh issue view 42` if it isn't a PR.

## When a skill says "publish to the issue tracker"

Create a GitHub issue.

## When a skill says "fetch the relevant ticket"

Run `gh issue view <number> --comments`.

## Wayfinding operations

`/wayfinder` uses one **map** issue to track the work and **child** issues as tickets.

### Map and tickets

- Create the map with `gh issue create --label wayfinder:map`. Its body holds Notes, Decisions-so-far, and Fog.
- Link each child to the map as a GitHub sub-issue using `gh api`.
- If sub-issues aren't available, add children to a task list in the map. Put `Part of #<map>` at the top of each child.
- Label children `wayfinder:<type>`, where the type is `research`, `prototype`, `grilling`, or `task`.
- Assign claimed tickets to the developer doing the work.

### Blockers

Use GitHub's native issue dependencies so blockers are visible in the UI.
Fetch the blocker's numeric database ID:

```sh
gh api repos/<owner>/<repo>/issues/<n> --jq .id
```

Use that ID, not the issue number or `node_id`, to add the dependency:

```sh
gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>
```

`issue_dependencies_summary.blocked_by` counts open blockers.
If dependencies aren't available, put `Blocked by: #<n>, #<n>` at the top
of the child's body. A ticket is unblocked when every blocker is closed.

### Choose, claim, and resolve

1. List the map's open children with `gh issue list --state open`, using its sub-issues or task list.
2. Exclude assigned tickets and those with open blockers. Check native dependencies or the `Blocked by` line.
3. Choose the first remaining ticket in map order.
4. Claim it with `gh issue edit <n> --add-assignee @me`. This is the session's first write.
5. Post the answer with `gh issue comment <n> --body "<answer>"`, then close it with `gh issue close <n>`.
6. Add a gist link to the map's Decisions-so-far so the next session can find the answer.
