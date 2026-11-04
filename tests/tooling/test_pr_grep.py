import json
import re
import sys
from collections.abc import Callable
from types import ModuleType
from typing import Any, Final

import pytest

WORKFLOW_DIFF: Final = """diff --git a/.github/workflows/ci.yml b/.github/workflows/ci.yml
index 1111111..2222222 100644
--- a/.github/workflows/ci.yml
+++ b/.github/workflows/ci.yml
@@ -10,4 +10,5 @@ jobs:
       - name: Install
-        run: pip install flake8
+        run: uv pip install --system flake8
+        # pip install stays in this comment
       - name: Lint
@@ -40,2 +41,2 @@ jobs:
--- removed line that starts with two dashes, pip install
+++ added line that starts with two pluses
diff --git a/docs/setup.md b/docs/setup.md
index 3333333..4444444 100644
--- a/docs/setup.md
+++ b/docs/setup.md
@@ -1,1 +1,1 @@
-pip install -r requirements.txt
+uv sync
"""
NEW_AND_DELETED_DIFF: Final = """diff --git a/scripts/new.sh b/scripts/new.sh
new file mode 100755
--- /dev/null
+++ b/scripts/new.sh
@@ -0,0 +1,2 @@
+#!/bin/sh
+pip3 install rich
diff --git a/scripts/old.sh b/scripts/old.sh
deleted file mode 100755
--- a/scripts/old.sh
+++ /dev/null
@@ -1,2 +0,0 @@
-#!/bin/sh
-python -m pip install yq
diff --git a/image.png b/image.png
Binary files a/image.png and b/image.png differ
"""
BUNDLE_DIFF: Final = """diff --git a/.github/actions/telemetry/dist/index.js b/.github/actions/telemetry/dist/index.js
--- /dev/null
+++ b/.github/actions/telemetry/dist/index.js
@@ -0,0 +1,1 @@
+const pip = "pip install"; // bundled
diff --git a/.github/actions/telemetry/main.js b/.github/actions/telemetry/main.js
--- /dev/null
+++ b/.github/actions/telemetry/main.js
@@ -0,0 +1,2 @@
+const short = "pip install";
+const long = "pip install""" + "x" * 500 + "\"\n"


