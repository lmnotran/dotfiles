import json
import re
import sys
from collections.abc import Callable
from types import ModuleType
from unittest.mock import Mock

import pytest

BLOCKS = {"id": "10000", "name": "Blocks", "inward": "is blocked by", "outward": "blocks"}
RELATES = {"id": "10003", "name": "Relates", "inward": "relates to", "outward": "relates to"}
CONTAIN = {"id": "10006", "name": "Contain", "inward": "is part of", "outward": "contains"}


@pytest.fixture
def link(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-link", "ABC-1", "Blocks", "ABC-2"])
    return tool("jira-link")


def reply(body: object = None, code: str = "200") -> Mock:
    return Mock(returncode=0, stdout=("" if body is None else json.dumps(body)) + "\n" + code, stderr="")


TYPES = reply({"issueLinkTypes": [BLOCKS, {**RELATES, "self": "https://example.atlassian.net/x"}, CONTAIN]})


def links(key: str, *found: dict) -> Mock:
    return reply({"id": "1", "key": key, "fields": {"issuelinks": list(found)}})


def entry(number: str, kind: dict, side: str, other: str) -> dict:
    return {"id": number, "type": kind, side: {"id": "9", "key": other, "fields": {"summary": "Other issue"}}}


def requests(curl: Mock) -> list[tuple[str, str]]:
    return [(call.args[0][call.args[0].index("-X") + 1], call.args[0][-1]) for call in curl.call_args_list]


def test_links_issues_and_reads_the_link_from_both_sides(link: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    # Given: ABC-1 already has another link, and the new one is listed on both issues
    old = entry("400", RELATES, "outwardIssue", "ABC-9")
    curl = Mock(side_effect=[TYPES, links("ABC-1", old), links("ABC-2"), reply(code="201"),
                             links("ABC-1", old, entry("500", BLOCKS, "outwardIssue", "ABC-2")),
                             links("ABC-2", entry("500", BLOCKS, "inwardIssue", "ABC-1"))])
    monkeypatch.setattr(link.subprocess, "run", curl)
    # When
    link.main()
    # Then
    assert capsys.readouterr().out == "201  ABC-1 blocks ABC-2 | ABC-2 is blocked by ABC-1\n"
    api = link.BASE + "/rest/api/3"
    assert requests(curl) == [
        ("GET", api + "/issueLinkType"), ("GET", api + "/issue/ABC-1?fields=issuelinks"),
        ("GET", api + "/issue/ABC-2?fields=issuelinks"), ("POST", api + "/issueLink"),
        ("GET", api + "/issue/ABC-1?fields=issuelinks"), ("GET", api + "/issue/ABC-2?fields=issuelinks")]
    assert json.loads(curl.call_args_list[3].kwargs["input"]) == {
        "type": {"name": "Blocks"}, "inwardIssue": {"key": "ABC-1"}, "outwardIssue": {"key": "ABC-2"}}
    assert all("-n" in call.args[0] for call in curl.call_args_list)


@pytest.mark.parametrize("wanted,name", [("Blocks", "Blocks"), ("blocks", "Blocks"), ("CONTAINS", "Contain"),
                                         ("relates  to", "Relates"), ("contain", "Contain")])
def test_type_is_a_name_or_an_outward_phrase_ignoring_case(link: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                           capsys: pytest.CaptureFixture[str], wanted: str,
                                                           name: str) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-link", "abc-1", wanted, "ABC-2", "--dry-run"])
    curl = Mock(side_effect=[TYPES, links("ABC-1"), links("ABC-2")])
    monkeypatch.setattr(link.subprocess, "run", curl)
    # When
    link.main()
    # Then
    assert json.loads(capsys.readouterr().out) == {
        "method": "POST", "endpoint": link.BASE + "/rest/api/3/issueLink",
        "payload": {"type": {"name": name}, "inwardIssue": {"key": "ABC-1"}, "outwardIssue": {"key": "ABC-2"}}}
    assert [method for method, _ in requests(curl)] == ["GET", "GET", "GET"]


@pytest.mark.parametrize("wanted,swap", [
    ("Blockz", ""),
    ("is blocked by", "\n'is blocked by' is Blocks read from the other side: jira-link ABC-2 'Blocks' ABC-1"),
])
def test_unknown_type_lists_the_link_types(link: ModuleType, monkeypatch: pytest.MonkeyPatch, wanted: str,
                                           swap: str) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-link", "ABC-1", wanted, "ABC-2"])
    curl = Mock(side_effect=[TYPES])
    monkeypatch.setattr(link.subprocess, "run", curl)
    # When
    with pytest.raises(SystemExit) as error:
        link.main()
    # Then
    assert error.value.code == (
        f"{wanted!r} isn't a link type's name or outward phrase. Jira's link types (name: outward / inward):\n"
        "  Blocks: blocks / is blocked by\n  Relates: relates to / relates to\n  Contain: contains / is part of" + swap)
    assert curl.call_count == 1


@pytest.mark.parametrize("argv,existing,line", [
    (["ABC-1", "Blocks", "ABC-2"], entry("500", BLOCKS, "outwardIssue", "ABC-2"), "skip  ABC-1 blocks ABC-2  already linked"),
    (["ABC-1", "Relates", "ABC-2"], entry("501", RELATES, "inwardIssue", "ABC-2"),
     "skip  ABC-1 relates to ABC-2  already linked"),
])
def test_skips_a_link_that_already_exists(link: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                          capsys: pytest.CaptureFixture[str], argv: list[str], existing: dict,
                                          line: str) -> None:
    # Given: a Relates link reads the same both ways round
    for dry_run in ([], ["--dry-run"]):
        monkeypatch.setattr(sys, "argv", ["jira-link", *argv, *dry_run])
        curl = Mock(side_effect=[TYPES, links("ABC-1", existing), links("ABC-2")])
        monkeypatch.setattr(link.subprocess, "run", curl)
        # When
        link.main()
        # Then
        assert capsys.readouterr().out == line + "\n"
        assert [method for method, _ in requests(curl)] == ["GET", "GET", "GET"]


def test_links_when_only_the_reverse_link_exists(link: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    # Given: ABC-2 blocks ABC-1 already
    reverse = entry("400", BLOCKS, "inwardIssue", "ABC-2")
    curl = Mock(side_effect=[TYPES, links("ABC-1", reverse), links("ABC-2"), reply(code="201"),
                             links("ABC-1", reverse, entry("500", BLOCKS, "outwardIssue", "ABC-2")),
                             links("ABC-2", entry("400", BLOCKS, "outwardIssue", "ABC-1"),
                                   entry("500", BLOCKS, "inwardIssue", "ABC-1"))])
    monkeypatch.setattr(link.subprocess, "run", curl)
    # When
    link.main()
    # Then
    assert capsys.readouterr().out == "201  ABC-1 blocks ABC-2 | ABC-2 is blocked by ABC-1\n"


@pytest.mark.parametrize("after,mirrored,reason", [
    (links("ABC-1", entry("500", BLOCKS, "inwardIssue", "ABC-2")), links("ABC-2", entry("500", BLOCKS, "outwardIssue", "ABC-1")),
     "Jira made link 500 the other way round: ABC-1 is blocked by ABC-2 | ABC-2 blocks ABC-1"),
    (links("ABC-1"), None, "Jira answered 201, but ABC-1 has no new Blocks link to ABC-2"),
    (links("ABC-1", entry("500", RELATES, "outwardIssue", "ABC-2")), None,
     "Jira answered 201, but ABC-1 has no new Blocks link to ABC-2"),
    (links("ABC-1", entry("500", BLOCKS, "outwardIssue", "ABC-2")), links("ABC-2"),
     "Jira answered 201, but ABC-2's links don't show link 500 from ABC-1"),
])
def test_failure_when_the_link_reads_wrong_or_is_missing(link: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str], after: Mock,
                                                         mirrored: Mock | None, reason: str) -> None:
    # Given
    answers = [TYPES, links("ABC-1"), links("ABC-2"), reply(code="201"), after] + ([mirrored] if mirrored else [])
    monkeypatch.setattr(link.subprocess, "run", Mock(side_effect=answers))
    # When
    with pytest.raises(SystemExit) as error:
        link.main()
    # Then
    assert error.value.code == reason
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("answers,reason", [
    ([reply({"errorMessages": ["denied"]}, "401")], "HTTP 401\n.*denied"),
    ([reply({"values": []})], "HTTP 200: missing issueLinkTypes array"),
    ([TYPES, reply({"errorMessages": ["Issue does not exist"]}, "404")], "ABC-1: HTTP 404\n.*does not exist"),
    ([TYPES, links("ABC-1"), reply({"errorMessages": ["Issue does not exist"]}, "404")], "ABC-2: HTTP 404\n"),
    ([TYPES, reply({"key": "ABC-1", "fields": {}})], "ABC-1: HTTP 200: missing issuelinks"),
    ([TYPES, links("ABC-1"), links("ABC-2"), reply({"errorMessages": ["No link type"]}, "404")], "HTTP 404\n.*No link type"),
    ([TYPES, links("ABC-1"), links("ABC-2"), reply(code="200")], "HTTP 200\n"),
    ([Mock(returncode=0, stdout="oops\n200", stderr="")], "HTTP 200: non-JSON response\noops"),
    ([Mock(returncode=6, stdout="\n000", stderr="no host")], "curl failed \\(6\\): no host"),
])
def test_failure_when_jira_answers_unexpectedly(link: ModuleType, monkeypatch: pytest.MonkeyPatch, answers: list[Mock],
                                                reason: str) -> None:
    # Given
    monkeypatch.setattr(link.subprocess, "run", Mock(side_effect=answers))
    # When
    with pytest.raises(SystemExit) as error:
        link.main()
    # Then
    assert re.match(reason, str(error.value.code))


@pytest.mark.parametrize("argv", [["ABC-1", "Blocks", "abc-1"], ["ABC-1", "Blocks"], ["ABC-1", " ", "ABC-2"],
                                  ["ABC", "Blocks", "ABC-2"], ["ABC-1", "Blocks", "ABC-2/remotelink"]])
def test_usage_error_when_arguments_are_wrong(link: ModuleType, monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-link", *argv])
    monkeypatch.setattr(link.subprocess, "run", Mock(side_effect=AssertionError("no request expected")))
    # When / Then
    with pytest.raises(SystemExit) as error:
        link.main()
    assert error.value.code == 2


def test_failure_when_site_unset(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.delenv("JIRA_BASE_URL")
    monkeypatch.setattr(sys, "argv", ["jira-link", "ABC-1", "Blocks", "ABC-2"])
    link = tool("jira-link")
    # When / Then
    with pytest.raises(SystemExit, match="set JIRA_BASE_URL"):
        link.main()
