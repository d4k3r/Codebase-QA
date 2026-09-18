"""Thin HTTP routes for health, indexing, retrieval, and RAG."""

import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    IndexRepositoryRequest,
    IndexRepositoryResponse,
    RetrievedChunkResponse,
    SearchRequest,
    SearchResponse,
)
from app.services.chunker import SourceFileError, SourceReadError
from app.services.embeddings import EmbeddingError
from app.services.rag import (
    LLMConfigurationError,
    RAGGenerationError,
    answer_question,
)
from app.services.repository_loader import RepositoryPathError, RepositoryReadError
from app.services.retrieval import RetrievalError, RetrievedChunk, search_code
from app.services.storage import StorageError, index_repository


router = APIRouter()
logger = logging.getLogger(__name__)


def _log_internal_failure(message: str, error: Exception) -> None:
    """Log failure location/type without serialising exception details."""

    logger.error("%s (%s)", message, type(error).__name__)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Report that the application process is running."""

    return HealthResponse(status="ok")


def _chunk_response(chunk: RetrievedChunk) -> RetrievedChunkResponse:
    return RetrievedChunkResponse(**asdict(chunk))


@router.post(
    "/repositories/index",
    response_model=IndexRepositoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def index_local_repository(
    request: IndexRepositoryRequest,
    db: Session = Depends(get_db),
) -> IndexRepositoryResponse:
    try:
        result = index_repository(db, request.repository_path, request.repository_name)
    except RepositoryReadError:
        raise HTTPException(
            status_code=400,
            detail="Could not safely read the repository directories.",
        )
    except SourceReadError:
        raise HTTPException(
            status_code=400,
            detail="Could not safely read the repository source files.",
        )
    except (RepositoryPathError, SourceFileError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (EmbeddingError, StorageError) as exc:
        _log_internal_failure("Repository indexing failed", exc)
        raise HTTPException(status_code=500, detail="Repository indexing failed.") from exc
    return IndexRepositoryResponse(**asdict(result))


@router.post("/search", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    try:
        results = search_code(db, request.query, request.top_k, request.repository)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (EmbeddingError, RetrievalError) as exc:
        _log_internal_failure("Semantic search failed", exc)
        raise HTTPException(status_code=500, detail="Semantic search failed.") from exc
    return SearchResponse(results=[_chunk_response(chunk) for chunk in results])


@router.post("/ask", response_model=AskResponse)
def ask_repository(
    request: AskRequest,
    db: Session = Depends(get_db),
) -> AskResponse:
    try:
        result = answer_question(
            db,
            request.question,
            request.top_k,
            request.repository,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RAGGenerationError as exc:
        _log_internal_failure("LLM generation failed", exc)
        raise HTTPException(status_code=502, detail="LLM generation failed.") from exc
    except (EmbeddingError, RetrievalError) as exc:
        _log_internal_failure("RAG retrieval failed", exc)
        raise HTTPException(status_code=500, detail="RAG retrieval failed.") from exc
    return AskResponse(
        answer=result.answer,
        sources=[_chunk_response(chunk) for chunk in result.sources],
    )
