import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest

REAL_RUN: Final = subprocess.run
REAL_POPEN: Final = subprocess.Popen
SCRIPT: Final = Path(__file__).resolve().parents[2] / "chezmoi/dot_local/bin/executable_chamberctl"


@pytest.fixture
def chamberctl(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Callable[[list[str]], subprocess.CompletedProcess[str]]:
    bash = shutil.which("bash")
    assert bash is not None, "chamberctl tests require bash"
    monkeypatch.setattr(subprocess, "Popen", REAL_POPEN)
    environment = {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "LC_ALL": "C", "TMPDIR": str(tmp_path)}

    def invoke(arguments: list[str]) -> subprocess.CompletedProcess[str]:
        return REAL_RUN([bash, str(SCRIPT), *arguments], cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10, check=False)

    return invoke


@pytest.mark.parametrize("arguments", [[], ["--help"], ["help"]])
def test_help_when_requested(chamberctl: Callable[[list[str]], subprocess.CompletedProcess[str]], arguments: list[str]) -> None:
    # Given / When
    result = chamberctl(arguments)
    # Then
    assert result.returncode == 0
    assert "Usage: chamberctl" in result.stdout
    assert "migrate [--yes]" in result.stdout


def test_unknown_command_when_given(chamberctl: Callable[[list[str]], subprocess.CompletedProcess[str]]) -> None:
    # Given / When
    result = chamberctl(["bogus"])
    # Then
    assert result.returncode == 2
    assert "Unknown command: bogus" in result.stderr
