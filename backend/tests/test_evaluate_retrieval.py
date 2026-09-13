"""Tests for the small retrieval evaluation utility's lifecycle guarantees."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import evaluate_retrieval


class FakeSession:
    def __init__(self, rollback_error: Exception | None = None) -> None:
        self.rollback_error = rollback_error
        self.executed: list[object] = []
        self.commit_calls = 0
        self.closed = False

    def rollback(self) -> None:
        if self.rollback_error is not None:
            raise self.rollback_error

    def execute(self, statement: object) -> None:
        self.executed.append(statement)

    def commit(self) -> None:
        self.commit_calls += 1

    def close(self) -> None:
        self.closed = True


def test_blank_explicit_repository_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="must not be blank"):
        evaluate_retrieval._resolve_repository_identity("   ")


def test_generated_identity_is_cleaned_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession()
    monkeypatch.setattr(evaluate_retrieval, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        evaluate_retrieval,
        "uuid4",
        lambda: SimpleNamespace(hex="generated-test-id"),
    )
    monkeypatch.setattr(
        evaluate_retrieval,
        "CASES",
        (evaluate_retrieval.EvaluationCase("test question", "test.py", "test"),),
    )
    monkeypatch.setattr(evaluate_retrieval, "search_code", lambda *args: [])
    monkeypatch.setattr(
        evaluate_retrieval,
        "index_repository",
        lambda db, path, name: SimpleNamespace(
            repository="canonical-generated-test-id", rows_stored=0
        ),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["evaluate_retrieval", str(tmp_path)],
    )

    evaluate_retrieval.main()

    assert session.closed is True
    assert session.commit_calls == 1
    assert len(session.executed) == 1
    assert "canonical-generated-test-id" in next(
        iter(session.executed[0].compile().params.values())
    )


def test_cleanup_failure_still_closes_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(RuntimeError("synthetic cleanup failure"))
    monkeypatch.setattr(evaluate_retrieval, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        evaluate_retrieval,
        "CASES",
        (evaluate_retrieval.EvaluationCase("test question", "test.py", "test"),),
    )
    monkeypatch.setattr(evaluate_retrieval, "search_code", lambda *args: [])
    monkeypatch.setattr(
        evaluate_retrieval,
        "index_repository",
        lambda db, path, name: SimpleNamespace(repository=name, rows_stored=0),
    )
    monkeypatch.setattr(sys, "argv", ["evaluate_retrieval", str(tmp_path)])

    with pytest.raises(RuntimeError, match="synthetic cleanup failure"):
        evaluate_retrieval.main()

    assert session.closed is True
