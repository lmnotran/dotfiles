import io
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

# The house style: jobs with no fill, one light tint per action, steps that name their tool on its own line.
CLEAN = """flowchart TB
  %% JOB --> ACT stays a comment
  subgraph JOB["job<br/>(workflow.yml)"]
    direction TB
    subgraph ACT["prepare-play-assets-rofs"]
      direction TB
      A1["pick the ROFS"] --> A2["batjam-rofs<br/>checks the ROFS"]
    end
    A2 --> A3["run ppp_test.sh"]
  end
  classDef added fill:#dff5e1,stroke:#1e8449,color:#000
  class A2 added
  style JOB fill:none,stroke:#666,stroke-width:3px
  style ACT fill:#e3f2fd,stroke:#1e88e5,color:#000
  linkStyle default stroke:#777
"""


@pytest.fixture
def render(tool: Callable[[str], ModuleType], monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    monkeypatch.delenv("MERMAID_RENDER_CHROME", raising=False)
    return tool("mermaid-render")


def rules(render: ModuleType, source: str) -> list[str]:
    return [finding.rule for finding in render.lint(render.Diagram(source, 1))]


def test_no_finding_when_diagram_follows_the_house_style(render: ModuleType) -> None:
    assert rules(render, CLEAN) == []


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ('flowchart TB\n  subgraph JOB["job"]\n    A["step"]\n  end\n', ["no-direction"]),
        ('flowchart TB\n  subgraph JOB["job"]\n    direction TB\n    subgraph "quoted title"\n      A["a"]\n    end\n  end\n',
         ["no-direction"]),
        ('flowchart TB\n  subgraph B["Before"]\n    direction LR\n    A["a"]\n  end\n'
         '  subgraph C["After"]\n    direction LR\n    D["d"]\n  end\n  B ~~~ C\n', ["subgraph-link", "subgraph-link"]),
        ('flowchart TB\n  A["check the ROFS<br/>with batjam-rofs"]\n', ["hyphen-wrap"]),
        ('flowchart TB\n  A["prepare-play-assets-rofs"]\n', ["hyphen-wrap"]),
        ('flowchart TB\n  A["step"]\n  style A fill:#fde2e2,stroke:#c0392b\n', ["light-fill-text"]),
        ('flowchart TB\n  A["step"]\n  classDef moved fill:#fde2e2,stroke:#c0392b\n  class A moved\n', ["light-fill-text"]),
        ('flowchart TB\n  subgraph S["action"]\n    direction TB\n    A["a"] --> B["b"]\n  end\n'
         '  style S fill:#e3f2fd,color:#000\n', ["faint-arrows"]),
    ],
    ids=["no-direction", "quoted-title", "subgraph-link", "hyphen-after-a-word", "long-hyphenated-word", "light-style",
         "light-classDef", "faint-arrows"],
)
def test_rule_when_diagram_breaks_it(render: ModuleType, source: str, expected: list[str]) -> None:
    assert rules(render, source) == expected


@pytest.mark.parametrize(
    "source",
    [
        'flowchart TB\n  A["step"]\n  style A fill:#333,color:#fff\n',
        'flowchart TB\n  A["step"]\n  style A fill:none,stroke:#666\n',
        'flowchart TB\n  A["wall-clock"] -->|"made-up-very-long-edge-text"| B\n',
    ],
    ids=["dark-fill", "no-fill", "edge-text"],
)
def test_no_finding_when_fill_is_dark_or_text_is_outside_a_node(render: ModuleType, source: str) -> None:
    assert rules(render, source) == []


def test_diagrams_found_with_file_line_numbers_when_text_is_markdown(render: ModuleType) -> None:
    text = "Intro.\n\n```mermaid\nflowchart TB\n  A --> B\n```\n\nMiddle.\n\n````mermaid\nflowchart LR\n  C --> D\n````\n"
    found = render.diagrams(text)
    assert [(diagram.first_line, diagram.source) for diagram in found] == [
        (4, "flowchart TB\n  A --> B\n"),
        (11, "flowchart LR\n  C --> D\n"),
    ]


