import json
import sqlite3
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest

PARENT: Final = "ses_" + "p" * 26
CHILD: Final = "ses_" + "c" * 26
GRANDCHILD: Final = "ses_" + "g" * 26
TEAM_MEMBER: Final = "ses_" + "t" * 26
OTHER_MAIN: Final = "ses_" + "o" * 26
UNRELATED: Final = "ses_" + "u" * 26


@pytest.fixture
def purge(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("oc-session-purge")


def write_transcript(path: Path, entries: list[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((entry if isinstance(entry, str) else json.dumps(entry)) + "\n" for entry in entries))


def result(tool_name: str, output: object) -> dict[str, object]:
    return {"type": "tool_result", "tool_name": tool_name, "tool_input": {}, "tool_output": output}


def make_db(path: Path, rows: list[tuple[str, str | None]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session (id TEXT PRIMARY KEY, parent_id TEXT)")
    con.executemany("INSERT INTO session VALUES (?, ?)", rows)
    con.commit()
    con.close()
    return path


def test_spawned_ids_when_transcript_mixes_tools(purge: ModuleType, tmp_path: Path) -> None:
    # Given
    transcript = tmp_path / "t.jsonl"
    write_transcript(transcript, [
        result("task", f"Background task launched.\nsession_id: {CHILD}"),
        result("team_create", {"members": [{"sessionId": TEAM_MEMBER}], "lead": PARENT}),
        result("session_read", f"Session: {UNRELATED}"),
        {"type": "tool_use", "tool_name": "task", "tool_input": {"task_id": UNRELATED}},
        "not json",
    ])
    # When
    found = purge.spawned_ids(transcript)
    # Then
    assert found == {CHILD, TEAM_MEMBER, PARENT}


def test_collect_when_spawned_id_is_top_level_session(purge: ModuleType, tmp_path: Path) -> None:
    # Given
    transcripts = tmp_path / "transcripts"
    write_transcript(transcripts / f"{PARENT}.jsonl", [result("task", f"session_id: {CHILD} and {OTHER_MAIN}")])
    db = purge.SessionDB(make_db(tmp_path / "oc.db", [(PARENT, None), (OTHER_MAIN, None)]))
    # When
    order, skipped = purge.collect([PARENT], db, transcripts)
    # Then
    assert order == [CHILD, PARENT]
    assert skipped == {OTHER_MAIN: PARENT}


def test_dry_run_when_copies_exist(purge: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    home = Path.home()
    transcript = home / ".claude/transcripts" / f"{PARENT}.jsonl"
    write_transcript(transcript, [result("task", f"session_id: {CHILD}")])
    scan = tmp_path / "scan"
    (scan / "digests").mkdir(parents=True)
    digest = scan / "digests" / f"{PARENT}.txt"
    digest.write_text("x")
    run = Mock()
    monkeypatch.setattr(purge.subprocess, "run", run)
    # When
    code = purge.main(["--dry-run", "--scan", str(scan), PARENT])
    # Then
    assert code == 0
    assert transcript.exists() and digest.exists()
    run.assert_not_called()
    out = capsys.readouterr().out
    assert f"would delete {transcript}" in out
    assert f"would delete {digest}" in out


def test_purge_when_children_span_database_and_transcripts(purge: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    home = Path.home()
    transcripts = home / ".claude/transcripts"
    write_transcript(transcripts / f"{PARENT}.jsonl", [result("team_create", f"lead {PARENT} member {TEAM_MEMBER}")])
    write_transcript(transcripts / f"{CHILD}.jsonl", [result("call_omo_agent", f"session_id: {GRANDCHILD}")])
    write_transcript(transcripts / f"{GRANDCHILD}.jsonl", [])
    write_transcript(transcripts / f"{TEAM_MEMBER}.jsonl", [])
    write_transcript(transcripts / f"{UNRELATED}.jsonl", [])
    storage = home / ".local/share/opencode/storage"
    (storage / "directory-readme").mkdir(parents=True)
    state = storage / "directory-readme" / f"{CHILD}.json"
    state.write_text("{}")
    keep_state = storage / "directory-readme" / f"{UNRELATED}.json"
    keep_state.write_text("{}")
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / f"{GRANDCHILD}.users.txt").write_text("x")
    (scan / "keep.txt").write_text("x")
    db = make_db(tmp_path / "oc.db", [(PARENT, None), (CHILD, PARENT), (UNRELATED, None)])
    run = Mock(return_value=subprocess.CompletedProcess([], 0, "", ""))
    monkeypatch.setattr(purge.subprocess, "run", run)
    # When
    code = purge.main(["--db", str(db), "--scan", str(scan), PARENT])
    # Then
    assert code == 0
    deleted = [call.args[0] for call in run.call_args_list]
    assert deleted == [["opencode", "session", "delete", CHILD], ["opencode", "session", "delete", PARENT]]
    for sid in (PARENT, CHILD, GRANDCHILD, TEAM_MEMBER):
        assert not (transcripts / f"{sid}.jsonl").exists()
    assert (transcripts / f"{UNRELATED}.jsonl").exists()
    assert not state.exists() and keep_state.exists()
    assert sorted(p.name for p in scan.iterdir()) == ["keep.txt"]


def test_exit_code_when_database_delete_fails(purge: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    db = make_db(tmp_path / "oc.db", [(PARENT, None)])
    run = Mock(return_value=subprocess.CompletedProcess([], 1, "", "Error: locked"))
    monkeypatch.setattr(purge.subprocess, "run", run)
    # When
    code = purge.main(["--db", str(db), "--scan", str(tmp_path / "none"), PARENT])
    # Then
    assert code == 1


def test_invalid_session_id_when_given(purge: ModuleType) -> None:
    # Given / When / Then
    with pytest.raises(SystemExit) as exit_info:
        purge.main(["ses_short"])
    assert exit_info.value.code == 2
