"""Markdown conversion contracts without Jira or external commands."""
import io
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def md(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("md2adf")


@pytest.mark.parametrize("level", range(1, 7))
def test_heading_when_atx(md: ModuleType, level: int) -> None:
    # Given / When
    node = md.convert("#" * level + " Title")["content"][0]
    # Then
    assert node == {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": "Title"}]}


def test_paragraph_when_soft_wrapped_or_unknown_syntax(md: ModuleType) -> None:
    # Given / When
    doc = md.convert("hello\nworld\n\n~~unsupported~~\n=======")
    # Then
    assert doc["content"] == [md.paragraph("hello world"), md.paragraph("~~unsupported~~ =======")]


def test_lists_when_nested_and_mixed(md: ModuleType) -> None:
    # Given / When
    doc = md.convert("- outer\n  continuation\n  1. child\n     * leaf\n  2. next\n- sibling\n\n3. ordered\n4. final")
    # Then
    bullet, ordered = doc["content"]
    assert bullet["type"] == "bulletList"
    outer, sibling = bullet["content"]
    assert outer["content"][0] == md.paragraph("outer continuation")
    nested = outer["content"][1]
    assert nested["type"] == "orderedList"
    assert nested["content"][0]["content"] == [md.paragraph("child"), {
        "type": "bulletList", "content": [{"type": "listItem", "content": [md.paragraph("leaf")]}],
    }]
    assert nested["content"][1]["content"] == [md.paragraph("next")]
    assert sibling["content"] == [md.paragraph("sibling")]
    assert ordered["attrs"] == {"order": 3}
    assert [item["content"] for item in ordered["content"]] == [[md.paragraph("ordered")], [md.paragraph("final")]]


@pytest.mark.parametrize("fence", ["```", "~~~~"])
def test_code_block_when_fenced(md: ModuleType, fence: str) -> None:
    # Given / When
    doc = md.convert(f"{fence}python\nprint('**literal**')\n\npass\n{fence}")
    # Then
    assert doc["content"] == [{"type": "codeBlock", "attrs": {"language": "python"},
                               "content": [{"type": "text", "text": "print('**literal**')\n\npass"}]}]


def test_table_when_header_separator_and_empty_cells(md: ModuleType) -> None:
    # Given / When
    node = md.convert("| Name | Value |\n| :--- | ---: |\n| **A** | `x` |\n| B | |\n\nafter")["content"][0]
    # Then
    assert node["type"] == "table"
    header, first, second = node["content"]
    assert [cell["type"] for cell in header["content"]] == ["tableHeader", "tableHeader"]
    assert header["content"][0]["content"] == [md.paragraph("Name")]
    assert first["content"] == [{"type": "tableCell", "content": [md.paragraph("**A**")]},
                                {"type": "tableCell", "content": [md.paragraph("`x`")]}]
    assert second["content"][1]["content"] == [{"type": "paragraph", "content": []}]


def test_rule_and_quote_when_blocks(md: ModuleType) -> None:
    # Given / When
    doc = md.convert("---\n> # Quoted\n> soft\n> wrapped\n>\n> - item")
    # Then
    assert doc["content"][0] == {"type": "rule"}
    quote = doc["content"][1]
    assert quote["type"] == "blockquote"
    assert [node["type"] for node in quote["content"]] == ["heading", "paragraph", "bulletList"]
    assert quote["content"][1] == md.paragraph("soft wrapped")


@pytest.mark.parametrize("source,mark", [("**bold**", "strong"), ("_italic_", "em"), ("*italic*", "em"), ("`code`", "code")])
def test_inline_when_marked(md: ModuleType, source: str, mark: str) -> None:
    # Given / When
    nodes = md.inline(source)
    # Then
    assert nodes == [{"type": "text", "text": source.strip("*_`"), "marks": [{"type": mark}]}]


def test_code_when_inside_bold_link(md: ModuleType) -> None:
    # Given / When
    nodes = md.inline("**[before `code` after](https://example.invalid/a_(b))**")
    # Then
    link = {"type": "link", "attrs": {"href": "https://example.invalid/a_(b)"}}
    assert nodes == [
        {"type": "text", "text": "before ", "marks": [{"type": "strong"}, link]},
        {"type": "text", "text": "code", "marks": [link, {"type": "code"}]},
        {"type": "text", "text": " after", "marks": [{"type": "strong"}, link]},
    ]


def test_empty_text_when_empty_constructs(md: ModuleType) -> None:
    # Given
    doc = md.convert("#\n\n```sh\n```\n\n| H |\n| --- |\n| |\n\n[](url)")
    pending = [doc]
    # When / Then
    while pending:
        node = pending.pop()
        if node["type"] == "text":
            assert node["text"]
        pending.extend(node.get("content", []))


@pytest.mark.parametrize("from_stdin", [True, False])
def test_cli_when_file_or_stdin(md: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
                                capsys: pytest.CaptureFixture[str], from_stdin: bool) -> None:
    # Given
    path = tmp_path / "sample.md"
    path.write_text("# Café", encoding="utf-8")
    monkeypatch.setattr(sys, "stdin", io.StringIO("# Café"))
    monkeypatch.setattr(sys, "argv", ["md2adf", "-" if from_stdin else str(path)])
    # When
    md.main()
    # Then
    assert json.loads(capsys.readouterr().out)["content"][0]["content"][0]["text"] == "Café"
