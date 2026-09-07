"""Tests for the PostgreSQL table definition without requiring a live database."""

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models import CodeChunk


def test_code_chunks_uses_384_dimension_vector() -> None:
    ddl = str(CreateTable(CodeChunk.__table__).compile(dialect=postgresql.dialect()))

    assert CodeChunk.__tablename__ == "code_chunks"
    assert "VECTOR(384) NOT NULL" in ddl
    assert "hnsw" not in ddl.lower()
    assert "ivfflat" not in ddl.lower()
