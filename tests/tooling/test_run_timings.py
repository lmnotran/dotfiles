import io
import json
import sys
from collections.abc import Callable
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def timing(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-run-timings")


@pytest.mark.parametrize("seconds, expected", [(None, "-"), (0, "0s"), (59.6, "1m00s"), (61, "1m01s"), (3661, "1h01m")])
def test_duration_when_crossing_units(timing: ModuleType, seconds: float | None, expected: str) -> None:
    # Given / When / Then
    assert timing.fmt_duration(seconds) == expected


@pytest.mark.parametrize("attempt", [None, 3])
def test_fetch_jobs_when_paginated_attempt_requested(timing: ModuleType, monkeypatch: pytest.MonkeyPatch, attempt: int | None) -> None:
    # Given
    api = Mock(return_value='{"id":1,"name":"parent / child"}\n\n{"id":2,"name":"other"}\n')
    monkeypatch.setattr(timing.subprocess, "check_output", api)
    # When
    jobs = timing.fetch_jobs("repos/o/r", "42", attempt)
    # Then
    suffix = "" if attempt is None else "/attempts/3"
    assert api.call_args.args[0] == ["gh", "api", f"repos/o/r/actions/runs/42{suffix}/jobs", "--paginate", "--jq", ".jobs[]"]
    assert [job["id"] for job in jobs] == [1, 2]


def test_json_cli_when_filter_sort_top_applied(timing: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    jobs = [
        {"id": 1, "name": "build / slow", "created_at": "2026-01-01T00:00:00Z", "started_at": "2026-01-01T00:00:10Z", "completed_at": "2026-01-01T00:02:10Z", "conclusion": "success"},
        {"id": 2, "name": "build / queued", "status": "queued"},
        {"id": 3, "name": "unrelated", "started_at": "2026-01-01T00:00:00Z", "completed_at": "2026-01-01T01:00:00Z"},
    ]
    api = Mock(return_value="\n".join(json.dumps(job) for job in jobs))
    monkeypatch.setattr(timing.subprocess, "check_output", api)
    monkeypatch.setattr(sys, "argv", ["gh-run-timings", "https://github.com/a/b/actions/runs/42", "--pattern", "build /", "--sort", "duration", "--top", "1", "--json"])
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    # When
    timing.main()
    # Then: the run URL's repository, not the current clone's.
    assert api.call_args.args[0][2] == "repos/a/b/actions/runs/42/jobs"
    assert json.loads(output.getvalue()) == [{"id": 1, "name": "build / slow", "queue_seconds": 10.0, "run_seconds": 120.0, "status": "success", "started_at": "2026-01-01T00:00:10+00:00", "completed_at": "2026-01-01T00:02:10+00:00", "url": None}]


def test_step_table_when_steps_skipped(timing: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    jobs = [{"name": "build", "started_at": "2026-01-01T00:00:00Z", "completed_at": "2026-01-01T00:01:00Z", "steps": [
        {"number": 1, "name": "compile", "started_at": "2026-01-01T00:00:10Z", "completed_at": "2026-01-01T00:00:20Z", "conclusion": "success"},
        {"number": 2, "name": "omitted", "conclusion": "skipped"},
    ]}]
    monkeypatch.setattr(timing.subprocess, "check_output", Mock(return_value=json.dumps(jobs[0])))
    monkeypatch.setattr(sys, "argv", ["gh-run-timings", "42", "--steps"])
    # When
    timing.main()
    # Then
    output = capsys.readouterr().out
    assert "compile" in output and "10s" in output
    assert "omitted" not in output
    assert "wall-clock (first start → last end): 1m00s" in output


def test_empty_filter_when_no_jobs_match(timing: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(timing.subprocess, "check_output", Mock(return_value='{"name":"build"}'))
    monkeypatch.setattr(sys, "argv", ["gh-run-timings", "42", "--pattern", "missing"])
    # When / Then
    with pytest.raises(SystemExit) as error:
        timing.main()
    assert error.value.code == 1


@pytest.mark.parametrize("arg, repo, expected", [
    ("42", None, ("repos/{owner}/{repo}", "42")),
    ("42", "o/r", ("repos/o/r", "42")),
    ("https://github.com/o/r/actions/runs/42", None, ("repos/o/r", "42")),
    ("https://github.com/o/r/actions/runs/42/job/7#step:3:9", None, ("repos/o/r", "42")),
    ("github.com/o/r.js/actions/runs/42/attempts/2", "O/R.JS", ("repos/o/r.js", "42")),
])
def test_run_target_when_id_or_url(timing: ModuleType, arg: str, repo: str | None, expected: tuple[str, str]) -> None:
    # Given / When / Then
    assert timing.run_target(arg, repo) == expected


@pytest.mark.parametrize("arg, repo, message", [
    ("https://github.com/a/b/pull/42", None, "can't parse run id"),
    ("https://github.com/a/b/actions/runs/42", "c/d", "conflicts with the run URL's repository, a/b"),
    ("42", "not-a-repo", "--repo must be OWNER/REPO"),
])
def test_run_target_when_invalid(timing: ModuleType, arg: str, repo: str | None, message: str) -> None:
    # Given / When / Then
    with pytest.raises(SystemExit, match=message):
        timing.run_target(arg, repo)


@pytest.mark.parametrize("argv, where", [(["42"], "the current repository"), (["42", "-R", "o/r"], "o/r")])
def test_hint_when_run_lookup_fails(timing: ModuleType, monkeypatch: pytest.MonkeyPatch, argv: list[str], where: str) -> None:
    # Given
    monkeypatch.setattr(timing.subprocess, "check_output", Mock(side_effect=timing.subprocess.CalledProcessError(1, ["gh"])))
    monkeypatch.setattr(sys, "argv", ["gh-run-timings", *argv])
    # When / Then
    with pytest.raises(SystemExit, match=f"run 42's jobs in {where}.*pass its URL or -R OWNER/REPO"):
        timing.main()
