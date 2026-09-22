import io
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest

FOOTER: Final = "[P11F-123](https://jira.invalid/browse/P11F-123)\n\n[P11F-123]: https://jira.invalid/?atlOrigin=x"
BODY: Final = "## Summary\n\nOriginal\n\n## Test plan\n\nOld\n### Nested\nDetails\n\n" + FOOTER


@pytest.fixture
def pr(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-pr-body")


def test_nested_section_when_followed_by_peer(pr: ModuleType) -> None:
    # Given
    body = "## A\nalpha\n### Child\nbeta\n## B\ngamma"
    # When
    section = pr.extract_section(body, "## A")
    # Then
    assert section == "## A\nalpha\n### Child\nbeta\n"


@pytest.mark.parametrize("replacement", ["New", "## Test plan\nNew"])
def test_last_section_edit_when_footer_exists(pr: ModuleType, monkeypatch: pytest.MonkeyPatch, replacement: str) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17", "--section", "## Test plan", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(replacement))
    monkeypatch.setattr(pr, "fetch_body", Mock(return_value=BODY))
    push = Mock()
    monkeypatch.setattr(pr, "push_body", push)
    # When
    pr.main()
    # Then
    sent = push.call_args.args[1]
    assert sent.startswith("## Summary\n\nOriginal\n\n## Test plan\n")
    assert "New" in sent and "Old" not in sent and "Details" not in sent
    assert sent.endswith(FOOTER + "\n")
    assert sent.count("## Test plan") == 1


def test_replacement_footer_wins_when_replacing_body(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    replacement = "## Summary\nChanged\n\n[P11F-999]: https://jira.invalid/new"
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17", "--edit-file", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(replacement))
    monkeypatch.setattr(pr, "fetch_body", Mock(return_value=BODY))
    push = Mock()
    monkeypatch.setattr(pr, "push_body", push)
    # When
    pr.main()
    # Then
    push.assert_called_once_with(17, replacement + "\n")


def test_missing_section_when_requested(pr: ModuleType) -> None:
    # Given / When / Then
    with pytest.raises(SystemExit, match="section not found"):
        pr.extract_section(BODY, "## Missing")


def test_reference_inside_body_when_not_trailing(pr: ModuleType) -> None:
    # Given
    body = "[ref]: https://example.invalid\n\nNot a footer"
    # When / Then
    assert pr.split_footer(body) == (body, "")


def test_push_when_server_normalizes_whitespace(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    edit = Mock()
    fetch = Mock(return_value="## Summary\r\nNew\r\n")
    monkeypatch.setattr(pr.subprocess, "check_call", edit)
    monkeypatch.setattr(pr.subprocess, "check_output", fetch)
    # When
    pr.push_body(17, "## Summary  \nNew\n")
    # Then
    command = edit.call_args.args[0]
    assert command[:5] == ["gh", "pr", "edit", "17", "-F"]
    assert Path(command[5]).read_text() == "## Summary  \nNew\n"
    assert fetch.call_args.args[0][:4] == ["gh", "pr", "view", "17"]


def test_push_when_server_retains_old_body(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(pr.subprocess, "check_call", Mock())
    monkeypatch.setattr(pr.subprocess, "check_output", Mock(return_value="Old"))
    # When / Then
    with pytest.raises(SystemExit, match="verify failed"):
        pr.push_body(17, "New")
