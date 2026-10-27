import json
import subprocess
from collections.abc import Callable
from types import ModuleType
from typing import Any, Final
from unittest.mock import Mock

import pytest

HEAD: Final = "e" * 40
OLD: Final = "a" * 40
CHECKS: Final = [
    {"name": "build", "workflow": "Product", "bucket": "pass"},
    {"name": "unit", "workflow": "Product", "bucket": "pending"},
    {"name": "hardware", "workflow": "Functional", "bucket": "fail"},
    {"name": "lint", "workflow": "Validation", "bucket": "skipping"},
]
REQUIRED: Final = [{"name": "build", "workflow": "Product", "bucket": "pass"},
                   {"name": "unit", "workflow": "Product", "bucket": "pending"}]


@pytest.fixture
def state(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-pr-state")


def pr(**changes: Any) -> dict[str, Any]:
    fields = {
        "number": 17, "title": "DOCS: Add an ADR (P11F-1)", "url": "https://github.com/o/r/pull/17", "state": "OPEN",
        "isDraft": False, "body": "## Test plan\n\n- [x] done\n- [ ] on a brick\n```\n- [ ] in a fence\n```\n",
        "headRefName": "feature/x", "headRefOid": HEAD, "baseRefName": "master", "mergeable": "MERGEABLE",
        "mergeStateStatus": "UNSTABLE", "reviewDecision": "APPROVED",
        "latestOpinionatedReviews": {"nodes": [
            {"author": {"login": "ann"}, "state": "APPROVED", "submittedAt": "t1", "commit": {"oid": HEAD}},
            {"author": {"login": "bob"}, "state": "APPROVED", "submittedAt": "t0", "commit": {"oid": OLD}},
            {"author": {"login": "cat"}, "state": "CHANGES_REQUESTED", "submittedAt": "t2", "commit": {"oid": HEAD}},
        ]},
        "reviewRequests": {"nodes": [{"requestedReviewer": {"login": "steven"}}, {"requestedReviewer": {"slug": "fw-team"}}]},
        "reviewThreads": {"totalCount": 2, "nodes": [{"isResolved": True}, {"isResolved": False}]},
        "comments": {"totalCount": 3, "nodes": [{"author": {"login": "dan"}, "createdAt": "t3"}]},
    }
    return {**fields, **changes}


STACK: Final = {"number": 9, "open": True, "base": {"ref": "master"}, "pull_requests": [
    {"number": 17, "state": "open", "draft": False}, {"number": 18, "state": "open", "draft": True}]}
PROTECTION: Final = {"required_pull_request_reviews": {"required_approving_review_count": 1,
                                                        "require_code_owner_reviews": True, "dismiss_stale_reviews": True},
                     "required_status_checks": {"strict": False}}


def serve(state: ModuleType, monkeypatch: pytest.MonkeyPatch, *, protection: object = PROTECTION,
          rulesets: list[dict[str, Any]] | None = None, stacks: list[list[dict[str, Any]]] | None = None,
          checks: object = None, required: object = None, pull: dict[str, Any] | None = None) -> Mock:
    api = {
        "repos/o/r/stacks?per_page=100": json.dumps([[STACK]] if stacks is None else stacks),
        "repos/o/r/branches/master/protection": protection,
        "repos/o/r/rules/branches/master": json.dumps(rulesets or []),
    }

    def gh(*args: str) -> str:
        if args[:2] == ("api", "graphql"):
            return json.dumps({"data": {"repository": {"nameWithOwner": "o/r", "pullRequest": pull or pr()}}})
        answer = api[args[1]]
        if isinstance(answer, Exception):
            raise answer
        return answer if isinstance(answer, str) else json.dumps(answer)

    def pr_checks(repo: str, number: int, only_required: bool) -> object:
        answer = (REQUIRED if required is None else required) if only_required else (CHECKS if checks is None else checks)
        if isinstance(answer, Exception):
            raise answer
        return answer

    fake = Mock(side_effect=gh)
    monkeypatch.setattr(state, "gh", fake)
    monkeypatch.setattr(state, "pr_checks", Mock(side_effect=pr_checks))
    return fake


def test_summary_names_what_needs_attention(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(state, monkeypatch)
    # When
    status = state.main(["17", "-R", "o/r"])
    # Then
    assert status == 0
    assert capsys.readouterr().out.splitlines() == [
        "PR #17: DOCS: Add an ADR (P11F-1)",
        "State: open, ready for review. Merge state UNSTABLE, mergeable.",
        "Head: feature/x at eeeeeeeeee, into master",
        "Reviews: APPROVED",
        "  approved: ann, bob (on aaaaaaaaaa)",
        "  changes requested: cat",
        "  requested: steven, fw-team",
        "Conversation: 1 unresolved threads, 3 comments (last by dan, t3), 1 unchecked boxes",
        "Required checks (2): 1 pass, 1 pending",
        "  pending: unit",
        "Other checks (2): 1 fail, 1 skipping",
        "  fail: hardware",
        "Stack #9 (open): master <- #17 (this) <- #18 (draft)",
        "master rules: 1 approval, code owners, a push dismisses approvals",
    ]


def test_json_splits_checks_by_workflow_and_name(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(state, monkeypatch, required=[{"name": "build", "workflow": "Product", "bucket": "pass"}],
          checks=[*CHECKS, {"name": "build", "workflow": "Nightly", "bucket": "fail"}])
    # When
    state.main(["https://github.com/o/r/pull/17", "--json"])
    # Then
    out = json.loads(capsys.readouterr().out)
    assert [(c["workflow"], c["name"]) for c in out["checks"]["required"]] == [("Product", "build")]
    assert ("Nightly", "build") in [(c["workflow"], c["name"]) for c in out["checks"]["other"]]
    assert out["reviews"][1] == {"author": "bob", "state": "APPROVED", "submittedAt": "t0", "onHead": False, "commit": OLD}
    assert out["stack"]["number"] == 9


def test_url_selects_its_repository(state: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    fake = serve(state, monkeypatch)
    # When
    state.main(["https://github.com/o/r/pull/17"])
    # Then
    graphql = fake.call_args_list[0].args
    assert ("-F", "owner=o") == graphql[2:4] and ("-F", "name=r") == graphql[4:6] and ("-F", "number=17") == graphql[6:8]


def test_without_admin_rules_come_from_rulesets(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(state, monkeypatch, protection=state.GhError("gh: Not Found (HTTP 404)"), rulesets=[
        {"type": "pull_request", "parameters": {"required_approving_review_count": 2, "dismiss_stale_reviews_on_push": False,
                                                "require_last_push_approval": True}},
        {"type": "required_status_checks", "parameters": {"strict_required_status_checks_policy": True}}])
    # When
    state.main(["17", "-R", "o/r"])
    # Then
    assert capsys.readouterr().out.splitlines()[-1] == (
        "master rules: 2 approvals, approvals survive a push, the last push needs its own approval, must be up to date. "
        "Branch protection isn't readable without admin, so this is rulesets only")


def test_unprotected_branch_is_known_not_unreadable(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(state, monkeypatch, protection=state.GhError("gh: Branch not protected (HTTP 404)"))
    # When
    state.main(["17", "-R", "o/r"])
    # Then
    assert capsys.readouterr().out.splitlines()[-1] == "master rules: 0 approvals, approvals survive a push"


@pytest.mark.parametrize("case", [
    ({"stacks": []}, "Stack: none"),
    ({"stacks": [[{**STACK, "pull_requests": [{"number": 5, "state": "open", "draft": False}]}]]}, "Stack: none"),
])
def test_stack_line_when_the_pr_is_in_no_stack(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str], case: tuple[dict[str, Any], str]) -> None:
    # Given
    serve(state, monkeypatch, **case[0])
    # When
    state.main(["17", "-R", "o/r"])
    # Then
    assert case[1] in capsys.readouterr().out.splitlines()


@pytest.mark.parametrize("which", ["checks", "required"])
def test_a_failed_checks_call_reports_checks_unknown(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                      capsys: pytest.CaptureFixture[str], which: str) -> None:
    # Given
    serve(state, monkeypatch, **{which: state.GhError("gh: HTTP 502")})
    # When
    state.main(["17", "-R", "o/r"])
    # Then
    out = capsys.readouterr().out
    assert "Checks: unknown (gh: HTTP 502)" in out and "Other checks" not in out


def test_missing_pr_exits_1_with_gh_message(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(state, "gh", Mock(side_effect=state.GhError("GraphQL: Could not resolve to a PullRequest")))
    # When
    status = state.main(["99", "-R", "o/r"])
    # Then
    assert status == 1
    assert "Could not resolve" in capsys.readouterr().err


@pytest.mark.parametrize("arguments", [["abc"], ["17", "-R", "just-owner"]])
def test_rejects_bad_arguments(state: ModuleType, arguments: list[str]) -> None:
    with pytest.raises(SystemExit) as error:
        state.main(arguments)
    assert error.value.code == 2


@pytest.mark.parametrize("case", [
    (0, '[{"name": "b", "workflow": "W", "bucket": "pass"}]', "", [{"name": "b", "workflow": "W", "bucket": "pass"}]),
    (8, '[{"name": "b", "workflow": "W", "bucket": "pending"}]', "", [{"name": "b", "workflow": "W", "bucket": "pending"}]),
    (1, "", "no checks reported on the 'x' branch", []),
    (1, "", "no required checks reported on the 'x' branch", []),
])
def test_pr_checks_reads_json_despite_nonzero_exits(state: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                    case: tuple[int, str, str, list[dict[str, str]]]) -> None:
    # Given
    code, stdout, stderr, expected = case
    run = Mock(return_value=subprocess.CompletedProcess([], code, stdout, stderr))
    monkeypatch.setattr(subprocess, "run", run)
    # When / Then
    assert state.pr_checks("o/r", 17, True) == expected
    assert run.call_args.args[0] == ["gh", "pr", "checks", "17", "-R", "o/r", "--json", "name,workflow,bucket", "--required"]


def test_pr_checks_raises_on_other_errors(state: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 1, "", "HTTP 401")))
    with pytest.raises(state.GhError, match="HTTP 401"):
        state.pr_checks("o/r", 17, False)