def test_finding_line_is_the_file_line_when_diagram_is_in_markdown(render: ModuleType) -> None:
    (diagram,) = render.diagrams("Intro.\n\n```mermaid\nflowchart TB\n  subgraph S\n    A\n  end\n```\n")
    assert [(finding.line, finding.rule) for finding in render.lint(diagram)] == [(5, "no-direction")]


def test_newest_cached_chrome_picked_when_several_are_installed(render: ModuleType) -> None:
    for version in ("linux-151.0.7922.47", "linux-153.0.8010.36", "linux-99.0.1.1"):
        binary = Path.home() / ".cache/puppeteer/chrome-headless-shell" / version / "chrome-headless-shell-linux64/chrome-headless-shell"
        binary.parent.mkdir(parents=True)
        binary.touch()
    chrome = render.find_chrome()
    assert chrome is not None and chrome.parents[1].name == "linux-153.0.8010.36"


def test_configured_chrome_used_when_env_names_one(render: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERMAID_RENDER_CHROME", "/opt/chrome")
    assert render.find_chrome() == Path("/opt/chrome")


def test_render_exits_2_when_no_chrome_is_installed(render: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                    tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(render.shutil, "which", lambda command: None)
    monkeypatch.setattr(render, "MAC_CHROME", tmp_path / "missing-chrome")
    source = tmp_path / "clean.mmd"
    source.write_text(CLEAN)
    assert render.main([str(source)]) == 2
    assert "no Chrome found" in capsys.readouterr().err


def test_lint_only_exits_1_with_findings(render: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "bad.mmd"
    source.write_text("flowchart TB\n  subgraph S\n    A\n  end\n")
    assert render.main(["--lint-only", str(source)]) == 1
    assert capsys.readouterr().out.startswith(f"{source}:2: no-direction: ")


def test_lint_only_reads_markdown_from_stdin(render: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                             capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"**After**\n\n```mermaid\n{CLEAN}```\n"))
    assert render.main(["--lint-only", "-"]) == 0
    assert capsys.readouterr().out == ""


def test_exits_2_when_markdown_has_no_mermaid_block(render: ModuleType, tmp_path: Path,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    body = tmp_path / "body.md"
    body.write_text("Just prose.\n\n```bash\necho hi\n```\n")
    assert render.main(["--lint-only", str(body)]) == 2
    assert "no mermaid diagram found" in capsys.readouterr().err


def test_light_and_dark_rendered_with_the_installed_chrome(render: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                           tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("MERMAID_RENDER_CHROME", "/opt/chrome")
    commands: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(render.subprocess, "run", run)
    source = tmp_path / "clean.mmd"
    source.write_text(CLEAN)
    out = tmp_path / "out"
    assert render.main(["--out", str(out), str(source)]) == 0
    light, dark = out / "clean-1-light.png", out / "clean-1-dark.png"
    assert [command[command.index("-o") + 1] for command in commands] == [str(light), str(dark)]
    assert "-t" not in commands[0] and commands[1][commands[1].index("-t") + 1] == "dark"
    assert json.loads((out / "puppeteer.json").read_text())["executablePath"] == "/opt/chrome"
    assert (out / "clean-1.mmd").read_text() == CLEAN
    assert capsys.readouterr().out.splitlines() == [f"{source}:1: {light}", f"{source}:1: {dark}"]


def test_exits_2_with_mmdc_error_when_render_fails(render: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                  tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("MERMAID_RENDER_CHROME", "/opt/chrome")
    stderr = ("Generating single mermaid chart\nError: Parse error on line 2:\n...  A -->\n"
              "Expecting 'SEMI', got 'EOF'\n    at async cli (index.js:1:1)\n")
    monkeypatch.setattr(render.subprocess, "run",
                        lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", stderr))
    source = tmp_path / "broken.mmd"
    source.write_text("flowchart TB\n  A -->\n")
    assert render.main(["--out", str(tmp_path / "out"), str(source)]) == 2
    err = capsys.readouterr().err
    assert "broken-1.mmd (light) failed:\nError: Parse error on line 2:" in err
    assert "at async cli" not in err
