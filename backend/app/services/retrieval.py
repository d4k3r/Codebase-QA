"""Exact dense, PostgreSQL lexical, and experimental RRF retrieval."""

from dataclasses import dataclass, replace
from typing import Literal

from sqlalchemy import case, func, literal, literal_column, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CodeChunk
from app.services.embeddings import embed_query
from app.services.lexical import exact_metadata_terms, lexical_terms


MAX_TOP_K = 50
RRF_CONSTANT = 60
RRF_BRANCH_DEPTH = 50
RetrievalMode = Literal["dense", "lexical", "hybrid"]


class RetrievalError(RuntimeError):
    """Raised when retrieval cannot complete."""


@dataclass(frozen=True, slots=True)
class RetrievedChunk:
    repository: str
    file_path: str
    symbol_type: str
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str
    cosine_distance: float | None
    row_id: int | None = None
    lexical_score: float | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    fusion_score: float | None = None
    fusion_rank: int | None = None


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
            row_id=chunk.id,
            dense_rank=rank,
        )
        for rank, (chunk, cosine_distance) in enumerate(rows, 1)
    ]


def _expanded_text(column: object) -> object:
    """Index both exact spelling and underscore/camel/path-separated forms."""

    original = func.coalesce(column, "")
    acronym = func.regexp_replace(original, r"([A-Z])([A-Z][a-z])", r"\1 \2", "g")
    camel = func.regexp_replace(acronym, r"([a-z0-9])([A-Z])", r"\1 \2", "g")
    separated = func.regexp_replace(camel, r"[_./:-]+", " ", "g")
    return original + literal(" ") + separated


def _lexical_vector() -> object:
    def field(column: object, weight: str) -> object:
        # PostgreSQL's setweight expects its internal "char" type. A SQL string
        # literal (not a VARCHAR bind parameter) resolves to that type safely;
        # weight is a fixed internal choice, never user input.
        return func.setweight(
            func.to_tsvector("simple", _expanded_text(column)),
            literal_column("'A'" if weight == "A" else "'D'"),
        )

    return field(CodeChunk.symbol_name, "A").op("||")(
        field(CodeChunk.file_path, "A")
    ).op("||")(field(CodeChunk.content, "D"))


