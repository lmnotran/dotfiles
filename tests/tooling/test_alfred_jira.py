import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def alfred(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["alfred-jira"])
    return tool("alfred-jira")


def issue(key: str, summary: str = "Fix the build") -> dict:
    return {"key": key, "fields": {"summary": summary, "status": {"name": "To Do"}, "issuetype": {"name": "Task"},
                                   "assignee": None}}


def fake_search(alfred: ModuleType, monkeypatch: pytest.MonkeyPatch, *, stdout: str = "[]", returncode: int = 0,
                stderr: str = "") -> Mock:
    run = Mock(return_value=alfred.subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr))
    monkeypatch.setattr(alfred.subprocess, "run", run)
    return run


def items(capsys: pytest.CaptureFixture[str]) -> list[dict]:
    return json.loads(capsys.readouterr().out)["items"]


@pytest.mark.parametrize("query,jql", [
    ("", "assignee = currentUser() AND resolution = Unresolved ORDER BY updated DESC"),
    ("abc-8145", "key = ABC-8145"),
    ('cache "key"', '(summary ~ "cache key*" OR text ~ "cache key") ORDER BY updated DESC'),
    ("(*)", "assignee = currentUser() AND resolution = Unresolved ORDER BY updated DESC"),
])
def test_jql_when_query_given(alfred: ModuleType, query: str, jql: str) -> None:
    assert alfred.build_jql(query) == jql


def test_items_when_issues_found(alfred: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["alfred-jira", "build"])
    run = fake_search(alfred, monkeypatch, stdout=json.dumps([issue("ABC-1", "Fix\nthe   build")]))
    # When
    alfred.main()
    # Then
    [item] = items(capsys)
    assert item["title"] == "ABC-1  Fix the build"
    assert item["subtitle"] == "Task · To Do · Unassigned"
    assert item["arg"] == alfred.BASE + "/browse/ABC-1"
    assert item["text"]["copy"] == item["mods"]["cmd"]["arg"] == "ABC-1"
    command = run.call_args.args[0]
    assert command[0].endswith("/bin/jira-search")
    assert command[2:] == ["--json", "--fields", alfred.FIELDS, "--max", str(alfred.MAX_RESULTS)]


def test_direct_link_when_key_search_fails(alfred: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["alfred-jira", "nope-12"])
    fake_search(alfred, monkeypatch, returncode=1, stderr="HTTP 400\n{}")
    # When
    alfred.main()
    # Then
    [item] = items(capsys)
    assert item["title"] == "Open NOPE-12"
    assert item["arg"] == alfred.BASE + "/browse/NOPE-12"


def test_no_direct_link_when_key_found(alfred: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["alfred-jira", "ABC-1"])
    fake_search(alfred, monkeypatch, stdout=json.dumps([issue("ABC-1")]))
    # When
    alfred.main()
    # Then
    assert [item["uid"] for item in items(capsys)] == ["ABC-1"]


@pytest.mark.parametrize("kwargs,title,subtitle", [
    ({"returncode": 1, "stderr": "HTTP 401\ndenied"}, "Jira search failed", "HTTP 401"),
    ({"returncode": 1, "stdout": ""}, "Jira search failed", "jira-search exited 1"),
    ({"stdout": "not json"}, "Jira search failed", None),
    ({"stdout": "[]"}, "No Jira issues found", "words"),
])
def test_message_when_search_has_no_results(alfred: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                                            kwargs: dict, title: str, subtitle: str | None) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["alfred-jira", "words"])
    fake_search(alfred, monkeypatch, **kwargs)
    # When
    alfred.main()
    # Then
    [item] = items(capsys)
    assert item["title"] == title
    assert item["valid"] is False
    if subtitle is not None:
        assert item["subtitle"] == subtitle


@pytest.mark.parametrize("project,jql", [("XYZ", "key = XYZ-8415"),
                                         (None, '(summary ~ "8415*" OR text ~ "8415") ORDER BY updated DESC')])
def test_default_project_when_bare_number(alfred: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                                         project: str | None, jql: str) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["alfred-jira", "8415"])
    if project:
        monkeypatch.setenv("JIRA_DEFAULT_PROJECT", project)
    else:
        monkeypatch.delenv("JIRA_DEFAULT_PROJECT")
    run = fake_search(alfred, monkeypatch, stdout=json.dumps([issue("XYZ-8415")]))
    # When
    alfred.main()
    # Then
    assert [item["uid"] for item in items(capsys)] == ["XYZ-8415"]
    assert run.call_args.args[0][1] == jql


def test_config_file_when_environment_unset(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch,
                                            tmp_path: Path) -> None:
    # Given
    for name in ("JIRA_BASE_URL", "JIRA_DEFAULT_PROJECT"):
        monkeypatch.delenv(name)
    config = tmp_path / "xdg_config_home" / "jira" / "env"
    config.parent.mkdir(parents=True)
    config.write_text('# Jira site\nJIRA_BASE_URL="https://site.example/"\nJIRA_DEFAULT_PROJECT = XYZ\n')
    # When
    alfred = tool("alfred-jira")
    # Then
    assert alfred.BASE == "https://site.example"
    assert alfred.expand_key("12") == "XYZ-12"


def test_setup_message_when_site_unset(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch,
                                       capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.delenv("JIRA_BASE_URL")
    monkeypatch.setattr(sys, "argv", ["alfred-jira", "words"])
    alfred = tool("alfred-jira")
    # When
    alfred.main()
    # Then
    [item] = items(capsys)
    assert item["title"] == "Jira isn't set up"
    assert item["valid"] is False
