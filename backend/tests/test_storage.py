"""Tests for indexing orchestration without replacing PostgreSQL with a fake vector DB."""

from pathlib import Path
from typing import Any

import pytest

from app.services import storage


class RecordingSession:
    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.added: list[Any] = []
        self.commits = 0

    def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    def add_all(self, rows: list[Any]) -> None:
        self.added.extend(rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        raise AssertionError("rollback was not expected")


def test_indexes_fixture_in_one_batch_transaction(
    tiny_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        storage,
        "embed_texts",
        lambda texts: [[0.0] * 384 for _ in texts],
    )
    session = RecordingSession()

    stats = storage.index_repository(session, tiny_repository, "tiny-repo")  # type: ignore[arg-type]

    assert stats.repository == "tiny-repo"
    assert stats.python_files_discovered == 3
    assert stats.chunks_created == 4
    assert stats.rows_stored == 4
    assert len(session.executed) == 1
    assert len(session.added) == 4
    assert session.commits == 1
