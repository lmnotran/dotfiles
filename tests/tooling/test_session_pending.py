import json
import sqlite3
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest

SESSION: Final = "ses_" + "a" * 26
OTHER: Final = "ses_" + "b" * 26
QUEUED_AT: Final = 1795600000000
# A running part and a queued message as OpenCode 2 stores them.
CARD: Final = (
    '{"type":"tool","id":"toolu_1","name":"openchamber_render","state":{"status":"running","input":{"action":'
    '"render.page","parameters":{"awaitAnswer":true,"title":"Which way?","ui":"root = Stack([ask, pick])\\nask = '
    'Text(\\"Two ways to fix it.\\")\\npick = Choice(\\"plan\\", [{label: \\"First way\\", description: '
    '\\"Recommended.\\"}, {label: \\"Leave it\\", description: \\"Later.\\"}], \\"How should it go?\\")"}}}}')
ANSWER: Final = '{"text":"The answer is the first way."}'
TABLES: Final = {
    "session_v2": "CREATE TABLE session_v2 (id text PRIMARY KEY, title text)",
    "session_part": "CREATE TABLE session_part (message_id text NOT NULL, session_id text NOT NULL, ordinal integer NOT NULL, "
                    "type text NOT NULL, call_id text, time_created integer NOT NULL, time_updated integer NOT NULL, "
                    "data text NOT NULL, PRIMARY KEY (message_id, ordinal))",
    "session_inbox": "CREATE TABLE session_inbox (id text PRIMARY KEY, session_id text NOT NULL, type text NOT NULL, "
                     "payload text NOT NULL, delivery text NOT NULL, enqueued_seq integer NOT NULL, "
                     "time_created integer NOT NULL)",
}


@pytest.fixture
def pending(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("oc-session-pending")


def tool_part(name: str, given: object, status: str = "running", session: str = SESSION,
              created: int = 1) -> tuple[str, str, str]:
    data = {"type": "tool", "id": f"toolu_{created}", "name": name, "state": {"status": status, "input": given}}
    return session, json.dumps(data), str(created)


def make_db(path: Path, parts: Iterable[tuple[str, str, str]] = (),
            inbox: Iterable[tuple[str, str, int] | tuple[str, str, int, str]] = (), without: str = "") -> Path:
    con = sqlite3.connect(path)
    for name, create in TABLES.items():
        if name != without:
            con.execute(create)
    if without != "session_v2":
        con.executemany("INSERT INTO session_v2 (id) VALUES (?)", [(SESSION,), (OTHER,)])
    if without != "session_part":
        con.executemany("INSERT INTO session_part VALUES (?, ?, ?, 'tool', ?, ?, ?, ?)",
                        [(f"msg_{n}", session, n, f"toolu_{n}", int(created), int(created), data)
                         for n, (session, data, created) in enumerate(parts, 1)])
    if without != "session_inbox":
        con.executemany("INSERT INTO session_inbox VALUES (?, ?, ?, ?, 'steer', ?, ?)",
                        [(f"inb_{seq}", session, kind, payload, seq, QUEUED_AT + seq * 1000)
                         for kind, payload, seq, session in ((*entry, SESSION)[:4] for entry in inbox)])
    con.commit()
    con.close()
    return path


def at(seq: int) -> str:
    return datetime.fromtimestamp((QUEUED_AT + seq * 1000) / 1000).strftime("%Y-%m-%d %H:%M:%S")


def test_card_shows_its_question_and_choices_and_the_message_behind_it(pending: ModuleType, tmp_path: Path,
                                                                       capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db", [(SESSION, CARD, "1")], [("synthetic", ANSWER, 1)])
    # When
    code = pending.main([SESSION, "--db", str(db)])
    # Then
    assert code == 0
    assert capsys.readouterr().out == (
        f"{SESSION}: 1 tool call running, 1 message queued\n"
        "running  openchamber_render  Which way?\n"
        "    How should it go?\n"
        "      - First way: Recommended.\n"
        "      - Leave it: Later.\n"
        f"queued   {at(1)}  steer  The answer is the first way.\n"
        "A message queued behind a card waits until the card is answered.\n")


def test_html_card_shows_the_text_a_browser_would(pending: ModuleType, tmp_path: Path,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    page = ("<!doctype html><html><head><title>Hidden</title><style>.q { color: red; }</style></head><body>"
            "<p class=\"q\"><strong>Which</strong> fix &amp; why?</p>\n<script>let x = '<b>no</b>';</script>"
            "<button class=\"oc-option\">Fast</button><button>Safe</button><p>" + "word " * 100 + "</p></body></html>")
    db = make_db(tmp_path / "opencode.db", [tool_part("openchamber_render", {
        "action": "render.page", "parameters": {"title": "Pick one", "awaitAnswer": True, "html": page}})])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "running  openchamber_render  Pick one"
    assert lines[2].startswith("    Which fix & why? Fast Safe word word ")
    assert len(lines[2]) == 4 + 400 and lines[2].endswith("…")


@pytest.mark.parametrize("ui", [
    'root = Stack([pick])\npick = Choice("plan", [{label: "First"', 'root = Stack([Text("No choice here.")])',
    'root = Stack([pick]) pick = Choice("plan", ["A"]', "root := Stack([])",
])
def test_card_falls_back_to_its_program_when_it_reads_no_choice(pending: ModuleType, tmp_path: Path,
                                                                capsys: pytest.CaptureFixture[str], ui: str) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db", [tool_part("openchamber_render", {
        "action": "render.page", "parameters": {"title": "Odd", "awaitAnswer": True, "ui": ui}})])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    assert capsys.readouterr().out.splitlines()[1:] == ["running  openchamber_render  Odd", "    " + " ".join(ui.split())]


