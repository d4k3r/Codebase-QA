"""Optional real PostgreSQL/pgvector and sentence-transformer integration test."""

import os
from uuid import uuid4
from pathlib import Path

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import SQLAlchemyError

from app import evaluation
from app.database import SessionLocal, engine
from app.models import Base, CodeChunk
from app.services.chunker import SourceFileError
from app.services import retrieval
from app.services.retrieval import search_code
from app.services.storage import StorageError, index_repository


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
            results = search_code(
                db,
                "Which function adds two numbers?",
                top_k=3,
                repository=repository_name,
            )

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


@DATABASE_TEST_SKIP
def test_repository_scope_filters_before_limit_and_ties_are_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    Base.metadata.create_all(bind=engine)
    target_repository = f"scope-target-{uuid4().hex}"
    other_repository = f"scope-other-{uuid4().hex}"
    vector = [1.0] + [0.0] * 383
    rows = [
        CodeChunk(
            repository=other_repository,
            file_path="shared.py",
            symbol_type="function",
            symbol_name="shared_identifier",
            start_line=1,
            end_line=2,
            content="def shared_identifier():\n    return 'other'\n",
            embedding=vector,
        ),
        CodeChunk(
            repository=target_repository,
            file_path="zeta.py",
            symbol_type="function",
            symbol_name="shared_identifier",
            start_line=1,
            end_line=2,
            content="def shared_identifier():\n    return 'zeta'\n",
            embedding=vector,
        ),
        CodeChunk(
            repository=target_repository,
            file_path="alpha.py",
            symbol_type="function",
            symbol_name="shared_identifier",
            start_line=1,
            end_line=2,
            content="def shared_identifier():\n    return 'alpha'\n",
            embedding=vector,
        ),
    ]
    monkeypatch.setattr(retrieval, "embed_query", lambda query: vector)

    with SessionLocal() as db:
        try:
            db.add_all(rows)
            db.commit()

            scoped = retrieval.search_code(
                db,
                "shared identifier",
                top_k=1,
                repository=target_repository,
            )
            tied = retrieval.search_code(
                db,
                "shared identifier",
                top_k=2,
                repository=target_repository,
            )
            missing = retrieval.search_code(
                db,
                "shared identifier",
                top_k=3,
                repository=f"missing-{uuid4().hex}",
            )
            indexed_target = evaluation.load_indexed_chunks(db, target_repository)
            dataset = evaluation.EvaluationDataset(
                format_version=1,
                dataset_version="scoped-integration-v1",
                dataset_status="test fixture",
                corpus=evaluation.CorpusManifest(
                    repository=target_repository,
                    expected_chunk_count=2,
                    index_manifest_sha256=evaluation.compute_index_manifest(
                        indexed_target
                    ),
                    chunking_identifier=evaluation.CHUNKING_IDENTIFIER,
                ),
                cases=[
                    evaluation.EvaluationCase(
                        case_id="scoped-overlap",
                        question="shared identifier",
                        primary_category="integration",
                        repository=target_repository,
                        source_answerable=True,
                        required_evidence=[
                            evaluation.EvidenceUnit(
                                evidence_id="target-alpha",
                                acceptable_spans=[
                                    evaluation.EvidenceSpan(
                                        file_path="alpha.py",
                                        start_line=1,
                                        end_line=2,
                                        symbol_name="shared_identifier",
                                        content_contains=["return 'alpha'"],
                                    )
                                ],
                            )
                        ],
                        rationale="Only the target repository is acceptable.",
                    )
                ],
            )
            monkeypatch.setattr(
                evaluation,
                "collect_embedding_diagnostics",
                lambda chunks: (
                    {},
                    {
                        "effective_input_limit": None,
                        "resolved_model_revision": None,
                    },
                ),
            )
            report = evaluation.evaluate_dataset(
                db,
                dataset,
                "integration-dataset-hash",
                target_repository,
                candidate_depth=10,
            )

            assert [item.repository for item in scoped] == [target_repository]
            assert [item.file_path for item in tied] == ["alpha.py", "zeta.py"]
            assert missing == []
            assert {
                candidate["repository"]
                for candidate in report["cases"][0]["candidates"]
            } == {target_repository}
            assert report["metrics"]["hit_at_1"]["value"] == 1
        finally:
            db.rollback()
            db.execute(
                delete(CodeChunk).where(
                    CodeChunk.repository.in_([target_repository, other_repository])
                )
            )
            db.commit()
