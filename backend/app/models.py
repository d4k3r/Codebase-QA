"""SQLAlchemy models persisted by the Codebase QA V2 backend."""

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import VECTOR


class Base(DeclarativeBase):
    """Base class for SQLAlchemy declarative models."""


class CodeChunk(Base):
    """A repository code chunk and its 384-dimensional embedding."""

    __tablename__ = "code_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    repository: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    symbol_type: Mapped[str] = mapped_column(String, nullable=False)
    symbol_name: Mapped[str | None] = mapped_column(String, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(VECTOR(384), nullable=False)
