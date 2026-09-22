import io
import json
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


@pytest.mark.parametrize("payload", [b"not a zip", b"PK\x03\x04truncated"])
def test_cli_when_archive_is_invalid(anchor: ModuleType, monkeypatch: pytest.MonkeyPatch, payload: bytes) -> None:
    # Given
    metadata = {"run_id": 42, "run_attempt": 1, "html_url": URL, "status": "completed", "steps": [{"number": 1}]}
    monkeypatch.setattr(anchor, "gh", Mock(side_effect=[json.dumps(metadata).encode(), b"job", payload]))
    monkeypatch.setattr(sys, "argv", ["gh-step-anchor", URL, "job"])
    # When / Then
    with pytest.raises(SystemExit) as error:
        anchor.main()
    assert error.value.code == 1
