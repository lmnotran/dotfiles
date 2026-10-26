import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest


@pytest.fixture
def lint(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("prose-lint")


def rules(findings: list) -> list[str]:
    return [finding.rule for finding in findings]


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("This cuts the build — a lot.", ["em-dash"]),
        ("It builds; then it tests.", ["semicolon"]),
        ("Wall-clock dropped ~−44%.", ["tilde-minus"]),
        ("Wall-clock dropped ~-3s.", ["tilde-minus"]),
        ("Fixed in `66ecc807bb`.", ["backticked-sha"]),
        ("See [P11F-1](https://x.atlassian.net/browse/P11F-1?atlOrigin=abc).", ["atl-origin"]),
    ],
)
def test_rule_when_line_breaks_it(lint: ModuleType, line: str, expected: list[str]) -> None:
    assert rules(lint.lint_markdown(line)) == expected


@pytest.mark.parametrize(
    "line",
    [
        "Plain sentence with a comma, and a period.",
        "**TL;DR:** build good → can't merge → now it can.",
        "Tom &amp; Jerry, and the range is min–max.",
        "The code `a; b — c` stays code.",
        "Fixed in 66ecc807bb, bare so GitHub links it.",
        "See [`66ecc807bb`](https://github.com/o/r/commit/66ecc807bb) for the change.",
        "The hash `3d9ff2ef1ed2006fd99d05fd6d042d51` is a schema baseline, not a commit.",
        "Version `v2.119.0-21-g595f1896e` and value `0xDEADBEEF` and count `1352`.",
        "It dropped −44%, about a third.",
        "A link [docs](https://example.com/a;b) keeps its URL.",
        "[P11F-8063]: https://cpl-legogroup.atlassian.net/browse/P11F-8063?atlOrigin=eyJp",
    ],
)
def test_no_finding_when_line_is_fine(lint: ModuleType, line: str) -> None:
    assert lint.lint_markdown(line) == []


def test_fenced_code_skipped_until_matching_fence(lint: ModuleType) -> None:
    text = "Intro.\n````mermaid\nA --> B; C\n```\nstill code — here\n````\nAfter — this.\n"
    findings = lint.lint_markdown(text)
    assert [(finding.where, finding.rule) for finding in findings] == [("7", "em-dash")]


def test_baseline_skips_lines_it_already_has(lint: ModuleType) -> None:
    old = "Kept line — from someone else.\n"
    new = "Kept line — from someone else.\nMy new line; with a problem.\n"
    findings = lint.lint_markdown(new, baseline=old)
    assert [(finding.where, finding.rule) for finding in findings] == [("2", "semicolon")]


def paragraph(*inlines: dict) -> dict:
    return {"type": "paragraph", "content": list(inlines)}


def text(value: str, *marks: dict) -> dict:
    node: dict = {"type": "text", "text": value}
    if marks:
        node["marks"] = list(marks)
    return node


def doc(*blocks: dict) -> dict:
    return {"type": "doc", "version": 1, "content": list(blocks)}


CODE = {"type": "code"}


def test_adf_checks_prose_and_skips_code(lint: ModuleType) -> None:
    document = doc(
        {"type": "heading", "attrs": {"level": 2}, "content": [text("Goal — now")]},
        paragraph(text("Uses "), text("a;b", CODE), text(" and "), text("66ecc807bb", CODE), text(".")),
        {"type": "codeBlock", "content": [text("x = 1; y — 2")]},
        {"type": "bulletList", "content": [{"type": "listItem", "content": [paragraph(text("It builds; it tests."))]}]},
        paragraph(text("ticket", {"type": "link", "attrs": {"href": "https://x/browse/P11F-1?atlOrigin=abc"}})),
    )
    findings = lint.lint_adf(document)
    assert [(finding.where, finding.rule) for finding in findings] == [
        ("block 1 (heading)", "em-dash"),
        ("block 3 (paragraph)", "semicolon"),
        ("block 4 (paragraph)", "atl-origin"),
    ]


def test_adf_baseline_skips_unchanged_blocks(lint: ModuleType) -> None:
    old = doc(paragraph(text("Old — kept.")))
    new = doc(paragraph(text("Old — kept.")), paragraph(text("New — flagged.")))
    findings = lint.lint_adf(new, baseline=old)
    assert [(finding.where, finding.rule) for finding in findings] == [("block 2 (paragraph)", "em-dash")]


@pytest.mark.parametrize("wrap", [lambda d: d, lambda d: {"body": d}, lambda d: {"fields": {"description": d}}])
def test_adf_doc_unwraps_payloads(lint: ModuleType, wrap: Callable[[dict], dict]) -> None:
    document = doc(paragraph(text("x")))
    assert lint.adf_doc(wrap(document)) == document


def test_cli_exit_codes_and_output(lint: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("All good.\n")
    bad = tmp_path / "bad.md"
    bad.write_text("Line one.\nLine two — oops.\n")
    assert lint.main([str(clean)]) == 0
    assert lint.main([str(bad)]) == 1
    assert capsys.readouterr().out.strip() == f"{bad}:2: em-dash: Line two — oops."
    adf = tmp_path / "d.json"
    adf.write_text(json.dumps(doc(paragraph(text("A; B")))))
    assert lint.main(["--adf", str(adf)]) == 1
    adf.write_text("{not json")
    assert lint.main(["--adf", str(adf)]) == 2


def test_cli_baseline_needs_one_file(lint: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        lint.main(["--baseline", "old.md", "a.md", "b.md"])
    assert raised.value.code == 2


def test_word_budget_flags_a_long_summary_when_the_diff_is_large(lint: ModuleType) -> None:
    # Given
    body = "## Summary\n\n" + "word " * 61 + "\n\n## Changes\n\n" + "more " * 300
    # When
    findings = lint.lint_length(body, 400)
    # Then
    assert [(finding.where, finding.rule) for finding in findings] == [("Summary", "summary-length")]


@pytest.mark.parametrize(("diff_lines", "expected"), [(49, ["body-length"]), (50, [])])
def test_word_budget_for_the_whole_body_applies_under_fifty_changed_lines(
        lint: ModuleType, diff_lines: int, expected: list[str]) -> None:
    # Given
    body = "Fixes the cache key.\n\n" + "word " * 147
    # When / Then
    assert rules(lint.lint_length(body, diff_lines)) == expected


def test_word_count_skips_what_reviewers_do_not_read(lint: ModuleType) -> None:
    # Given
    body = (
        "## Summary\n\nOne two three.\n<!-- template\nnote -->\n```mermaid\nflowchart LR\n  A --> B\n```\n"
        "## Test plan\n\n- [x] Checked the [step](https://github.com/o/r/actions/runs/1) at https://x.invalid/a "
        "<img alt=\"x\" src=\"y\">\n\n[P11F-1]: https://jira.invalid/browse/P11F-1?atlOrigin=x\n"
    )
    # When / Then
    assert lint.word_counts(body) == (7, 3)


def test_cli_diff_lines_adds_the_word_budget(lint: ModuleType, tmp_path: Path,
                                            capsys: pytest.CaptureFixture[str]) -> None:
    body = tmp_path / "body.md"
    body.write_text("## Summary\n\n" + "word " * 61 + "\n")
    assert lint.main([str(body)]) == 0
    assert lint.main(["--diff-lines", "400", str(body)]) == 1
    assert f"{body}:Summary: summary-length:" in capsys.readouterr().out
    with pytest.raises(SystemExit) as raised:
        lint.main(["--adf", "--diff-lines", "4", str(body)])
    assert raised.value.code == 2
