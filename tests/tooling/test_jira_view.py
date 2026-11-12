import io
import json
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Final
from unittest.mock import Mock

import pytest


@pytest.fixture
def view(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("jira-view")


def test_adf_rendering_when_nested_blocks_and_inline_marks(view: ModuleType) -> None:
    # Given
    paragraph = {"type": "paragraph", "content": [{"type": "text", "text": "item"}]}
    doc = {"type": "doc", "content": [
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Title"}]},
        {"type": "bulletList", "content": [{"type": "listItem", "content": [paragraph,
            {"type": "orderedList", "content": [{"type": "listItem", "content": [paragraph]}]}]}]},
        {"type": "codeBlock", "attrs": {"language": "sh"}, "content": [{"type": "text", "text": "true"}]},
        {"type": "blockquote", "content": [paragraph]},
        {"type": "rule"},
    ]}
    # When / Then
    assert view.render_adf(doc) == "\n## Title\n- item\n  1. item\n```sh\ntrue\n```\n> item\n---\n"


@pytest.mark.parametrize("mark, expected", [("code", "`x`"), ("strong", "**x**"), ("em", "*x*"), ("link", "[x](https://example.invalid)")])
def test_inline_marks_when_rendering_text(view: ModuleType, mark: str, expected: str) -> None:
    # Given
    doc = {"type": "paragraph", "content": [{"type": "text", "text": "x", "marks": [{"type": mark, "attrs": {"href": "https://example.invalid"}}]}]}
    # When / Then
    assert view.render_adf(doc) == expected + "\n"


def test_inline_cards_mentions_breaks_when_rendering(view: ModuleType) -> None:
    # Given
    doc = {"type": "paragraph", "content": [
        {"type": "mention", "attrs": {"text": "person"}}, {"type": "hardBreak"},
        {"type": "inlineCard", "attrs": {"url": "https://example.invalid"}},
        {"type": "extension", "content": [{"type": "text", "text": "!"}]},
    ]}
    # When / Then
    assert view.render_adf(doc) == "@person\nhttps://example.invalid!\n"


@pytest.mark.parametrize("value", [None, "", []])
def test_absent_adf_when_description_is_empty(view: ModuleType, value: str | list[str] | None) -> None:
    # Given / When / Then
    assert view.render_adf(value) == ""


@pytest.mark.parametrize("flag", ["--json", "--description-raw"])
def test_raw_cli_output_when_requested(view: ModuleType, monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    # Given
    issue = {"key": "TEST-17", "fields": {"description": {"type": "doc", "version": 1, "content": []}}}
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    monkeypatch.setattr(sys, "argv", ["jira-view", "TEST-17", flag])
    curl = Mock(return_value=json.dumps(issue))
    monkeypatch.setattr(view.subprocess, "check_output", curl)
    # When
    view.main()
    # Then
    expected = {"--json": issue, "--description-raw": issue["fields"]["description"]}
    assert json.loads(output.getvalue()) == expected[flag]
    assert curl.call_count == 1


def test_non_json_response_when_api_returns_html(view: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(view.subprocess, "check_output", Mock(return_value="<html>bad gateway</html>"))
    # When / Then
    with pytest.raises(SystemExit, match="non-JSON response"):
        view.curl_json("/rest/api/3/issue/TEST-17")


def text(value: str, *marks: str, href: str = "") -> dict[str, object]:
    node: dict[str, object] = {"type": "text", "text": value}
    if marks:
        node["marks"] = [{"type": mark, "attrs": {"href": href}} if mark == "link" else {"type": mark} for mark in marks]
    return node


def para(*nodes: dict[str, object]) -> dict[str, object]:
    return {"type": "paragraph", "content": list(nodes)}


def cell(kind: str, *nodes: dict[str, object]) -> dict[str, object]:
    return {"type": kind, "attrs": {"colwidth": [120]}, "content": [para(*nodes)]}


RICH: Final = {"type": "doc", "version": 1, "content": [
    {"type": "heading", "attrs": {"level": 2}, "content": [text("Background")]},
    para(text("Run "), text("uv sync", "code"), text(" then read "), text("the guide", "link", href="https://example.invalid/a_(b)"),
         text(". Keep *stars*, _under_ scores, snake_case, [brackets], and a \\ backslash.")),
    para(text("Bold ", "strong"), text("both", "strong", "em"), text(" and "), text("italic", "em"), text(" and "),
         text("linked code", "link", "code", href="https://example.invalid")),
    para(text("# not a heading")),
    para(text("1. not a list")),
    para(text("- not a bullet")),
    para(text("---")),
    {"type": "bulletList", "content": [{"type": "listItem", "content": [
        para(text("outer")),
        {"type": "orderedList", "attrs": {"order": 3}, "content": [
            {"type": "listItem", "content": [para(text("a"))]},
            {"type": "listItem", "content": [para(text("b", "strong"))]},
        ]},
    ]}]},
    {"type": "codeBlock", "attrs": {"language": "yaml"}, "content": [text("run: |\n  ```\n  echo hi")]},
    {"type": "table", "attrs": {"layout": "default"}, "content": [
        {"type": "tableRow", "content": [cell("tableHeader", text("Where")), cell("tableHeader", text("Installs"))]},
        {"type": "tableRow", "content": [cell("tableCell", text(".github/a.yml", "code"), text(" job")),
                                         cell("tableCell", text("pip | uv"))]},
    ]},
    {"type": "blockquote", "content": [para(text("quoted"))]},
    {"type": "panel", "attrs": {"panelType": "note"}, "content": [para(text("Headline.", "strong"), text(" Rest"))]},
    {"type": "rule"},
]}


def test_markdown_round_trips_through_md2adf(view: ModuleType, tool: Callable[[str], ModuleType]) -> None:
    # Given
    writer = view.MarkdownWriter()
    # When
    markdown = writer.document(RICH)
    # Then
    assert writer.lost == []
    assert view.normalize(tool("md2adf").convert(markdown)) == view.normalize(RICH)
    lines = markdown.splitlines()
    assert "| `.github/a.yml` job | pip \\| uv |" in lines
    assert "````yaml" in lines
    assert "> [!IMPORTANT]" in lines and "> **Headline.** Rest" in lines
    assert "- outer" in lines and "  3. a" in lines and "  4. **b**" in lines
    assert ["\\# not a heading", "1\\. not a list", "\\- not a bullet", "\\---"] == [line for line in lines if "not a" in line or line == "\\---"]


@pytest.mark.parametrize(("node", "lost"), [
    (para(text("hi "), {"type": "mention", "attrs": {"text": "@Mason"}}), "mentions"),
    (para(text("a"), {"type": "hardBreak"}, text("b")), "line breaks inside a paragraph"),
    (para({"type": "inlineCard", "attrs": {"url": "https://example.invalid"}}), "smart links"),
    ({"type": "panel", "attrs": {"panelType": "custom"}, "content": [para(text("note"))]}, "panel blocks"),
    (para(text("under", "underline")), "underline formatting"),
    ({"type": "bulletList", "content": [{"type": "listItem", "content": [para(text("a")), para(text("b"))]}]},
     "list items with more than one paragraph or block"),
    ({"type": "table", "content": [{"type": "tableRow", "content": [cell("tableCell", text("x"))]}]},
     "tables whose first row isn't a header row"),
    (para(), "empty paragraphs"),
])
def test_markdown_names_what_it_cannot_keep(view: ModuleType, node: dict[str, object], lost: str) -> None:
    # Given
    writer = view.MarkdownWriter()
    # When
    writer.document({"type": "doc", "version": 1, "content": [node]})
    # Then
    assert lost in writer.lost


def serve_issue(view: ModuleType, monkeypatch: pytest.MonkeyPatch, description: object) -> Mock:
    issue = {"key": "TEST-17", "fields": {"summary": "Title", "description": description}}
    curl = Mock(return_value=json.dumps(issue))
    monkeypatch.setattr(view.subprocess, "check_output", curl)
    return curl


def test_markdown_cli_prints_only_the_description(view: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                  capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    curl = serve_issue(view, monkeypatch, {"type": "doc", "version": 1, "content": [para(text("Body"))]})
    monkeypatch.setattr(sys, "argv", ["jira-view", "TEST-17", "--markdown"])
    # When
    view.main()
    # Then
    captured = capsys.readouterr()
    assert captured.out == "Body\n"
    assert captured.err == ""
    assert curl.call_count == 1


def test_markdown_cli_warns_about_what_it_cannot_keep(view: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                      capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_issue(view, monkeypatch, {"type": "doc", "version": 1, "content": [
        para(text("hi "), {"type": "mention", "attrs": {"text": "@Mason"}})]})
    monkeypatch.setattr(sys, "argv", ["jira-view", "TEST-17", "--markdown"])
    # When
    view.main()
    # Then
    captured = capsys.readouterr()
    assert captured.out == "hi @Mason\n"
    assert "can't keep mentions" in captured.err and "--description-raw" in captured.err


def test_markdown_cli_when_there_is_no_description(view: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                   capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve_issue(view, monkeypatch, None)
    monkeypatch.setattr(sys, "argv", ["jira-view", "TEST-17", "--markdown"])
    # When
    view.main()
    # Then
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "has no description" in captured.err


def test_markdown_conflicts_with_raw_output(view: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["jira-view", "TEST-17", "--markdown", "--json"])
    # When / Then
    with pytest.raises(SystemExit) as error:
        view.main()
    assert error.value.code == 2


def test_markdown_keeps_a_space_between_marked_nodes(view: ModuleType, tool: Callable[[str], ModuleType]) -> None:
    # Given
    doc = {"type": "doc", "version": 1, "content": [
        para(text("unit-test.yml", "link", href="https://example.invalid"), text(" "), text("linting-lamatest", "code"))]}
    writer = view.MarkdownWriter()
    # When
    markdown = writer.document(doc)
    # Then
    assert markdown == "[unit-test.yml](https://example.invalid) `linting-lamatest`\n"
    assert view.normalize(tool("md2adf").convert(markdown)) == view.normalize(doc)
