import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest

TITLE: Final = "CI_CD: Fix the cache key (ABC-1234)"
PROTECTION_GAPS: Final = [
    {"checks": [("apps_emm_audiobrick_part_one", "fail")]},
    {"checks": [("ppp_test", "pending")]},
    {"review_decision": "REVIEW_REQUIRED"},
    {"merge_state": "BLOCKED"},
    {"merge_state": "BEHIND"},
]


@pytest.fixture
def merge(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-pr-merge")


def stub(merge: ModuleType, monkeypatch: pytest.MonkeyPatch, checks: tuple | list = (("Build", "pass"),),
         queue: tuple[bool, bool] = (False, False), stdout: str = "", **changes: object) -> Mock:
    fields = {"number": 17, "title": TITLE, "body": "## Test plan\n\n- [x] Done\n", "state": "OPEN",
              "is_draft": False, "mergeable": "MERGEABLE", "merge_state": "CLEAN", "review_decision": "APPROVED",
              "node_id": "PR_kwDO17", "base": "main"}
    monkeypatch.setattr(merge, "fetch_pr", Mock(return_value=merge.PullRequest(**{**fields, **changes})))
    monkeypatch.setattr(merge, "required_checks", Mock(return_value=list(checks)))
    monkeypatch.setattr(merge, "merge_queue", Mock(return_value=merge.MergeQueue(*queue)))
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=stdout))
    monkeypatch.setattr(subprocess, "run", run)
    return run


