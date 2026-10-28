import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest

REGISTRY = "ghcr.io/lego-cpl/firmware-developer-p11"
WORKSPACE = "/__w/p11-firmware/p11-firmware"


@pytest.fixture
def ci(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("p11-ci-local")


@pytest.mark.parametrize("image, tag, expected", [
    ("bnsim-test", "local", f"{REGISTRY}-bnsim-test:local"),
    ("firmware-build", "abc123", f"{REGISTRY}-firmware-build:abc123"),
    ("monolith", "local", f"{REGISTRY}:local"),
    ("ubuntu:26.04", "local", "ubuntu:26.04"),
    (f"{REGISTRY}-unit-test@sha256:00", "local", f"{REGISTRY}-unit-test@sha256:00"),
])
def test_resolve_image_when_name_or_reference(ci: ModuleType, image: str, tag: str, expected: str) -> None:
    # Given / When / Then
    assert ci.resolve_image(image, tag) == expected


@pytest.mark.parametrize("servers, expected", [
    ([{"serverId": "first"}, {"serverId": "artifactory", "isDefault": True}], "artifactory"),
    ([{"serverId": "only"}], "only"),
    ([], None),
])
def test_default_jf_server_when_config_lists_servers(ci: ModuleType, tmp_path: Path, servers: list[dict[str, object]], expected: str | None) -> None:
    # Given
    (tmp_path / "jfrog-cli.conf.v6").write_text(json.dumps({"version": "6", "servers": servers}))
    # When / Then
    assert ci.default_jf_server(tmp_path) == expected


def test_docker_command_when_worktree_with_linuxbrew_jf(ci: ModuleType, tmp_path: Path) -> None:
    # Given
    checkout, common, home = tmp_path / "wt", tmp_path / "main/.git", tmp_path / "home"
    jf = Path("/home/linuxbrew/.linuxbrew/Cellar/jfrog-cli/2.112.0/bin/jf")
    # When
    argv = ci.docker_command(f"{REGISTRY}-bnsim-test:local", checkout, common, home, {"GIT_BRANCH": "feature/x"},
                             jf, "artifactory", tmp_path / ".jfrog", Path("/opt/uv"), "cmake --preset pcab", tty=False)
    # Then
    assert argv[:4] == ["docker", "run", "--rm", "-i"]
    assert "-t" not in argv
    pairs = list(zip(argv, argv[1:]))
    assert ("-w", WORKSPACE) in pairs
    for value in ("CI=true", f"GITHUB_WORKSPACE={WORKSPACE}", "P11_DISABLE_GIT_SUBMODULE_UPDATE=1", "GIT_BRANCH=feature/x", "HOME=/tmp/p11-ci-home"):
        assert ("-e", value) in pairs
    for mount in (f"{checkout}:{WORKSPACE}", f"{common}:{common}", "/home/linuxbrew/.linuxbrew:/home/linuxbrew/.linuxbrew:ro",
                  f"{tmp_path / '.jfrog'}:/tmp/p11-ci-home/.jfrog", "/opt/uv:/usr/local/bin/uv:ro", f"{home}:/tmp/p11-ci-home"):
        assert ("-v", mount) in pairs
    assert argv[-5:-1] == ["--entrypoint", "bash", f"{REGISTRY}-bnsim-test:local", "-c"]
    assert argv[-1] == ("set -e\nexport PATH=\"$PATH:/home/linuxbrew/.linuxbrew/Cellar/jfrog-cli/2.112.0/bin\"\n"
                        "jf pip-config --repo-resolve=cpl-pypi-virtual --server-id-resolve=artifactory >/dev/null\n"
                        "set +e\ncmake --preset pcab")


def test_docker_command_when_main_checkout_and_shell(ci: ModuleType, tmp_path: Path) -> None:
    # Given
    checkout = tmp_path / "repo"
    # When
    argv = ci.docker_command("img", checkout, checkout / ".git", tmp_path / "home", {}, Path("/usr/bin/jf"), None, None, None, None, tty=True)
    # Then
    assert "-t" in argv
    assert f"{checkout / '.git'}:{checkout / '.git'}" not in argv
    assert "/usr/bin/jf:/usr/local/bin/jf:ro" in argv
    assert argv[-1] == "set -e\nset +e\nexec bash -i"


def git_responses(checkout: Path, common: Path, describe: str | None) -> Callable[..., Mock]:
    def run(command: list[str], **kwargs: object) -> Mock:
        if command[0] == "docker" and command[1] == "image":
            return Mock(returncode=0)
        if command[0] == "docker":
            (checkout / ".jfrog" / "projects").mkdir(parents=True)  # what jf pip-config leaves behind
            return Mock(returncode=7)
        args = command[3:]
        outputs = {
            ("rev-parse", "--show-toplevel"): str(checkout),
            ("rev-parse", "--path-format=absolute", "--git-common-dir"): str(common),
            ("rev-parse", "--short", "HEAD"): "abc1234",
            ("rev-parse", "--abbrev-ref", "HEAD"): "feature/x",
        }
        if args[0] == "describe":
            return Mock(returncode=0 if describe else 128, stdout=describe or "", stderr="fatal: no names found")
        return Mock(returncode=0, stdout=outputs[tuple(args)], stderr="")
    return run


@pytest.mark.parametrize("describe, version", [("v2.120.0-28-gabc1234", "v2.120.0-28-gabc1234"), (None, "v0.0.0-0-gabc1234")])
def test_cli_when_command_runs_in_a_worktree(ci: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, describe: str | None, version: str) -> None:
    # Given
    checkout, common = tmp_path / "wt", tmp_path / "main/.git"
    checkout.mkdir()
    (checkout / "CMakePresets.json").write_text("{}")
    run = Mock(side_effect=git_responses(checkout, common, describe))
    monkeypatch.setattr(ci.subprocess, "run", run)
    monkeypatch.setattr(ci, "which", Mock(return_value=None))
    monkeypatch.chdir(checkout)
    monkeypatch.setattr(sys, "argv", ["p11-ci-local", "bnsim-test", "--", "echo", "two words"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        ci.main()
    # Then
    assert exit_info.value.code == 7
    docker = next(call.args[0] for call in run.call_args_list if call.args[0][:2] == ["docker", "run"])
    assert f"GIT_BUILD_VERSION={version}" in docker
    assert docker[-1].endswith("\necho 'two words'")
    assert not (checkout / ".jfrog").exists()


def test_cli_keeps_jfrog_dir_that_was_already_there(ci: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    checkout = tmp_path / "repo"
    (checkout / ".jfrog").mkdir(parents=True)
    (checkout / "CMakePresets.json").write_text("{}")
    def run(command: list[str], **kwargs: object) -> Mock:
        if command[0] == "docker":
            return Mock(returncode=0)
        return git_responses(checkout, checkout / ".git", "v1.0.0")(command)
    monkeypatch.setattr(ci.subprocess, "run", Mock(side_effect=run))
    monkeypatch.setattr(ci, "which", Mock(return_value=None))
    monkeypatch.setattr(sys, "argv", ["p11-ci-local", "--checkout", str(checkout), "unit-test", "--", "true"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        ci.main()
    # Then
    assert exit_info.value.code == 0
    assert (checkout / ".jfrog").is_dir()


def test_cli_when_local_image_missing(ci: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    (tmp_path / "CMakePresets.json").write_text("{}")
    monkeypatch.setattr(ci.subprocess, "run", Mock(return_value=Mock(returncode=1)))
    monkeypatch.setattr(sys, "argv", ["p11-ci-local", "--checkout", str(tmp_path), "bnsim-test"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        ci.main()
    # Then
    assert exit_info.value.code == 2
    assert "build it with `p11-image-build bnsim-test`" in capsys.readouterr().err


def test_cli_when_not_a_p11_firmware_checkout(ci: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["p11-ci-local", "--checkout", str(tmp_path), "bnsim-test"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        ci.main()
    # Then
    assert exit_info.value.code == 2
    assert "doesn't look like a p11-firmware checkout" in capsys.readouterr().err


def test_cli_creates_the_jfrog_mount_point_as_the_user(ci: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    checkout = tmp_path / "repo"
    checkout.mkdir()
    (checkout / "CMakePresets.json").write_text("{}")
    jfrog = Path.home() / ".jfrog"
    jfrog.mkdir()
    (jfrog / "jfrog-cli.conf.v6").write_text(json.dumps({"servers": [{"serverId": "artifactory", "isDefault": True}]}))
    def run(command: list[str], **kwargs: object) -> Mock:
        if command[0] == "docker":
            return Mock(returncode=0)
        return git_responses(checkout, checkout / ".git", "v1.0.0")(command)
    monkeypatch.setattr(ci.subprocess, "run", Mock(side_effect=run))
    monkeypatch.setattr(ci, "which", Mock(return_value=Path("/usr/bin/tool")))
    monkeypatch.setattr(sys, "argv", ["p11-ci-local", "--checkout", str(checkout), "unit-test", "--", "true"])
    # When
    with pytest.raises(SystemExit) as exit_info:
        ci.main()
    # Then
    assert exit_info.value.code == 0
    assert (tmp_path / "xdg_cache_home" / "p11-ci-local" / "home" / ".jfrog").is_dir()
