"""Tests for read-only, source-grounded retrieval evaluation."""

from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from app import evaluation
from app.services import rag
from app.services.retrieval import RetrievedChunk
from scripts import evaluate_retrieval


def _outcome(
    case_id: str,
    required: set[str],
    indexed: set[str],
    candidates: list[set[str]],
    context: set[str],
    *,
    answerable: bool = True,
) -> evaluation.CaseOutcome:
    return evaluation.CaseOutcome(
        case_id=case_id,
        source_answerable=answerable,
        required_evidence_ids=frozenset(required),
        indexed_evidence_ids=frozenset(indexed),
        candidate_evidence_by_rank=tuple(frozenset(item) for item in candidates),
        context_evidence_ids=frozenset(context),
    )


def _span(file_path: str, start: int, end: int) -> evaluation.EvidenceSpan:
    return evaluation.EvidenceSpan(
        file_path=file_path,
        start_line=start,
        end_line=end,
    )


def test_metrics_match_hand_calculated_cases() -> None:
    outcomes = [
        _outcome(
            "multiple",
            {"a", "b"},
            {"a", "b"},
            [{"a"}, set(), {"b"}],
            {"a"},
        ),
        _outcome("retrieval-miss", {"c"}, {"c"}, [set(), set(), set()], set()),
        _outcome("index-miss", {"d"}, set(), [set(), set(), set()], set()),
        _outcome("unanswerable", set(), set(), [], set(), answerable=False),
    ]

    metrics = evaluation.calculate_metrics(outcomes)

    assert metrics["source_answerability"]["numerator"] == 3
    assert metrics["source_answerability"]["denominator"] == 4
    assert metrics["index_evidence_coverage"]["numerator"] == 3
    assert metrics["index_evidence_coverage"]["denominator"] == 4
    assert metrics["hit_at_1"]["value"] == pytest.approx(1 / 3)
    assert metrics["macro_evidence_recall_at_1"]["value"] == pytest.approx(1 / 6)
    assert metrics["micro_evidence_recall_at_3"]["value"] == pytest.approx(2 / 4)
    assert metrics["all_evidence_at_3"]["value"] == pytest.approx(1 / 3)
    assert metrics["mrr_at_10"]["value"] == pytest.approx(1 / 3)
    assert metrics["final_context_evidence_recall"]["value"] == pytest.approx(1 / 4)
    assert metrics["context_sufficiency"]["value"] == 0
    assert metrics["selection_loss_rate"]["value"] == pytest.approx(1 / 2)
    assert metrics["unanswerable_cases"]["case_ids"] == ["unanswerable"]


def test_alternative_spans_count_one_evidence_unit_once() -> None:
    case = evaluation.EvaluationCase(
        case_id="alternatives",
        question="Where is the behavior?",
        primary_category="test",
        repository="fixture",
        source_answerable=True,
        required_evidence=[
            evaluation.EvidenceUnit(
                evidence_id="same-fact",
                acceptable_spans=[
                    _span("first.py", 1, 5),
                    _span("second.py", 10, 20),
                ],
            )
        ],
        rationale="Either implementation demonstrates the same fact.",
    )
    chunks = [
        evaluation.IndexedChunk(
            1, "fixture", "first.py", "function", "first", 1, 5, ""
        ),
        evaluation.IndexedChunk(
            2, "fixture", "second.py", "function", "second", 10, 20, ""
        ),
    ]

    assert evaluation.evidence_matches(case, chunks) == frozenset({"same-fact"})


def test_manifest_mismatch_fails_explicitly() -> None:
    chunk = evaluation.IndexedChunk(
        1, "fixture", "module.py", "module", None, 1, 2, "value = 1\n"
    )
    dataset = evaluation.EvaluationDataset(
        format_version=1,
        dataset_version="test-v1",
        dataset_status="test",
        corpus=evaluation.CorpusManifest(
            repository="fixture",
            expected_chunk_count=1,
            index_manifest_sha256="0" * 64,
            chunking_identifier=evaluation.CHUNKING_IDENTIFIER,
        ),
        cases=[
            evaluation.EvaluationCase(
                case_id="case",
                question="question",
                primary_category="test",
                repository="fixture",
                source_answerable=False,
                rationale="No answer expected.",
            )
        ],
    )

    with pytest.raises(evaluation.CorpusManifestMismatch, match="manifest mismatch"):
        evaluation.validate_corpus_manifest(dataset, "fixture", [chunk])


