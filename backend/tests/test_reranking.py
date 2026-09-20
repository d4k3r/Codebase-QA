"""Regression tests for bounded local reranking without loading a model."""

from dataclasses import replace
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


def _ranked_result(
    ordered: list[RetrievedChunk], ce_ids: list[int]
) -> reranking.RerankResult:
    by_id = {chunk.row_id: chunk for chunk in ordered}
    scored = [replace(by_id[row_id], reranker_rank=rank,
                      reranker_score=float(len(ce_ids) - rank))
              for rank, row_id in enumerate(ce_ids, 1)]
    return reranking.RerankResult(
        candidates=scored[:2], pre_rerank_candidates=ordered,
        ranked_candidates=scored, union_size=len(ordered),
        scored_candidates=len(scored), truncated_inputs=0,
        maximum_input_tokens=20, model_input_limit=512,
        device="cpu", model_revision="fixture", model_parameters=None,
    )


def test_rrf_ce_formula_preserves_both_ranks_and_unscored_candidates() -> None:
    ordered = [_chunk(1, "strong RRF", 1), _chunk(2, "strong CE", 2),
               _chunk(3, "unscored", 3)]
    result = _ranked_result(ordered, [2, 1])
    fused = reranking.fuse_reranker_ranks(result, top_k=2, mode="rrf_ce")
    by_id = {chunk.row_id: chunk for chunk in fused.signal_ranked_candidates or []}
    assert by_id[1].signal_fusion_score == pytest.approx(1 / 61 + 1 / 62)
    assert by_id[2].signal_fusion_score == pytest.approx(1 / 62 + 1 / 61)
    assert by_id[3].signal_fusion_score == pytest.approx(1 / 63)
    assert by_id[3].reranker_rank is None and by_id[3].reranker_score is None
    assert [chunk.row_id for chunk in fused.candidates] == [1, 2]
    assert [chunk.signal_fusion_rank for chunk in fused.candidates] == [1, 2]
    assert by_id[1].fusion_score == ordered[0].fusion_score
    assert by_id[1].cosine_distance == ordered[0].cosine_distance
    assert by_id[1].content == ordered[0].content
    assert result.candidates[0].row_id == 2  # Baseline result is untouched.


def test_three_signal_formula_uses_only_available_branch_ranks() -> None:
    both = _chunk(1, "both", 1)
    dense_only = replace(_chunk(2, "dense", 2), lexical_rank=None, lexical_score=None)
    lexical_only = replace(_chunk(3, "lexical", 3), dense_rank=None,
                           cosine_distance=None)
    result = _ranked_result([both, dense_only, lexical_only], [3, 1])
    fused = reranking.fuse_reranker_ranks(result, top_k=2, mode="three_signal")
    by_id = {chunk.row_id: chunk for chunk in fused.signal_ranked_candidates or []}
    assert by_id[1].signal_fusion_score == pytest.approx(1 / 61 + 1 / 61 + 1 / 62)
    assert by_id[2].signal_fusion_score == pytest.approx(1 / 62)
    assert by_id[3].signal_fusion_score == pytest.approx(1 / 63 + 1 / 61)
    assert by_id[2].reranker_rank is None
    assert all(chunk.repository == "fixture" for chunk in fused.candidates)


def test_fusion_deduplicates_and_ties_use_stable_rrf_order() -> None:
    first = _chunk(1, "first", 1)
    second = _chunk(2, "second", 2)
    result = _ranked_result([first, first, second], [2, 1])
    fused = reranking.fuse_reranker_ranks(result, top_k=2, mode="rrf_ce")
    assert [chunk.row_id for chunk in fused.signal_ranked_candidates or []] == [1, 2]
    assert [chunk.signal_fusion_rank for chunk in fused.candidates] == [1, 2]
    assert fused.union_size == result.union_size


def test_experimental_wrapper_keeps_scope_and_depth_20(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[object, ...]] = []

    def fake_rerank(db: object, query: str, top_k: int, repository: str,
                    **kwargs: object) -> reranking.RerankResult:
        calls.append((query, top_k, repository, kwargs["depth"],
                      kwargs["branch_depth"], kwargs["rrf_constant"]))
        return _ranked_result([_chunk(1, "one", 1)], [1])

    monkeypatch.setattr(reranking, "rerank_hybrid", fake_rerank)
    output = reranking.rerank_hybrid_fused(
        object(), "question", 1, "fixture", mode="rrf_ce"  # type: ignore[arg-type]
    )
    assert output.candidates[0].repository == "fixture"
    assert calls == [("question", 1, "fixture", 20, 50, 60)]
    assert len(reranking.fuse_reranker_ranks(
        _ranked_result([_chunk(1, "one", 1)], [1]), top_k=10, mode="rrf_ce"
    ).candidates) == 1
    with pytest.raises(ValueError, match="20-candidate window"):
        reranking.fuse_reranker_ranks(
            _ranked_result([_chunk(1, "one", 1)], [1]), top_k=21, mode="rrf_ce"
        )
