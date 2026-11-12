import io
import json
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from types import ModuleType
from typing import Final
from unittest.mock import Mock
from zipfile import ZipFile

import pytest

URL: Final = "https://github.com/owner/repo/actions/runs/42/job/17"


def archive_bytes(files: Mapping[str, str]) -> bytes:
    stream = io.BytesIO()
    with ZipFile(stream, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("utf-8"))
    return stream.getvalue()


@pytest.fixture
def anchor(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-step-anchor")


@pytest.fixture
def logs(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch) -> Mock:
    setup = "\ufeffrunner setup\r\nTARGET setup\r\n"
    build = "2026-01-01T00:00:00Z ##[group]outer\n##[group]nested\nTARGET build\n##[endgroup]\n\nTARGET continuation\n##[endgroup]\n"
    post = "cleanup\nTARGET post\n"
    whole = setup + build + post
    archive = archive_bytes({"0_other.txt": "another job", "other/1_Set up.txt": "not this job", "-1_build.txt": whole, "build/7_Post.txt": post, "build/3_Run.txt": build, "build/1_Set up.txt": setup})
    metadata = {"run_id": 42, "run_attempt": 2, "html_url": URL + "#old", "status": "completed", "steps": [{"number": number} for number in (1, 2, 3, 7)]}
    responses = {
        "repos/owner/repo/actions/jobs/17": json.dumps(metadata).encode(),
        "repos/owner/repo/actions/jobs/17/logs": whole.encode(),
        "repos/owner/repo/actions/runs/42/attempts/2/logs": archive,
    }
    api = Mock(side_effect=responses.__getitem__)
    monkeypatch.setattr(anchor, "gh", api)
    return api


def test_setup_anchor_when_bom_and_crlf(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET"])
    # When
    anchor.main()
    # Then
    assert output.getvalue() == URL + "#step:1:2\n"
    assert logs.call_args.args == ("repos/owner/repo/actions/runs/42/attempts/2/logs",)


def test_all_matches_when_nested_groups_skipped_gaps_post_and_multiline(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "17", "TARGET", "--repo", "owner/repo", "--all", "--json"])
    # When
    anchor.main()
    # Then
    assert json.loads(output.getvalue()) == [
        {"step": 1, "line": 2, "text": "TARGET setup", "url": URL + "#step:1:2"},
        {"step": 3, "line": 3, "text": "TARGET build", "url": URL + "#step:3:3"},
        {"step": 3, "line": 6, "text": "TARGET continuation", "url": URL + "#step:3:6"},
        {"step": 7, "line": 2, "text": "TARGET post", "url": URL + "#step:7:2"},
    ]


def test_step_filter_when_post_step_requested(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--step", "7"])
    # When
    anchor.main()
    # Then
    assert output.getvalue() == URL + "#step:7:2\n"


@pytest.mark.parametrize("pattern", [r"^##\[group\]outer", r"^2026-01-01T00:00:00Z ##\[group\]outer"])
def test_caret_anchors_after_timestamp_when_step_files_exist(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, pattern: str) -> None:
    # Given
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, pattern])
    # When
    anchor.main()
    # Then
    assert output.getvalue() == URL + "#step:3:1\n"


@pytest.mark.parametrize("arguments", [["absent"], ["TARGET", "--step", "2"], ["TARGET", "--step", "99"], ["["]])
def test_cli_failure_when_match_unavailable(anchor: ModuleType, logs: Mock, arguments: list[str]) -> None:
    # Given
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(sys, "argv", ["gh-step-anchor", URL, *arguments])
        # When / Then
        with pytest.raises(SystemExit) as error:
            anchor.main()
    assert error.value.code == 1


@pytest.mark.parametrize("files", [
    {"0_a.txt": "same", "1_b.txt": "same", "a/1_Setup.txt": "x"},
    {"0_a.txt": "different", "a/1_Setup.txt": "x"},
    {"0_a.txt": "same"},
    {"0_a.txt": "same", "a/1_First.txt": "x", "a/1_Duplicate.txt": "y"},
])
def test_mapping_refuses_when_ambiguous_or_unavailable(anchor: ModuleType, files: Mapping[str, str]) -> None:
    # Given
    with ZipFile(io.BytesIO(archive_bytes(files))) as archive, pytest.raises(anchor.AnchorError):
        anchor.step_logs(archive, "same")


