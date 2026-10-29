import io
import json
import sys
from collections.abc import Callable
from types import ModuleType
from typing import BinaryIO
from unittest.mock import Mock
from zipfile import ZipFile

import pytest


@pytest.fixture
def artifact(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = tool("gh-artifact-file")
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("dir/types.h", "alpha\nbeta RPC_TAG\ngamma RPC_TAG\ndelta\n")
    def download(endpoint: str, output: BinaryIO) -> None:
        output.write(archive.getvalue())
    monkeypatch.setattr(module, "download", download)
    return module


def run_record(run_id: int, conclusion: str | None = "success") -> dict[str, str | int | None]:
    return {"id": run_id, "head_sha": f"{run_id:040x}", "created_at": "2026-10-28T12:00:00Z",
            "status": "completed" if conclusion else "in_progress", "conclusion": conclusion}


def invoke(module: ModuleType, args: list[str], monkeypatch: pytest.MonkeyPatch) -> int:
    monkeypatch.setattr(sys, "argv", ["gh-artifact-file", *args, "build_*_{sha}", "dir/types.h"])
    with pytest.raises(SystemExit) as result:
        module.main()
    return int(result.value.code)


@pytest.fixture
def single(artifact: ModuleType, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    def gh(endpoint: str) -> str:
        if "/artifacts?" in endpoint:
            return json.dumps({"artifacts": [{"id": 12, "expired": False, "name": f"build_app_{2:040x}"}]})
        if endpoint.endswith("/jobs?per_page=100&page=1"):
            return json.dumps({"jobs": [{"id": 7, "name": "Build / app"}]})
        if endpoint == "repos/{owner}/{repo}":
            return '{"full_name": "context/repo"}'
        return json.dumps(run_record(2))
    monkeypatch.setattr(artifact, "gh", Mock(side_effect=gh))
    return artifact


def test_selection_when_runs_have_different_statuses(artifact: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    runs = [run_record(4), run_record(3, "cancelled"), run_record(2, "failure"), run_record(1, None)]
    def gh(*args: str) -> str:
        endpoint = args[0]
        if "/artifacts?" in endpoint:
            run_id = int(endpoint.split("/runs/")[1].split("/")[0])
            return json.dumps({"artifacts": [{"id": run_id + 10, "expired": False,
                               "name": f"build_app_{run_id:040x}"}]})
        assert "status=" not in endpoint
        return json.dumps({"workflow_runs": runs})
    monkeypatch.setattr(artifact, "gh", gh)
    # When
    code = invoke(artifact, ["-R", "owner/repo", "--branch", "master", "--last", "4", "--json"], monkeypatch)
    # Then
    assert code == 0
    assert [(r["run_id"], r["run_status"]) for r in json.loads(capsys.readouterr().out)] == [
        (4, "success"), (3, "cancelled"), (2, "failure"), (1, "in_progress")]


@pytest.mark.parametrize("options, expected", [
    (["--lines", "2-3"], "2: beta RPC_TAG\n3: gamma RPC_TAG\n"),
    (["--grep", "^gamma"], "3: gamma RPC_TAG\n"),
    (["--sha256"], "4456ca89ba07e60994d62f17ac691a5926c00ac7791b385bb5a526e8df59efcf\n"),
])
def test_output_when_filtered(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
                              capsys: pytest.CaptureFixture[str], options: list[str], expected: str) -> None:
    # Given / When
    code = invoke(single, ["-R", "owner/repo", "--run", "2", *options], monkeypatch)
    # Then
    assert code == 0
    assert capsys.readouterr().out.split("\n", 2)[2] == expected


def test_json_when_using_context_repo(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                     capsys: pytest.CaptureFixture[str]) -> None:
    # Given / When
    code = invoke(single, ["--run", "2", "--json", "--lines", "2-2"], monkeypatch)
    # Then
    assert code == 0
    url = "https://github.com/context/repo/actions/runs/2/artifacts/12"
    assert json.loads(capsys.readouterr().out) == [{
        "sha": f"{2:040x}", "run_id": 2, "run_status": "success", "created_at": "2026-10-28T12:00:00Z",
        "artifact_id": 12, "artifact_url": url, "citation_url": url,
        "lines": [{"line": 2, "text": "beta RPC_TAG"}]}]


@pytest.mark.parametrize("count, expected_code", [(1, 0), (2, 1)])
def test_selection_when_artifacts_are_absent_or_expired(artifact: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str], count: int, expected_code: int) -> None:
    # Given
    visited = []
    def gh(endpoint: str) -> str:
        if "/artifacts?" not in endpoint:
            assert "/workflows/product.yml/runs?branch=feature%2Ftest&" in endpoint
            return json.dumps({"workflow_runs": [run_record(n) for n in (5, 4, 3, 2)]})
        run_id = int(endpoint.split("/runs/")[1].split("/")[0])
        visited.append(run_id)
        if run_id in (5, 2):
            return '{"artifacts": []}'
        return json.dumps({"artifacts": [{"id": 12, "expired": run_id == 4,
                            "name": f"build_app_{run_id:040x}"}]})
    monkeypatch.setattr(artifact, "gh", gh)
    # When
    code = invoke(artifact, ["-R", "o/r", "--workflow", "product.yml", "--branch", "feature/test",
                             "--last", str(count), "--json"], monkeypatch)
    # Then
    output = capsys.readouterr()
    assert code == expected_code
    assert [r["run_id"] for r in json.loads(output.out)] == [3]
    assert "skipping run 5: no matching artifact" in output.err
    assert "skipping run 4: expired" in output.err
    assert visited == ([5, 4, 3] if count == 1 else [5, 4, 3, 2])


@pytest.mark.parametrize("failure", [False, True])
def test_citation_when_job_anchor_succeeds_or_fails(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str], failure: bool) -> None:
    # Given
    url = "https://github.com/o/r/actions/runs/2/job/7#step:10:35"
    anchor = Mock(side_effect=single.ArtifactError("no matching log line")) if failure else Mock(return_value=url)
    monkeypatch.setattr(single, "step_anchor", anchor, raising=False)
    # When
    code = invoke(single, ["-R", "o/r", "--run", "2", "--job", "app$", "--json"], monkeypatch)
    # Then
    assert code == 0
    result = json.loads(capsys.readouterr().out)[0]
    assert result["citation_url"] == (result["artifact_url"] if failure else url)
    anchor.assert_called_once_with("o/r", 7, 12)


def test_missing_path_when_basename_has_many_matches(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zipped:
        for n in range(7):
            zipped.writestr(f"other{n}/types.h", "example")
        zipped.writestr("irrelevant.txt", "example")
    monkeypatch.setattr(single, "download", lambda endpoint, output: output.write(archive.getvalue()))
    # When
    code = invoke(single, ["-R", "o/r", "--run", "2"], monkeypatch)
    # Then
    error = capsys.readouterr().err
    assert code == 1
    assert "dir/types.h not in artifact 12" in error
    assert all(f"other{n}/types.h" in error for n in range(5))
    assert "other5" not in error and "irrelevant" not in error


def test_unknown_run_when_api_returns_404(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(single, "gh", Mock(side_effect=single.ArtifactError("HTTP 404:\nNot Found")))
    # When
    code = invoke(single, ["-R", "o/r", "--run", "999"], monkeypatch)
    # Then
    assert code == 1
    assert capsys.readouterr().err == "gh-artifact-file: HTTP 404: Not Found\n"


def test_json_hash_when_file_is_binary(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("dir/types.h", b"\xff")
    monkeypatch.setattr(single, "download", lambda endpoint, output: output.write(archive.getvalue()))
    # When
    code = invoke(single, ["-R", "o/r", "--run", "2", "--sha256", "--json"], monkeypatch)
    # Then
    assert code == 0
    result = json.loads(capsys.readouterr().out)[0]
    assert result["sha256"] == "a8100ae6aa1940d0b663bb31cd466142ebbdbd5187131b92d93818987832eb89"
    assert "lines" not in result


def test_pagination_when_first_page_has_no_artifact(artifact: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    def gh(endpoint: str) -> str:
        if "/artifacts?" in endpoint:
            run_id = int(endpoint.split("/runs/")[1].split("/")[0])
            if run_id != 101:
                return '{"artifacts": []}'
            if endpoint.endswith("page=1"):
                return json.dumps({"artifacts": [{"id": n, "name": "unrelated", "expired": False} for n in range(100)]})
            return json.dumps({"artifacts": [{"id": 12, "name": f"build_app_{101:040x}", "expired": False}]})
        return json.dumps({"workflow_runs": [run_record(n) for n in range(100)]
                           if endpoint.endswith("page=1") else [run_record(101)]})
    monkeypatch.setattr(artifact, "gh", gh)
    # When
    code = invoke(artifact, ["-R", "o/r", "--branch", "master", "--last", "1", "--json"], monkeypatch)
    # Then
    assert code == 0
    assert [r["run_id"] for r in json.loads(capsys.readouterr().out)] == [101]


def test_explicit_runs_when_order_is_requested(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str]) -> None:
    # Given / When
    code = invoke(single, ["-R", "o/r", "--run", "2", "--run", "2"], monkeypatch)
    # Then
    output = capsys.readouterr().out
    assert code == 0
    assert output.count("0000000000 run 2 (success) 2026-10-28T12:00:00Z artifact 12") == 2
    assert output.count("alpha\nbeta RPC_TAG\ngamma RPC_TAG\ndelta\n") == 2


@pytest.mark.parametrize("options", [["--lines", "0-2"], ["--lines", "3-2"], ["--grep", "["],
                                      ["--last", "0"], ["--workflow", "product.yml"]])
def test_error_when_options_are_invalid(single: ModuleType, monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str], options: list[str]) -> None:
    # Given / When
    code = invoke(single, ["-R", "o/r", "--run", "2", *options], monkeypatch)
    # Then
    assert code == 1
    assert capsys.readouterr().err.startswith("gh-artifact-file: ")
