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
        {"step": 3, "line": 5, "text": "TARGET continuation", "url": URL + "#step:3:5"},
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


def test_fallback_anchors_when_archive_has_no_step_files(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET", "--all", "--json"])
    # When
    anchor.main()
    # Then
    captured = capsys.readouterr()
    assert [(match["step"], match["line"], match["url"]) for match in json.loads(captured.out)] == [
        (2, 4, URL + "#step:2:4"), (3, 2, URL + "#step:3:2"), (5, 2, URL + "#step:5:2"), (5, 3, URL + "#step:5:3"),
    ]
    assert captured.err


def test_fallback_first_match_when_archive_has_no_step_files(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "TARGET b"])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:3:2\n"


@pytest.mark.parametrize("pattern", ["^TARGET b", r"^2026-01-01T00:00:02\.5000000Z TARGET build$"])
def test_fallback_caret_anchors_after_timestamp(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], pattern: str) -> None:
    # Given
    serve_job_log(anchor, monkeypatch, JOB_LOG, STEP_TIMES)
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, pattern])
    # When
    anchor.main()
    # Then
    assert capsys.readouterr().out == URL + "#step:3:2\n"


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
    assert [(match["step"], match["line"]) for match in json.loads(capsys.readouterr().out)] == [(2, 2), (3, 11), (4, 2)]


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
        URL + "#step:2:4", URL + "#step:3:2", URL + "#step:5:2", URL + "#step:5:3",
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


def test_line_numbers_skip_the_markers_the_log_viewer_hides(anchor: ModuleType) -> None:
    # Given
    lines = ["2026-01-01T00:00:00.5000000Z ##[group]Run make", "2026-01-01T00:00:00.5000000Z ##[endgroup]",
             "##[start-action display=Build;id=build]", "##[end-action id=build;outcome=success]", "TARGET"]
    # When
    numbered = list(anchor.numbered(lines))
    # Then
    assert numbered == [(1, lines[0]), (2, lines[2]), (3, lines[4])]


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