@pytest.mark.parametrize("case", [
    ("17", None, ("repos/{owner}/{repo}", "17")),
    ("17", "owner/repo", ("repos/owner/repo", "17")),
    (URL + "?check_suite_focus=true#step:3:1", None, ("repos/owner/repo", "17")),
    (URL, "OWNER/REPO", ("repos/owner/repo", "17")),
])
def test_job_target_when_numeric_or_url(anchor: ModuleType, case: tuple[str, str | None, tuple[str, str]]) -> None:
    # Given
    value, repo, expected = case
    # When / Then
    assert anchor.job_target(value, repo) == expected


@pytest.mark.parametrize("case", [(URL, "other/repo"), ("17", "owner/repo/extra"), ("http://github.com/owner/repo/actions/runs/42/job/17", None), (URL.replace("github.com", "evil.invalid"), None)])
def test_job_target_when_repo_or_url_invalid(anchor: ModuleType, case: tuple[str, str | None]) -> None:
    # Given / When / Then
    with pytest.raises(anchor.AnchorError):
        anchor.job_target(*case)


def stamped(second: int, *texts: str) -> str:
    return "".join(f"2026-01-01T00:00:{second:02d}.5000000Z {text}\n" for text in texts)


def serve_job_log(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, whole: str, times: Mapping[int, tuple[int, int, str]]) -> None:
    steps = [{"number": number, "name": name, "conclusion": "skipped" if name == "Lint" else "success",
              "started_at": f"2026-01-01T00:00:{start:02d}Z", "completed_at": f"2026-01-01T00:00:{end:02d}Z"}
             for number, (start, end, name) in times.items()]
    metadata = {"run_id": 42, "run_attempt": 2, "html_url": URL, "status": "completed", "steps": steps}
    responses = {
        "repos/owner/repo/actions/jobs/17": json.dumps(metadata).encode(),
        "repos/owner/repo/actions/jobs/17/logs": whole.encode(),
        "repos/owner/repo/actions/runs/42/attempts/2/logs": archive_bytes({"0_build.txt": whole, "build/system.txt": "Requested labels: x"}),
    }
    monkeypatch.setattr(anchor, "gh", Mock(side_effect=responses.__getitem__))


# Steps share seconds, Checkout is a composite action with an inner Run line, Lint is skipped,
# and Complete job has no known first line, so "TARGET post" can't be placed.
JOB_LOG: Final = (
    stamped(0, "Current runner version: '2.338.0'")
    + stamped(1, "Complete job name: build", "##[group]Run org/checkout@v1", "##[endgroup]",
              "##[start-action display=Fetch;id=fetch]", "##[group]Run actions/checkout@v4")
    + stamped(2, "##[endgroup]", "TARGET inner", "##[end-action id=fetch;outcome=success]",
              "##[group]Run make build", "##[endgroup]", "TARGET build", "##[group]Run make test", "##[endgroup]")
    + stamped(3, "TARGET test")
    + stamped(4, "TARGET late test", "Post job cleanup.", "TARGET post", "Cleaning up orphan processes")
)
STEP_TIMES: Final = {1: (0, 1, "Set up job"), 2: (1, 2, "Checkout"), 3: (2, 2, "Build"), 4: (2, 2, "Lint"),
                     5: (2, 4, "Test"), 8: (4, 4, "Post Checkout"), 9: (4, 4, "Complete job")}


