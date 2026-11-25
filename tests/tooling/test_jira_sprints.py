import json
import sys
from collections.abc import Callable
from types import ModuleType
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.fixture
def sprints(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-sprints", "12"])
    return tool("jira-sprints")


def sprint(number: int, state: str, board: int = 12, **dates: str) -> dict:
    return {"id": number, "self": f"https://example.atlassian.net/rest/agile/1.0/sprint/{number}", "state": state,
            "name": f"Sprint {number}", "originBoardId": board, **dates}


def answer(values: list[dict], last: bool | None = True, start: int = 0) -> object:
    page: dict = {"maxResults": 50, "startAt": start, "values": values}
    if last is not None:
        page["isLast"] = last
    return Mock(returncode=0, stdout=json.dumps(page) + "\n200", stderr="")


def test_pages_and_keeps_the_boards_own_sprints_when_others_share_it(sprints: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                                      capsys: pytest.CaptureFixture[str]) -> None:
    # Given: 50 sprints on the first page, two of them another board's, then a last page with one of each
    first = [sprint(n, "closed", 99 if n in (3, 7) else 12, startDate=f"2025-01-{n % 28 + 1:02d}T08:00:00.000Z",
                    endDate=f"2025-02-{n % 28 + 1:02d}T15:00:00.000Z") for n in range(1, 51)]
    second = [sprint(51, "active", startDate="2026-11-13T08:18:50.779Z", endDate="2026-11-25T15:00:00.000Z"),
              sprint(52, "future", 99), sprint(53, "future")]
    curl = Mock(side_effect=[answer(first, last=False), answer(second, start=50)])
    monkeypatch.setattr(sprints.subprocess, "run", curl)
    # When
    sprints.main()
    # Then
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 50 and lines[0] == "1 | closed | Sprint 1 | 2025-01-02 to 2025-02-02"
    assert lines[-2:] == ["51 | active | Sprint 51 | 2026-11-13 to 2026-11-25", "53 | future | Sprint 53 | - to -"]
    assert not [line for line in lines if line.split(" | ")[0] in ("3", "7", "52")]
    for call, start in zip(curl.call_args_list, ("0", "50"), strict=True):
        command = call.args[0]
        assert "-n" in command and command[command.index("-X") + 1] == "GET"
        url = urlsplit(command[-1])
        assert url.scheme + "://" + url.netloc + url.path == sprints.BASE + "/rest/agile/1.0/board/12/sprint"
        assert parse_qs(url.query) == {"startAt": [start], "maxResults": ["50"], "state": ["active,future,closed"]}


def test_json_and_state_when_asked(sprints: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-sprints", "12", "--state", "active, future", "--json"])
    values = [sprint(51, "active", goal="Ship it"), sprint(52, "future", 99), sprint(53, "future")]
    curl = Mock(return_value=answer(values))
    monkeypatch.setattr(sprints.subprocess, "run", curl)
    # When
    sprints.main()
    # Then
    assert json.loads(capsys.readouterr().out) == [values[0], values[2]]
    assert parse_qs(urlsplit(curl.call_args.args[0][-1]).query)["state"] == ["active,future"]
    assert curl.call_count == 1


@pytest.mark.parametrize("page", [answer([]), answer([], last=False), answer([sprint(1, "closed")], last=None)])
def test_stops_when_jira_has_no_more(sprints: ModuleType, monkeypatch: pytest.MonkeyPatch, page: object) -> None:
    # Given: an empty last page, an empty page that says more come, and a page that doesn't say
    curl = Mock(return_value=page)
    monkeypatch.setattr(sprints.subprocess, "run", curl)
    # When
    sprints.main()
    # Then
    assert curl.call_count == 1


@pytest.mark.parametrize("body,code,reason", [
    ('{"errorMessages":["The board does not support sprints"]}', "400", "HTTP 400\n.*does not support sprints"),
    ("denied", "401", "HTTP 401\ndenied"), ("bad", "200", "non-JSON"), ('{"errorMessages":[]}', "200", "missing values array"),
])
def test_failure_when_api_rejects_request(sprints: ModuleType, monkeypatch: pytest.MonkeyPatch, body: str, code: str,
                                          reason: str) -> None:
    # Given
    monkeypatch.setattr(sprints.subprocess, "run", Mock(return_value=Mock(returncode=0, stdout=body + "\n" + code, stderr="")))
    # When / Then
    with pytest.raises(SystemExit, match=reason):
        sprints.main()


def test_transport_failure_when_curl_fails(sprints: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sprints.subprocess, "run", Mock(return_value=Mock(returncode=7, stdout="\n000", stderr="offline")))
    # When / Then
    with pytest.raises(SystemExit, match="curl failed.*offline"):
        sprints.main()


@pytest.mark.parametrize("argv", [["12", "--state", "done"], ["12", "--state", ","], ["0"], ["board"], []])
def test_usage_error_when_arguments_are_wrong(sprints: ModuleType, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-sprints", *argv])
    monkeypatch.setattr(sprints.subprocess, "run", Mock(side_effect=AssertionError("no request expected")))
    # When / Then
    with pytest.raises(SystemExit) as error:
        sprints.main()
    assert error.value.code == 2


def test_failure_when_site_unset(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.delenv("JIRA_BASE_URL")
    monkeypatch.setattr(sys, "argv", ["jira-sprints", "12"])
    sprints = tool("jira-sprints")
    # When / Then
    with pytest.raises(SystemExit, match="set JIRA_BASE_URL"):
        sprints.main()
