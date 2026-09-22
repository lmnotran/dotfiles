import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

REAL_RUN: Final = subprocess.run
REAL_POPEN: Final = subprocess.Popen
SCRIPT: Final = Path(__file__).resolve().parents[2] / "chezmoi/dot_local/bin/executable_sandbox"


@pytest.fixture
def sandbox(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[list[str]], subprocess.CompletedProcess[str]]:
    bash = shutil.which("bash")
    assert bash is not None, "sandbox tests require bash"
    monkeypatch.setattr(subprocess, "Popen", REAL_POPEN)
    environment = {
        "HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull, "GIT_TERMINAL_PROMPT": "0",
        "GIT_CEILING_DIRECTORIES": str(tmp_path), "GIT_MASTER": "1",
        "TMPDIR": str(tmp_path),
    }

    def invoke(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return REAL_RUN([bash, str(SCRIPT), *arguments], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10, check=False)

    return invoke


@pytest.mark.parametrize("arguments", [[], ["--help"], ["help"]])
def test_help_when_outside_repository(sandbox: Callable[[list[str]], subprocess.CompletedProcess[str]], arguments: list[str]) -> None:
    # Given / When
    result = sandbox(arguments)
    # Then
    assert result.returncode == 0
    assert "Usage: sandbox" in result.stdout
    assert "create <name>" in result.stdout


def test_unknown_command_when_outside_repository(sandbox: Callable[[list[str]], subprocess.CompletedProcess[str]]) -> None:
    # Given / When
    result = sandbox(["unknown-command"])
    # Then
    assert result.returncode == 1
    assert "Unknown command: unknown-command" in result.stderr


@pytest.mark.parametrize("arguments", [["create", "test"], ["list"], ["rm", "test"], ["cd", "test"], ["cleanup", "--yes"]])
def test_repository_required_when_outside_repository(sandbox: Callable[[list[str]], subprocess.CompletedProcess[str]], arguments: list[str]) -> None:
    # Given / When
    result = sandbox(arguments)
    # Then
    assert result.returncode == 1
    assert "not in a git repo" in result.stderr
