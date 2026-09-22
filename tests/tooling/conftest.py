"""Offline, per-test isolation for extensionless chezmoi helpers."""

import importlib.util
import socket
import subprocess
import sys
import tempfile
from collections.abc import Callable
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest

BIN: Final = Path(__file__).resolve().parents[2] / "chezmoi/dot_local/bin"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("HOME", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "TMPDIR"):
        directory = tmp_path / name.lower()
        directory.mkdir()
        monkeypatch.setenv(name, str(directory))
    for name in (
        "GH_TOKEN", "GITHUB_TOKEN", "GH_REPO", "CLAUDE_CONTEXT_NUDGE_DISABLE",
        "CLAUDE_CONTEXT_NUDGE_THRESHOLD", "CLAUDE_CONTEXT_NUDGE_STEP",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "tmpdir"))
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    monkeypatch.chdir(tmp_path)
    for name in ("Popen", "run", "check_call", "check_output", "call"):
        monkeypatch.setattr(subprocess, name, Mock(side_effect=AssertionError("real subprocess blocked")))
    monkeypatch.setattr(socket.socket, "connect", Mock(side_effect=AssertionError("network blocked")))
    monkeypatch.setattr(socket, "create_connection", Mock(side_effect=AssertionError("network blocked")))


@pytest.fixture
def tool(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], ModuleType]:
    def load(name: str) -> ModuleType:
        module_name = "tooling_" + name.replace("-", "_")
        loader = SourceFileLoader(module_name, str(BIN / f"executable_{name}"))
        spec = importlib.util.spec_from_loader(module_name, loader)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, module_name, module)
        loader.exec_module(module)
        return module

    return load