def test_blank_evaluation_scope_is_rejected_before_index_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        evaluation,
        "load_indexed_chunks",
        lambda *args: pytest.fail("blank scope must fail before querying the index"),
    )

    with pytest.raises(evaluation.EvaluationError, match="must not be blank"):
        evaluation.evaluate_dataset(  # type: ignore[arg-type]
            object(), SimpleNamespace(), "hash", "   "
        )


@pytest.mark.parametrize("mode", ["dense", "lexical", "hybrid", "rerank", "rerank_rrf_ce", "rerank_three_signal"])
def test_evaluator_reports_retrieved_evidence_excluded_by_real_context_selection(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    large = evaluation.IndexedChunk(
        1, "fixture", "large.py", "module", None, 1, 100, "marker " + "x" * 500
    )
    small = evaluation.IndexedChunk(
        2, "fixture", "small.py", "function", "small", 1, 2, "return 1"
    )
    manifest = evaluation.compute_index_manifest([large, small])
    case = evaluation.EvaluationCase(
        case_id="selection-loss",
        question="Where is marker?",
        primary_category="test",
        repository="fixture",
        source_answerable=True,
        required_evidence=[
            evaluation.EvidenceUnit(
                evidence_id="large-evidence",
                acceptable_spans=[
                    evaluation.EvidenceSpan(
                        file_path="large.py",
                        start_line=1,
                        end_line=100,
                        content_contains=["marker"],
                    )
                ],
            )
        ],
        rationale="The retrieved complete chunk exceeds the context budget.",
    )
    dataset = evaluation.EvaluationDataset(
        format_version=1,
        dataset_version="test-v1",
        dataset_status="test",
        corpus=evaluation.CorpusManifest(
            repository="fixture",
            expected_chunk_count=2,
            index_manifest_sha256=manifest,
            chunking_identifier=evaluation.CHUNKING_IDENTIFIER,
        ),
        cases=[case],
    )
    candidates = [
        RetrievedChunk(
            repository=item.repository,
            file_path=item.file_path,
            symbol_type=item.symbol_type,
            symbol_name=item.symbol_name,
            start_line=item.start_line,
            end_line=item.end_line,
            content=item.content,
            cosine_distance=rank / 10,
        )
        for rank, item in enumerate([large, small], start=1)
    ]
    monkeypatch.setattr(rag, "MAX_CONTEXT_CHARACTERS", 300)
    monkeypatch.setattr(evaluation, "MAX_CONTEXT_CHARACTERS", 300)
    monkeypatch.setattr(
        evaluation,
        "load_indexed_chunks",
        lambda db, repository: [large, small],
    )
    if mode == "dense":
        monkeypatch.setattr(evaluation, "search_code", lambda *args, **kwargs: candidates)
    else:
        monkeypatch.setattr(
            evaluation, "search_code",
            lambda *args, **kwargs: pytest.fail("non-dense mode must not use dense-only dispatch"),
        )
        if mode in {"rerank", "rerank_rrf_ce", "rerank_three_signal"}:
            def fake_rerank(*args: object, **kwargs: object) -> SimpleNamespace:
                if mode == "rerank":
                    assert kwargs["depth"] == 20
                else:
                    assert kwargs["mode"] == ("rrf_ce" if mode == "rerank_rrf_ce" else "three_signal")
                return SimpleNamespace(
                    candidates=candidates, union_size=2, scored_candidates=2,
                    pre_rerank_candidates=candidates,
                    ranked_candidates=candidates,
                    signal_ranked_candidates=candidates if mode != "rerank" else None,
                    truncated_inputs=0, maximum_input_tokens=12,
                    model_input_limit=512, device="cpu", model_revision="fixture",
                    model_parameters=22,
                )
            monkeypatch.setattr(
                evaluation,
                "rerank_hybrid" if mode == "rerank" else "rerank_hybrid_fused",
                fake_rerank,
            )
        else:
            def retrieve(*args: object, **kwargs: object) -> list[RetrievedChunk]:
                assert kwargs["mode"] == mode
                assert kwargs["repository"] == "fixture"
                return candidates
            monkeypatch.setattr(evaluation, "retrieve_code", retrieve)
    monkeypatch.setattr(
        evaluation,
        "collect_embedding_diagnostics",
        lambda chunks: (
            {},
            {"effective_input_limit": None, "resolved_model_revision": None},
        ),
    )
    monkeypatch.setattr(
        evaluation,
        "get_settings",
        lambda: SimpleNamespace(embedding_model_name="model"),
    )

    report = evaluation.evaluate_dataset(  # type: ignore[arg-type]
        object(), dataset, "dataset-hash", "fixture", mode=mode  # type: ignore[arg-type]
    )

    case_report = report["cases"][0]
    assert case_report["retrieved_evidence_at_depth"] == ["large-evidence"]
    assert case_report["context_evidence_ids"] == []
    assert case_report["selection_losses"] == ["large-evidence"]
    assert report["metrics"]["selection_loss_rate"]["value"] == 1
    if mode in {"rerank", "rerank_rrf_ce", "rerank_three_signal"}:
        assert case_report["candidate_union_size"] == 2
        assert case_report["reranked_candidates"] == 2
        assert "large-evidence" in case_report["rerank_evidence_ranks"]


def test_checked_in_dataset_is_versioned_balanced_and_not_claimed_human_reviewed() -> None:
    dataset, _ = evaluation.load_dataset(evaluate_retrieval.DEFAULT_DATASET)
    categories = Counter(case.primary_category for case in dataset.cases)

    assert len(dataset.cases) == 40
    assert set(categories.values()) == {4}
    assert len(categories) == 10
    assert "pending human review" in dataset.dataset_status.lower()
    assert "human-reviewed" not in dataset.dataset_status.lower()
    assert len(evaluation.compute_case_set_hash(dataset)) == 64


class ReadOnlySession:
    def __init__(self) -> None:
        self.statements: list[str] = []
        self.closed = False

    def __enter__(self) -> "ReadOnlySession":
        return self

    def __exit__(self, *args: object) -> None:
        self.closed = True

    def execute(self, statement: object) -> None:
        rendered = str(statement)
        assert rendered == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        self.statements.append(rendered)

    def add(self, value: object) -> None:
        pytest.fail("read-only evaluator must not add rows")

    def delete(self, value: object) -> None:
        pytest.fail("read-only evaluator must not delete rows")

    def commit(self) -> None:
        pytest.fail("read-only evaluator must not commit")


@pytest.mark.parametrize("mode", ["dense", "lexical", "hybrid", "rerank", "rerank_rrf_ce", "rerank_three_signal"])
def test_default_evaluator_sets_read_only_transaction_and_makes_no_provider_call(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mode: str,
) -> None:
    session = ReadOnlySession()
    dataset = SimpleNamespace()
    monkeypatch.setattr(evaluate_retrieval, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        evaluate_retrieval,
        "load_dataset",
        lambda path: (dataset, "hash"),
    )
    monkeypatch.setattr(
        evaluate_retrieval,
        "evaluate_dataset",
        lambda db, loaded, digest, repository, depth, **kwargs: (
            {"metrics": {}} if kwargs["mode"] == mode else pytest.fail("wrong mode")
        ),
    )
    monkeypatch.setattr(
        rag,
        "_create_client",
        lambda *args: pytest.fail("evaluation must not create an LLM client"),
    )

    report = evaluate_retrieval.run(tmp_path / "dataset.json", "fixture", 10, mode)

    assert report == {"metrics": {}}
    assert session.statements == ["SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"]
    assert session.closed is True
