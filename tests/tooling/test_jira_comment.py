import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def comment(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.setattr(sys, "argv", ["jira-comment", "TEST-17", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("**hello**"))
    module = tool("jira-comment")
    monkeypatch.setattr(module, "current_comment", Mock(return_value=None))
    return module


def test_prose_lint_blocks_new_comment_text(comment: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given: the subprocess blocker would fail if the POST were sent.
    monkeypatch.setattr(sys, "stdin", io.StringIO("It builds; then it tests."))
    # When / Then
    with pytest.raises(SystemExit, match=r"prose-lint flagged(.|\n)*comment:block 1 \(paragraph\): semicolon"):
        comment.main()
    comment.current_comment.assert_not_called()


def test_prose_lint_skips_text_the_edited_comment_already_has(comment: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    old = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Old — kept."}]}]}
    monkeypatch.setattr(sys, "argv", ["jira-comment", "TEST-17", "-", "--edit", "42"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("Old — kept.\n\nNew and clean."))
    monkeypatch.setattr(comment, "current_comment", Mock(return_value=old))
    curl = Mock(return_value=comment.subprocess.CompletedProcess([], 0, stdout='{"id":"42"}\n200'))
    monkeypatch.setattr(comment.subprocess, "run", curl)
    # When
    comment.main()
    # Then
    comment.current_comment.assert_called_once_with("TEST-17", "42")
    assert curl.call_count == 1


@pytest.mark.parametrize("edit", [False, True])
def test_payload_when_posting_or_editing(comment: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                        capsys: pytest.CaptureFixture[str], edit: bool) -> None:
    # Given
    if edit:
        monkeypatch.setattr(sys, "argv", ["jira-comment", "TEST-17", "-", "--edit", "42"])
    code = "200" if edit else "201"
    curl = Mock(return_value=comment.subprocess.CompletedProcess([], 0, stdout='{"id":"42"}\n' + code))
    monkeypatch.setattr(comment.subprocess, "run", curl)
    # When
    comment.main()
    # Then
    command = curl.call_args.args[0]
    assert command[command.index("-X") + 1] == ("PUT" if edit else "POST")
    assert "-n" in command
    assert command[-1] == comment.BASE + "/rest/api/3/issue/TEST-17/comment" + ("/42" if edit else "")
    assert json.loads(curl.call_args.kwargs["input"]) == {"body": {
        "type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [
            {"type": "text", "text": "hello", "marks": [{"type": "strong"}]},
        ]}],
    }}
    assert capsys.readouterr().out == f"{code}  42  {comment.BASE}/browse/TEST-17?focusedCommentId=42\n"
    assert curl.call_count == 1


@pytest.mark.parametrize("edit,code", [(False, "200"), (False, "400"), (True, "201"), (True, "403")])
def test_failure_when_unexpected_status(comment: ModuleType, monkeypatch: pytest.MonkeyPatch, edit: bool, code: str) -> None:
    # Given
    if edit:
        monkeypatch.setattr(sys, "argv", ["jira-comment", "TEST-17", "-", "--edit", "42"])
    curl = Mock(return_value=comment.subprocess.CompletedProcess([], 0, stdout='{"errorMessages":["rejected"]}\n' + code))
    monkeypatch.setattr(comment.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match=f"HTTP {code}\n.*rejected"):
        comment.main()
    assert curl.call_count == 1


@pytest.mark.parametrize("body,edit,reason", [('{}', False, "missing comment id"), ('{"id":"43"}', True, "mismatch"),
                                            ('bad JSON', False, "non-JSON")])
def test_failure_when_response_invalid(comment: ModuleType, monkeypatch: pytest.MonkeyPatch, body: str, edit: bool, reason: str) -> None:
    # Given
    if edit:
        monkeypatch.setattr(sys, "argv", ["jira-comment", "TEST-17", "-", "--edit", "42"])
    code = "200" if edit else "201"
    monkeypatch.setattr(comment.subprocess, "run", Mock(return_value=comment.subprocess.CompletedProcess([], 0, stdout=body + "\n" + code)))
    # When / Then
    with pytest.raises(SystemExit, match=reason):
        comment.main()


@pytest.mark.parametrize("input_kind", ["markdown", "adf", "adf-payload"])
def test_dry_run_when_file_input(comment: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                capsys: pytest.CaptureFixture[str], input_kind: str) -> None:
    # Given
    doc = {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}]}
    path = tmp_path / "input"
    path.write_text({"markdown": "hello", "adf": json.dumps(doc), "adf-payload": json.dumps({"body": doc})}[input_kind])
    adf = ["--adf"] if input_kind != "markdown" else []
    monkeypatch.setattr(sys, "argv", ["jira-comment", "TEST-17", str(path), "--dry-run", "--edit", "42"] + adf)
    # When: subprocess remains blocked.
    comment.main()
    # Then
    assert json.loads(capsys.readouterr().out) == {"method": "PUT", "endpoint": comment.BASE + "/rest/api/3/issue/TEST-17/comment/42", "payload": {"body": doc}}


@pytest.mark.parametrize("raw", ["{broken", "[]", "null", '{"type":"paragraph"}'])
def test_invalid_adf_when_input_rejected(comment: ModuleType, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-comment", "TEST-17", "-", "--adf"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    # When / Then
    with pytest.raises(SystemExit, match="input"):
        comment.main()


def test_transport_failure_when_curl_fails(comment: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    curl = Mock(return_value=comment.subprocess.CompletedProcess([], 28, stdout="\n000", stderr="timeout"))
    monkeypatch.setattr(comment.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match="curl failed.*timeout"):
        comment.main()
    assert curl.call_count == 1
