import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def put(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-put-description", "TEST-17", "-"])
    module = tool("jira-put-description")
    monkeypatch.setattr(module, "current_description", Mock(return_value=None))
    return module


@pytest.mark.parametrize("raw", ["{broken", "[]", "null", '{"type":"paragraph"}'])
def test_rejects_invalid_input_before_network(put: ModuleType, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    # Given
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    # When / Then: the default subprocess blocker would fail if curl were called.
    with pytest.raises(SystemExit, match="input is not"):
        put.main()


def test_payload_when_successful_put(put: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    doc = {"type": "doc", "version": 1, "content": []}
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(doc)))
    curl = Mock(return_value=put.subprocess.CompletedProcess([], 0, stdout="\n204"))
    monkeypatch.setattr(put.subprocess, "run", curl)
    # When
    put.main()
    # Then
    command = curl.call_args.args[0]
    assert json.loads(curl.call_args.kwargs["input"]) == {"fields": {"description": doc}}
    assert command[command.index("--data-binary") + 1] == "@-"
    assert "-n" in command
    assert command[command.index("-X") + 1] == "PUT"
    assert command[-1].endswith("/rest/api/3/issue/TEST-17")
    assert capsys.readouterr().out.startswith("204  https://")


def test_non_204_when_server_rejects_payload(put: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"type":"doc","version":1,"content":[]}'))
    curl = Mock(return_value=put.subprocess.CompletedProcess([], 0, stdout='{"errorMessages":["rejected"]}\n400'))
    monkeypatch.setattr(put.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match='HTTP 400\n.*rejected'):
        put.main()
    assert curl.call_count == 1


@pytest.mark.parametrize("markdown", [False, True])
def test_dry_run_when_input_is_file(put: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                  capsys: pytest.CaptureFixture[str], markdown: bool) -> None:
    # Given
    doc = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}]}
    path = tmp_path / "input"
    path.write_text("hello" if markdown else json.dumps(doc))
    monkeypatch.setattr(sys, "argv", ["jira-put-description", "TEST-17", "--dry-run", str(path)] + (["--markdown"] if markdown else []))
    check = Mock()
    monkeypatch.setattr(put, "check_doc", check)
    # When: the subprocess blocker proves no write is sent.
    put.main()
    # Then
    assert json.loads(capsys.readouterr().out) == {"fields": {"description": doc}}
    check.assert_called_once_with(doc, None)


def test_payload_when_markdown_stdin(put: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-put-description", "TEST-17", "-", "--markdown"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("# Title"))
    curl = Mock(return_value=put.subprocess.CompletedProcess([], 0, stdout="\n204"))
    monkeypatch.setattr(put.subprocess, "run", curl)
    check = Mock()
    monkeypatch.setattr(put, "check_doc", check)
    # When
    put.main()
    # Then
    doc = json.loads(curl.call_args.kwargs["input"])["fields"]["description"]
    assert doc["content"][0] == {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Title"}]}
    check.assert_called_once_with(doc, None)


def test_transport_error_when_curl_fails(put: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"type":"doc"}'))
    curl = Mock(return_value=put.subprocess.CompletedProcess([], 7, stdout="\n000", stderr="offline"))
    monkeypatch.setattr(put.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match="curl failed.*offline"):
        put.main()
    assert curl.call_count == 1


def paragraphs(*texts: str) -> dict:
    return {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": text}]} for text in texts
    ]}


def test_prose_lint_blocks_new_text_before_put(put: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the subprocess blocker would fail if the PUT were sent.
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(paragraphs("New text — with a dash."))))
    # When / Then
    with pytest.raises(SystemExit, match=r"prose-lint flagged(.|\n)*description:block 1 \(paragraph\): em-dash"):
        put.main()


def test_prose_lint_skips_text_the_description_already_has(put: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(put, "current_description", Mock(return_value=paragraphs("Old — kept.")))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(paragraphs("Old — kept.", "New and clean."))))
    curl = Mock(return_value=put.subprocess.CompletedProcess([], 0, stdout="\n204"))
    monkeypatch.setattr(put.subprocess, "run", curl)
    # When
    put.main()
    # Then
    put.current_description.assert_called_once_with("TEST-17")
    assert curl.call_count == 1


def test_no_lint_skips_check_and_baseline_fetch(put: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-put-description", "TEST-17", "-", "--no-lint"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(paragraphs("Someone else's text; kept as is."))))
    curl = Mock(return_value=put.subprocess.CompletedProcess([], 0, stdout="\n204"))
    monkeypatch.setattr(put.subprocess, "run", curl)
    # When
    put.main()
    # Then
    put.current_description.assert_not_called()
    assert curl.call_count == 1
