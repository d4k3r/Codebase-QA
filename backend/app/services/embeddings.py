"""Create normalized local sentence-transformer embeddings."""

from functools import lru_cache
from typing import Any, Sequence

from app.config import get_settings


EMBEDDING_DIMENSION = 384
DEFAULT_BATCH_SIZE = 32


class EmbeddingError(RuntimeError):
    """Raised when the configured model cannot produce expected embeddings."""


@lru_cache(maxsize=1)
def get_embedding_model() -> Any:
    """Load and cache the single MVP embedding model on first use."""

    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(get_settings().embedding_model_name)
    except Exception as exc:
        raise EmbeddingError(f"Could not load embedding model: {exc}") from exc

    if hasattr(model, "get_embedding_dimension"):
        dimension = model.get_embedding_dimension()
    else:
        dimension = model.get_sentence_embedding_dimension()
    if dimension is not None and dimension != EMBEDDING_DIMENSION:
        raise EmbeddingError(
            f"Embedding model dimension is {dimension}; expected {EMBEDDING_DIMENSION}"
        )
    return model


def _validate_vectors(vectors: list[list[float]]) -> None:
    for index, vector in enumerate(vectors):
        if len(vector) != EMBEDDING_DIMENSION:
            raise EmbeddingError(
                f"Embedding {index} has dimension {len(vector)}; "
                f"expected {EMBEDDING_DIMENSION}"
            )


def embed_texts(texts: Sequence[str]) -> list[list[float]]:
    """Embed multiple texts in one normalized batch."""

    if not texts:
        return []

    model = get_embedding_model()
    try:
        encoded = model.encode(
            list(texts),
            batch_size=DEFAULT_BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        vectors = encoded.tolist()
    except Exception as exc:
        raise EmbeddingError(f"Could not create embeddings: {exc}") from exc

    _validate_vectors(vectors)
    return vectors


def embed_query(query: str) -> list[float]:
    """Embed one non-empty semantic-search query."""

    if not query.strip():
        raise ValueError("Query must not be empty")
    return embed_texts([query])[0]
