"""Regression tests for bounded local reranking without loading a model."""

from types import SimpleNamespace

import pytest

from app.services import reranking, retrieval
from app.services.retrieval import RetrievedChunk


def _chunk(row_id: int, source: str, rrf_rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        repository="fixture", file_path=f"file_{row_id}.py",
        symbol_type="function", symbol_name=f"function_{row_id}",
        start_line=1, end_line=1, content=source,
        cosine_distance=0.1, row_id=row_id, lexical_score=0.4,
        dense_rank=rrf_rank, lexical_rank=rrf_rank,
        fusion_rank=rrf_rank, fusion_score=1 / (60 + rrf_rank),
    )


class FakeModel:
    max_seq_length = 20
    device = "cpu"
    model = SimpleNamespace(config=SimpleNamespace(_commit_hash="fake-revision"))

    def __init__(self) -> None:
        self.pairs: list[tuple[str, str]] = []

    def tokenizer(self, query: str, document: str, **kwargs: object) -> dict[str, list[int]]:
        assert kwargs == {
            "add_special_tokens": True, "truncation": False, "verbose": False,
        }
        return {"input_ids": list(range(len((query + " " + document).split()) + 3))}

    def predict(self, pairs: list[tuple[str, str]], **kwargs: object) -> list[float]:
        assert kwargs["batch_size"] == reranking.RERANKER_BATCH_SIZE
        self.pairs = pairs
        return [float(document.count("match")) for _, document in pairs]


def test_input_is_truthful_metadata_plus_original_source() -> None:
    chunk = _chunk(1, "def function_1():\n    return 'match'\n", 1)
    document = reranking.reranker_document(chunk)
    assert document.startswith("Repository: fixture\nFile: file_1.py\n")
    assert "Symbol: function function_1" in document
    assert document.endswith("Source:\n" + chunk.content)


def test_reranking_keeps_provenance_separates_scores_and_records_truncation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeModel()
    monkeypatch.setattr(reranking, "get_reranker_model", lambda: model)
    first = _chunk(1, "short source", 1)
    second = _chunk(2, "match " + "many " * 30, 2)
    result = reranking.rerank_candidates(
        "question", [first, second], union_size=3, top_k=2, depth=20
    )

    assert [c.row_id for c in result.candidates] == [2, 1]
    assert result.union_size == 3 and result.scored_candidates == 2
    assert result.truncated_inputs == 1
    assert result.model_input_limit == 20
    assert result.maximum_input_tokens > 20
    assert result.candidates[0].content == second.content
    assert result.candidates[0].file_path == second.file_path
    assert result.candidates[0].cosine_distance == second.cosine_distance
    assert result.candidates[0].lexical_score == second.lexical_score
    assert result.candidates[0].fusion_score == second.fusion_score
    assert result.candidates[0].reranker_score == 1.0
    assert result.candidates[0].reranker_rank == 1
    assert result.candidates[0].reranker_input_truncated is True
    assert model.pairs[0] == ("question", reranking.reranker_document(first))


def test_depth_20_cannot_promote_candidate_21_but_depth_50_can(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = FakeModel()
    monkeypatch.setattr(reranking, "get_reranker_model", lambda: model)
    candidates = [_chunk(i, "match" if i == 21 else "plain", i) for i in range(1, 22)]

    first = reranking.rerank_candidates(
        "question", candidates, union_size=30, top_k=10, depth=20
    )
    assert first.scored_candidates == 20
    assert all(chunk.row_id != 21 for chunk in first.candidates)
    second = reranking.rerank_candidates(
        "question", candidates, union_size=30, top_k=10, depth=50
    )
    assert second.scored_candidates == 21
    assert second.candidates[0].row_id == 21


def test_equal_reranker_scores_keep_deterministic_rrf_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(reranking, "get_reranker_model", FakeModel)
    chunks = [_chunk(3, "plain", 1), _chunk(2, "plain", 2)]
    result = reranking.rerank_candidates(
        "question", chunks, union_size=2, top_k=2, depth=20
    )
    assert [chunk.row_id for chunk in result.candidates] == [3, 2]


def test_reranker_uses_existing_hybrid_pool_once_and_preserves_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    def fake_pool(db: object, query: str, repository: str, branch_depth: int,
                  constant: int, depth: int) -> tuple[list[RetrievedChunk], int]:
        calls.append((query, repository, branch_depth, constant, depth))
        return [_chunk(1, "plain", 1)], 1
    monkeypatch.setattr(reranking, "hybrid_candidate_pool", fake_pool)
    monkeypatch.setattr(reranking, "get_reranker_model", FakeModel)
    result = reranking.rerank_hybrid(
        object(), "question", 1, "fixture", depth=20  # type: ignore[arg-type]
    )
    assert [chunk.repository for chunk in result.candidates] == ["fixture"]
    assert calls == [("question", "fixture", 50, 60, 50)]
