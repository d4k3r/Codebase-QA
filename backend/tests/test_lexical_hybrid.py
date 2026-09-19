"""Code-aware terms, honest scores, and deterministic rank fusion."""

import pytest

from app.services import retrieval
from app.services.lexical import exact_metadata_terms, lexical_terms
from app.services.retrieval import RetrievedChunk


@pytest.mark.parametrize(
    ("query", "required"),
    [
        ("get_embedding_model", {"get_embedding_model", "get", "embedding", "model"}),
        ("SettingsLoader", {"settingsloader", "settings", "loader"}),
        ("LLM_MAX_RETRIES", {"llm_max_retries", "llm", "max", "retries"}),
        ("backend/app/services/rag.py", {"backend", "app", "services", "rag", "py"}),
        ("POST /repositories/index", {"post", "repositories", "index"}),
        ("sentence-transformers/all-MiniLM-L6-v2", {"sentence", "transformers", "minilm", "l6", "v2"}),
        ("create.Engine()", {"create", "engine"}),
        ("embedding", {"embedding"}),
    ],
)
def test_code_aware_terms(query: str, required: set[str]) -> None:
    assert required <= set(lexical_terms(query))


def test_question_glue_can_produce_no_lexical_terms() -> None:
    assert lexical_terms("the and to, which?") == ()
    assert {"rag.py", "llm_max_retries"} <= set(
        exact_metadata_terms("Where are rag.py and LLM_MAX_RETRIES?")
    )


def _chunk(row_id: int, file_path: str, *, distance: float | None = None,
           lexical_score: float | None = None) -> RetrievedChunk:
    return RetrievedChunk(
        repository="fixture", file_path=file_path, symbol_type="function",
        symbol_name=file_path.removesuffix(".py"), start_line=1, end_line=2,
        content=f"def {file_path.removesuffix('.py')}(): pass\n",
        cosine_distance=distance, row_id=row_id, lexical_score=lexical_score,
    )


def test_rrf_formula_branch_only_overlap_deduplication_and_scores() -> None:
    shared_dense = _chunk(1, "shared.py", distance=0.1)
    shared_lexical = _chunk(1, "shared.py", lexical_score=0.8)
    dense_only = _chunk(2, "dense.py", distance=0.2)
    lexical_only = _chunk(3, "lexical.py", lexical_score=0.7)

    fused = retrieval.fuse_rrf(
        [shared_dense, dense_only], [lexical_only, shared_lexical], 3, constant=60
    )

    assert len(fused) == 3
    assert fused[0].file_path == "shared.py"
    assert fused[0].fusion_score == pytest.approx(1 / 61 + 1 / 62)
    assert fused[0].dense_rank == 1 and fused[0].lexical_rank == 2
    assert fused[0].fusion_rank == 1
    assert fused[0].cosine_distance == 0.1
    assert fused[0].lexical_score == 0.8
    assert fused[1].file_path == "lexical.py"
    assert fused[1].cosine_distance is None
    assert fused[1].fusion_score == pytest.approx(1 / 61)
    assert fused[2].file_path == "dense.py"
    assert fused[2].lexical_score is None


def test_rrf_equal_scores_use_stable_source_order() -> None:
    zeta = _chunk(1, "zeta.py", distance=0.1)
    alpha = _chunk(2, "alpha.py", lexical_score=0.4)
    assert [c.file_path for c in retrieval.fuse_rrf([zeta], [alpha], 2)] == [
        "alpha.py", "zeta.py"
    ]


def test_hybrid_uses_one_scope_and_establishes_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str | None, int]] = []

    class Session:
        def in_transaction(self) -> bool:
            return False

        def execute(self, statement: object) -> None:
            assert str(statement) == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
            calls.append(("snapshot", None, 0))

    def dense(db: object, query: str, top_k: int, repository: str | None) -> list[RetrievedChunk]:
        calls.append(("dense", repository, top_k))
        return [_chunk(1, "shared.py", distance=0.1)]

    def lexical(db: object, query: str, top_k: int, repository: str | None) -> list[RetrievedChunk]:
        calls.append(("lexical", repository, top_k))
        return [_chunk(1, "shared.py", lexical_score=0.5)]

    monkeypatch.setattr(retrieval, "search_code", dense)
    monkeypatch.setattr(retrieval, "search_lexical", lexical)
    result = retrieval.retrieve_code(
        Session(), "query", 1, "fixture", "hybrid", branch_depth=3  # type: ignore[arg-type]
    )
    assert [c.file_path for c in result] == ["shared.py"]
    assert calls == [
        ("snapshot", None, 0), ("dense", "fixture", 3), ("lexical", "fixture", 3)
    ]


def test_empty_lexical_query_does_not_execute_sql() -> None:
    class Session:
        def execute(self, statement: object) -> None:
            pytest.fail("no SQL for a query with no useful terms")

    assert retrieval.search_lexical(
        Session(), "the and to", repository="fixture"  # type: ignore[arg-type]
    ) == []


def test_hybrid_rejects_an_existing_read_committed_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Session:
        def in_transaction(self) -> bool:
            return True

        def execute(self, statement: object) -> object:
            assert str(statement) == "SHOW transaction_isolation"
            return type("Result", (), {"scalar_one": lambda self: "read committed"})()

    monkeypatch.setattr(
        retrieval, "search_code",
        lambda *args: pytest.fail("must reject before querying either branch"),
    )
    with pytest.raises(retrieval.RetrievalError, match="repeatable-read"):
        retrieval.retrieve_code(
            Session(), "query", 1, "fixture", "hybrid"  # type: ignore[arg-type]
        )


def test_invalid_rrf_constant_is_rejected_before_database_access() -> None:
    with pytest.raises(ValueError, match="rrf_constant"):
        retrieval.retrieve_code(
            object(), "query", 1, "fixture", "hybrid", rrf_constant=0  # type: ignore[arg-type]
        )
