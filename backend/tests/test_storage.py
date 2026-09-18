"""Tests for indexing orchestration without replacing PostgreSQL with a fake vector DB."""

from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.services import storage
from app.services.chunker import SourceFileError
from app.services.embeddings import EmbeddingError
from app.services.repository_loader import RepositoryPathError


class RecordingSession:
    def __init__(self) -> None:
        self.executed: list[Any] = []
        self.added: list[Any] = []
        self.commits = 0
        self.rollback_calls = 0
        self.fail_commit = False

    def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    def add_all(self, rows: list[Any]) -> None:
        self.added.extend(rows)

    def commit(self) -> None:
        if self.fail_commit:
            raise SQLAlchemyError("synthetic commit failure")
        self.commits += 1

    def rollback(self) -> None:
        self.rollback_calls += 1


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
    assert stats.chunks_created == 5
    assert stats.rows_stored == 5
    assert len(session.executed) == 1
    assert len(session.added) == 5
    assert session.commits == 1
    assert session.rollback_calls == 0


def test_indexing_dispatches_python_and_allowlisted_config_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "app.py").write_text(
        "SETTING = 1\n\ndef read_setting():\n    return SETTING\n",
        encoding="utf-8",
    )
    config_source = "services:\n  database: postgres\n"
    (tmp_path / "compose.yml").write_text(config_source, encoding="utf-8")
    monkeypatch.setattr(
        storage,
        "embed_texts",
        lambda texts: [[0.0] * 384 for _ in texts],
    )
    session = RecordingSession()

    stats = storage.index_repository(session, tmp_path, "mixed-repo")  # type: ignore[arg-type]

    assert stats.python_files_discovered == 1
    assert stats.chunks_created == 3
    assert [row.symbol_type for row in session.added] == [
        "module_companion",
        "function",
        "config",
    ]
    assert session.added[-1].content == config_source


@pytest.mark.parametrize(
    ("failure", "error_type"),
    [
        (RepositoryPathError("synthetic discovery failure"), RepositoryPathError),
        (SourceFileError("synthetic parse failure"), SourceFileError),
        (EmbeddingError("synthetic embedding failure"), EmbeddingError),
    ],
)
def test_precommit_failure_does_not_execute_replacement(
    tiny_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    error_type: type[Exception],
) -> None:
    session = RecordingSession()
    if isinstance(failure, RepositoryPathError):
        monkeypatch.setattr(
            storage,
            "discover_source_files",
            lambda root: (_ for _ in ()).throw(failure),
        )
    elif isinstance(failure, SourceFileError):
        monkeypatch.setattr(storage, "_load_chunks", lambda root, repository, files: (_ for _ in ()).throw(failure))
    else:
        monkeypatch.setattr(storage, "embed_texts", lambda texts: (_ for _ in ()).throw(failure))

    with pytest.raises(error_type, match="synthetic"):
        storage.index_repository(session, tiny_repository, "tiny-repo")  # type: ignore[arg-type]

    assert session.executed == []
    assert session.added == []
    assert session.commits == 0


def test_commit_failure_rolls_back_replacement(
    tiny_repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        storage,
        "embed_texts",
        lambda texts: [[0.0] * 384 for _ in texts],
    )
    session = RecordingSession()
    session.fail_commit = True

    with pytest.raises(storage.StorageError, match="Could not store repository chunks"):
        storage.index_repository(session, tiny_repository, "tiny-repo")  # type: ignore[arg-type]

    assert len(session.executed) == 1
    assert len(session.added) == 5
    assert session.rollback_calls == 1
