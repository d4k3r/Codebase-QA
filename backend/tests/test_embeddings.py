"""Tests for embedding batching and dimension validation without loading a model."""

import pytest

from app.services import embeddings


class FakeEncoded:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    def tolist(self) -> list[list[float]]:
        return self.vectors


class FakeModel:
    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.last_options: dict[str, object] = {}

    def encode(self, texts: list[str], **options: object) -> FakeEncoded:
        self.last_options = options
        return FakeEncoded([[float(index)] * self.dimension for index, _ in enumerate(texts)])


def test_embeds_batch_with_normalization(monkeypatch: pytest.MonkeyPatch) -> None:
    model = FakeModel()
    monkeypatch.setattr(embeddings, "get_embedding_model", lambda: model)

    vectors = embeddings.embed_texts(["first", "second"])

    assert len(vectors) == 2
    assert all(len(vector) == 384 for vector in vectors)
    assert model.last_options["normalize_embeddings"] is True
    assert model.last_options["batch_size"] == 32


def test_rejects_unexpected_embedding_dimension(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(embeddings, "get_embedding_model", lambda: FakeModel(12))

    with pytest.raises(embeddings.EmbeddingError, match="expected 384"):
        embeddings.embed_query("where is addition implemented?")