def test_resolve_step_logs_fallback_keeps_conservative_step_ownership(anchor: ModuleType) -> None:
    # Given
    steps = [{"number": number, "name": name, "conclusion": "skipped" if name == "Lint" else "success",
              "started_at": f"2026-01-01T00:00:{start:02d}Z", "completed_at": f"2026-01-01T00:00:{end:02d}Z"}
             for number, (start, end, name) in STEP_TIMES.items()]
    # When
    logs = anchor.resolve_step_logs(None, JOB_LOG, steps, anchor.re.compile("TARGET"))
    matches = [
        (number, line[line.index("TARGET "):])
        for number, step_lines in logs
        for line in step_lines
        if "TARGET " in line
    ]
    # Then
    assert matches == [(2, "TARGET inner"), (3, "TARGET build"), (5, "TARGET test"), (5, "TARGET late test")]


def test_fallback_anchors_when_archive_has_no_step_files(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--all", "--json"])
    # When
    anchor.main()
    # Then
    captured = capsys.readouterr()
    assert [(match["step"], match["line"], match["url"]) for match in json.loads(captured.out)] == [
        (2, 6, URL + "#step:2:6"), (3, 3, URL + "#step:3:3"), (5, 3, URL + "#step:5:3"), (5, 4, URL + "#step:5:4"),
    ]
    assert captured.err


def test_fallback_first_match_when_archive_has_no_step_files(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET b"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:3:3\n"


@pytest.mark.parametrize("pattern", ["^TARGET b", r"^2026-01-01T00:00:02\.5000000Z TARGET build$"])
def test_fallback_caret_anchors_after_timestamp(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], pattern: str) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, pattern])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:3:3\n"


@pytest.mark.parametrize("case", [
    (JOB_LOG, STEP_TIMES, "TARGET post"),
    (JOB_LOG, {**STEP_TIMES, 3: (3, 3, "Build")}, "TARGET build"),
    (stamped(1, "a") + stamped(0, "TARGET"), {1: (0, 1, "Set up job")}, "TARGET"),
])
def test_fallback_refuses_when_step_is_unclear_or_log_does_not_fit(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, case: tuple[str, Mapping[int, tuple[int, int, str]], str]) -> None:
    # Given
    whole, times, pattern = case
    serve_job_log(anchor, monkeypatch, whole, times)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, pattern])
    # When / Then
    with pytest.raises(SystemExit) as error:
        anchor.main()
    assert error.value.code == 1


# Set up job prepares the job's actions too. Setup runs a local composite action: its step opens with
# the runner preparing the actions the composite uses, and the composite's own Run line follows in the
# same second.
LOCAL_ACTION_LOG: Final = (
    stamped(0, "Current runner version: '2.338.0'", "Prepare all required actions", "Getting action download info",
            "Download action repository 'org/checkout@v1' (SHA:abc)")
    + stamped(1, "Complete job name: build", "##[group]Run org/checkout@v1", "##[endgroup]", "TARGET checkout")
    + stamped(2, "Prepare all required actions", "Getting action download info",
              "##[group]Download immutable action package 'org/cache@v2'", "Version: 2.0.0", "##[endgroup]",
              "Download action repository 'org/uv@v7' (SHA:def)", "##[group]Run ./.github/actions/setup", "env:",
              "##[endgroup]", "##[start-action display=Setup uv;id=setup.uv]", "##[group]Run org/uv@v7", "##[endgroup]",
              "##[end-action id=setup.uv;outcome=success]", "##[start-action display=Install;id=setup.install]",
              "TARGET install", "##[end-action id=setup.install;outcome=success]")
    + stamped(3, "##[group]Run make", "##[endgroup]", "TARGET make")
)


def test_fallback_anchors_when_a_step_runs_a_local_action(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, LOCAL_ACTION_LOG,
                  {1: (0, 1, "Set up job"), 2: (1, 2, "Checkout"), 3: (2, 2, "Setup"), 4: (3, 3, "Build")})
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--all", "--json"])
    # When
    anchor.main()
    # Then
    assert [(match["step"], match["line"]) for match in json.loads(capsys.readouterr().out)] == [(2, 3), (3, 15), (4, 3)]