def test_card_cuts_a_long_program(pending: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    ui = 'root = Stack([Text("' + "long " * 200 + '")])'
    db = make_db(tmp_path / "opencode.db", [tool_part("openchamber_render", {
        "action": "render.page", "parameters": {"awaitAnswer": True, "ui": ui}})])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    lines = capsys.readouterr().out.splitlines()
    assert lines[1] == "running  openchamber_render"
    assert lines[2] == "    " + ui[:399] + "…"


@pytest.mark.parametrize("ui,questions", [
    ('root = Stack([Card("Pick", [Choice("a", ["One", {label: "Two"}, {label: "Say \\"three\\"", description: "3",},],)])])',
     [{"question": "a", "multiple": False, "options": [{"label": "One"}, {"label": "Two"},
                                                      {"label": 'Say "three"', "description": "3"}]}]),
    ('root = Stack([x, y])\nx = Choice("checks", [{label: "Clock \\u2713"}], "Checks", true)\n'
     'y = Choice("when", [{description: "no label", label: "Stop"}, 7, null], "When?", false)\nz = Slider("n", 0, -1.5)',
     [{"question": "Checks", "multiple": True, "options": [{"label": "Clock ✓"}]},
      {"question": "When?", "multiple": False, "options": [{"label": "Stop", "description": "no label"},
                                                           {"label": "7"}, {"label": "null"}]}]),
    ('root = Stack([Choice("q", [], "Odd \\q escape\\n")])', [{"question": "Odd q escape\n", "multiple": False,
                                                             "options": []}]),
])
def test_choices_read_from_openui_lang(pending: ModuleType, ui: str, questions: list[dict]) -> None:
    # Given / When / Then
    assert pending.choices(ui) == questions


@pytest.mark.parametrize("ui", ['root = Stack([pick]) @', '"root" = Stack([])', 'root = {1: "a"}', "root = )",
                                'root = Stack([Choice("a", ["One"]'])
def test_no_choices_when_the_program_doesnt_parse(pending: ModuleType, ui: str) -> None:
    # Given / When / Then
    assert pending.choices(ui) == []


@pytest.mark.parametrize("given,entry", [
    ("not a dict", {"tool": "openchamber_render", "card": False, "summary": '"not a dict"'}),
    ({"awaitAnswer": True, "title": "Flat", "html": "<p>x</p>", "parameters": "{broken"},
     {"tool": "openchamber_render", "card": True, "title": "Flat", "text": "x"}),
    ({"parameters": {"awaitAnswer": False, "title": "Shown", "html": "<p>x</p>"}},
     {"tool": "openchamber_render", "card": False,
      "summary": '{"parameters": {"awaitAnswer": false, "title": "Shown", "html": "<p>x</p>"}}'}),
])
def test_render_input_read_the_way_openchamber_reads_it(pending: ModuleType, given: object, entry: dict) -> None:
    # Given / When / Then
    assert pending.describe("openchamber_render", given) == entry


def test_question_shows_each_question_and_its_options(pending: ModuleType, tmp_path: Path,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db", [tool_part("question", {"questions": [
        {"header": "Reviewers", "question": "Who should review?", "multiple": True,
         "options": [{"label": "Sam (Recommended)", "description": "Most approvals"}, {"label": "Alex"}]},
        {"header": "Merge", "question": "Merge after?", "options": [{"label": "Yes"}, {"label": "No"}]}]})])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    assert capsys.readouterr().out.splitlines()[1:] == [
        "running  question  Reviewers / Merge", "    Who should review? (one or more)",
        "      - Sam (Recommended): Most approvals", "      - Alex", "    Merge after?", "      - Yes", "      - No"]


