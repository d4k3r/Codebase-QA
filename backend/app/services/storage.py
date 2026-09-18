"""Orchestrate repository indexing and transactional row replacement."""

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import CodeChunk
from app.services.chunker import SourceChunk, chunk_python_file
from app.services.embeddings import embed_texts
from app.services.repository_loader import discover_source_files, resolve_repository_root
from app.services.text_chunker import chunk_config_file


class StorageError(RuntimeError):
    """Raised when indexed chunks cannot be stored."""


@dataclass(frozen=True, slots=True)
class IndexingStats:
    repository: str
    python_files_discovered: int
    chunks_created: int
    rows_stored: int


def _resolve_repository_name(root: Path, repository_name: str | None) -> str:
    name = repository_name.strip() if repository_name is not None else root.name
    if not name:
        raise ValueError("Repository name must not be empty")
    return name


def _load_chunks(root: Path, repository: str, files: list[Path]) -> list[SourceChunk]:
    chunks: list[SourceChunk] = []
    for file_path in files:
        if file_path.suffix == ".py":
            chunks.extend(chunk_python_file(file_path, root, repository))
        else:
            chunks.extend(chunk_config_file(file_path, root, repository))
    return chunks


def index_repository(
    db: Session,
    repository_path: str | Path,
    repository_name: str | None = None,
) -> IndexingStats:
    """Discover, chunk, embed, and replace one repository in one DB transaction."""

    root = resolve_repository_root(repository_path)
    repository = _resolve_repository_name(root, repository_name)
    files = discover_source_files(root)
    chunks = _load_chunks(root, repository, files)
    vectors = embed_texts([chunk.content for chunk in chunks])

    if len(vectors) != len(chunks):
        raise StorageError("Embedding count does not match chunk count")

    rows = [
        CodeChunk(
            repository=chunk.repository,
            file_path=chunk.file_path,
            symbol_type=chunk.symbol_type,
            symbol_name=chunk.symbol_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            content=chunk.content,
            embedding=embedding,
        )
        for chunk, embedding in zip(chunks, vectors, strict=True)
    ]

    try:
        db.execute(delete(CodeChunk).where(CodeChunk.repository == repository))
        db.add_all(rows)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise StorageError(f"Could not store repository chunks: {exc}") from exc

    return IndexingStats(
        repository=repository,
        python_files_discovered=sum(path.suffix == ".py" for path in files),
        chunks_created=len(chunks),
        rows_stored=len(rows),
    )
