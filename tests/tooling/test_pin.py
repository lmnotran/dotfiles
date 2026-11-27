import email.message
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest

SESSION: Final = "ses_" + "a" * 26
PASSWORD: Final = "correct horse"
COOKIE: Final = "oc_ui_session_3000=signed"
NOW: Final = 1795700000000
EARLIER: Final = 1795600000000
TEAMS: Final = "steams"
REVIEW: Final = "sreview"
LISTS: Final = [{"id": REVIEW, "name": "Needs review"}, {"id": TEAMS, "name": "Send in Teams"}]
WORK: Final = {"state": "open", "openedAt": EARLIER, "openedBy": "auto"}
METADATA_PATH: Final = f"/api/openchamber/sessions/{SESSION}/metadata"


def merged(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Apply a JSON merge patch, as OpenChamber's server does."""
    result = dict(current)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict):
            result[key] = merged(result.get(key) if isinstance(result.get(key), dict) else {}, value)
        else:
            result[key] = value
    return result


class Response(io.BytesIO):
    def __init__(self, body: object, cookies: tuple[str, ...] = ()) -> None:
        super().__init__(json.dumps(body).encode())
        self.headers = email.message.Message()
        for cookie in cookies:
            self.headers["Set-Cookie"] = cookie


class FakeChamber:
    """OpenChamber's login, settings and session metadata routes, in memory."""

    def __init__(self, metadata: dict[str, Any], races: tuple[dict[str, Any], ...] = ()) -> None:
        self.metadata = metadata
        # Patches another writer lands just before each of the next compare-and-sets.
        self.races = list(races)
        self.calls: list[tuple[str, str, Any]] = []

    def urlopen(self, request: urllib.request.Request, timeout: float) -> Response:
        url = urllib.parse.urlsplit(request.full_url)
        body = json.loads(request.data) if isinstance(request.data, bytes) else None
        self.calls.append((request.get_method(), url.path, body))
        if url.path == "/auth/session":
            if body != {"password": PASSWORD}:
                raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", email.message.Message(),
                                             io.BytesIO(b'{"error":"Invalid credentials"}'))
            return Response({"authenticated": True}, (f"{COOKIE}; Path=/; HttpOnly; SameSite=Strict",))
        assert request.get_header("Cookie") == COOKIE
        if url.path == "/api/config/settings":
            return Response({"sidebarPinLists": LISTS, "sidebarSections": []})
        if url.path == METADATA_PATH:
            return Response({"metadata": self.metadata})
        assert url.path == METADATA_PATH + "/compare-and-set"
        if self.races:
            self.metadata = merged(self.metadata, self.races.pop(0))
        if body["expected"] != self.metadata:
            return Response({"metadata": self.metadata, "conflict": True})
        self.metadata = merged(self.metadata, body["patch"])
        return Response({"metadata": self.metadata, "conflict": False})

    def writes(self) -> list[Any]:
        return [body["patch"] for method, path, body in self.calls if path.endswith("/compare-and-set")]


