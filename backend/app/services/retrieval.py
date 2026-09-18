"""Retrieve code chunks with exact pgvector cosine-distance search."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CodeChunk
from app.services.embeddings import embed_query


MAX_TOP_K = 50


class RetrievalError(RuntimeError):
    """Raised when semantic retrieval cannot complete."""


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    repository: str
    file_path: str
    symbol_type: str
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str
    cosine_distance: float


def search_code(
    db: Session,
    query: str,
    top_k: int | None = None,
    repository: str | None = None,
) -> list[RetrievedChunk]:
    """Return the nearest chunks; lower cosine distance means a closer match."""

    limit = get_settings().default_top_k if top_k is None else top_k
    if not 1 <= limit <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")

    scope = repository.strip() if repository is not None else None
    if repository is not None and not scope:
        raise ValueError("Repository scope must not be blank")

    query_vector = embed_query(query)
    distance = CodeChunk.embedding.cosine_distance(query_vector).label("cosine_distance")
    statement = select(CodeChunk, distance)
    if scope is not None:
        statement = statement.where(CodeChunk.repository == scope)
    statement = statement.order_by(
        distance,
        CodeChunk.repository,
        CodeChunk.file_path,
        CodeChunk.start_line,
        CodeChunk.end_line,
        CodeChunk.symbol_type,
        func.coalesce(CodeChunk.symbol_name, ""),
        CodeChunk.id,
    ).limit(limit)

    try:
        rows = db.execute(statement).all()
    except SQLAlchemyError as exc:
        raise RetrievalError(f"Could not retrieve code chunks: {exc}") from exc

    return [
        RetrievedChunk(
            repository=chunk.repository,
            file_path=chunk.file_path,
            symbol_type=chunk.symbol_type,
            symbol_name=chunk.symbol_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            content=chunk.content,
            cosine_distance=float(cosine_distance),
        )
        for chunk, cosine_distance in rows
    ]
