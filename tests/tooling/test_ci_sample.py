import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def ci(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("ci-sample")


@pytest.mark.parametrize("branch", ["main", "master", "HEAD"])
def test_cleanup_when_branch_is_protected(ci: ModuleType, monkeypatch: pytest.MonkeyPatch, branch: str) -> None:
    # Given
    read = Mock(return_value=branch)
    monkeypatch.setattr(ci.subprocess, "check_output", read)
    monkeypatch.setattr(sys, "argv", ["ci-sample", "--cleanup", "--dry-run"])
    # When / Then
    with pytest.raises(SystemExit, match="refusing to operate"):
        ci.main()
    assert read.call_count == 1


def test_cleanup_dry_run_when_trigger_commits_exist(ci: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(ci.subprocess, "check_output", Mock(side_effect=[
        "feature/test", "aaa TEST: trigger CI sample 2/2\nbbb TEST: trigger CI sample 1/2\nccc CI_CD: real change", "aaa",
    ]))
    monkeypatch.setattr(sys, "argv", ["ci-sample", "--cleanup", "--dry-run"])
    # When: mutations remain blocked by the autouse fixture.
    ci.main()
    # Then
    output = capsys.readouterr()
    assert "2 trigger commit(s)" in output.err
    assert "ccc" in output.err and "dry-run" in output.out


def test_cleanup_when_history_has_no_safe_target(ci: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(ci.subprocess, "check_output", Mock(side_effect=["feature/test", "aaa TEST: trigger CI sample 1/1"]))
    monkeypatch.setattr(sys, "argv", ["ci-sample", "--cleanup"])
    # When / Then
    with pytest.raises(SystemExit, match="refusing to reset"):
        ci.main()


def test_summary_when_outlier_and_missing_duration(ci: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    for index, duration in enumerate([60, 120, 900, None]):
        (tmp_path / f"sample-{index}.json").write_text(json.dumps({"jobs": [{"name": "build", "run_seconds": duration}]}))
    # When
    ci.cmd_summary(ci.argparse.Namespace(summary=str(tmp_path)))
    # Then
    row = capsys.readouterr().out.splitlines()[-1].split()
    assert row == ["build", "3", "2m00s", "1m00s", "15m00s"]


def test_summary_when_no_sample_files(ci: ModuleType, tmp_path: Path) -> None:
    # Given / When / Then
    with pytest.raises(SystemExit, match="no sample-.*json files"):
        ci.cmd_summary(ci.argparse.Namespace(summary=str(tmp_path)))


def test_job_summary_when_timestamps_present(ci: ModuleType) -> None:
    # Given
    job = {"id": 7, "name": "build", "created_at": "2026-01-01T00:00:00Z", "started_at": "2026-01-01T00:00:10Z", "completed_at": "2026-01-01T00:01:20Z", "status": "completed", "conclusion": "failure"}
    # When
    summary = ci.job_summary(job)
    # Then
    assert (summary["queue_seconds"], summary["run_seconds"], summary["status"]) == (10, 70, "failure")


def test_job_summary_when_job_is_queued(ci: ModuleType) -> None:
    # Given / When
    summary = ci.job_summary({"id": 7, "name": "build", "status": "queued"})
    # Then
    assert (summary["queue_seconds"], summary["run_seconds"], summary["status"]) == (None, None, "queued")


@pytest.mark.parametrize("workflow", ["Build", "ci.yml"])
def test_workflow_when_name_or_path_matches(ci: ModuleType, monkeypatch: pytest.MonkeyPatch, workflow: str) -> None:
    # Given
    monkeypatch.setattr(ci.subprocess, "check_output", Mock(return_value='{"workflows":[{"id":7,"name":"Build","path":".github/workflows/ci.yml"}]}'))
    # When / Then
    assert ci.resolve_workflow(workflow) == 7


def test_workflow_when_numeric_id_needs_no_api(ci: ModuleType) -> None:
    # Given / When / Then
    assert ci.resolve_workflow("123") == 123


def test_workflow_when_ambiguous(ci: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    workflows = [{"id": number, "name": "Build", "path": f"{number}.yml"} for number in (1, 2)]
    monkeypatch.setattr(ci.subprocess, "check_output", Mock(return_value=json.dumps({"workflows": workflows})))
    # When / Then
    with pytest.raises(SystemExit, match="ambiguous"):
        ci.resolve_workflow("Build")
