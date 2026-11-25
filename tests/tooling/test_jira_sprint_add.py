import json
import re
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import Mock

import pytest


@pytest.fixture
def sprint_add(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-sprint-add", "42", "ABC-1", "ABC-2"])
    return tool("jira-sprint-add")


def reply(body: object = None, code: str = "200") -> Mock:
    return Mock(returncode=0, stdout=("" if body is None else json.dumps(body)) + "\n" + code, stderr="")


def sprint(state: str = "active", **fields: str) -> Mock:
    return reply({"id": 42, "self": "https://example.atlassian.net/rest/agile/1.0/sprint/42", "state": state,
                  "name": "Sprint 42", "originBoardId": 12, **fields})


def issue(key: str, number: int) -> Mock:
    return reply({"id": str(number), "key": key, "self": f"https://example.atlassian.net/rest/api/3/issue/{number}"})


def found(*keys: str) -> Mock:
    return reply({"issues": [{"id": str(10000 + int(key.split("-")[1])), "key": key} for key in keys], "isLast": True})


def requests(curl: Mock) -> list[tuple[str, str]]:
    return [(call.args[0][call.args[0].index("-X") + 1], call.args[0][-1]) for call in curl.call_args_list]


def sent(curl: Mock, index: int) -> Any:
    return json.loads(curl.call_args_list[index].kwargs["input"])


def test_adds_issues_and_finds_them_in_the_sprint(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    # Given: a key in lower case, and one given twice
    monkeypatch.setattr(sys, "argv", ["jira-sprint-add", "42", "abc-1", "ABC-2", "ABC-1"])
    curl = Mock(side_effect=[sprint(), issue("ABC-1", 10001), issue("ABC-2", 10002), reply(code="204"),
                             found("ABC-1", "ABC-2")])
    monkeypatch.setattr(sprint_add.subprocess, "run", curl)
    # When
    sprint_add.main()
    # Then
    assert capsys.readouterr().out == "204  sprint 42 (Sprint 42)  +ABC-1 +ABC-2\n"
    base = sprint_add.BASE
    assert requests(curl) == [
        ("GET", base + "/rest/agile/1.0/sprint/42"), ("GET", base + "/rest/api/3/issue/ABC-1?fields=*none"),
        ("GET", base + "/rest/api/3/issue/ABC-2?fields=*none"), ("POST", base + "/rest/agile/1.0/sprint/42/issue"),
        ("POST", base + "/rest/api/3/search/jql")]
    assert sent(curl, 3) == {"issues": ["ABC-1", "ABC-2"]}
    assert sent(curl, 4) == {"jql": "sprint = 42 AND key in (ABC-1, ABC-2)", "fields": ["key"], "maxResults": 50,
                             "reconcileIssues": [10001, 10002]}
    assert all("-n" in call.args[0] for call in curl.call_args_list)


@pytest.mark.parametrize("dates,reason", [
    ({"completeDate": "2026-11-25T13:08:09.113Z"},
     "sprint 42 (Sprint 42) closed at 2026-11-25T13:08:09.113Z. Jira adds issues only to an active or future sprint."),
    ({}, "sprint 42 (Sprint 42) closed. Jira adds issues only to an active or future sprint."),
])
def test_closed_sprint_stops_before_any_change(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                               dates: dict[str, str], reason: str) -> None:
    # Given: with and without --dry-run
    for argv in (["42", "ABC-1"], ["42", "ABC-1", "--dry-run"]):
        monkeypatch.setattr(sys, "argv", ["jira-sprint-add", *argv])
        curl = Mock(side_effect=[sprint("closed", **dates)])
        monkeypatch.setattr(sprint_add.subprocess, "run", curl)
        # When
        with pytest.raises(SystemExit) as error:
            sprint_add.main()
        # Then
        assert error.value.code == reason
        assert curl.call_count == 1


def test_names_issues_the_search_doesnt_find(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    curl = Mock(side_effect=[sprint("future"), issue("ABC-1", 10001), issue("ABC-2", 10002), reply(code="204"),
                             found("ABC-1")])
    monkeypatch.setattr(sprint_add.subprocess, "run", curl)
    # When
    with pytest.raises(SystemExit) as error:
        sprint_add.main()
    # Then
    assert error.value.code == "Jira answered 204, but a search doesn't find ABC-2 in sprint 42 (Sprint 42)"
    assert capsys.readouterr().out == "204  sprint 42 (Sprint 42)  +ABC-1\n"


def test_no_result_line_when_the_search_finds_none(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    curl = Mock(side_effect=[sprint(), issue("ABC-1", 10001), issue("ABC-2", 10002), reply(code="204"), found()])
    monkeypatch.setattr(sprint_add.subprocess, "run", curl)
    # When
    with pytest.raises(SystemExit, match="doesn't find ABC-1, ABC-2 in sprint 42"):
        sprint_add.main()
    # Then
    assert capsys.readouterr().out == ""


def test_sends_at_most_50_keys_a_call(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                      capsys: pytest.CaptureFixture[str]) -> None:
    # Given: 51 issues, and the last one moved to another project since its key was copied
    keys = [f"ABC-{n}" for n in range(1, 52)]
    current = [*keys[:50], "XYZ-51"]
    monkeypatch.setattr(sys, "argv", ["jira-sprint-add", "42", *keys])
    curl = Mock(side_effect=[sprint(), *(issue(key, 10000 + n) for n, key in enumerate(current, 1)),
                             reply(code="204"), reply(code="204"), found(*current[:50]), found("XYZ-51")])
    monkeypatch.setattr(sprint_add.subprocess, "run", curl)
    # When
    sprint_add.main()
    # Then
    assert capsys.readouterr().out == "204  sprint 42 (Sprint 42)  " + " ".join(f"+{key}" for key in current) + "\n"
    assert [sent(curl, index) for index in (52, 53)] == [{"issues": current[:50]}, {"issues": ["XYZ-51"]}]
    assert sent(curl, 54)["reconcileIssues"] == list(range(10001, 10051))
    assert sent(curl, 55) == {"jql": "sprint = 42 AND key in (XYZ-51)", "fields": ["key"], "maxResults": 50,
                              "reconcileIssues": [10051]}


def test_failed_call_names_the_keys_earlier_calls_added(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    keys = [f"ABC-{n}" for n in range(1, 52)]
    monkeypatch.setattr(sys, "argv", ["jira-sprint-add", "42", *keys])
    curl = Mock(side_effect=[sprint(), *(issue(key, 10000 + n) for n, key in enumerate(keys, 1)), reply(code="204"),
                             reply({"errorMessages": ["Issue ABC-51 can't be moved"]}, "400")])
    monkeypatch.setattr(sprint_add.subprocess, "run", curl)
    # When
    with pytest.raises(SystemExit) as error:
        sprint_add.main()
    # Then
    assert str(error.value.code).startswith("adding ABC-51 to sprint 42 (Sprint 42): HTTP 400\n")
    assert str(error.value.code).endswith("\nThe calls before it added " + ", ".join(keys[:50]) + ".")
    assert curl.call_count == 54


@pytest.mark.parametrize("answers,reason", [
    ([reply({"errorMessages": ["Sprint does not exist"]}, "404")], "HTTP 404\n.*Sprint does not exist"),
    ([reply({"id": 42})], "HTTP 200: missing sprint state"),
    ([sprint(), reply({"errorMessages": ["Issue does not exist"]}, "404")], "ABC-1: HTTP 404\n.*Issue does not exist"),
    ([sprint(), reply({"key": "ABC-1"})], "ABC-1: HTTP 200: missing issue key or id"),
    ([sprint(), issue("ABC-1", 10001), issue("ABC-2", 10002), reply({"errorMessages": ["rejected"]}, "400")],
     "adding ABC-1, ABC-2 to sprint 42 \\(Sprint 42\\): HTTP 400\n.*rejected"),
    ([sprint(), issue("ABC-1", 10001), issue("ABC-2", 10002), reply(code="204"), reply({"errorMessages": ["bad"]}, "400")],
     "HTTP 400\n.*bad"),
    ([sprint(), issue("ABC-1", 10001), issue("ABC-2", 10002), reply(code="204"), reply({"isLast": True})],
     "HTTP 200: missing issues array"),
    ([Mock(returncode=0, stdout="oops\n200", stderr="")], "HTTP 200: non-JSON response\noops"),
    ([Mock(returncode=7, stdout="\n000", stderr="offline")], "curl failed \\(7\\): offline"),
])
def test_failure_when_jira_answers_unexpectedly(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                answers: list[Mock], reason: str) -> None:
    # Given
    monkeypatch.setattr(sprint_add.subprocess, "run", Mock(side_effect=answers))
    # When
    with pytest.raises(SystemExit) as error:
        sprint_add.main()
    # Then
    assert re.match(reason, str(error.value.code), re.DOTALL)


def test_dry_run_reads_then_prints_the_post(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-sprint-add", "42", "ABC-1", "ABC-2", "--dry-run"])
    curl = Mock(side_effect=[sprint(), issue("ABC-1", 10001), issue("ABC-2", 10002)])
    monkeypatch.setattr(sprint_add.subprocess, "run", curl)
    # When
    sprint_add.main()
    # Then
    assert json.loads(capsys.readouterr().out) == {
        "method": "POST", "endpoint": sprint_add.BASE + "/rest/agile/1.0/sprint/42/issue",
        "payload": {"issues": ["ABC-1", "ABC-2"]}}
    assert [method for method, _ in requests(curl)] == ["GET", "GET", "GET"]


@pytest.mark.parametrize("argv", [["0", "ABC-1"], ["sprint", "ABC-1"], ["42"], ["42", "ABC"], ["42", "ABC-1?x=1"], []])
def test_usage_error_when_arguments_are_wrong(sprint_add: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                              argv: list[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-sprint-add", *argv])
    monkeypatch.setattr(sprint_add.subprocess, "run", Mock(side_effect=AssertionError("no request expected")))
    # When / Then
    with pytest.raises(SystemExit) as error:
        sprint_add.main()
    assert error.value.code == 2


def test_failure_when_site_unset(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.delenv("JIRA_BASE_URL")
    monkeypatch.setattr(sys, "argv", ["jira-sprint-add", "42", "ABC-1"])
    sprint_add = tool("jira-sprint-add")
    # When / Then
    with pytest.raises(SystemExit, match="set JIRA_BASE_URL"):
        sprint_add.main()
