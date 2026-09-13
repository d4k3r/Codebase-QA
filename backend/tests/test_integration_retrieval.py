"""Optional real PostgreSQL/pgvector and sentence-transformer integration test."""

import os
from uuid import uuid4
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select

from app.database import SessionLocal, engine
from app.models import Base, CodeChunk
from app.services.chunker import SourceFileError
from app.services.retrieval import search_code
from app.services.storage import StorageError, index_repository
from sqlalchemy.exc import SQLAlchemyError


pytestmark = pytest.mark.integration


DATABASE_TEST_SKIP = pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostgreSQL/pgvector running",
)


@DATABASE_TEST_SKIP
def test_real_index_and_semantic_retrieval(tiny_repository: Path) -> None:
    Base.metadata.create_all(bind=engine)
    repository_name = f"tiny-repo-integration-{uuid4().hex}"
    with SessionLocal() as db:
        try:
            stats = index_repository(db, tiny_repository, repository_name)
            results = search_code(db, "Which function adds two numbers?", top_k=3)

            assert stats.repository == repository_name
            assert stats.rows_stored == 4
            assert any(
                result.repository == repository_name
                and result.file_path == "calculator.py"
                and result.symbol_name == "add"
                for result in results
            )

            index_repository(db, tiny_repository, repository_name)
            row_count = db.scalar(
                select(func.count()).select_from(CodeChunk).where(
                    CodeChunk.repository == repository_name
                )
            )
            assert row_count == 4
        finally:
            db.rollback()
            db.execute(delete(CodeChunk).where(CodeChunk.repository == repository_name))
            db.commit()


@DATABASE_TEST_SKIP
def test_failed_replacement_preserves_previous_rows(
    tiny_repository: Path,
    tmp_path: Path,
) -> None:
    Base.metadata.create_all(bind=engine)
    repository_name = f"tiny-repo-preservation-{uuid4().hex}"
    broken_repository = tmp_path / "broken"
    broken_repository.mkdir()
    (broken_repository / "broken.py").write_text("def broken(:\n", encoding="utf-8")

    with SessionLocal() as db:
        try:
            stats = index_repository(db, tiny_repository, repository_name)
            assert stats.rows_stored == 4

            with pytest.raises(SourceFileError):
                index_repository(db, broken_repository, repository_name)

            row_count = db.scalar(
                select(func.count()).select_from(CodeChunk).where(
                    CodeChunk.repository == repository_name
                )
            )
            assert row_count == 4
        finally:
            db.rollback()
            db.execute(delete(CodeChunk).where(CodeChunk.repository == repository_name))
            db.commit()


@DATABASE_TEST_SKIP
def test_post_delete_failure_rolls_back_to_previous_rows(
    tiny_repository: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Base.metadata.create_all(bind=engine)
    repository_name = f"tiny-repo-rollback-{uuid4().hex}"
    replacement_repository = tmp_path / "replacement"
    replacement_repository.mkdir()
    (replacement_repository / "replacement.py").write_text(
        "def replacement():\n    return 'new'\n",
        encoding="utf-8",
    )

    with SessionLocal() as db:
        fail_commit = False
        observed_rows_after_delete: list[int] = []
        real_commit = db.commit

        def commit_with_post_delete_failure() -> None:
            if not fail_commit:
                real_commit()
                return
            db.flush()
            observed_rows_after_delete.append(
                db.scalar(
                    select(func.count()).select_from(CodeChunk).where(
                        CodeChunk.repository == repository_name
                    )
                )
            )
            raise SQLAlchemyError("synthetic failure after DELETE and flush")

        try:
            initial_stats = index_repository(db, tiny_repository, repository_name)
            assert initial_stats.rows_stored == 4
            monkeypatch.setattr(db, "commit", commit_with_post_delete_failure)
            fail_commit = True

            with pytest.raises(StorageError, match="Could not store repository chunks"):
                index_repository(db, replacement_repository, repository_name)

            assert observed_rows_after_delete == [1]
            restored_paths = db.scalars(
                select(CodeChunk.file_path).where(CodeChunk.repository == repository_name)
            ).all()
            assert sorted(restored_paths) == [
                "calculator.py",
                "calculator.py",
                "constants.py",
                "nested/greetings.py",
            ]
        finally:
            fail_commit = False
            db.rollback()
            db.execute(delete(CodeChunk).where(CodeChunk.repository == repository_name))
            db.commit()
