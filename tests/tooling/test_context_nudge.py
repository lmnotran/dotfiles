import io
import json
import sys
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def nudge(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("claude-context-nudge")


@pytest.fixture
def transcript(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "transcript.jsonl"
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"session_id": "test-session", "transcript_path": str(path)})))
    return path


def test_tier_persisted_when_cache_tokens_cross_threshold(nudge: ModuleType, transcript: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    transcript.write_text(json.dumps({"message": {"usage": {"input_tokens": 10, "cache_read_input_tokens": 199980, "cache_creation_input_tokens": 10}}}) + "\nmalformed\n")
    # When
    result = nudge.main()
    # Then
    assert result == 0
    assert set(json.loads(capsys.readouterr().out)) == {"systemMessage"}
    assert (Path.home() / ".cache/claude-context-nudge/test-session.tier").read_text() == "0"


@pytest.mark.parametrize("case", [(0, 250000, False), (1, 200000, False), (0, 300000, True)])
def test_persistence_when_tier_changes(nudge: ModuleType, transcript: Path, case: tuple[int, int, bool]) -> None:
    # Given
    previous, tokens, emits = case
    transcript.write_text(json.dumps({"usage": {"input_tokens": tokens}}))
    state = Path.home() / ".cache/claude-context-nudge/test-session.tier"
    state.parent.mkdir(parents=True)
    state.write_text(str(previous))
    output = io.StringIO()
    # When
    with redirect_stdout(output):
        assert nudge.main() == 0
    # Then
    assert bool(output.getvalue()) is emits
    assert state.read_text() == str(1 if emits else previous)


def test_latest_usage_when_older_message_exceeds_threshold(nudge: ModuleType, transcript: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    transcript.write_text('\n'.join(json.dumps({"usage": {"input_tokens": tokens}}) for tokens in (400000, 1000)))
    # When
    assert nudge.main() == 0
    # Then
    assert capsys.readouterr().out == ""
    assert not (Path.home() / ".cache/claude-context-nudge").exists()


@pytest.mark.parametrize("raw", ["", "{broken", "{}", '{"transcript_path":"/missing/synthetic/transcript"}'])
def test_silent_when_hook_input_unusable(nudge: ModuleType, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    # Given
    monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    # When / Then
    assert nudge.main() == 0
    assert output.getvalue() == ""


def test_disabled_when_stdin_not_read(nudge: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setenv("CLAUDE_CONTEXT_NUDGE_DISABLE", "1")
    # When / Then: pytest's unreadable stdin also proves early return.
    assert nudge.main() == 0


def test_invalid_tunables_and_state_when_usage_crosses_default(nudge: ModuleType, transcript: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setenv("CLAUDE_CONTEXT_NUDGE_THRESHOLD", "invalid")
    monkeypatch.setenv("CLAUDE_CONTEXT_NUDGE_STEP", "0")
    transcript.write_text(json.dumps({"usage": {"input_tokens": 300000}}))
    state = Path.home() / ".cache/claude-context-nudge/test-session.tier"
    state.parent.mkdir(parents=True)
    state.write_text("broken")
    # When
    assert nudge.main() == 0
    # Then
    assert state.read_text() == "1"