def search_lexical(
    db: Session,
    query: str,
    top_k: int | None = None,
    repository: str | None = None,
) -> list[RetrievedChunk]:
    """Rank OR-matched code terms with PostgreSQL ts_rank_cd, not BM25."""

    limit = get_settings().default_top_k if top_k is None else top_k
    if not 1 <= limit <= MAX_TOP_K:
        raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
    scope = repository.strip() if repository is not None else None
    if repository is not None and not scope:
        raise ValueError("Repository scope must not be blank")
    terms = lexical_terms(query)
    if not terms:
        return []

    tsquery = func.to_tsquery("simple", " | ".join(terms))
    vector = _lexical_vector()
    exact = exact_metadata_terms(query)
    base_score = func.ts_rank_cd(vector, tsquery, 32)
    if exact:
        symbol_match = func.lower(func.coalesce(CodeChunk.symbol_name, "")).in_(exact)
        path_match = func.lower(CodeChunk.file_path).in_(exact)
        basename_match = func.lower(
            func.regexp_replace(CodeChunk.file_path, r"^.*/", "")
        ).in_(exact)
        score = (
            base_score + case((symbol_match, 0.10), else_=0.0)
            + case((path_match, 0.10), else_=0.0)
            + case((basename_match, 0.05), else_=0.0)
        ).label("lexical_score")
    else:
        score = base_score.label("lexical_score")
    statement = select(CodeChunk, score).where(vector.op("@@")(tsquery))
    if scope is not None:
        statement = statement.where(CodeChunk.repository == scope)
    statement = statement.order_by(
        score.desc(),
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
        raise RetrievalError("Could not retrieve lexical code chunks") from exc
    return [
        RetrievedChunk(
            repository=chunk.repository,
            file_path=chunk.file_path,
            symbol_type=chunk.symbol_type,
            symbol_name=chunk.symbol_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            content=chunk.content,
            cosine_distance=None,
            row_id=chunk.id,
            lexical_score=float(value),
            lexical_rank=rank,
        )
        for rank, (chunk, value) in enumerate(rows, 1)
    ]


def _identity(chunk: RetrievedChunk) -> tuple[object, ...]:
    if chunk.row_id is not None:
        return (chunk.repository, chunk.row_id)
    return (
        chunk.repository,
        chunk.file_path,
        chunk.symbol_type,
        chunk.symbol_name,
        chunk.start_line,
        chunk.end_line,
        chunk.content,
    )


def fuse_rrf(
    dense: list[RetrievedChunk],
    lexical: list[RetrievedChunk],
    top_k: int,
    constant: int = RRF_CONSTANT,
) -> list[RetrievedChunk]:
    """Fuse ranks only; cosine distance and PostgreSQL rank are never added."""

    if constant < 1 or not 1 <= top_k <= MAX_TOP_K:
        raise ValueError("Invalid RRF constant or top_k")
    combined: dict[tuple[object, ...], RetrievedChunk] = {}
    for rank, chunk in enumerate(dense, 1):
        key = _identity(chunk)
        combined[key] = replace(
            chunk, dense_rank=rank, fusion_score=1 / (constant + rank)
        )
    for rank, chunk in enumerate(lexical, 1):
        key = _identity(chunk)
        old = combined.get(key)
        if old is None:
            combined[key] = replace(
                chunk, lexical_rank=rank, fusion_score=1 / (constant + rank)
            )
        else:
            combined[key] = replace(
                old,
                lexical_rank=rank,
                lexical_score=chunk.lexical_score,
                fusion_score=(old.fusion_score or 0) + 1 / (constant + rank),
            )
    ranked = sorted(
        combined.values(),
        key=lambda chunk: (
            -(chunk.fusion_score or 0), chunk.repository, chunk.file_path,
            chunk.start_line, chunk.end_line, chunk.symbol_type,
            chunk.symbol_name or "", chunk.row_id or 0,
        ),
    )[:top_k]
    return [replace(chunk, fusion_rank=rank) for rank, chunk in enumerate(ranked, 1)]


def retrieve_code(
    db: Session,
    query: str,
    top_k: int | None = None,
    repository: str | None = None,
    mode: RetrievalMode = "dense",
    branch_depth: int = RRF_BRANCH_DEPTH,
    rrf_constant: int = RRF_CONSTANT,
) -> list[RetrievedChunk]:
    """Select an explicit experimental mode; dense remains the serving default."""

    if mode == "dense":
        return search_code(db, query, top_k, repository)
    if mode == "lexical":
        return search_lexical(db, query, top_k, repository)
    if mode != "hybrid":
        raise ValueError(f"Unknown retrieval mode: {mode}")
    limit = get_settings().default_top_k if top_k is None else top_k
    if not 1 <= limit <= MAX_TOP_K or not 1 <= branch_depth <= MAX_TOP_K:
        raise ValueError("Invalid top_k or branch_depth")
    if rrf_constant < 1:
        raise ValueError("rrf_constant must be positive")
    if repository is not None and not repository.strip():
        raise ValueError("Repository scope must not be blank")
    # A fresh session gets one short, repeatable-read snapshot. An existing
    # transaction is accepted only if its caller already established that level.
    try:
        if not db.in_transaction():
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        elif (
            db.execute(text("SHOW transaction_isolation")).scalar_one()
            != "repeatable read"
        ):
            raise RetrievalError("Hybrid retrieval needs a repeatable-read transaction")
    except SQLAlchemyError as exc:
        raise RetrievalError("Could not establish a consistent retrieval snapshot") from exc
    dense = search_code(db, query, branch_depth, repository)
    lexical = search_lexical(db, query, branch_depth, repository)
    return fuse_rrf(dense, lexical, limit, rrf_constant)
