import json
import sys
import urllib.error
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from types import ModuleType
from typing import Any
from unittest.mock import Mock, call

import pytest

NOW = datetime(2026, 11, 4, 18, 30, tzinfo=timezone.utc)
ACTIONS_UPDATES = (
    ("2026-11-04T17:40:33.887Z", "investigating", "We are investigating reports of degraded availability for Actions"),
    ("2026-11-04T18:07:51.114Z", "monitoring", "The degradation affecting Actions has been mitigated.\n\nWe are monitoring."),
)


@pytest.fixture
def incidents(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-incidents")


def incident(name: str, posted: str, resolved: str | None = None,
             updates: tuple[tuple[str, str, str], ...] = ()) -> dict[str, Any]:
    """An incident as githubstatus.com sends it, newest update first."""
    return {
        "id": "x1", "name": name, "impact": "major", "status": "resolved" if resolved else "monitoring",
        "created_at": posted, "started_at": posted, "resolved_at": resolved, "shortlink": "https://stspg.io/x1",
        "components": [{"name": "Actions", "status": "operational"}],
        "incident_updates": [{"status": status, "body": body, "created_at": at, "display_at": at}
                             for at, status, body in reversed(updates)],
    }


def summary(*open_incidents: dict[str, Any], indicator: str = "none", actions: str = "operational") -> dict[str, Any]:
    description = "All Systems Operational" if indicator == "none" else "Minor Service Outage"
    return {
        "status": {"indicator": indicator, "description": description},
        "components": [{"name": "Git Operations", "status": "operational"}, {"name": "Actions", "status": actions}],
        "incidents": list(open_incidents),
    }


def run(module: ModuleType, monkeypatch: pytest.MonkeyPatch, feeds: dict[str, dict[str, Any]], *args: str) -> tuple[int, Mock]:
    fetch = Mock(side_effect=lambda feed: feeds[feed])
    monkeypatch.setattr(module, "fetch", fetch)
    monkeypatch.setattr(sys, "argv", ["gh-incidents", *args])
    with pytest.raises(SystemExit) as exit_info:
        module.main()
    return int(exit_info.value.code or 0), fetch


def test_cli_when_nothing_is_open(incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given / When
    code, fetch = run(incidents, monkeypatch, {"summary": summary()})
    # Then
    assert code == 0
    assert fetch.call_args_list == [call("summary")]
    assert capsys.readouterr().out.startswith("GitHub status now: All Systems Operational\nNo incidents open.\n")


def test_cli_when_an_incident_is_open_while_every_component_is_operational(
        incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    feeds = {"summary": summary(incident("Incident with Actions", "2026-11-04T17:40:33.675Z", updates=ACTIONS_UPDATES))}
    # When
    code, _ = run(incidents, monkeypatch, feeds)
    # Then
    assert code == 1
    assert capsys.readouterr().out.splitlines() == [
        "GitHub status now: All Systems Operational",
        "1 incident open:",
        "",
        "MAJOR  Incident with Actions [Actions]",
        "  posted 2026-11-04 17:40Z, open (monitoring)  https://stspg.io/x1",
        "  17:40Z investigating: We are investigating reports of degraded availability for Actions",
        "  18:07Z monitoring: The degradation affecting Actions has been mitigated. We are monitoring.",
    ]


def test_cli_since_when_incidents_end_before_during_and_after_the_range(
        incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    history = {"incidents": [
        incident("Retroactive, ended before since", "2026-11-04T18:20:00Z", "2026-11-04T17:10:00Z"),
        incident("Retroactive, ended after since", "2026-11-04T18:10:00Z", "2026-11-04T17:50:00Z"),
        incident("Open", "2026-11-04T18:00:00Z"),
        incident("Resolved after since", "2026-11-04T17:00:00Z", "2026-11-04T17:45:00Z"),
        incident("Resolved before since", "2026-11-04T16:05:00Z", "2026-11-04T17:01:00Z"),
    ]}
    # When
    code, _ = run(incidents, monkeypatch, {"summary": summary(), "incidents": history}, "--since", "2026-11-04T17:30Z")
    # Then
    assert code == 1
    assert [line for line in capsys.readouterr().out.splitlines() if line.startswith(("3 ", "MAJOR", "  posted"))] == [
        "3 incidents open or resolved since 2026-11-04 17:30Z:",
        "MAJOR  Resolved after since [Actions]",
        "  posted 2026-11-04 17:00Z, resolved 17:45Z  https://stspg.io/x1",
        "MAJOR  Open [Actions]",
        "  posted 2026-11-04 18:00Z, open (monitoring)  https://stspg.io/x1",
        "MAJOR  Retroactive, ended after since [Actions]",
        "  posted 2026-11-04 18:10Z, resolved 17:50Z  https://stspg.io/x1",
    ]


def test_cli_when_a_component_is_not_operational(incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given / When
    code, _ = run(incidents, monkeypatch, {"summary": summary(indicator="minor", actions="partial_outage")})
    # Then
    assert code == 1
    assert capsys.readouterr().out.splitlines()[:2] == [
        "GitHub status now: Minor Service Outage", "Not operational: Actions (partial outage)"]


@pytest.mark.parametrize("value, expected", [
    ("90m", NOW - timedelta(minutes=90)),
    ("2d", NOW - timedelta(days=2)),
    ("2026-11-04T17:22Z", datetime(2026, 11, 4, 17, 22, tzinfo=timezone.utc)),
    ("2026-11-04", datetime(2026, 11, 4, tzinfo=timezone.utc)),
    ("2026-11-04T12:22-05:00", datetime(2026, 11, 4, 17, 22, tzinfo=timezone.utc)),
])
def test_parse_time_when_time_or_duration(incidents: ModuleType, value: str, expected: datetime) -> None:
    # Given / When
    parsed = incidents.parse_time(value, NOW)
    # Then
    assert (parsed, parsed.utcoffset()) == (expected, timedelta(0))


@pytest.mark.parametrize("value", ["yesterday", "6w", "2026-13-01"])
def test_parse_time_when_unusable(incidents: ModuleType, value: str) -> None:
    # Given / When / Then
    with pytest.raises(ValueError):
        incidents.parse_time(value, NOW)


@pytest.mark.parametrize("value", ["yesterday", "2999-01-01"])
def test_cli_when_since_is_unusable_or_in_the_future(incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    # Given / When
    code, fetch = run(incidents, monkeypatch, {}, "--since", value)
    # Then
    assert code == 2
    fetch.assert_not_called()


def test_cli_when_since_predates_the_feed(incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    history = {"incidents": [incident("Oldest", "2026-08-26T22:56:31Z", "2026-08-26T23:30:00Z")]}
    # When
    run(incidents, monkeypatch, {"summary": summary(), "incidents": history}, "--since", "2026-08-01")
    # Then
    assert "back to 2026-08-26 22:56Z" in capsys.readouterr().err


def test_cli_json_when_since(incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    history = {"incidents": [incident("Incident with Actions", "2026-11-04T17:40:33.675Z", updates=ACTIONS_UPDATES)]}
    # When
    code, _ = run(incidents, monkeypatch, {"summary": summary(), "incidents": history}, "--since", "2026-11-04T17:30Z", "--json")
    # Then
    data = json.loads(capsys.readouterr().out)
    assert code == 1
    assert (data["since"], data["affected"], data["incidents"][0]["resolved"]) == ("2026-11-04T17:30:00Z", [], None)
    assert [(update["at"], update["status"]) for update in data["incidents"][0]["updates"]] == [
        ("2026-11-04T17:40:33Z", "investigating"), ("2026-11-04T18:07:51Z", "monitoring")]


def test_cli_when_githubstatus_is_unreachable(incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(incidents.urllib.request, "urlopen", Mock(side_effect=urllib.error.URLError("timed out")))
    monkeypatch.setattr(sys, "argv", ["gh-incidents"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        incidents.main()
    # Then
    assert exit_info.value.code == 3
    assert capsys.readouterr().err == (
        "gh-incidents: can't read https://www.githubstatus.com/api/v2/summary.json: <urlopen error timed out>\n")


def test_cli_when_githubstatus_answers_unexpectedly(incidents: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given / When
    code, _ = run(incidents, monkeypatch, {"summary": {"status": {"indicator": "none"}}})
    # Then
    assert code == 3
    assert capsys.readouterr().err.startswith("gh-incidents: unexpected answer from https://www.githubstatus.com: KeyError(")
