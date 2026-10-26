import json
import sys
from collections.abc import Callable
from types import ModuleType
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.fixture
def search(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-search", 'project = TEST AND summary ~ "A & B"'])
    return tool("jira-search")


def test_pagination_when_multiple_pages(search: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    first = {"key": "TEST-1", "fields": {"summary": "First", "status": {"name": "Open"}, "issuetype": {"name": "Task"},
             "parent": {"key": "TEST-99"}, "assignee": {"displayName": "Mason"}}}
    second = {"key": "TEST-2", "fields": {"summary": "Second\nline", "status": {"name": "Done"}, "issuetype": {"name": "Bug"},
              "parent": None, "assignee": None}}
    pages = [{"issues": [first], "nextPageToken": "a + / &", "isLast": False}, {"issues": [second], "isLast": True}]
    curl = Mock(side_effect=[search.subprocess.CompletedProcess([], 0, stdout=json.dumps(page) + "\n200") for page in pages])
    monkeypatch.setattr(search.subprocess, "run", curl)
    # When
    search.main()
    # Then
    assert capsys.readouterr().out.splitlines() == ["TEST-1 | Task | Open | TEST-99 | Mason | First",
                                                 "TEST-2 | Bug | Done |  | (unassigned) | Second line"]
    assert curl.call_count == 2
    for index, call in enumerate(curl.call_args_list):
        command = call.args[0]
        assert "-n" in command
        assert command[command.index("-X") + 1] == "GET"
        url = urlsplit(command[-1])
        assert url.scheme + "://" + url.netloc + url.path == search.BASE + "/rest/api/3/search/jql"
        params = parse_qs(url.query)
        assert params["jql"] == ['project = TEST AND summary ~ "A & B"']
        assert params["fields"] == ["summary,status,issuetype,parent,assignee"]
        assert params["maxResults"] == [str(100 - index)]
        assert params.get("nextPageToken") == (["a + / &"] if index else None)


def test_json_when_max_reached(search: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-search", "project = TEST", "--max", "2", "--fields", "summary", "--json"])
    issues = [{"key": f"TEST-{number}", "extra": number} for number in range(3)]
    curl = Mock(return_value=search.subprocess.CompletedProcess([], 0, stdout=json.dumps({"issues": issues, "nextPageToken": "unused"}) + "\n200"))
    monkeypatch.setattr(search.subprocess, "run", curl)
    # When
    search.main()
    # Then
    assert json.loads(capsys.readouterr().out) == issues[:2]
    params = parse_qs(urlsplit(curl.call_args.args[0][-1]).query)
    assert params["maxResults"] == ["2"]
    assert params["fields"] == ["summary"]
    assert curl.call_count == 1


@pytest.mark.parametrize("page", [{"issues": [], "isLast": True}, {"issues": []}])
def test_empty_when_no_results(search: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], page: dict) -> None:
    # Given
    curl = Mock(return_value=search.subprocess.CompletedProcess([], 0, stdout=json.dumps(page) + "\n200"))
    monkeypatch.setattr(search.subprocess, "run", curl)
    # When
    search.main()
    # Then
    assert capsys.readouterr().out == ""
    assert curl.call_count == 1


@pytest.mark.parametrize("body,code,reason", [('denied', "401", "HTTP 401\ndenied"), ('bad', "200", "non-JSON"),
                                            ('{"errorMessages":["bad"]}', "200", "missing issues array")])
def test_failure_when_api_rejects_request(search: ModuleType, monkeypatch: pytest.MonkeyPatch, body: str, code: str, reason: str) -> None:
    # Given
    monkeypatch.setattr(search.subprocess, "run", Mock(return_value=search.subprocess.CompletedProcess([], 0, stdout=body + "\n" + code)))
    # When / Then
    with pytest.raises(SystemExit, match=reason):
        search.main()


def test_failure_when_token_repeats(search: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    page = {"issues": [], "isLast": False, "nextPageToken": "same"}
    curl = Mock(return_value=search.subprocess.CompletedProcess([], 0, stdout=json.dumps(page) + "\n200"))
    monkeypatch.setattr(search.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match="repeated nextPageToken"):
        search.main()
    assert curl.call_count == 2


def test_failure_when_max_invalid(search: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-search", "key = TEST-1", "--max", "0"])
    # When / Then
    with pytest.raises(SystemExit) as error:
        search.main()
    assert error.value.code == 2


def test_transport_failure_when_curl_fails(search: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(search.subprocess, "run", Mock(return_value=search.subprocess.CompletedProcess([], 7, stdout="\n000", stderr="offline")))
    # When / Then
    with pytest.raises(SystemExit, match="curl failed.*offline"):
        search.main()
