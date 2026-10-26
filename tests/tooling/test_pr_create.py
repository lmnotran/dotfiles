import io
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest

TITLE: Final = "CI_CD: Fix the cache key (P11F-1234)"
BODY: Final = "Fixes the venv cache key, so branches restore master's copy.\n\n[P11F-1234](https://jira.invalid/browse/P11F-1234)\n"
URL: Final = "https://github.com/LEGO-CPL/p11-firmware/pull/9"


@pytest.fixture
def create(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ModuleType:
    module = tool("gh-pr-create")
    components = tmp_path / "scripts/changelog/our_github.py"
    components.parent.mkdir(parents=True)
    components.write_text('KNOWN_COMPONENTS = {\n    "AB",\n    "CI_CD",\n    "TEST"\n}\n')
    monkeypatch.setattr(module, "repo_info", Mock(return_value=("p11-firmware", "master")))
    monkeypatch.setattr(module, "diff_lines", Mock(return_value=12))
    monkeypatch.setattr(module, "git", Mock(return_value=f"{tmp_path}\n"))
    return module


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> Mock:
    create_call = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=f"Creating draft pull request\n{URL}\n"))
    monkeypatch.setattr(subprocess, "run", create_call)
    # The live body is what was sent, plus the footer the Jira integration appends once the PR opens.
    monkeypatch.setattr(subprocess, "check_output", Mock(
        side_effect=lambda *_, **__: create_call.call_args.kwargs["input"] + "\n[P11F-1234]: https://jira.invalid/?atlOrigin=x\n"))
    return create_call


def open_pr(create: ModuleType, monkeypatch: pytest.MonkeyPatch, *extra: str,
            title: str = TITLE, body: str = BODY) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(body))
    create.main(["--title", title, "--body-file", "-", *extra])


def test_opens_a_draft_and_prints_the_url(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch,
                                          capsys: pytest.CaptureFixture[str]) -> None:
    # When
    open_pr(create, monkeypatch)
    # Then
    command = gh.call_args.args[0]
    assert command[:3] == ["gh", "pr", "create"] and "--draft" in command
    assert command[command.index("--title") + 1] == TITLE and command[command.index("--base") + 1] == "master"
    assert gh.call_args.kwargs["input"] == BODY
    assert capsys.readouterr().out == URL + "\n"


@pytest.mark.parametrize(("title", "count"), [
    ("CI_CD: Fix the cache key (P11F-1234)", 0),
    ("AB, TEST: Fix the cache key (P11F-1234)", 0),
    ("CI_CD: Fix the cache key", 1),
    ("CI_CD: fix the cache key. (P11F-1234)", 2),
    ("CI: Fix the cache key (P11F-1234)", 1),
])
def test_title_problems(create: ModuleType, title: str, count: int) -> None:
    assert len(create.title_problems(title, frozenset({"AB", "CI_CD", "TEST"}))) == count


def test_known_components_come_from_the_changelog_script(create: ModuleType, tmp_path: Path) -> None:
    assert create.known_components(tmp_path) == frozenset({"AB", "CI_CD", "TEST"})
    assert create.known_components(tmp_path / "elsewhere") is None


@pytest.mark.parametrize(("extra", "title", "body", "rule"), [
    ([], "CI: Fix the cache key (P11F-1234)", BODY, "unknown component"),
    ([], TITLE, "Fixes the cache key — for real.\n", "em-dash"),
    ([], TITLE, "Fixes the cache key.\n\n" + "word " * 150, "body-length"),
    (["--long", "the migration needs it"], TITLE, "Fixes it; for real.\n", "semicolon"),
])
def test_stops_before_the_pr_exists_when_a_check_fails(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch,
                                                       extra: list[str], title: str, body: str, rule: str) -> None:
    # When / Then
    with pytest.raises(SystemExit, match=rule):
        open_pr(create, monkeypatch, *extra, title=title, body=body)
    gh.assert_not_called()


def test_long_reason_skips_the_word_budget(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    # When
    open_pr(create, monkeypatch, "--long", "the migration needs it", body="Fixes the cache key.\n\n" + "word " * 150)
    # Then
    gh.assert_called_once()
    assert "word budget skipped: the migration needs it" in capsys.readouterr().err


def test_ready_and_title_format_outside_p11_repos(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(create, "repo_info", Mock(return_value=("dotfiles", "main")))
    # When
    open_pr(create, monkeypatch, "--ready", title="fix: tidy the prompt")
    # Then
    command = gh.call_args.args[0]
    assert "--draft" not in command and command[command.index("--base") + 1] == "main"


def test_dry_run_prints_the_command_without_creating(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    # When
    open_pr(create, monkeypatch, "--dry-run")
    # Then
    gh.assert_not_called()
    assert capsys.readouterr().out.startswith("would run: gh pr create --title")


def test_fails_loudly_when_the_live_body_differs(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(subprocess, "check_output", Mock(return_value="Something else\n"))
    # When / Then
    with pytest.raises(SystemExit, match="doesn't match"):
        open_pr(create, monkeypatch)


def test_diff_lines_counts_text_changes_against_the_fetched_base(tool: Callable[[str], ModuleType],
                                                                 monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    module = tool("gh-pr-create")
    git = Mock(side_effect=["", "3\t1\tsrc/a.c\n-\t-\tlogo.png\n10\t0\tdocs/b.md\n"])
    monkeypatch.setattr(module, "git", git)
    # When / Then
    assert module.diff_lines("master") == 14
    assert [call.args for call in git.call_args_list] == [
        ("fetch", "--quiet", "origin", "master"), ("diff", "--numstat", "origin/master...HEAD")]
