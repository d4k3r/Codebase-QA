"""Small Pydantic request/response schemas for the HTTP API."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _normalise_repository_scope(value: str | None) -> str | None:
    if value is None:
        return None
    scope = value.strip()
    if not scope:
        raise ValueError("Repository scope must not be blank")
    return scope


class HealthResponse(BaseModel):
    """Response returned by the health check."""

    status: Literal["ok"]


class IndexRepositoryRequest(BaseModel):
    repository_path: str = Field(min_length=1)
    repository_name: str | None = Field(default=None, min_length=1)


class IndexRepositoryResponse(BaseModel):
    repository: str
    python_files_discovered: int
    chunks_created: int
    rows_stored: int


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    repository: str | None = None

    _validate_repository = field_validator("repository")(_normalise_repository_scope)


class RetrievedChunkResponse(BaseModel):
    repository: str
    file_path: str
    symbol_type: str
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str
    cosine_distance: float


class SearchResponse(BaseModel):
    results: list[RetrievedChunkResponse]


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=50)
    repository: str | None = None

    _validate_repository = field_validator("repository")(_normalise_repository_scope)


class AskResponse(BaseModel):
    answer: str
    sources: list[RetrievedChunkResponse]
