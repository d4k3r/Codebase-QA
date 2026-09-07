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
