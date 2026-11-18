import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

REAL_RUN: Final = subprocess.run
REAL_POPEN: Final = subprocess.Popen
SCRIPT: Final = Path(__file__).resolve().parents[2] / "chezmoi/dot_local/bin/executable_git-merge-check"
Run = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, str]:
    monkeypatch.setattr(subprocess, "Popen", REAL_POPEN)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    return {
        "HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_TERMINAL_PROMPT": "0", "GIT_CEILING_DIRECTORIES": str(tmp_path), "TMPDIR": str(scratch),
        "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.com",
    }


@pytest.fixture
def repo(env: dict[str, str], tmp_path: Path) -> Path:
    """main has a.txt and then c.txt. feature, cut after a.txt, adds b.txt."""
    root = tmp_path / "repo"
    root.mkdir()

    def git(*args: str) -> None:
        REAL_RUN(["git", *args], cwd=root, env=env, capture_output=True, text=True, timeout=10, check=True)

    git("init", "-q", "-b", "main")
    (root / "a.txt").write_text("one\n")
    git("add", "a.txt")
    git("commit", "-q", "-m", "a")
    git("switch", "-q", "-c", "feature")
    (root / "b.txt").write_text("two\n")
    git("add", "b.txt")
    git("commit", "-q", "-m", "b")
    git("switch", "-q", "main")
    (root / "c.txt").write_text("three\n")
    git("add", "c.txt")
    git("commit", "-q", "-m", "c")
    return root


@pytest.fixture
def run(env: dict[str, str], repo: Path) -> Run:
    bash = shutil.which("bash")
    assert bash is not None, "git-merge-check tests require bash"

    def invoke(*arguments: str, cwd: Path = repo) -> subprocess.CompletedProcess[str]:
        return REAL_RUN([bash, str(SCRIPT), *arguments], cwd=cwd, env=env, capture_output=True, text=True,
                        timeout=10, check=False)

    return invoke


def git(env: dict[str, str], repo: Path, *args: str) -> str:
    return REAL_RUN(["git", *args], cwd=repo, env=env, capture_output=True, text=True, timeout=10, check=True).stdout


def test_runs_the_command_on_the_merge_and_cleans_up(run: Run, env: dict[str, str], repo: Path) -> None:
    # Given main and feature each added a file
    # When
    result = run("--base", "main", "feature", "--", "sh", "-c", "cat a.txt b.txt c.txt")
    # Then the command saw both sides, and nothing is left behind
    assert result.returncode == 0
    assert result.stdout == "one\ntwo\nthree\n"
    assert "Merged feature" in result.stderr and "into main" in result.stderr
    assert git(env, repo, "worktree", "list", "--porcelain").count("worktree ") == 1
    assert list(Path(env["TMPDIR"]).iterdir()) == []
    assert git(env, repo, "branch", "--show-current") == "main\n"


def test_exits_with_the_commands_status(run: Run) -> None:
    # Given / When
    result = run("--base", "main", "feature", "--", "sh", "-c", "exit 7")
    # Then
    assert result.returncode == 7


def test_conflicts_exit_3_and_name_the_files(run: Run, env: dict[str, str], repo: Path) -> None:
    # Given both branches change a.txt
    git(env, repo, "switch", "-q", "feature")
    (repo / "a.txt").write_text("feature\n")
    git(env, repo, "commit", "-q", "-am", "feature edit")
    git(env, repo, "switch", "-q", "main")
    (repo / "a.txt").write_text("main\n")
    git(env, repo, "commit", "-q", "-am", "main edit")
    # When
    result = run("--base", "main", "feature", "--", "true")
    # Then
    assert result.returncode == 3
    assert "feature conflicts with main in:\n  a.txt" in result.stderr


def test_base_defaults_to_origin_head(run: Run, env: dict[str, str], repo: Path) -> None:
    # Given origin/HEAD points at origin/main, which has only a.txt
    git(env, repo, "update-ref", "refs/remotes/origin/main", "main~1")
    git(env, repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    # When
    result = run("feature", "--", "ls")
    # Then
    assert result.returncode == 0
    assert result.stdout.split() == ["a.txt", "b.txt"]
    assert "into origin/main" in result.stderr


def test_branch_defaults_to_head(run: Run, env: dict[str, str], repo: Path) -> None:
    # Given feature is checked out
    git(env, repo, "switch", "-q", "feature")
    # When
    result = run("--base", "main", "--", "ls")
    # Then
    assert result.stdout.split() == ["a.txt", "b.txt", "c.txt"]


def test_keep_leaves_the_worktree(run: Run, env: dict[str, str], repo: Path) -> None:
    # Given / When
    result = run("--keep", "--base", "main", "feature", "--", "true")
    # Then
    kept = Path(result.stderr.strip().rsplit(" ", 1)[-1])
    assert (kept / "b.txt").is_file() and (kept / "c.txt").is_file()
    assert git(env, repo, "worktree", "list", "--porcelain").count("worktree ") == 2


def test_checkout_hooks_do_not_run(run: Run, repo: Path) -> None:
    # Given a post-checkout hook that leaves a marker
    hook = repo / ".git/hooks/post-checkout"
    hook.write_text(f"#!/bin/sh\ntouch {repo / 'hook-ran'}\n")
    hook.chmod(0o755)
    # When
    result = run("--base", "main", "feature", "--", "true")
    # Then
    assert result.returncode == 0
    assert not (repo / "hook-ran").exists()


@pytest.mark.parametrize("arguments, message", [
    (["feature"], "Give a COMMAND after --"),
    (["--base"], "--base needs a REF"),
    (["--nope", "--", "true"], "Unknown option: --nope"),
    (["one", "two", "--", "true"], "Only one BRANCH"),
])
def test_usage_errors_exit_2(run: Run, arguments: list[str], message: str) -> None:
    # Given / When
    result = run(*arguments)
    # Then
    assert result.returncode == 2
    assert message in result.stderr
    assert "Usage: executable_git-merge-check" in result.stderr


def test_help_exits_0(run: Run) -> None:
    # Given / When
    result = run("--help")
    # Then
    assert result.returncode == 0
    assert "Exit status" in result.stdout


@pytest.mark.parametrize("arguments, message", [
    (["--base", "nope", "feature", "--", "true"], "Not a commit: nope"),
    (["feature", "--", "true"], "No origin/HEAD to default to"),
])
def test_missing_refs_exit_1(run: Run, arguments: list[str], message: str) -> None:
    # Given / When
    result = run(*arguments)
    # Then
    assert result.returncode == 1
    assert message in result.stderr


def test_outside_a_repository_exits_1(run: Run, tmp_path: Path) -> None:
    # Given / When
    result = run("--base", "main", "--", "true", cwd=tmp_path)
    # Then
    assert result.returncode == 1
    assert "inside a git repository" in result.stderr