@pytest.mark.parametrize("payload", ["not a zip", "PK\x03\x04truncated"])
def test_cli_when_archive_is_invalid(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, payload: str) -> None:
    # Given
    metadata = {"run_id": 42, "run_attempt": 1, "html_url": URL, "status": "completed", "steps": [{"number": 1}]}
    monkeypatch.setattr(anchor, "gh", Mock(side_effect=[json.dumps(metadata).encode(), b"job", payload.encode()]))
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "job"])
    # When / Then
    with pytest.raises(SystemExit) as error:
        anchor.main()
    assert error.value.code == 1


def serve_without_archive(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, archive_error: str) -> None:
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    served = anchor.gh.side_effect

    def gh(endpoint: str) -> bytes:
        if endpoint == "repos/owner/repo/actions/runs/42/attempts/2/logs":
            raise anchor.ApiError(archive_error)
        return served(endpoint)

    monkeypatch.setattr(anchor, "gh", Mock(side_effect=gh))


def test_fallback_anchors_while_the_run_is_still_going(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_without_archive(anchor, monkeypatch, "gh: Not Found (HTTP 404)")
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--all", "--json"])
    # When
    anchor.main()
    # Then
    captured = capsys.readouterr()
    assert [match["url"] for match in json.loads(captured.out)] == [
        URL + "#step:2:6", URL + "#step:3:3", URL + "#step:5:3", URL + "#step:5:4",
    ]
    assert captured.err


def test_cli_failure_when_the_archive_fails_for_another_reason(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_without_archive(anchor, monkeypatch, "gh: Server Error (HTTP 502)")
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET b"])
    # When
    with pytest.raises(SystemExit) as error:
        anchor.main()
    # Then
    assert error.value.code == 1
    assert "HTTP 502" in capsys.readouterr().err


@pytest.mark.parametrize("case", [
    (0, b"payload", b"", None),
    (1, b"", b"gh: Not Found (HTTP 404)\n", "gh: Not Found (HTTP 404)"),
    (1, b"", b"", "`gh api repos/owner/repo/x` exited 1"),
])
def test_gh_returns_stdout_or_raises_with_its_error_output(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, case: tuple[int, bytes, bytes, str | None]) -> None:
    # Given
    returncode, stdout, stderr, message = case
    monkeypatch.setattr(subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], returncode, stdout, stderr)))
    # When / Then
    if message is None:
        assert anchor.gh("repos/owner/repo/x") == stdout
    else:
        with pytest.raises(anchor.ApiError, match=re.escape(message)):
            anchor.gh("repos/owner/repo/x")


@pytest.mark.parametrize("line", [
    "\x1b[32m43 passed\x1b[0m, \x1b[33m262 deselected\x1b[0m",
    "2026-01-01T00:00:00.1234567Z \x1b[32m43 passed\x1b[0m, \x1b[33m262 deselected\x1b[0m",
])
def test_line_matches_when_ansi_codes_split_the_text(anchor: ModuleType, line: str) -> None:
    # Given
    pattern = re.compile(r"^43 passed, 262 deselected")
    # When
    matched = anchor.line_matches(pattern, line)
    # Then
    assert matched


