import json
import re
import sys
from collections.abc import Callable
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def move(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-move", "ABC-1", "--to", "In Progress"])
    return tool("jira-move")


def reply(body: object = None, code: str = "200") -> Mock:
    return Mock(returncode=0, stdout=("" if body is None else json.dumps(body)) + "\n" + code, stderr="")


def status(name: str, key: str = "ABC-1") -> Mock:
    return reply({"key": key, "fields": {"status": {"name": name}}})


def transition(number: str, name: str, to: str | None = None) -> dict:
    return {"id": number, "name": name, "to": {"name": to or name}, "isAvailable": True}


OFFERED = reply({"transitions": [transition("11", "To Do"), transition("21", "Start work", "In Progress"),
                                 transition("41", "Blocked")]})


def requests(curl: Mock) -> list[tuple[str, str]]:
    return [(call.args[0][call.args[0].index("-X") + 1], call.args[0][-1]) for call in curl.call_args_list]


def test_moves_issue_and_reads_its_status_back(move: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    # Given: the status is matched ignoring case
    monkeypatch.setattr(sys, "argv", ["jira-move", "abc-1", "--to", "in progress"])
    curl = Mock(side_effect=[status("To Do"), OFFERED, reply(code="204"), status("In Progress")])
    monkeypatch.setattr(move.subprocess, "run", curl)
    # When
    move.main()
    # Then
    assert capsys.readouterr().out == "204  ABC-1  To Do -> In Progress\n"
    issue = move.BASE + "/rest/api/3/issue/ABC-1"
    assert requests(curl) == [("GET", issue + "?fields=status"), ("GET", issue + "/transitions"),
                              ("POST", issue + "/transitions"), ("GET", issue + "?fields=status")]
    assert json.loads(curl.call_args_list[2].kwargs["input"]) == {"transition": {"id": "21"}}
    assert all("-n" in call.args[0] for call in curl.call_args_list)


def test_skips_issue_already_in_status_and_moves_the_rest(move: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                          capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-move", "ABC-1", "ABC-2", "ABC-1", "--to", "In Progress"])
    curl = Mock(side_effect=[status("In Progress"), status("To Do", "ABC-2"), OFFERED, reply(code="204"),
                             status("In Progress", "ABC-2")])
    monkeypatch.setattr(move.subprocess, "run", curl)
    # When
    move.main()
    # Then: ABC-1 is asked about once, and gets no transition
    assert capsys.readouterr().out == "skip  ABC-1  already In Progress\n204  ABC-2  To Do -> In Progress\n"
    assert [method for method, _ in requests(curl)] == ["GET", "GET", "GET", "POST", "GET"]
    assert requests(curl)[3][1].endswith("/rest/api/3/issue/ABC-2/transitions")


def test_names_the_statuses_it_can_reach_and_keeps_going(move: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    # Given: ABC-1 can't reach Done, ABC-2 can
    monkeypatch.setattr(sys, "argv", ["jira-move", "ABC-1", "ABC-2", "--to", "Done"])
    done = reply({"transitions": [transition("31", "Done")]})
    curl = Mock(side_effect=[status("To Do"), OFFERED, status("In Review", "ABC-2"), done, reply(code="204"),
                             status("Done", "ABC-2")])
    monkeypatch.setattr(move.subprocess, "run", curl)
    # When
    with pytest.raises(SystemExit) as error:
        move.main()
    # Then
    assert error.value.code == 1
    out, err = capsys.readouterr()
    assert out == "204  ABC-2  In Review -> Done\n"
    assert err == "ABC-1: no transition goes from To Do to Done. It can move to To Do, In Progress, Blocked.\n"


def test_failure_when_jira_offers_no_transitions(move: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(move.subprocess, "run", Mock(side_effect=[status("Done"), reply({"transitions": []})]))
    # When
    with pytest.raises(SystemExit) as error:
        move.main()
    # Then
    assert error.value.code == 1
    assert capsys.readouterr().err == "ABC-1: no transition goes from Done to In Progress. Jira offers it no transitions.\n"


def test_failure_when_status_read_back_differs(move: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    # Given: a workflow rule sends the issue on to another status
    curl = Mock(side_effect=[status("To Do"), OFFERED, reply(code="204"), status("In Review")])
    monkeypatch.setattr(move.subprocess, "run", curl)
    # When
    with pytest.raises(SystemExit) as error:
        move.main()
    # Then
    assert error.value.code == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert err == "ABC-1: Jira answered 204, but the status reads In Review, not In Progress\n"


@pytest.mark.parametrize("answers,reason", [
    ([reply({"errorMessages": ["Issue does not exist"]}, "404")], "ABC-1: HTTP 404\n.*does not exist"),
    ([status("To Do"), OFFERED, reply({"errors": {"resolution": "required"}}, "400")], "ABC-1: HTTP 400\n.*resolution"),
    ([status("To Do"), OFFERED, reply({}, "200")], "ABC-1: HTTP 200\n"),
    ([reply({"fields": {}})], "ABC-1: HTTP 200: missing status"),
    ([status("To Do"), reply({"values": []})], "ABC-1: HTTP 200: missing transitions array"),
    ([status("To Do"), reply({"transitions": [{"name": "Start", "to": {"name": "In Progress"}}]})],
     "ABC-1: HTTP 200: the transition to In Progress has no id"),
    ([Mock(returncode=0, stdout="oops\n200", stderr="")], "ABC-1: HTTP 200: non-JSON response\noops"),
    ([Mock(returncode=7, stdout="\n000", stderr="offline")], "ABC-1: curl failed \\(7\\): offline"),
])
def test_failure_when_jira_answers_unexpectedly(move: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str], answers: list[Mock],
                                                reason: str) -> None:
    # Given
    monkeypatch.setattr(move.subprocess, "run", Mock(side_effect=answers))
    # When
    with pytest.raises(SystemExit) as error:
        move.main()
    # Then
    assert error.value.code == 1
    assert re.match(reason, capsys.readouterr().err)


def test_dry_run_reads_then_prints_the_post(move: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    # Given: two transitions end in Done, and the one named Done wins
    monkeypatch.setattr(sys, "argv", ["jira-move", "ABC-1", "--to", "Done", "--dry-run"])
    offered = reply({"transitions": [transition("51", "Won't do", "Done"), transition("31", "Done")]})
    curl = Mock(side_effect=[status("In Progress"), offered])
    monkeypatch.setattr(move.subprocess, "run", curl)
    # When
    move.main()
    # Then
    assert json.loads(capsys.readouterr().out) == {
        "method": "POST", "endpoint": move.BASE + "/rest/api/3/issue/ABC-1/transitions",
        "payload": {"transition": {"id": "31"}}}
    assert [method for method, _ in requests(curl)] == ["GET", "GET"]


@pytest.mark.parametrize("argv", [["ABC-1"], ["--to", "Done"], ["ABC", "--to", "Done"], ["1-ABC", "--to", "Done"],
                                  ["ABC-1/x", "--to", "Done"], ["ABC-1", "--to", " "]])
def test_usage_error_when_arguments_are_wrong(move: ModuleType, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-move", *argv])
    monkeypatch.setattr(move.subprocess, "run", Mock(side_effect=AssertionError("no request expected")))
    # When / Then
    with pytest.raises(SystemExit) as error:
        move.main()
    assert error.value.code == 2


def test_failure_when_site_unset(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.delenv("JIRA_BASE_URL")
    monkeypatch.setattr(sys, "argv", ["jira-move", "ABC-1", "--to", "Done"])
    move = tool("jira-move")
    # When / Then
    with pytest.raises(SystemExit, match="set JIRA_BASE_URL"):
        move.main()
