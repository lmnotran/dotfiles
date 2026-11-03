import io
import json
import subprocess
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def queue(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-queue-times")


def params_of(cmd: list[str]) -> dict[str, str]:
    return dict(cmd[i + 1].split("=", 1) for i, part in enumerate(cmd) if part == "-f")


def run(run_id: int, created: str, status: str = "completed", attempt: int = 1) -> dict[str, object]:
    return {"id": run_id, "created_at": created, "status": status, "run_attempt": attempt, "event": "push", "head_branch": "feature"}


def job(job_id: int, created: str, started: str | None, *, labels: list[str], runner: str | None = "runner-1",
        conclusion: str = "success", status: str = "completed", attempt: int = 1, name: str = "Tests / FDK") -> dict[str, object]:
    return {"id": job_id, "run_id": 7, "run_attempt": attempt, "name": name, "status": status, "conclusion": conclusion,
            "created_at": created, "started_at": started, "completed_at": started, "labels": labels,
            "runner_name": runner, "head_branch": "feature", "html_url": f"https://example.test/job/{job_id}"}


def test_list_runs_when_range_exceeds_cap(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the whole range is over GitHub's 1,000-run cap, each half fits, and one run shows up in both halves
    by_range = {
        "2026-05-01..2026-05-04": {"total_count": 1500, "workflow_runs": []},
        "2026-05-01..2026-05-02": {"total_count": 2, "workflow_runs": [run(2, "2026-05-02T00:00:00Z"), run(1, "2026-05-01T00:00:00Z")]},
        "2026-05-03..2026-05-04": {"total_count": 2, "workflow_runs": [run(3, "2026-05-03T00:00:00Z"), run(2, "2026-05-02T00:00:00Z")]},
    }
    calls: list[dict[str, str]] = []

    def gh(cmd: list[str], **_: object) -> str:
        calls.append(params_of(cmd))
        return json.dumps(by_range[params_of(cmd)["created"]])

    monkeypatch.setattr(queue.subprocess, "check_output", gh)
    # When
    runs = queue.list_runs("a/b", "wf.yml", date(2026, 5, 1), date(2026, 5, 4), "push", None)
    # Then
    assert [r["id"] for r in runs] == [1, 2, 3]
    assert {c["created"] for c in calls} == set(by_range)
    assert all(c["event"] == "push" and c["exclude_pull_requests"] == "true" for c in calls)


def test_list_runs_when_results_span_pages(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: 150 runs, so a second page of 100
    pages = {"1": [run(i, f"2026-05-01T00:{i % 60:02d}:00Z") for i in range(100)],
             "2": [run(i, f"2026-05-01T01:{i % 60:02d}:00Z") for i in range(100, 150)]}

    def gh(cmd: list[str], **_: object) -> str:
        page = params_of(cmd)["page"]
        return json.dumps({"total_count": 150, "workflow_runs": pages[page]})

    monkeypatch.setattr(queue.subprocess, "check_output", gh)
    # When
    runs = queue.list_runs("a/b", "1", date(2026, 5, 1), date(2026, 5, 1), None, None)
    # Then
    assert len(runs) == 150


def test_fetch_jobs_when_finished_run_is_cached(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a finished run whose jobs include fields the cache doesn't keep
    raw = job(11, "2026-05-01T00:00:00Z", "2026-05-01T00:00:30Z", labels=["self-hosted", "HW4", "FDK"]) | {"steps": [{"name": "x"}]}
    api = Mock(return_value=json.dumps(raw) + "\n")
    monkeypatch.setattr(queue.subprocess, "check_output", api)
    cache = queue.cache_dir("a/b")
    # When
    jobs, cached = queue.fetch_jobs("a/b", run(7, "2026-05-01T00:00:00Z"), cache, refresh=False)
    monkeypatch.setattr(queue.subprocess, "check_output", Mock(side_effect=AssertionError("cache not used")))
    again, cached_again = queue.fetch_jobs("a/b", run(7, "2026-05-01T00:00:00Z"), cache, refresh=False)
    # Then
    assert api.call_args.args[0][:5] == ["gh", "api", "-X", "GET", "repos/a/b/actions/runs/7/attempts/1/jobs"]
    assert params_of(api.call_args.args[0]) == {"per_page": "100"}
    assert (cached, cached_again) == (False, True)
    assert again == jobs and "steps" not in jobs[0]
    assert (cache / "7-1.json").exists()


def test_fetch_jobs_when_run_was_rerun(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a run on its third attempt, with a blank line in one response
    def gh(cmd: list[str], **_: object) -> str:
        attempt = int(cmd[4].split("/attempts/")[1].split("/")[0])
        return json.dumps(job(attempt, "2026-05-01T00:00:00Z", "2026-05-01T00:00:01Z", labels=["self-hosted", "HW4"], attempt=attempt)) + "\n\n"

    monkeypatch.setattr(queue.subprocess, "check_output", gh)
    # When
    jobs, _ = queue.fetch_jobs("a/b", run(7, "2026-05-01T00:00:00Z", attempt=3), queue.cache_dir("a/b"), refresh=False)
    # Then
    assert [j["run_attempt"] for j in jobs] == [1, 2, 3]
    assert (queue.cache_dir("a/b") / "7-3.json").exists()


def test_fetch_jobs_when_run_still_going_is_not_cached(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(queue.subprocess, "check_output", Mock(return_value=""))
    cache = queue.cache_dir("a/b")
    # When
    queue.fetch_jobs("a/b", run(8, "2026-05-01T00:00:00Z", status="in_progress"), cache, refresh=False)
    # Then
    assert not (cache / "8-1.json").exists()


def test_records_when_skipped_queued_and_never_ran(queue: ModuleType) -> None:
    # Given
    the_run = run(7, "2026-05-01T00:00:00Z")
    pairs = [
        (the_run, job(1, "2026-05-01T00:00:00Z", "2026-05-01T00:01:30Z", labels=["self-hosted", "HW4", "FDK"])),
        (the_run, job(2, "2026-05-01T00:00:00Z", "2026-05-01T00:00:00Z", labels=["self-hosted", "HW4", "FDK"], conclusion="skipped")),
        (the_run, job(3, "2026-05-01T00:00:00Z", None, labels=["self-hosted", "HW4", "FDK"], status="queued", conclusion="")),
        (the_run, job(4, "2026-05-01T00:00:00Z", "2026-05-01T00:20:00Z", labels=["self-hosted", "HW4", "FDK"], runner=None, conclusion="cancelled")),
        (the_run, job(5, "2026-05-01T00:00:00Z", "2026-05-01T00:00:05Z", labels=["ubuntu-24.04"])),
        (the_run, job(6, "2026-05-01T00:00:00Z", "2026-05-01T00:00:09Z", labels=["self-hosted", "HW4", "FDK"], attempt=2)),
    ]
    # When
    hardware = queue.to_records(pairs, "HW4", None, first_attempt=True)
    # Then
    assert [r.job_id for r in hardware] == [1, 4]
    assert hardware[0].queue_seconds == 90.0 and hardware[0].got_runner
    assert hardware[1].queue_seconds is None and not hardware[1].got_runner


def test_summary_when_grouped_by_week(queue: ModuleType) -> None:
    # Given: waits of 10, 20, 30, 40 and 600 seconds in one week, one more in the next week, and a job that never ran
    the_run = run(7, "2026-05-04T00:00:00Z")
    waits = [10, 20, 30, 40, 600]
    pairs = [(the_run, job(i, "2026-05-05T00:00:00Z", f"2026-05-05T00:{w // 60:02d}:{w % 60:02d}Z", labels=["self-hosted", "HW4"]))
             for i, w in enumerate(waits)]
    pairs.append((the_run, job(9, "2026-05-12T10:00:00Z", "2026-05-12T10:00:03Z", labels=["self-hosted", "HW4"])))
    pairs.append((the_run, job(10, "2026-05-06T00:00:00Z", "2026-05-06T00:30:00Z", labels=["self-hosted", "HW4"], runner=None, conclusion="cancelled")))
    # When
    summaries = queue.summarize(queue.to_records(pairs, None, None, first_attempt=False), "week")
    # Then
    assert [(s.period, s.jobs, s.median_seconds, s.p90_seconds, s.max_seconds, s.never_ran) for s in summaries] == [
        ("2026-05-04", 5, 30.0, 600.0, 600.0, 1),
        ("2026-05-11", 1, 3.0, 3.0, 3.0, 0),
    ]


def server_error(stderr: str) -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(1, ["gh"], stderr=stderr)


def test_gh_api_when_server_error_clears(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: one 502, then a good response
    api = Mock(side_effect=[server_error("gh: Server Error (HTTP 502)\n"), "ok"])
    monkeypatch.setattr(queue.subprocess, "check_output", api)
    sleep = Mock()
    monkeypatch.setattr(queue.time, "sleep", sleep)
    # When
    out = queue.gh_api("repos/a/b/actions/runs/7/jobs")
    # Then
    assert out == "ok"
    sleep.assert_called_once_with(10)


@pytest.mark.parametrize("stderr", ["gh: Not Found (HTTP 404)\n", ""])
def test_gh_api_when_error_is_permanent(queue: ModuleType, monkeypatch: pytest.MonkeyPatch, stderr: str) -> None:
    # Given
    monkeypatch.setattr(queue.subprocess, "check_output", Mock(side_effect=server_error(stderr)))
    sleep = Mock()
    monkeypatch.setattr(queue.time, "sleep", sleep)
    # When / Then
    with pytest.raises(SystemExit, match="Not Found|exit code 1"):
        queue.gh_api("repos/a/b/actions/workflows/9/runs")
    sleep.assert_not_called()


def test_gh_api_when_retries_run_out(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: a secondary rate limit that never clears
    api = Mock(side_effect=server_error("gh: You have exceeded a secondary rate limit (HTTP 403)\n"))
    monkeypatch.setattr(queue.subprocess, "check_output", api)
    sleep = Mock()
    monkeypatch.setattr(queue.time, "sleep", sleep)
    # When / Then
    with pytest.raises(SystemExit, match="secondary rate limit"):
        queue.gh_api("rate_limit")
    assert [c.args[0] for c in sleep.call_args_list] == [10, 30, 90, 270]
    assert api.call_count == 5


def test_rate_limit_when_nearly_used_up(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(queue.subprocess, "check_output", Mock(return_value=json.dumps({"resources": {"core": {"remaining": 10, "reset": 1060}}})))
    monkeypatch.setattr(queue.time, "time", Mock(return_value=1000.0))
    sleep = Mock()
    monkeypatch.setattr(queue.time, "sleep", sleep)
    # When
    queue.wait_for_rate_limit()
    # Then
    sleep.assert_called_once_with(65.0)


def test_cli_json_and_csv_when_label_filtered(queue: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Given
    jobs = [job(1, "2026-05-01T00:00:00Z", "2026-05-01T00:02:00Z", labels=["self-hosted", "HW4", "FDK"]),
            job(2, "2026-05-01T00:00:00Z", "2026-05-01T00:00:04Z", labels=["ubuntu-24.04"])]

    def gh(cmd: list[str], **_: object) -> str:
        path = cmd[4]
        if path == "rate_limit":
            return json.dumps({"resources": {"core": {"remaining": 5000, "reset": 0}}})
        if path.endswith("/runs"):
            return json.dumps({"total_count": 1, "workflow_runs": [run(7, "2026-05-01T00:00:00Z")]})
        return "\n".join(json.dumps(j) for j in jobs)

    monkeypatch.setattr(queue.subprocess, "check_output", gh)
    out_csv = tmp_path / "jobs.csv"
    monkeypatch.setattr(sys, "argv", ["gh-queue-times", "-R", "a/b", "--workflow", "7", "--since", "2026-05-01",
                                      "--until", "2026-05-01", "--label", "HW4", "--json", "--workers", "1", "--csv", str(out_csv)])
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    # When
    queue.main()
    # Then
    assert json.loads(output.getvalue()) == [{"labels": "self-hosted,HW4,FDK", "period": "2026-05", "jobs": 1, "median_seconds": 120.0,
                                              "p90_seconds": 120.0, "max_seconds": 120.0, "never_ran": 0}]
    rows = out_csv.read_text().splitlines()
    assert rows[0].startswith("run_id,run_attempt,event,branch,job_id")
    assert len(rows) == 2 and ",120," in rows[1]


def test_cli_when_since_after_until(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-queue-times", "-R", "a/b", "--workflow", "7", "--since", "2026-06-01", "--until", "2026-05-01"])
    # When / Then
    with pytest.raises(SystemExit, match="is after --until"):
        queue.main()


def test_cli_when_repo_malformed(queue: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-queue-times", "-R", "not a repo", "--workflow", "7", "--since", "2026-05-01", "--until", "2026-05-01"])
    # When / Then
    with pytest.raises(SystemExit, match="OWNER/REPO"):
        queue.main()
