import json
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any
from unittest.mock import Mock

import pytest

RUN_URL = "https://github.com/owner/repo/actions/runs/42"
JOB_URL = RUN_URL + "/job/7"

PYTEST_LOG = (
    "\ufeff2026-01-01T00:00:00.1Z ##[group]Run pytest\n"
    "2026-01-01T00:00:01.1Z \x1b[31mE   AssertionError: assert 2 <= 1\x1b[0m\n"
    "2026-01-01T00:00:02.1Z =========================== short test summary info ============================\n"
    "2026-01-01T00:00:02.2Z \x1b[31mFAILED\x1b[0m /__w/repo/repo/tests/test_a.py::test_one - AssertionError: gaps\n"
    "2026-01-01T00:00:02.3Z ERROR tests/test_b.py - Failed: 'jira' not found in `markers`\n"
    "2026-01-01T00:00:02.4Z \x1b[31m====== \x1b[1m1 failed\x1b[0m, \x1b[32m7 passed\x1b[0m in 498.18s (0:08:18) ======\x1b[0m\n"
    "2026-01-01T00:00:03.1Z ##[error]Process completed with exit code 1.\n"
)

COMPILER_LOG = (
    "2026-01-01T00:00:00Z FAILED: [code=1] src/a.cpp.o\n"
    "2026-01-01T00:00:00Z /__w/repo/repo/src/a.cpp:10:6: error: 'function' in namespace 'std' does not name a template type\n"
    "2026-01-01T00:00:00Z /__w/repo/repo/src/a.cpp:10:6: error: 'function' in namespace 'std' does not name a template type\n"
    "2026-01-01T00:00:00Z CMake Error at cmake/git.cmake:29 (message):\n"
    "2026-01-01T00:00:00Z /usr/bin/ld: main.o: undefined reference to `foo'\n"
    "2026-01-01T00:00:00Z ##[error]Process completed with exit code 1.\n"
)


