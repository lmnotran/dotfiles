import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest

TITLE: Final = "CI_CD: Fix the cache key (P11F-1234)"
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
         **changes: object) -> Mock:
    fields = {"number": 17, "title": TITLE, "body": "## Test plan\n\n- [x] Done\n", "state": "OPEN",
              "is_draft": False, "mergeable": "MERGEABLE", "merge_state": "CLEAN", "review_decision": "APPROVED"}
    monkeypatch.setattr(merge, "fetch_pr", Mock(return_value=merge.PullRequest(**{**fields, **changes})))
    monkeypatch.setattr(merge, "required_checks", Mock(return_value=list(checks)))
    run = Mock(return_value=subprocess.CompletedProcess([], 0))
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
    (notes / "P11F-1234.md").write_text("# P11F-1234\n\n## Follow-ups\n\n- [ ] Next master run deploys docs\n"
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
