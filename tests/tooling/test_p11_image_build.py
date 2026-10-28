import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import Mock

import pytest

REGISTRY = "ghcr.io/lego-cpl/firmware-developer-p11"

DOCKERFILES = {
    "build-base/Dockerfile": "ARG UBUNTU_VERSION=26.04\nFROM ubuntu:${UBUNTU_VERSION}\n",
    "python-tools/Dockerfile": f"ARG BASE_TAG=latest\nFROM {REGISTRY}-build-base:${{BASE_TAG}} AS build-base\n",
    "unit-test/Dockerfile": (f"ARG BASE_TAG=latest\nFROM {REGISTRY}-python-tools:${{BASE_TAG}} AS catch2-builder\n"
                             f"FROM {REGISTRY}-python-tools:${{BASE_TAG}} AS python-tools\n"),
    "firmware-build-toolchain/Dockerfile": f"ARG BASE_TAG=latest\nFROM {REGISTRY}-build-base:${{BASE_TAG}} AS installer\n",
    "Dockerfile": (f"ARG BASE_TAG=latest\nARG EMM_TAG=latest\n"
                   f"FROM {REGISTRY}-firmware-build-toolchain:${{EMM_TAG}} AS toolchain\n"
                   f"FROM {REGISTRY}-unit-test:${{BASE_TAG}}\n"),
}


@pytest.fixture
def build(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("p11-image-build")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "builder"
    for path, text in DOCKERFILES.items():
        target = root / "firmware-developer-p11" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    (root / "firmware-developer-p11" / "ceedling").mkdir()
    return root


def test_discover_when_images_from_registry_parents(build: ModuleType, repo: Path) -> None:
    # Given / When
    images = build.discover(repo)
    # Then
    assert sorted(images) == ["build-base", "firmware-build-toolchain", "monolith", "python-tools", "unit-test"]
    assert images["unit-test"].parents == ("python-tools",)
    assert images["monolith"].parents == ("firmware-build-toolchain", "unit-test")
    assert images["build-base"].args == frozenset({"UBUNTU_VERSION"})


def test_closure_when_monolith_requested(build: ModuleType, repo: Path) -> None:
    # Given
    images = build.discover(repo)
    # When
    order = build.closure(images, ["monolith"])
    # Then
    assert order == ["build-base", "firmware-build-toolchain", "python-tools", "unit-test", "monolith"]


def test_closure_when_image_unknown(build: ModuleType, repo: Path) -> None:
    # Given
    images = build.discover(repo)
    # When / Then
    with pytest.raises(build.BuildError, match="unknown image 'nope'; images: build-base, "):
        build.closure(images, ["nope"])


def test_bake_definition_when_child_requested(build: ModuleType, repo: Path) -> None:
    # Given
    images = build.discover(repo)
    # When
    definition = build.bake_definition(repo, images, ["unit-test"], "try1")
    # Then
    context = str(repo / "firmware-developer-p11")
    assert definition == {"target": {
        "build-base": {"context": context, "dockerfile": f"{context}/build-base/Dockerfile", "args": {},
                       "contexts": {}, "output": ["type=cacheonly"]},
        "python-tools": {"context": context, "dockerfile": f"{context}/python-tools/Dockerfile", "args": {"BASE_TAG": "try1"},
                         "contexts": {f"{REGISTRY}-build-base:try1": "target:build-base"}, "output": ["type=cacheonly"]},
        "unit-test": {"context": context, "dockerfile": f"{context}/unit-test/Dockerfile", "args": {"BASE_TAG": "try1"},
                      "contexts": {f"{REGISTRY}-python-tools:try1": "target:python-tools"}, "output": ["type=docker"],
                      "tags": [f"{REGISTRY}-unit-test:try1"]},
    }}


def test_monolith_tag_and_emm_arg(build: ModuleType, repo: Path) -> None:
    # Given
    images = build.discover(repo)
    # When
    target = build.bake_definition(repo, images, ["monolith"], "local")["target"]["monolith"]
    # Then
    assert target["tags"] == [f"{REGISTRY}:local"]
    assert target["args"] == {"BASE_TAG": "local", "EMM_TAG": "local"}
    assert target["contexts"] == {f"{REGISTRY}-firmware-build-toolchain:local": "target:firmware-build-toolchain",
                                  f"{REGISTRY}-unit-test:local": "target:unit-test"}


def test_print_when_requested_runs_nothing(build: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["p11-image-build", "--repo", str(repo), "--print", "python-tools"])
    # When
    build.main()
    # Then
    assert sorted(json.loads(capsys.readouterr().out)["target"]) == ["build-base", "python-tools"]


@pytest.mark.parametrize("tag", ["latest", "-bad", ""])
def test_tag_when_unusable(build: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch, tag: str) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["p11-image-build", "--repo", str(repo), "--tag", tag, "unit-test"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        build.main()
    # Then
    assert exit_info.value.code == 2


def test_build_when_builder_missing(build: ModuleType, repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    calls: list[list[str]] = []
    bake_files: list[dict[str, Any]] = []

    def run(command: list[str], **kwargs: object) -> Mock:
        calls.append(command)
        if command[:3] == ["docker", "buildx", "bake"]:
            bake_files.append(json.loads(Path(command[command.index("--file") + 1]).read_text()))
            assert isinstance(kwargs.get("env"), dict) and kwargs["env"]["BUILDX_NO_DEFAULT_ATTESTATIONS"] == "1"
        return Mock(returncode=1 if command[:3] == ["docker", "buildx", "inspect"] else 0)

    monkeypatch.setattr(build.subprocess, "run", Mock(side_effect=run))
    monkeypatch.setattr(sys, "argv", ["p11-image-build", "--repo", str(repo), "python-tools"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        build.main()
    # Then
    assert exit_info.value.code == 0
    assert calls[0] == ["docker", "buildx", "inspect", "p11-images"]
    assert calls[1] == ["docker", "buildx", "create", "--name", "p11-images", "--driver", "docker-container", "--bootstrap"]
    context = str(repo / "firmware-developer-p11")
    assert calls[2][:9] == ["docker", "buildx", "bake", "--builder", "p11-images", "--allow", f"fs.read={context}", "--file", calls[2][8]]
    assert calls[2][9:] == ["python-tools"]
    assert sorted(bake_files[0]["target"]) == ["build-base", "python-tools"]
    assert capsys.readouterr().out == f"loaded {REGISTRY}-python-tools:local\n"


@pytest.mark.parametrize("flag, command", [("--du", ["docker", "buildx", "du", "--builder", "mine"]),
                                           ("--rm", ["docker", "buildx", "rm", "mine"])])
def test_du_and_rm_when_requested(build: ModuleType, monkeypatch: pytest.MonkeyPatch, flag: str, command: list[str]) -> None:
    # Given
    run = Mock(return_value=Mock(returncode=0))
    monkeypatch.setattr(build.subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["p11-image-build", "--builder", "mine", flag])
    # When
    with pytest.raises(SystemExit) as exit_info:
        build.main()
    # Then
    assert exit_info.value.code == 0
    assert run.call_args.args[0] == command