def test_line_numbers_count_the_markers_the_log_viewer_hides(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given: GitHub resolves #step:N:L by physical line. Its log viewer hides these markers and
    # shows TARGET as line 3, but a link to line 3 lands on the start-action line.
    step = ("##[group]Run make\n##[endgroup]\n##[start-action display=Build;id=build]\n"
            "##[end-action id=build;outcome=success]\nTARGET\n")
    metadata = {"run_id": 42, "run_attempt": 1, "html_url": URL, "status": "completed", "steps": [{"number": 1}]}
    responses = {
        "repos/owner/repo/actions/jobs/17": json.dumps(metadata).encode(),
        "repos/owner/repo/actions/jobs/17/logs": step.encode(),
        "repos/owner/repo/actions/runs/42/attempts/1/logs": archive_bytes({"-1_build.txt": step, "build/1_Run make.txt": step}),
    }
    monkeypatch.setattr(anchor, "gh", Mock(side_effect=responses.__getitem__))
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "^TARGET"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:1:5\n"


def test_json_text_when_ansi_codes_in_line(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    whole = "##[group]Run pytest\n2026-01-01T00:00:00Z \x1b[32m43 passed\x1b[0m, \x1b[33m262 deselected\x1b[0m\n"
    metadata = {"run_id": 42, "run_attempt": 1, "html_url": URL, "status": "completed", "steps": [{"number": 1}]}
    responses = {
        "repos/owner/repo/actions/jobs/17": json.dumps(metadata).encode(),
        "repos/owner/repo/actions/jobs/17/logs": whole.encode(),
        "repos/owner/repo/actions/runs/42/attempts/1/logs": archive_bytes({"-1_test.txt": whole, "test/1_Run pytest.txt": whole}),
    }
    monkeypatch.setattr(anchor, "gh", Mock(side_effect=responses.__getitem__))
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "43 passed, 262 deselected", "--json"])
    # When
    anchor.main()
    # Then
    assert json.loads(output.getvalue()) == [{"step": 1, "line": 2, "text": "2026-01-01T00:00:00Z 43 passed, 262 deselected", "url": URL + "#step:1:2"}]


# The runner prints a run step's script in a "Run" group at the top of the step, and a composite
# step's script after its start-action marker. "Run tests" is a group the script itself opens.
SCRIPT_STEP: Final = (
    '##[group]Run echo "TARGET"\necho "TARGET"\nshell: /usr/bin/bash -e {0}\n##[endgroup]\nTARGET\n'
    '##[start-action display=Report;id=report]\n##[group]Run echo "TARGET inner"\necho "TARGET inner"\n##[endgroup]\n'
    "TARGET inner\n##[end-action id=report;outcome=success]\n"
    "##[group]Run tests\nTARGET in a group\n##[endgroup]\n"
)


def serve_step(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, step: str) -> None:
    metadata = {"run_id": 42, "run_attempt": 1, "html_url": URL, "status": "completed", "steps": [{"number": 1}]}
    responses = {
        "repos/owner/repo/actions/jobs/17": json.dumps(metadata).encode(),
        "repos/owner/repo/actions/jobs/17/logs": step.encode(),
        "repos/owner/repo/actions/runs/42/attempts/1/logs": archive_bytes({"-1_build.txt": step, "build/1_Run echo.txt": step}),
    }
    monkeypatch.setattr(anchor, "gh", Mock(side_effect=responses.__getitem__))


@pytest.mark.parametrize(("flags", "lines"), [([], [5, 10, 13]), (["--include-header"], [1, 2, 5, 7, 8, 10, 13])])
def test_step_headers_skipped_unless_included(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                                              flags: list[str], lines: list[int]) -> None:
    # Given
    serve_step(anchor, monkeypatch, SCRIPT_STEP)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--all", "--json", *flags])
    # When
    anchor.main()
    # Then
    assert [match["line"] for match in json.loads(capsys.readouterr().out)] == lines


def test_cli_hint_when_pattern_only_matches_a_step_header(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_step(anchor, monkeypatch, SCRIPT_STEP)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "shell: "])
    # When
    with pytest.raises(SystemExit) as error:
        anchor.main()
    # Then
    assert error.value.code == 1
    assert "--include-header" in capsys.readouterr().err


RUN_JOBS: Final = "repos/owner/repo/actions/runs/42/jobs?filter=latest&per_page=100&page={page}"


def serve_run_jobs(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, logs: Mock, pages: list[list[dict[str, object]]]) -> Mock:
    served = logs.side_effect
    responses = {RUN_JOBS.format(page=number): json.dumps({"jobs": jobs}).encode() for number, jobs in enumerate(pages, 1)}

    def gh(endpoint: str) -> bytes:
        return responses[endpoint] if endpoint in responses else served(endpoint)

    api = Mock(side_effect=gh)
    monkeypatch.setattr(anchor, "gh", api)
    return api


