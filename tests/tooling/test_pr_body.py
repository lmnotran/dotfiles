import io
import os
import subprocess
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
    monkeypatch.setattr(pr, "fetch_diff_lines", Mock(return_value=10))
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


def test_repo_flag_when_outside_checkout(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setenv("GH_REPO", "restored/at-teardown")
    monkeypatch.delenv("GH_REPO")
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17", "-R", "LEGO-CPL/p11-firmware", "--section", "## Summary"])
    fetch = Mock(return_value=BODY)
    monkeypatch.setattr(pr, "fetch_body", fetch)
    # When
    pr.main()
    # Then
    assert os.environ["GH_REPO"] == "LEGO-CPL/p11-firmware"
    fetch.assert_called_once_with(17)


def test_pr_url_when_given_instead_of_number(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    url = "https://github.com/LEGO-CPL/p11-firmware/pull/6339"
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", url + "/"])
    fetch = Mock(return_value=BODY)
    monkeypatch.setattr(pr, "fetch_body", fetch)
    # When
    pr.main()
    # Then
    fetch.assert_called_once_with(url)


def test_pr_argument_when_neither_number_nor_url(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "pull/6339"])
    # When / Then
    with pytest.raises(SystemExit) as exit_info:
        pr.main()
    assert exit_info.value.code == 2


def test_gh_failure_when_run_outside_repo(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17"])
    failure = subprocess.CalledProcessError(1, ["gh", "pr", "view", "17", "--json", "body"])
    monkeypatch.setattr(pr, "fetch_body", Mock(side_effect=failure))
    # When / Then
    with pytest.raises(SystemExit, match=r"`gh pr view 17` failed \(exit 1\).*-R OWNER/REPO"):
        pr.main()


def test_prose_lint_blocks_new_section_text(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17", "--section", "## Test plan", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("- [x] I checked it — twice."))
    monkeypatch.setattr(pr, "fetch_body", Mock(return_value=BODY))
    push = Mock()
    monkeypatch.setattr(pr, "push_body", push)
    # When / Then
    with pytest.raises(SystemExit, match=r"prose-lint flagged(.|\n)*body:1: em-dash"):
        pr.main()
    push.assert_not_called()


def test_prose_lint_skips_lines_the_section_already_has(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    body = "## Summary\n\nOld line — someone else's.\n\n" + FOOTER
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17", "--section", "## Summary", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("Old line — someone else's.\nMy new line."))
    monkeypatch.setattr(pr, "fetch_body", Mock(return_value=body))
    monkeypatch.setattr(pr, "fetch_diff_lines", Mock(return_value=10))
    push = Mock()
    monkeypatch.setattr(pr, "push_body", push)
    # When
    pr.main()
    # Then
    push.assert_called_once()


@pytest.mark.parametrize("missing_lint", [False, True])
def test_prose_lint_skipped_when_no_lint_or_missing(pr: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                    capsys: pytest.CaptureFixture[str], missing_lint: bool) -> None:
    # Given
    argv = ["gh-pr-body", "17", "--edit-file", "-"] + ([] if missing_lint else ["--no-lint"])
    monkeypatch.setattr(sys, "argv", argv)
    monkeypatch.setattr(sys, "stdin", io.StringIO("Body; with a semicolon."))
    monkeypatch.setattr(pr, "fetch_body", Mock(return_value=BODY))
    if missing_lint:
        monkeypatch.setattr(pr, "load_prose_lint", Mock(return_value=None))
    push = Mock()
    monkeypatch.setattr(pr, "push_body", push)
    # When
    pr.main()
    # Then
    push.assert_called_once()
    assert ("prose check was skipped" in capsys.readouterr().err) == missing_lint


def test_word_budget_blocks_a_long_whole_body_edit(pr: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17", "--edit-file", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("## Summary\n\n" + "word " * 61))
    monkeypatch.setattr(pr, "fetch_body", Mock(return_value=BODY))
    monkeypatch.setattr(pr, "fetch_diff_lines", Mock(return_value=400))
    push = Mock()
    monkeypatch.setattr(pr, "push_body", push)
    # When / Then
    with pytest.raises(SystemExit, match=r"over its word budget(.|\n)*summary-length"):
        pr.main()
    push.assert_not_called()


@pytest.mark.parametrize(("extra", "text"), [
    (["--section", "## Test plan"], "- [x] word word word word\n" * 50),
    (["--long", "the migration needs it"], "## Summary\n\n" + "word " * 61),
])
def test_word_budget_skipped_for_other_sections_or_with_long(pr: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                             extra: list[str], text: str) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-pr-body", "17", *extra, "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(text))
    monkeypatch.setattr(pr, "fetch_body", Mock(return_value=BODY))
    monkeypatch.setattr(pr, "fetch_diff_lines", Mock(side_effect=AssertionError("budget not checked")))
    push = Mock()
    monkeypatch.setattr(pr, "push_body", push)
    # When
    pr.main()
    # Then
    push.assert_called_once()