def test_squash_merges_when_nothing_is_open(merge: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    run = stub(merge, monkeypatch)
    # When / Then
    assert merge.main(["17"]) == 0
    assert [call.args[0] for call in run.call_args_list] == [["gh", "pr", "merge", "17", "--squash"]]


@pytest.mark.parametrize("gap", PROTECTION_GAPS)
def test_stops_on_a_protection_gap_without_a_reason(merge: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                    gap: dict) -> None:
    # Given
    run = stub(merge, monkeypatch, **gap)
    # When / Then
    assert merge.main(["17"]) == 1
    run.assert_not_called()


@pytest.mark.parametrize("gap", PROTECTION_GAPS)
def test_reason_posts_a_comment_then_merges_with_admin(merge: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                       gap: dict) -> None:
    # Given
    run = stub(merge, monkeypatch, **gap)
    # When
    status = merge.main(["17", "--reason", "The NVM fix in #6374 unblocks this build."])
    # Then
    comment, merge_call = run.call_args_list
    assert status == 0
    assert comment.args[0][:4] == ["gh", "pr", "comment", "17"]
    assert comment.kwargs["input"].endswith("\n\nThe NVM fix in #6374 unblocks this build.")
    assert merge_call.args[0] == ["gh", "pr", "merge", "17", "--squash", "--admin"]


def test_unchecked_boxes_need_a_reason_but_no_admin(merge: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    run = stub(merge, monkeypatch, body="## Test plan\n\n- [ ] `ppp_test` passes\n")
    # When / Then
    assert merge.main(["17"]) == 1
    assert merge.main(["17", "--rebase", "--reason", "The PR's own CI run shows it."]) == 0
    assert run.call_args_list[-1].args[0] == ["gh", "pr", "merge", "17", "--rebase"]


@pytest.mark.parametrize("change", [{"is_draft": True}, {"state": "MERGED"}, {"mergeable": "CONFLICTING"}])
def test_stops_even_with_a_reason(merge: ModuleType, monkeypatch: pytest.MonkeyPatch, change: dict) -> None:
    # Given
    run = stub(merge, monkeypatch, **change)
    # When / Then
    assert merge.main(["17", "--reason", "Ship it."]) == 1
    run.assert_not_called()


def test_dry_run_shows_the_comment_and_command_without_running_them(merge: ModuleType,
                                                                    monkeypatch: pytest.MonkeyPatch,
                                                                    capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    run = stub(merge, monkeypatch, review_decision="REVIEW_REQUIRED")
    # When
    status = merge.main(["17", "--dry-run", "--reason", "Approved in Teams."])
    # Then
    assert status == 0
    run.assert_not_called()
    assert "Would run: gh pr merge 17 --squash --admin" in capsys.readouterr().out


def test_prints_open_follow_ups_from_the_ticket_notes_after_merging(merge: ModuleType,
                                                                    monkeypatch: pytest.MonkeyPatch,
                                                                    capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    notes = Path.home() / "notes"
    notes.mkdir()
    (notes / "ABC-1234.md").write_text("# ABC-1234\n\n## Follow-ups\n\n- [ ] Next master run deploys docs\n"
                                        "- [x] Done already\n\n## Log\n\n- [ ] Not a follow-up\n")
    stub(merge, monkeypatch)
    # When
    merge.main(["17"])
    # Then
    out = capsys.readouterr().out
    assert "- [ ] Next master run deploys docs" in out and "Not a follow-up" not in out


def test_unchecked_items_skip_fenced_code_and_track_sections(merge: ModuleType) -> None:
    body = ("## Summary\n\nText.\n\n## Test plan\n\n- [x] Done\n- [ ] `ppp_test` passes\n"
            "```md\n- [ ] Not a real box\n```\n\n### Follow-ups\n\n* [ ] Next master run deploys\n")
    assert merge.unchecked_items(body) == [("Test plan", "`ppp_test` passes"), ("Follow-ups", "Next master run deploys")]


@pytest.mark.parametrize(("result", "expected"), [
    (subprocess.CompletedProcess([], 8, stdout='[{"name": "Build", "bucket": "pending"}]', stderr=""),
     [("Build", "pending")]),
    (subprocess.CompletedProcess([], 1, stdout="", stderr="no required checks reported on the 'x' branch\n"), []),
])
def test_required_checks_read_json_whatever_the_exit_code(merge: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                          result: subprocess.CompletedProcess, expected: list) -> None:
    monkeypatch.setattr(subprocess, "run", Mock(return_value=result))
    assert merge.required_checks(17) == expected


def test_adds_the_pr_to_the_merge_queue_when_the_base_has_one(merge: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                              capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    run = stub(merge, monkeypatch, queue=(True, False),
               stdout='{"data": {"enqueuePullRequest": {"mergeQueueEntry": {"position": 2}}}}')
    # When
    status = merge.main(["17"])
    # Then
    (call,) = run.call_args_list
    assert status == 0
    assert call.args[0][:3] == ["gh", "api", "graphql"]
    assert "enqueuePullRequest" in call.args[0][4] and call.args[0][-1] == "id=PR_kwDO17"
    assert "merge queue for main at position 2" in capsys.readouterr().out


def test_an_already_queued_pr_succeeds_without_queueing_again(merge: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                               capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    run = stub(merge, monkeypatch, queue=(True, True), body="## Test plan\n\n- [ ] CI passes\n")
    # When / Then
    assert merge.main(["17"]) == 0
    run.assert_not_called()
    assert "Already in the merge queue for main" in capsys.readouterr().out


@pytest.mark.parametrize(("polls", "expected"), [
    # (state, queued) per poll after the PR is found queued
    ([("OPEN", True), ("MERGED", False)], 0),
    ([("OPEN", True), ("CLOSED", False)], 1),
    # The queue lets go of a merging PR a moment before it reads as merged.
    ([("OPEN", False), ("MERGED", False)], 0),
    ([("OPEN", False), ("OPEN", True), ("OPEN", False), ("MERGED", False)], 0),
    ([("OPEN", True), ("OPEN", False), ("OPEN", False)], 1),
])
def test_wait_blocks_until_the_queue_merges_or_drops_the_pr(merge: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                            polls: list[tuple[str, bool]], expected: int) -> None:
    # Given
    stub(merge, monkeypatch, queue=(True, True))
    queued_pr = merge.fetch_pr.return_value
    fields = {f: getattr(queued_pr, f) for f in queued_pr.__slots__}
    merge.fetch_pr.side_effect = [queued_pr] + [merge.PullRequest(**{**fields, "state": s}) for s, _ in polls]
    merge.merge_queue.side_effect = [merge.MergeQueue(True, True)] + [
        merge.MergeQueue(True, queued) for state, queued in polls if state == "OPEN"]
    monkeypatch.setattr(merge.time, "sleep", Mock())
    # When / Then
    assert merge.main(["17", "--wait"]) == expected


def test_wait_after_enqueueing_reports_the_merge(merge: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    stub(merge, monkeypatch, queue=(True, False),
         stdout='{"data": {"enqueuePullRequest": {"mergeQueueEntry": {"position": 1}}}}')
    open_pr = merge.fetch_pr.return_value
    merged_pr = merge.PullRequest(**{**{f: getattr(open_pr, f) for f in open_pr.__slots__}, "state": "MERGED"})
    merge.fetch_pr.side_effect = [open_pr, merged_pr]
    monkeypatch.setattr(merge.time, "sleep", Mock())
    # When / Then
    assert merge.main(["17", "--wait"]) == 0
    assert "Merged PR #17." in capsys.readouterr().out


def test_admin_override_merges_directly_instead_of_queueing(merge: ModuleType,
                                                            monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    run = stub(merge, monkeypatch, queue=(True, False), review_decision="REVIEW_REQUIRED")
    # When
    status = merge.main(["17", "--reason", "Approved in Teams."])
    # Then
    assert status == 0
    assert run.call_args_list[-1].args[0] == ["gh", "pr", "merge", "17", "--squash", "--admin"]


@pytest.mark.parametrize(("node", "expected"), [
    ({"isInMergeQueue": False, "repository": {"mergeQueue": {"id": "MQ_1"}}}, (True, False)),
    ({"isInMergeQueue": True, "repository": {"mergeQueue": {"id": "MQ_1"}}}, (True, True)),
    ({"isInMergeQueue": False, "repository": {"mergeQueue": None}}, (False, False)),
])
def test_merge_queue_reads_the_graphql_answer(merge: ModuleType, monkeypatch: pytest.MonkeyPatch, node: dict,
                                              expected: tuple[bool, bool]) -> None:
    # Given
    pr = merge.PullRequest(17, TITLE, "", "OPEN", False, "MERGEABLE", "CLEAN", "APPROVED", "PR_kwDO17", "main")
    check_output = Mock(return_value=json.dumps({"data": {"node": node}}))
    monkeypatch.setattr(subprocess, "check_output", check_output)
    # When
    queue = merge.merge_queue(pr)
    # Then
    assert (queue.enabled, queue.queued) == expected
    assert check_output.call_args.args[0][-3:] == ["id=PR_kwDO17", "-f", "branch=main"]
