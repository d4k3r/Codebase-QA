"""Thin HTTP routes for health, indexing, retrieval, and RAG."""

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
from app.services.chunker import SourceFileError
from app.services.embeddings import EmbeddingError
from app.services.rag import (
    LLMConfigurationError,
    RAGGenerationError,
    answer_question,
)
from app.services.repository_loader import RepositoryPathError
from app.services.retrieval import RetrievalError, RetrievedChunk, search_code
from app.services.storage import StorageError, index_repository


router = APIRouter()


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
    except (RepositoryPathError, SourceFileError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (EmbeddingError, StorageError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return IndexRepositoryResponse(**asdict(result))


@router.post("/search", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
) -> SearchResponse:
    try:
        results = search_code(db, request.query, request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (EmbeddingError, RetrievalError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return SearchResponse(results=[_chunk_response(chunk) for chunk in results])


@router.post("/ask", response_model=AskResponse)
def ask_repository(
    request: AskRequest,
    db: Session = Depends(get_db),
) -> AskResponse:
    try:
        result = answer_question(db, request.question, request.top_k)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RAGGenerationError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except (EmbeddingError, RetrievalError) as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return AskResponse(
        answer=result.answer,
        sources=[_chunk_response(chunk) for chunk in result.sources],
    )