@pytest.fixture
def failures(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-run-failures")


def job(job_id: int, name: str, conclusion: str | None, status: str = "completed", steps: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"id": job_id, "name": name, "status": status, "conclusion": conclusion,
            "html_url": f"{RUN_URL}/job/{job_id}", "steps": steps or []}


def api(responses: dict[str, str]) -> Mock:
    def call(*args: str) -> str:
        return responses[args[0]]
    return Mock(side_effect=call)


def test_failure_lines_when_pytest_log_has_ansi_and_timestamps(failures: ModuleType) -> None:
    # Given / When
    lines = failures.failure_lines(PYTEST_LOG, 8)
    # Then
    assert lines == [
        "FAILED tests/test_a.py::test_one - AssertionError: gaps",
        "ERROR tests/test_b.py - Failed: 'jira' not found in `markers`",
        "1 failed, 7 passed in 498.18s (0:08:18)",
        "##[error]Process completed with exit code 1.",
    ]


def test_failure_lines_when_compiler_errors_repeat(failures: ModuleType) -> None:
    # Given / When
    lines = failures.failure_lines(COMPILER_LOG, 8)
    # Then
    assert lines == [
        "src/a.cpp:10:6: error: 'function' in namespace 'std' does not name a template type",
        "CMake Error at cmake/git.cmake:29 (message):",
        "/usr/bin/ld: main.o: undefined reference to `foo'",
        "##[error]Process completed with exit code 1.",
    ]


def test_failure_lines_when_over_the_limit(failures: ModuleType) -> None:
    # Given
    log = "\n".join(f"src/f{n}.c:1:1: error: bad {n}" for n in range(5))
    # When
    lines = failures.failure_lines(log, 3)
    # Then
    assert lines == ["src/f0.c:1:1: error: bad 0", "src/f1.c:1:1: error: bad 1", "… 3 more"]


@pytest.mark.parametrize("value, repo, expected", [
    ("42", None, ("{owner}/{repo}", "42")),
    ("42", "o/r", ("o/r", "42")),
    (RUN_URL + "/attempts/2", None, ("owner/repo", "42")),
])
def test_parse_target_when_id_or_url(failures: ModuleType, value: str, repo: str | None, expected: tuple[str, str]) -> None:
    # Given / When
    target = failures.parse_target(value, repo)
    # Then
    assert (target.repo, target.run_id) == expected


@pytest.mark.parametrize("value, repo", [("not-a-run", None), (RUN_URL, "other/repo")])
def test_parse_target_when_invalid(failures: ModuleType, value: str, repo: str | None) -> None:
    # Given / When / Then
    with pytest.raises(ValueError):
        failures.parse_target(value, repo)


def test_cli_when_a_job_failed(failures: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    jobs = [
        job(7, "Tests / pytest", "failure", steps=[{"number": 1, "name": "Set up", "conclusion": "success"},
                                                   {"number": 9, "name": "Run pytest", "conclusion": "failure"}]),
        job(8, "Build", "success"),
        job(9, "Lint", "cancelled"),
    ]
    gh = api({
        "repos/owner/repo/actions/runs/42": json.dumps({"name": "Product", "status": "completed", "conclusion": "failure"}),
        "repos/owner/repo/actions/runs/42/jobs?per_page=100": "\n".join(json.dumps(j) for j in jobs),
        "repos/owner/repo/actions/jobs/7/logs": PYTEST_LOG,
    })
    monkeypatch.setattr(failures, "gh", gh)
    monkeypatch.setattr(sys, "argv", ["gh-run-failures", RUN_URL])
    # When
    with pytest.raises(SystemExit) as exit_info:
        failures.main()
    # Then
    assert exit_info.value.code == 1
    output = capsys.readouterr().out
    assert output.startswith("Product 42: completed failure, 1 of 3 jobs failed\n")
    assert f"FAIL Tests / pytest\n     {JOB_URL}#step:9:1 (Run pytest)\n     FAILED tests/test_a.py::test_one" in output
    assert "1 cancelled: Lint" in output


def test_cli_when_waiting_until_the_run_finishes_green(failures: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    runs = iter([{"name": "Product", "status": "in_progress"}, {"name": "Product", "status": "completed", "conclusion": "success"}])
    def gh(*args: str) -> str:
        if args[0] == "repos/owner/repo/actions/runs/42":
            return json.dumps(next(runs))
        return json.dumps(job(8, "Build", "success"))
    monkeypatch.setattr(failures, "gh", Mock(side_effect=gh))
    sleep = Mock()
    monkeypatch.setattr(failures.time, "sleep", sleep)
    monkeypatch.setattr(failures.time, "monotonic", Mock(side_effect=[0.0, 1.0, 2.0, 16.0, 17.0]))
    monkeypatch.setattr(sys, "argv", ["gh-run-failures", "42", "-R", "owner/repo", "--wait", "60"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        failures.main()
    # Then
    assert exit_info.value.code == 0
    assert sleep.call_args.args == (15,)
    assert capsys.readouterr().out == "Product 42: completed success, 0 of 1 jobs failed\n"


def test_cli_when_still_running_after_the_wait(failures: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    gh = api({
        "repos/owner/repo/actions/runs/42": json.dumps({"name": "Product", "status": "in_progress"}),
        "repos/owner/repo/actions/runs/42/jobs?per_page=100": json.dumps(job(8, "Build", None, status="in_progress")),
    })
    monkeypatch.setattr(failures, "gh", gh)
    monkeypatch.setattr(sys, "argv", ["gh-run-failures", "42", "-R", "owner/repo"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        failures.main()
    # Then
    assert exit_info.value.code == 2
    assert capsys.readouterr().out.endswith("1 jobs still running: Build\n")


def test_cli_when_gh_fails(failures: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(failures, "gh", Mock(side_effect=failures.ApiError("HTTP 404: Not Found")))
    monkeypatch.setattr(sys, "argv", ["gh-run-failures", "42"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        failures.main()
    # Then
    assert exit_info.value.code == 3
    assert capsys.readouterr().err == "gh-run-failures: HTTP 404: Not Found\n"