@pytest.fixture
def pin(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    for name in ("OPENCHAMBER_UI_PASSWORD", "OPENCHAMBER_AGENT_TOOL_URL", "OPENCHAMBER_DATA_DIR", "OPENCODE_SESSION_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENCHAMBER_UI_PASSWORD", PASSWORD)
    monkeypatch.setenv("OPENCODE_SESSION_ID", SESSION)
    module = tool("oc-pin")
    monkeypatch.setattr(module, "now", lambda: NOW)
    return module


def serve(monkeypatch: pytest.MonkeyPatch, metadata: dict[str, Any], races: tuple[dict[str, Any], ...] = ()) -> FakeChamber:
    chamber = FakeChamber(metadata, races)
    monkeypatch.setattr(urllib.request, "urlopen", chamber.urlopen)
    return chamber


def run(pin: ModuleType, *argv: str) -> int:
    try:
        return int(pin.main(list(argv)))
    except SystemExit as exit_info:
        return int(exit_info.code or 0)


def test_pins_the_session_and_leaves_in_work_alone(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    chamber = serve(monkeypatch, {"openchamber": {"work": WORK}, "other": 1})
    # When
    code = run(pin, "send in teams")
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: pinned to Send in Teams\n"
    assert chamber.calls[0] == ("POST", "/auth/session", {"password": PASSWORD})
    assert chamber.writes() == [{"openchamber": {"pinned": {"at": NOW, "list": TEAMS}}}]
    assert chamber.metadata == {"openchamber": {"work": WORK, "pinned": {"at": NOW, "list": TEAMS}}, "other": 1}


def test_a_move_keeps_when_it_was_pinned_and_pinned_is_the_plain_section(
        pin: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    chamber = serve(monkeypatch, {"openchamber": {"pinned": {"at": EARLIER, "list": TEAMS}}})
    # When
    code = run(pin, "Pinned")
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: moved from Send in Teams to Pinned\n"
    assert chamber.writes() == [{"openchamber": {"pinned": {"list": None}}}]
    assert chamber.metadata == {"openchamber": {"pinned": {"at": EARLIER}}}


@pytest.mark.parametrize("argv,pinned,said", [
    (("Send in Teams",), {"at": EARLIER, "list": TEAMS}, "already pinned to Send in Teams"),
    (("--if-unpinned", "Send in Teams"), {"at": EARLIER, "list": REVIEW}, "left pinned to Needs review"),
    (("--if-unpinned", "Send in Teams"), {"at": EARLIER}, "left pinned to Pinned"),
    (("--unpin", "Send in Teams"), {"at": EARLIER, "list": REVIEW}, "pinned to Needs review, not Send in Teams, so left there"),
    (("--unpin",), None, "not pinned"),
    (("--unpin",), {"list": TEAMS}, "not pinned"),
])
def test_writes_nothing_when_the_pin_is_already_right(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                      capsys: pytest.CaptureFixture[str], argv: tuple[str, ...],
                                                      pinned: dict[str, Any] | None, said: str) -> None:
    # Given
    chamber = serve(monkeypatch, {"openchamber": {"pinned": pinned}} if pinned else {})
    # When
    code = run(pin, *argv)
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: {said}\n"
    assert chamber.writes() == []


@pytest.mark.parametrize("argv", [("--unpin",), ("--unpin", "send in teams")])
def test_unpins_the_session(pin: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                            argv: tuple[str, ...]) -> None:
    # Given
    chamber = serve(monkeypatch, {"openchamber": {"work": WORK, "pinned": {"at": EARLIER, "list": TEAMS}}})
    # When
    code = run(pin, *argv)
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: unpinned from Send in Teams\n"
    assert chamber.writes() == [{"openchamber": {"pinned": None}}]
    assert chamber.metadata == {"openchamber": {"work": WORK}}


def test_writes_again_when_the_metadata_changed_under_it(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    done = {"openchamber": {"work": {"state": "done", "doneAt": NOW}}}
    chamber = serve(monkeypatch, {"openchamber": {"work": WORK}}, races=(done,))
    # When
    code = run(pin, "--if-unpinned", "Send in Teams")
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: pinned to Send in Teams\n"
    assert len(chamber.writes()) == 2
    assert chamber.metadata == {"openchamber": {"work": {**WORK, "state": "done", "doneAt": NOW},
                                                "pinned": {"at": NOW, "list": TEAMS}}}


def test_a_race_that_pins_it_first_is_respected(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    chamber = serve(monkeypatch, {}, races=({"openchamber": {"pinned": {"at": EARLIER, "list": REVIEW}}},))
    # When
    code = run(pin, "--if-unpinned", "Send in Teams")
    # Then
    assert code == 0
    assert capsys.readouterr().out == f"{SESSION}: left pinned to Needs review\n"
    assert chamber.metadata == {"openchamber": {"pinned": {"at": EARLIER, "list": REVIEW}}}


def test_gives_up_when_the_metadata_keeps_changing(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    chamber = serve(monkeypatch, {}, races=tuple({"n": n} for n in range(5)))
    # When
    code = run(pin, "Send in Teams")
    # Then
    assert code == 1
    assert "metadata kept changing while it was written, 5 times" in capsys.readouterr().err
    assert len(chamber.writes()) == 5


def test_an_unknown_list_names_the_lists(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                         capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    chamber = serve(monkeypatch, {})
    # When
    code = run(pin, "Later")
    # Then
    assert code == 1
    assert capsys.readouterr().err == "oc-pin: no pin list named 'Later'. The lists: Pinned, Needs review, Send in Teams\n"
    assert chamber.writes() == []


def test_lists_prints_the_names(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(monkeypatch, {})
    monkeypatch.delenv("OPENCODE_SESSION_ID")
    # When
    code = run(pin, "--lists")
    # Then
    assert code == 0
    assert capsys.readouterr().out == "Pinned\nNeeds review\nSend in Teams\n"


def test_password_and_address_come_from_the_running_instance(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                             tmp_path: Path) -> None:
    # Given
    monkeypatch.delenv("OPENCHAMBER_UI_PASSWORD")
    monkeypatch.setenv("OPENCHAMBER_AGENT_TOOL_URL", "http://127.0.0.1:4100/api/openchamber/agent-tool")
    monkeypatch.setenv("OPENCHAMBER_DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data/run").mkdir(parents=True)
    (tmp_path / "data/run/openchamber-4100.json").write_text(json.dumps({"port": 4100, "uiPassword": PASSWORD}))
    chamber = serve(monkeypatch, {})
    urls: list[str] = []
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda request, timeout: urls.append(request.full_url) or chamber.urlopen(request, timeout))
    # When
    code = run(pin, "Send in Teams")
    # Then
    assert code == 0
    assert chamber.calls[0] == ("POST", "/auth/session", {"password": PASSWORD})
    assert {urllib.parse.urlsplit(url).netloc for url in urls} == {"127.0.0.1:4100"}


def test_a_refused_password_fails(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                  capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setenv("OPENCHAMBER_UI_PASSWORD", "wrong")
    chamber = serve(monkeypatch, {})
    # When
    code = run(pin, "Send in Teams")
    # Then
    assert code == 1
    assert capsys.readouterr().err == "oc-pin: POST /auth/session answered 401: Invalid credentials\n"
    assert len(chamber.calls) == 1


def test_an_unreachable_openchamber_fails(pin: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                          capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    def refuse(request: urllib.request.Request, timeout: float) -> None:
        raise urllib.error.URLError(ConnectionRefusedError(111, "Connection refused"))

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    # When
    code = run(pin, "Send in Teams")
    # Then
    assert code == 1
    assert capsys.readouterr().err.startswith("oc-pin: can't reach OpenChamber at http://127.0.0.1:3000: ")


@pytest.mark.parametrize("argv,session,error", [
    ((), SESSION, "name the pin list to pin the session to, or use --unpin or --lists"),
    (("--if-unpinned",), SESSION, "name the pin list to pin the session to, or use --unpin or --lists"),
    (("--lists", "Send in Teams"), SESSION, "--lists takes no LIST"),
    (("--unpin", "--if-unpinned"), SESSION, "not allowed with argument"),
    (("Send in Teams",), None, "no session: run it in an OpenCode session, or pass --session"),
    (("Send in Teams",), "ses_short", "not an OpenCode session ID"),
    (("Send in Teams", "--session", "abc"), SESSION, "not an OpenCode session ID"),
])
def test_usage_errors(pin: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
                      argv: tuple[str, ...], session: str | None, error: str) -> None:
    # Given
    chamber = serve(monkeypatch, {})
    if session is None:
        monkeypatch.delenv("OPENCODE_SESSION_ID")
    else:
        monkeypatch.setenv("OPENCODE_SESSION_ID", session)
    # When
    code = run(pin, *argv)
    # Then
    assert code == 2
    assert error in capsys.readouterr().err
    assert chamber.calls == []
