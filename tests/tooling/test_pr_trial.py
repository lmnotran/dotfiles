import json
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any, Final

import pytest

HEAD: Final = "a" * 40
URL: Final = "https://github.com/owner/repo/actions/runs/{}"


def workflow_run(run_id: int, name: str, status: str, conclusion: str = "") -> dict[str, Any]:
    return {"databaseId": run_id, "workflowName": name, "status": status, "conclusion": conclusion, "url": URL.format(run_id)}


JOBS: Final = {"jobs": [
    {"name": "Detect", "status": "completed", "conclusion": "success", "url": URL.format(2) + "/job/21"},
    {"name": "Compare", "status": "completed", "conclusion": "success", "url": URL.format(2) + "/job/22"},
]}


class FakeShell:
    def __init__(self, trial: ModuleType, polls: list[list[dict[str, Any]]], branch: str = "feature/ABC-1-x",
                 default: str | None = "master", pushed: bool = False) -> None:
        self.trial, self.polls, self.branch, self.default, self.pushed = trial, polls, branch, default, pushed
        self.calls: list[tuple[str, ...]] = []

    def run(self, *command: str) -> str:
        self.calls.append(command)
        if command[:3] == ("git", "rev-parse", "--abbrev-ref"):
            return self.branch
        if command == ("git", "rev-parse", "HEAD"):
            return HEAD
        if command[:3] == ("git", "rev-parse", "--short=10"):
            return "b" * 10
        if command[:2] == ("git", "symbolic-ref"):
            if self.default is None:
                raise self.trial.TrialError("fatal: ref refs/remotes/origin/HEAD is not a symbolic ref")
            return f"origin/{self.default}"
        if command[:3] == ("gh", "run", "list"):
            return json.dumps(self.polls.pop(0) if len(self.polls) > 1 else self.polls[0])
        if command[:3] == ("gh", "run", "view"):
            return json.dumps(JOBS)
        if command[:2] in {("git", "fetch"), ("git", "push"), ("git", "revert"), ("git", "commit")} or command[:3] == ("gh", "run", "cancel"):
            return ""
        raise AssertionError(f"unexpected command {command}")

    def succeeds(self, *command: str) -> bool:
        self.calls.append(command)
        return self.pushed

    def made(self, *prefix: str) -> list[tuple[str, ...]]:
        return [call for call in self.calls if call[:len(prefix)] == prefix]


@pytest.fixture
def trial(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = tool("gh-pr-trial")
    clock = [0.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    return module


def start(trial: ModuleType, monkeypatch: pytest.MonkeyPatch, shell: FakeShell, *argv: str) -> int:
    monkeypatch.setattr(trial, "run", shell.run)
    monkeypatch.setattr(trial, "succeeds", shell.succeeds)
    monkeypatch.setattr(sys, "argv", ["gh-pr-trial", *argv])
    with pytest.raises(SystemExit) as exit_info:
        trial.main()
    return int(exit_info.value.code or 0)


TARGET: Final = ["--workflow", "^Firmware Tool Diff$", "--cancel", "^Product$"]
REVERT: Final = ["--revert-message", "CI_CD: Drop the temporary comment (ABC-1)"]


def test_trial_pushes_cancels_waits_and_reverts(trial: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    shell = FakeShell(trial, [
        [],
        [workflow_run(1, "Product", "in_progress"), workflow_run(2, "Firmware Tool Diff", "in_progress")],
        [workflow_run(1, "Product", "completed", "cancelled"), workflow_run(2, "Firmware Tool Diff", "completed", "success")],
    ])
    # When
    status = start(trial, monkeypatch, shell, *TARGET, *REVERT)
    # Then
    assert status == 0
    assert shell.made("gh", "run", "cancel") == [("gh", "run", "cancel", "1")]
    assert shell.made("git", "commit") == [("git", "commit", "--quiet", "-m", "CI_CD: Drop the temporary comment (ABC-1)")]
    assert shell.made("git", "push") == [("git", "push", "--quiet", "origin", "feature/ABC-1-x")] * 2
    assert capsys.readouterr().out.splitlines() == [
        f"Firmware Tool Diff: success {URL.format(2)}",
        f"  Detect: success {URL.format(2)}/job/21",
        f"  Compare: success {URL.format(2)}/job/22",
        "cancelled: 1",
        "reverted in bbbbbbbbbb",
    ]


def test_failed_run_is_still_reverted_and_exits_one(trial: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    shell = FakeShell(trial, [[workflow_run(2, "Firmware Tool Diff", "completed", "failure")]])
    # When
    status = start(trial, monkeypatch, shell, *TARGET, *REVERT)
    # Then
    assert status == 1
    assert shell.made("git", "revert")


def test_keep_leaves_the_trial_commit(trial: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    shell = FakeShell(trial, [[workflow_run(2, "Firmware Tool Diff", "completed", "success")]])
    # When
    status = start(trial, monkeypatch, shell, *TARGET, "--keep")
    # Then
    assert status == 0
    assert not shell.made("git", "revert")
    assert len(shell.made("git", "push")) == 1


@pytest.mark.parametrize("polls", [
    [[workflow_run(2, "Firmware Tool Diff", "in_progress")]],  # never finishes
    [[workflow_run(1, "Product", "in_progress")]],  # never shows up
])
def test_no_revert_when_the_run_does_not_start_or_finish_in_time(trial: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                                  capsys: pytest.CaptureFixture[str], polls: list[list[dict[str, Any]]]) -> None:
    # Given
    shell = FakeShell(trial, polls)
    # When
    status = start(trial, monkeypatch, shell, *TARGET, *REVERT, "--wait", "600")
    # Then
    assert status == 2
    assert not shell.made("git", "revert")
    assert len(shell.made("git", "push")) == 1
    assert "still pushed" in capsys.readouterr().err


@pytest.mark.parametrize(("shell_options", "message"), [
    ({"branch": "master"}, "refusing to push a trial commit to master"),
    ({"branch": "develop", "default": "develop"}, "refusing to push a trial commit to develop"),
    ({"pushed": True}, "is already on origin/feature/ABC-1-x"),
    ({"branch": "HEAD"}, "HEAD is detached"),
])
def test_refuses_before_pushing(trial: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                                shell_options: dict[str, Any], message: str) -> None:
    # Given
    shell = FakeShell(trial, [[]], **shell_options)
    # When
    status = start(trial, monkeypatch, shell, *TARGET, *REVERT)
    # Then
    assert status == 3
    assert not shell.made("git", "push")
    assert message in capsys.readouterr().err


def test_works_when_the_clone_has_no_remote_head(trial: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    shell = FakeShell(trial, [[workflow_run(2, "Firmware Tool Diff", "completed", "success")]], default=None)
    # When
    status = start(trial, monkeypatch, shell, *TARGET, *REVERT)
    # Then
    assert status == 0


def test_revert_message_is_required_without_keep(trial: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    shell = FakeShell(trial, [[]])
    # When
    status = start(trial, monkeypatch, shell, *TARGET)
    # Then
    assert status == 2
    assert "--revert-message is required" in capsys.readouterr().err
    assert not shell.calls


def test_repo_flag_reaches_every_gh_call(trial: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    shell = FakeShell(trial, [[workflow_run(1, "Product", "in_progress"), workflow_run(2, "Firmware Tool Diff", "completed", "success")]])
    # When
    start(trial, monkeypatch, shell, *TARGET, *REVERT, "-R", "owner/repo")
    # Then
    gh_calls = [call for call in shell.calls if call[0] == "gh"]
    assert gh_calls and all(call[call.index("-R") + 1] == "owner/repo" for call in gh_calls)
