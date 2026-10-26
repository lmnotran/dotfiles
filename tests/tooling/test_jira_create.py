import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def create(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-create", "--summary", "New issue", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("# Context"))
    return tool("jira-create")


@pytest.mark.parametrize("no_lint", [False, True])
def test_prose_lint_gates_description(create: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                      capsys: pytest.CaptureFixture[str], no_lint: bool) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-create", "--summary", "S", "-", "--dry-run"] + (["--no-lint"] if no_lint else []))
    monkeypatch.setattr(sys, "stdin", io.StringIO("Dropped ~−44% overall."))
    # When / Then: dry run keeps the subprocess blocker active.
    if no_lint:
        create.main()
        assert json.loads(capsys.readouterr().out)["method"] == "POST"
    else:
        with pytest.raises(SystemExit, match=r"prose-lint flagged(.|\n)*tilde-minus"):
            create.main()


def test_payload_when_defaults(create: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    curl = Mock(return_value=create.subprocess.CompletedProcess([], 0, stdout='{"key":"TEST-18"}\n201'))
    monkeypatch.setattr(create.subprocess, "run", curl)
    # When
    create.main()
    # Then
    command = curl.call_args.args[0]
    assert command[command.index("-X") + 1] == "POST"
    assert command[-1] == create.BASE + "/rest/api/3/issue"
    assert "-n" in command
    assert json.loads(curl.call_args.kwargs["input"]) == {"fields": {
        "project": {"key": "P11F"}, "issuetype": {"name": "Task"}, "summary": "New issue",
        "assignee": {"accountId": "712020:107a92fe-aefc-4035-8178-223e6fdc76c7"},
        "description": {"type": "doc", "version": 1, "content": [{"type": "heading", "attrs": {"level": 1},
                         "content": [{"type": "text", "text": "Context"}]}]},
    }}
    assert capsys.readouterr().out == f"201  TEST-18  {create.BASE}/browse/TEST-18\n"
    assert curl.call_count == 1


@pytest.mark.parametrize("assignee,account", [("none", None), ("custom-id", "custom-id"), ("me", "712020:107a92fe-aefc-4035-8178-223e6fdc76c7")])
def test_dry_run_when_overrides(create: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                capsys: pytest.CaptureFixture[str], assignee: str, account: str | None) -> None:
    # Given
    path = tmp_path / "input.md"
    path.write_text("Description")
    monkeypatch.setattr(sys, "argv", ["jira-create", "--summary", "Override", "--project", "OTHER", "--type", "Bug",
                                      "--parent", "OTHER-1", "--assignee", assignee, "--dry-run", str(path)])
    # When: subprocess remains blocked.
    create.main()
    # Then
    request = json.loads(capsys.readouterr().out)
    assert request["method"] == "POST"
    assert request["endpoint"] == create.BASE + "/rest/api/3/issue"
    assert request["payload"] == {"fields": {"summary": "Override", "project": {"key": "OTHER"}, "issuetype": {"name": "Bug"},
        "parent": {"key": "OTHER-1"}, "assignee": {"accountId": account},
        "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Description"}]}]}}}


@pytest.mark.parametrize("code", ["200", "204", "400", "403"])
def test_failure_when_unexpected_status(create: ModuleType, monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    # Given
    curl = Mock(return_value=create.subprocess.CompletedProcess([], 0, stdout='{"errorMessages":["rejected"]}\n' + code))
    monkeypatch.setattr(create.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match=f"HTTP {code}\n.*rejected"):
        create.main()
    assert curl.call_count == 1


@pytest.mark.parametrize("body,reason", [('{}', "missing issue key"), ('{"key":null}', "missing issue key"), ('bad', "non-JSON")])
def test_failure_when_response_invalid(create: ModuleType, monkeypatch: pytest.MonkeyPatch, body: str, reason: str) -> None:
    # Given
    monkeypatch.setattr(create.subprocess, "run", Mock(return_value=create.subprocess.CompletedProcess([], 0, stdout=body + "\n201")))
    # When / Then
    with pytest.raises(SystemExit, match=reason):
        create.main()


def test_failure_when_assignee_is_email(create: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-create", "--summary", "S", "--assignee", "person@example.invalid", "-"])
    # When / Then
    with pytest.raises(SystemExit) as error:
        create.main()
    assert error.value.code == 2


def test_transport_failure_when_curl_fails(create: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    curl = Mock(return_value=create.subprocess.CompletedProcess([], 7, stdout="\n000", stderr="offline"))
    monkeypatch.setattr(create.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match="curl failed.*offline"):
        create.main()
    assert curl.call_count == 1