@pytest.mark.parametrize("run", ["42", "https://github.com/owner/repo/actions/runs/42", "https://github.com/owner/repo/actions/runs/42/attempts/2"])
def test_run_finds_the_job_by_name(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], run: str) -> None:
    # Given
    serve_run_jobs(anchor, monkeypatch, logs, [[{"id": 16, "name": "Build / unit / unittest-ctest"},
                                                {"id": 17, "name": "Build / unit / unittest-ci-scripts"}]])
    repo = ["--repo", "owner/repo"] if run.isdecimal() else []
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--run", run, *repo, "ci-scripts", "TARGET"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:1:2\n"


def test_run_reads_every_page_of_jobs(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    first = [{"id": 1000 + number, "name": f"shard {number}"} for number in range(100)]
    api = serve_run_jobs(anchor, monkeypatch, logs, [first, [{"id": 17, "name": "Build / unit / unittest-ci-scripts"}]])
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--run", "42", "--repo", "owner/repo", "ci-scripts$", "TARGET"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:1:2\n"
    assert RUN_JOBS.format(page=2) in [call.args[0] for call in api.call_args_list]


@pytest.mark.parametrize(("name", "message"), [
    ("unittest", "2 jobs in run 42 match 'unittest', narrow the pattern: Build / unit / unittest-ctest; Build / unit / unittest-ci-scripts"),
    ("lint", "no job in run 42 matches 'lint'"),
])
def test_run_refuses_when_the_name_is_ambiguous_or_missing(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], name: str, message: str) -> None:
    # Given
    serve_run_jobs(anchor, monkeypatch, logs, [[{"id": 16, "name": "Build / unit / unittest-ctest"},
                                                {"id": 17, "name": "Build / unit / unittest-ci-scripts"}]])
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--run", "42", "--repo", "owner/repo", name, "TARGET"])
    # When
    with pytest.raises(SystemExit) as error:
        anchor.main()
    # Then
    assert error.value.code == 1
    assert message in capsys.readouterr().err


def test_run_target_when_repo_conflicts_with_the_url(anchor: ModuleType) -> None:
    # When / Then
    with pytest.raises(anchor.AnchorError, match="conflicts"):
        anchor.run_target("https://github.com/owner/repo/actions/runs/42", "other/repo")


def test_text_prints_each_url_with_its_line(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--all", "--text"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out.splitlines() == [
        URL + "#step:1:2  TARGET setup", URL + "#step:3:3  TARGET build",
        URL + "#step:3:6  TARGET continuation", URL + "#step:7:2  TARGET post",
    ]


def test_text_drops_the_timestamp(anchor: ModuleType) -> None:
    # When / Then
    assert anchor.shown_text("2026-01-01T00:00:00.1234567Z 43 passed") == "43 passed"
    assert anchor.shown_text("no timestamp") == "no timestamp"


STREAM_ERROR: Final = b"stream error: stream ID 1; CANCEL; received from peer\n"