@pytest.fixture
def grep(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-pr-grep")


def pr(number: int, paths: list[str], draft: bool = False) -> dict[str, Any]:
    return {"number": number, "title": f"Title {number}", "author": {"login": "mason"}, "isDraft": draft,
            "url": f"https://github.com/owner/repo/pull/{number}", "files": [{"path": path} for path in paths]}


def serve(grep: ModuleType, monkeypatch: pytest.MonkeyPatch, prs: list[dict[str, Any]],
          diffs: dict[int, str | Exception]) -> list[tuple[str, ...]]:
    calls: list[tuple[str, ...]] = []

    def gh(*args: str) -> str:
        calls.append(args)
        if args[:2] == ("pr", "list"):
            return json.dumps(prs)
        diff = diffs[int(args[2])]
        if isinstance(diff, Exception):
            raise diff
        return diff

    monkeypatch.setattr(grep, "gh", gh)
    return calls


def run(grep: ModuleType, monkeypatch: pytest.MonkeyPatch, *argv: str) -> int:
    monkeypatch.setattr(sys, "argv", ["gh-pr-grep", *argv])
    with pytest.raises(SystemExit) as exit_info:
        grep.main()
    return int(exit_info.value.code or 0)


def test_changed_lines_numbers_each_side_and_reads_headers_only_before_hunks(grep: ModuleType) -> None:
    # When
    lines = list(grep.changed_lines(WORKFLOW_DIFF))
    # Then
    assert lines == [
        (".github/workflows/ci.yml", 11, "-", "        run: pip install flake8"),
        (".github/workflows/ci.yml", 11, "+", "        run: uv pip install --system flake8"),
        (".github/workflows/ci.yml", 12, "+", "        # pip install stays in this comment"),
        (".github/workflows/ci.yml", 40, "-", "-- removed line that starts with two dashes, pip install"),
        (".github/workflows/ci.yml", 41, "+", "++ added line that starts with two pluses"),
        ("docs/setup.md", 1, "-", "pip install -r requirements.txt"),
        ("docs/setup.md", 1, "+", "uv sync"),
    ]


def test_changed_lines_when_files_are_new_deleted_or_binary(grep: ModuleType) -> None:
    # When
    lines = list(grep.changed_lines(NEW_AND_DELETED_DIFF))
    # Then
    assert lines == [
        ("scripts/new.sh", 1, "+", "#!/bin/sh"),
        ("scripts/new.sh", 2, "+", "pip3 install rich"),
        ("scripts/old.sh", 1, "-", "#!/bin/sh"),
        ("scripts/old.sh", 2, "-", "python -m pip install yq"),
    ]


def test_path_globs_pick_which_prs_to_fetch_and_which_lines_to_print(grep: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                                       capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    calls = serve(grep, monkeypatch, [pr(7, [".github/workflows/ci.yml", "docs/setup.md"], draft=True), pr(5, ["docs/setup.md"])],
                  {7: WORKFLOW_DIFF})
    # When
    status = run(grep, monkeypatch, r"pip3? install", "--path", ".github/*")
    # Then
    captured = capsys.readouterr()
    assert status == 0
    assert captured.out.splitlines() == [
        "#7 Title 7 (mason, draft)",
        "  .github/workflows/ci.yml:11 - run: pip install flake8",
        "  .github/workflows/ci.yml:11 + run: uv pip install --system flake8",
        "  .github/workflows/ci.yml:12 + # pip install stays in this comment",
        "  .github/workflows/ci.yml:40 - -- removed line that starts with two dashes, pip install",
    ]
    assert [call[:3] for call in calls if call[:2] == ("pr", "diff")] == [("pr", "diff", "7")]
    assert "searched 1 of 2 open PRs" in captured.err


def test_side_keeps_only_added_or_removed_lines(grep: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                 capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(grep, monkeypatch, [pr(7, ["docs/setup.md"])], {7: WORKFLOW_DIFF})
    # When
    status = run(grep, monkeypatch, r"pip install", "--side", "removed", "--path", "docs/*")
    # Then
    assert status == 0
    assert capsys.readouterr().out.splitlines() == ["#7 Title 7 (mason)", "  docs/setup.md:1 - pip install -r requirements.txt"]


def test_generated_files_and_long_lines_are_skipped(grep: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                     capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(grep, monkeypatch, [pr(9, [".github/actions/telemetry/dist/index.js", ".github/actions/telemetry/main.js"])],
          {9: BUNDLE_DIFF})
    # When
    status = run(grep, monkeypatch, r"pip install")
    # Then
    captured = capsys.readouterr()
    assert status == 0
    assert captured.out.splitlines() == ["#9 Title 9 (mason)", '  .github/actions/telemetry/main.js:1 + const short = "pip install";']
    assert "skipped 1 changed line(s) over 400 characters" in captured.err


def test_pr_with_a_truncated_file_list_is_always_fetched(grep: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                         capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    paths = [f"src/file{number}.c" for number in range(100)]
    calls = serve(grep, monkeypatch, [pr(3, paths)], {3: WORKFLOW_DIFF})
    # When
    status = run(grep, monkeypatch, r"uv sync", "--path", "docs/*")
    # Then
    assert status == 0
    assert ("pr", "diff", "3") in calls
    assert "docs/setup.md:1 + uv sync" in capsys.readouterr().out


def test_no_match_exits_one(grep: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(grep, monkeypatch, [pr(7, ["docs/setup.md"])], {7: WORKFLOW_DIFF})
    # When
    status = run(grep, monkeypatch, r"conda install")
    # Then
    assert status == 1
    assert capsys.readouterr().out == ""


def test_a_diff_that_fails_is_reported_and_the_rest_still_searched(grep: ModuleType, monkeypatch: pytest.MonkeyPatch,
                                                                     capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    too_big = grep.GhError("HTTP 406: Sorry, the diff exceeded the maximum number of files (300).")
    serve(grep, monkeypatch, [pr(8, ["docs/setup.md"]), pr(7, ["docs/setup.md"])], {8: too_big, 7: WORKFLOW_DIFF})
    # When
    status = run(grep, monkeypatch, r"uv sync")
    # Then
    captured = capsys.readouterr()
    assert status == 0
    assert "couldn't fetch the diff of #8: HTTP 406" in captured.err
    assert "searched 1 of 2 open PRs" in captured.err
    assert captured.out.splitlines() == ["#7 Title 7 (mason)", "  docs/setup.md:1 + uv sync"]


def test_json_rows_carry_the_pr_fields(grep: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(grep, monkeypatch, [pr(7, ["docs/setup.md"])], {7: WORKFLOW_DIFF})
    # When
    status = run(grep, monkeypatch, r"uv sync", "--json")
    # Then
    assert status == 0
    assert json.loads(capsys.readouterr().out) == [{
        "pr": 7, "path": "docs/setup.md", "line": 1, "side": "+", "text": "uv sync", "title": "Title 7",
        "author": "mason", "draft": False, "url": "https://github.com/owner/repo/pull/7",
    }]


def test_repo_flag_reaches_every_gh_call(grep: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    calls = serve(grep, monkeypatch, [pr(7, ["docs/setup.md"])], {7: WORKFLOW_DIFF})
    # When
    run(grep, monkeypatch, r"uv sync", "-R", "owner/repo")
    # Then
    assert calls and all(call[call.index("-R") + 1] == "owner/repo" for call in calls)


def test_invalid_pattern_exits_two(grep: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    serve(grep, monkeypatch, [], {})
    # When
    status = run(grep, monkeypatch, r"pip(")
    # Then
    assert status == 2
    assert re.search(r"invalid pattern", capsys.readouterr().err)
