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
    return tool("jira-put-description")


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
    curl = Mock(return_value=put.subprocess.CompletedProcess([], 0, stdout="204"))
    monkeypatch.setattr(put.subprocess, "run", curl)
    # When
    put.main()
    # Then
    command = curl.call_args.args[0]
    payload_path = command[command.index("--data-binary") + 1][1:]
    assert json.loads(Path(payload_path).read_text()) == {"fields": {"description": doc}}
    assert command[command.index("-X") + 1] == "PUT"
    assert command[-1].endswith("/rest/api/3/issue/TEST-17")
    assert capsys.readouterr().out.startswith("204  https://")


def test_non_204_when_server_rejects_payload(put: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"type":"doc","version":1,"content":[]}'))
    curl = Mock(side_effect=[
        put.subprocess.CompletedProcess([], 0, stdout="400"),
        put.subprocess.CompletedProcess([], 0, stdout='{"errorMessages":["rejected"]}'),
    ])
    monkeypatch.setattr(put.subprocess, "run", curl)
    # When / Then
    with pytest.raises(SystemExit, match='HTTP 400\n.*rejected'):
        put.main()
