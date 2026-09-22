import io
import json
import sys
from collections.abc import Callable
from types import ModuleType
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