def test_other_tools_show_their_input_on_one_line(pending: ModuleType, tmp_path: Path,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    # Given: a page that doesn't wait for an answer is just another tool
    db = make_db(tmp_path / "opencode.db", [
        tool_part("shell", {"command": "git status &&\n  make test", "timeout": 60000}, created=1),
        tool_part("read", {"filePath": "/tmp/x"}, created=2),
        tool_part("shell", {"command": "x" * 200}, created=3),
        tool_part("custom_tool", {"action": "go", "limit": 3}, created=4),
        tool_part("openchamber_render", {"action": "render.page", "parameters": {"title": "Chart", "ui": "root"}},
                  created=5),
        tool_part("task", None, created=6),
    ])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    assert capsys.readouterr().out.splitlines() == [
        f"{SESSION}: 6 tool calls running", "running  shell  git status && make test", "running  read  /tmp/x",
        "running  shell  " + "x" * 159 + "…", 'running  custom_tool  {"action": "go", "limit": 3}',
        'running  openchamber_render  {"action": "render.page", "parameters": {"title": "Chart", "ui": "root"}}',
        "running  task"]


@pytest.mark.parametrize("given", [
    {"action": "render.page", "parameters": {"awaitAnswer": "true", "title": "Stringified", "html": "<p>Hi</p>"}},
    {"action": "render.page", "awaitAnswer": True, "title": "Stringified", "html": "<p>Hi</p>"},
    {"action": "render.page", "parameters": json.dumps({"awaitAnswer": True, "title": "Stringified", "html": "<p>Hi</p>"})},
])
def test_card_read_however_the_harness_passed_its_parameters(pending: ModuleType, tmp_path: Path,
                                                             capsys: pytest.CaptureFixture[str], given: dict) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db", [tool_part("openchamber_render", given)], [("synthetic", ANSWER, 1)])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    lines = capsys.readouterr().out.splitlines()
    assert lines[1:3] == ["running  openchamber_render  Stringified", "    Hi"]
    assert lines[-1] == "A message queued behind a card waits until the card is answered."


def test_lists_only_this_sessions_running_tool_calls_oldest_first(pending: ModuleType, tmp_path: Path,
                                                                  capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db", [
        tool_part("shell", {"command": "second"}, created=20),
        tool_part("shell", {"command": "first"}, created=10),
        tool_part("shell", {"command": "done"}, status="completed", created=5),
        tool_part("shell", {"command": "pending"}, status="pending", created=6),
        tool_part("shell", {"command": "elsewhere"}, session=OTHER, created=7),
        tool_part("shell", {"command": "running"}, status="error", created=8),
        (SESSION, 'not JSON, but "running"', "9"),
    ])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    assert capsys.readouterr().out.splitlines() == [f"{SESSION}: 2 tool calls running", "running  shell  first",
                                                    "running  shell  second"]


def test_queued_messages_in_order_with_their_first_line(pending: ModuleType, tmp_path: Path,
                                                        capsys: pytest.CaptureFixture[str]) -> None:
    # Given: no card is running, so there's no note about one
    db = make_db(tmp_path / "opencode.db", [tool_part("shell", {"command": "make"})], [
        ("user", '{"text":"\\n  Second line first\\nthen more"}', 2), ("compaction", "{}", 3),
        ("synthetic", ANSWER, 1), ("user", "not json", 4)])
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    assert capsys.readouterr().out.splitlines() == [
        f"{SESSION}: 1 tool call running, 4 messages queued", "running  shell  make",
        f"queued   {at(1)}  steer  The answer is the first way.", f"queued   {at(2)}  steer  Second line first",
        f"queued   {at(3)}  steer  (compaction)", f"queued   {at(4)}  steer  (user)"]


