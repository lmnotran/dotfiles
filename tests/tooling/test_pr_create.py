import io
import json
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
    monkeypatch.setattr(module, "post_remote_link", Mock(return_value="208848"))
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
    create.post_remote_link.assert_not_called()


def test_links_the_pr_on_the_jira_issue_in_its_title(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    # When
    open_pr(create, monkeypatch)
    # Then
    create.post_remote_link.assert_called_once_with("P11F-1234", URL, f"{TITLE} #9")
    out, err = capsys.readouterr()
    assert out == URL + "\n" and "linked the PR on P11F-1234 (remote link 208848)" in err


def test_a_title_without_a_jira_key_links_nothing(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(create, "repo_info", Mock(return_value=("dotfiles", "main")))
    # When
    open_pr(create, monkeypatch, title="fix: tidy the prompt")
    # Then
    create.post_remote_link.assert_not_called()


def test_dry_run_names_the_issue_it_would_link(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch,
                                               capsys: pytest.CaptureFixture[str]) -> None:
    # When
    open_pr(create, monkeypatch, "--dry-run")
    # Then
    create.post_remote_link.assert_not_called()
    assert "would link the PR on P11F-1234" in capsys.readouterr().out


def test_a_failed_link_still_prints_the_url(create: ModuleType, gh: Mock, monkeypatch: pytest.MonkeyPatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(create, "post_remote_link", Mock(side_effect=SystemExit("gh-pr-create: HTTP 403")))
    # When / Then
    with pytest.raises(SystemExit, match="HTTP 403"):
        open_pr(create, monkeypatch)
    assert capsys.readouterr().out == URL + "\n"


@pytest.mark.parametrize("code", ["201", "200"])
def test_post_remote_link_uses_the_pr_url_as_its_global_id(tool: Callable[[str], ModuleType],
                                                           monkeypatch: pytest.MonkeyPatch, code: str) -> None:
    # Given Jira creates the link (201), or updates the one with the same globalId (200)
    module = tool("gh-pr-create")
    curl = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=f'{{"id":208848,"self":"x"}}\n{code}'))
    monkeypatch.setattr(subprocess, "run", curl)
    # When
    link_id = module.post_remote_link("P11F-1234", URL, f"{TITLE} #9")
    # Then
    command = curl.call_args.args[0]
    assert command[:2] == ["curl", "-n"] and command[-1].endswith("/rest/api/3/issue/P11F-1234/remotelink")
    assert json.loads(curl.call_args.kwargs["input"]) == {"globalId": URL, "object": {"url": URL, "title": f"{TITLE} #9"}}
    assert link_id == "208848"


@pytest.mark.parametrize(("result", "message"), [
    (subprocess.CompletedProcess([], 0, stdout='{"errorMessages":["nope"]}\n403'), "HTTP 403"),
    (subprocess.CompletedProcess([], 0, stdout="<html>\n200"), "HTTP 200"),
    (subprocess.CompletedProcess([], 6, stdout="", stderr="Could not resolve host"), "curl exit 6"),
])
def test_post_remote_link_stops_on_a_failure(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch,
                                             result: subprocess.CompletedProcess, message: str) -> None:
    # Given
    module = tool("gh-pr-create")
    monkeypatch.setattr(subprocess, "run", Mock(return_value=result))
    # When / Then
    with pytest.raises(SystemExit, match=message):
        module.post_remote_link("P11F-1234", URL, f"{TITLE} #9")


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