def test_gh_retries_a_transient_error(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    run = Mock(side_effect=[subprocess.CompletedProcess([], 1, b"", STREAM_ERROR), subprocess.CompletedProcess([], 0, b"payload", b"")])
    sleep = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(anchor.time, "sleep", sleep)
    # When
    payload = anchor.gh("repos/owner/repo/x")
    # Then
    assert payload == b"payload"
    assert run.call_count == 2
    assert sleep.call_args_list == [((2.0,),)]
    assert "retrying in 2s after: stream error" in capsys.readouterr().err


def test_gh_gives_up_after_the_retries(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    run = Mock(return_value=subprocess.CompletedProcess([], 1, b"", b"gh: Bad Gateway (HTTP 502)\n"))
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(anchor.time, "sleep", Mock())
    # When / Then
    with pytest.raises(anchor.ApiError, match="HTTP 502"):
        anchor.gh("repos/owner/repo/x")
    assert run.call_count == 3


def test_gh_does_not_retry_a_missing_archive(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    run = Mock(return_value=subprocess.CompletedProcess([], 1, b"", b"gh: Not Found (HTTP 404)\n"))
    sleep = Mock()
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(anchor.time, "sleep", sleep)
    # When / Then
    with pytest.raises(anchor.ApiError, match="HTTP 404"):
        anchor.gh("repos/owner/repo/x")
    assert run.call_count == 1
    sleep.assert_not_called()


def test_show_prints_the_line_each_link_lands_on(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--show", URL + "#step:1:2", URL + "?check_suite_focus=true#step:3:6"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out.splitlines() == [
        URL + "#step:1:2  TARGET setup", URL + "?check_suite_focus=true#step:3:6  TARGET continuation",
    ]
    assert logs.call_count == 3


def test_show_round_trips_every_link_the_search_finds(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--all", "--json"])
    anchor.main()
    found = json.loads(capsys.readouterr().out)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--json", "--show", *[match["url"] for match in found]])
    # When
    anchor.main()
    # Then
    assert json.loads(capsys.readouterr().out) == found


def test_show_when_the_archive_has_no_step_files(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--show", URL + "#step:3:3"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:3:3  TARGET build\n"


def test_show_drops_the_timestamp_and_ansi_codes(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_step(anchor, monkeypatch, "##[group]Run pytest\n2026-01-01T00:00:00Z \x1b[32m43 passed\x1b[0m, \x1b[33m262 deselected\x1b[0m\n")
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--show", URL + "#step:1:2"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:1:2  43 passed, 262 deselected\n"


def test_show_reports_each_link_it_cannot_resolve_and_goes_on(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given: step 2 is in the job but has no log file, and step 3's log has 7 lines.
    links = [URL, URL + "#step:2:1", URL + "#step:3:8", URL + "#step:9:1", URL + "#step:7:2"]
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", "--show", *links])
    # When
    with pytest.raises(SystemExit) as error:
        anchor.main()
    # Then
    captured = capsys.readouterr()
    assert error.value.code == 1
    assert captured.out == URL + "#step:7:2  TARGET post\n"
    assert captured.err.splitlines() == [
        f"gh-step-anchor: {URL}: --show expects https://github.com/OWNER/REPO/actions/runs/RUN/job/JOB#step:N:L links",
        f"gh-step-anchor: {URL}#step:2:1: can't tell which log lines belong to step 2; refusing to guess",
        f"gh-step-anchor: {URL}#step:3:8: step 3's log has 7 lines, so line 8 doesn't exist",
        f"gh-step-anchor: {URL}#step:9:1: step 9 is not in this job",
    ]


@pytest.mark.parametrize("arguments", [
    ["--show", URL + "#step:1:2", "--all"],
    ["--show", URL + "#step:1:2", "--step", "1"],
    ["--show", URL + "#step:1:2", "--include-header"],
    ["--run", "42", "--show", URL + "#step:1:2"],
    [URL, "TARGET", "--show", URL + "#step:1:2"],
    [URL],
    [],
])
def test_cli_usage_error_when_show_mixes_with_a_search_or_the_search_is_incomplete(anchor: ModuleType, logs: Mock, monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", *arguments])
    # When / Then
    with pytest.raises(SystemExit) as error:
        anchor.main()
    assert error.value.code == 2
    logs.assert_not_called()


@pytest.mark.parametrize(("link", "expected"), [
    (URL + "#step:3:1", ("repos/owner/repo", "17", 3, 1)),
    (URL + "?check_suite_focus=true#step:12:345", ("repos/owner/repo", "17", 12, 345)),
])
def test_anchor_target_when_the_link_has_a_step_anchor(anchor: ModuleType, link: str, expected: tuple[str, str, int, int]) -> None:
    # When / Then
    assert anchor.anchor_target(link, None) == expected


@pytest.mark.parametrize("link", [URL, URL + "#step:3:0", URL + "#step:3", URL + "#L5", "17",
                                  "https://github.com/owner/repo/actions/runs/42#step:1:1"])
def test_anchor_target_refuses_other_links(anchor: ModuleType, link: str) -> None:
    # When / Then
    with pytest.raises(anchor.AnchorError):
        anchor.anchor_target(link, None)
