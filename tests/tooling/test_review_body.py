import io
import json
import sys
from collections.abc import Callable
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def review(tool: Callable[[str], ModuleType]) -> ModuleType:
    return tool("gh-review-body")


@pytest.mark.parametrize("stream", ['[{"id":1}]\n[{"id":2}]', ' {"id":1} {"id":2} \n'])
def test_paginated_values_when_json_is_concatenated(review: ModuleType, stream: str) -> None:
    # Given / When
    values = review.load_json_stream(stream)
    # Then
    assert values == [{"id": 1}, {"id": 2}]


def test_latest_authored_body_when_newer_empty_or_other_reviews_exist(review: ModuleType) -> None:
    # Given
    reviews = [
        {"id": 1, "user": {"login": "me"}, "body": "First"},
        {"id": 2, "user": {"login": "me"}, "body": "Latest"},
        {"id": 3, "user": {"login": "other"}, "body": "Other"},
        {"id": 4, "user": {"login": "me"}, "body": ""},
    ]
    # When / Then
    assert review.pick_review(reviews, None, "me")["id"] == 2


def test_explicit_id_when_review_is_other_author_and_empty(review: ModuleType) -> None:
    # Given
    target = {"id": 8, "user": {"login": "other"}, "body": None}
    # When / Then
    assert review.pick_review([target], 8, "me") == target


@pytest.mark.parametrize("review_id", [None, 99])
def test_selection_refuses_when_no_match(review: ModuleType, review_id: int | None) -> None:
    # Given / When / Then
    with pytest.raises(SystemExit):
        review.pick_review([], review_id, "me")


def test_write_payload_when_live_body_is_normalized(review: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    write = Mock()
    read = Mock(return_value="New\r\nBody")
    monkeypatch.setattr(review.subprocess, "run", write)
    monkeypatch.setattr(review.subprocess, "check_output", read)
    # When
    review.push_review_body("owner/repo", 17, 23, "New  \nBody\n")
    # Then
    assert write.call_args.args[0] == ["gh", "api", "--method", "PUT", "repos/owner/repo/pulls/17/reviews/23", "--input", "-"]
    assert json.loads(write.call_args.kwargs["input"]) == {"body": "New  \nBody\n"}
    assert write.call_args.kwargs["check"] is True
    assert read.call_args.args[0][2] == "repos/owner/repo/pulls/17/reviews/23"


def test_write_fails_when_verification_differs(review: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(review.subprocess, "run", Mock())
    monkeypatch.setattr(review.subprocess, "check_output", Mock(return_value="Old"))
    # When / Then
    with pytest.raises(SystemExit, match="verify failed"):
        review.push_review_body("owner/repo", 17, 23, "New")


def test_cli_stdin_edit_when_latest_review_selected(review: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    monkeypatch.setattr(sys, "argv", ["gh-review-body", "17", "-"])
    monkeypatch.setattr(sys, "stdin", io.StringIO("Replacement"))
    reads = Mock(side_effect=["owner/repo", '[{"id":23,"user":{"login":"me"},"body":"Old"}]', "me", "Replacement"])
    write = Mock()
    monkeypatch.setattr(review.subprocess, "check_output", reads)
    monkeypatch.setattr(review.subprocess, "run", write)
    # When
    review.main()
    # Then
    assert json.loads(write.call_args.kwargs["input"]) == {"body": "Replacement"}
    assert "--paginate" in reads.call_args_list[1].args[0]