def test_nothing_pending(pending: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given: another session has a running call and a queued message
    db = make_db(tmp_path / "opencode.db", [tool_part("shell", {"command": "make"}, session=OTHER)],
                 [("synthetic", ANSWER, 1, OTHER)])
    # When
    code = pending.main([SESSION, "--db", str(db)])
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: nothing pending\n"


def test_json_prints_the_same(pending: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db", [(SESSION, CARD, "1"), tool_part("shell", {"command": "make"}, created=2)],
                 [("synthetic", ANSWER, 1)])
    # When
    pending.main([SESSION, "--db", str(db), "--json"])
    # Then
    assert json.loads(capsys.readouterr().out) == {
        "session": SESSION,
        "running": [
            {"tool": "openchamber_render", "card": True, "title": "Which way?", "questions": [
                {"question": "How should it go?", "multiple": False,
                 "options": [{"label": "First way", "description": "Recommended."},
                             {"label": "Leave it", "description": "Later."}]}]},
            {"tool": "shell", "card": False, "summary": "make"}],
        "queued": [{"queued": at(1), "delivery": "steer", "type": "synthetic", "text": "The answer is the first way."}],
        "note": "A message queued behind a card waits until the card is answered."}


def test_json_when_nothing_pending(pending: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db")
    # When
    pending.main([SESSION, "--db", str(db), "--json"])
    # Then
    assert json.loads(capsys.readouterr().out) == {"session": SESSION, "running": [], "queued": []}


def test_reads_the_database_read_only(pending: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    db = make_db(tmp_path / "open code.db", [(SESSION, CARD, "1")])
    connect = Mock(wraps=sqlite3.connect)
    monkeypatch.setattr(pending.sqlite3, "connect", connect)
    # When
    pending.main([SESSION, "--db", str(db)])
    # Then
    connect.assert_called_once_with(f"file:{tmp_path}/open%20code.db?mode=ro", uri=True)


@pytest.mark.parametrize("data_home", [True, False])
def test_default_database_follows_xdg_data_home(pending: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str], data_home: bool) -> None:
    # Given
    if data_home:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
        where = tmp_path / "data/opencode"
    else:
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        where = Path.home() / ".local/share/opencode"
    where.mkdir(parents=True)
    make_db(where / "opencode.db")
    # When
    code = pending.main([SESSION])
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: nothing pending\n"


def test_failure_when_session_is_not_in_the_database(pending: ModuleType, tmp_path: Path,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db")
    missing = "ses_" + "z" * 26
    # When
    with pytest.raises(SystemExit) as error:
        pending.main([missing, "--db", str(db)])
    # Then
    assert error.value.code == 1
    assert capsys.readouterr().err == f"oc-session-pending: no session {missing} in {db}\n"


@pytest.mark.parametrize("table", ["session_v2", "session_part", "session_inbox"])
def test_failure_when_a_table_is_missing(pending: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str],
                                         table: str) -> None:
    # Given
    db = make_db(tmp_path / "opencode.db", without=table)
    # When
    with pytest.raises(SystemExit) as error:
        pending.main([SESSION, "--db", str(db)])
    # Then
    assert error.value.code == 2
    assert capsys.readouterr().err == f"oc-session-pending: {db} has no {table} table. Is it from another OpenCode version?\n"


def test_failure_when_the_database_is_missing_or_not_one(pending: ModuleType, tmp_path: Path,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    missing, broken = tmp_path / "none.db", tmp_path / "broken.db"
    broken.write_text("not a database " * 100)
    # When / Then
    for db, reason in ((missing, f"no OpenCode database at {missing}"), (broken, f"can't read {broken}: ")):
        with pytest.raises(SystemExit) as error:
            pending.main([SESSION, "--db", str(db)])
        assert error.value.code == 2
        assert capsys.readouterr().err.startswith(f"oc-session-pending: {reason}")


@pytest.mark.parametrize("argv", [["ses_short"], ["ses_" + "a" * 25 + "!"], [], [SESSION, "--db"]])
def test_usage_error_when_arguments_are_wrong(pending: ModuleType, argv: list[str]) -> None:
    # Given / When / Then
    with pytest.raises(SystemExit) as error:
        pending.main(argv)
    assert error.value.code == 2
