"""Tests for retrieval result semantics without mocking vector mathematics."""

from typing import Any

import pytest

from app.models import CodeChunk
from app.services import retrieval


class RetrievalResult:
    def __init__(self, rows: list[tuple[CodeChunk, float]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[CodeChunk, float]]:
        return self.rows


class RetrievalSession:
    def __init__(self, rows: list[tuple[CodeChunk, float]]) -> None:
        self.rows = rows
        self.statement: Any = None

    def execute(self, statement: Any) -> RetrievalResult:
        self.statement = statement
        return RetrievalResult(self.rows)


def test_returns_explicit_cosine_distance(monkeypatch: pytest.MonkeyPatch) -> None:
    chunk = CodeChunk(
        repository="tiny-repo",
        file_path="calculator.py",
        symbol_type="function",
        symbol_name="add",
        start_line=4,
        end_line=6,
        content="def add(left, right):\n    return left + right\n",
        embedding=[0.0] * 384,
    )
    session = RetrievalSession([(chunk, 0.125)])
    monkeypatch.setattr(retrieval, "embed_query", lambda query: [0.0] * 384)

    results = retrieval.search_code(session, "add numbers", top_k=1)  # type: ignore[arg-type]

    assert len(results) == 1
    assert results[0].symbol_name == "add"
    assert results[0].cosine_distance == 0.125
    assert "<=>" in str(session.statement)


def test_repository_scope_is_part_of_the_sql_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RetrievalSession([])
    monkeypatch.setattr(retrieval, "embed_query", lambda query: [0.0] * 384)

    results = retrieval.search_code(
        session, "shared identifier", top_k=3, repository="repository-a"
    )  # type: ignore[arg-type]

    statement = str(session.statement)
    assert results == []
    assert "WHERE code_chunks.repository =" in statement
    assert statement.index("WHERE") < statement.index("ORDER BY") < statement.index("LIMIT")


def test_unknown_repository_does_not_fall_back_to_global_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RetrievalSession([])
    monkeypatch.setattr(retrieval, "embed_query", lambda query: [0.0] * 384)

    results = retrieval.search_code(
        session, "shared identifier", repository="missing-repository"
    )  # type: ignore[arg-type]

    assert results == []
    assert "WHERE code_chunks.repository =" in str(session.statement)


def test_omitted_repository_preserves_global_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RetrievalSession([])
    monkeypatch.setattr(retrieval, "embed_query", lambda query: [0.0] * 384)

    retrieval.search_code(session, "shared identifier")  # type: ignore[arg-type]

    assert "WHERE code_chunks.repository" not in str(session.statement)


def test_blank_repository_is_rejected_before_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        retrieval,
        "embed_query",
        lambda query: pytest.fail("embedding must not run for invalid scope"),
    )

    with pytest.raises(ValueError, match="must not be blank"):
        retrieval.search_code(RetrievalSession([]), "query", repository="  ")  # type: ignore[arg-type]


def test_equal_distance_ordering_uses_stable_source_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = RetrievalSession([])
    monkeypatch.setattr(retrieval, "embed_query", lambda query: [0.0] * 384)

    retrieval.search_code(session, "query")  # type: ignore[arg-type]

    order_by = str(session.statement).split(" ORDER BY ", maxsplit=1)[1]
    expected_order = (
        "cosine_distance",
        "code_chunks.repository",
        "code_chunks.file_path",
        "code_chunks.start_line",
        "code_chunks.end_line",
        "code_chunks.symbol_type",
        "coalesce(code_chunks.symbol_name",
        "code_chunks.id",
    )
    positions = [order_by.index(field) for field in expected_order]
    assert positions == sorted(positions)
