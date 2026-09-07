"""Optional real PostgreSQL/pgvector and sentence-transformer integration test."""

import os
from pathlib import Path

import pytest

from app.database import SessionLocal, engine
from app.models import Base, CodeChunk
from app.services.retrieval import search_code
from app.services.storage import index_repository


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_DATABASE_TESTS") != "1",
    reason="set RUN_DATABASE_TESTS=1 with PostgreSQL/pgvector running",
)
def test_real_index_and_semantic_retrieval(tiny_repository: Path) -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        stats = index_repository(db, tiny_repository, "tiny-repo-integration")
        results = search_code(db, "Which function adds two numbers?", top_k=3)

        assert stats.rows_stored == 4
        assert any(
            result.file_path == "calculator.py" and result.symbol_name == "add"
            for result in results
        )

        db.query(CodeChunk).filter(
            CodeChunk.repository == "tiny-repo-integration"
        ).delete()
        db.commit()
