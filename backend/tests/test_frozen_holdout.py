"""Audit-split, frozen-hash, and source-only checks; never score retrieval."""

import json
from collections import Counter

import pytest
from pydantic import ValidationError

from app.config import PROJECT_ROOT
from app.holdout import (
    FrozenDataset,
    canonical_hash,
    leakage_warnings,
    load_candidates,
    load_frozen,
    validate_sources,
)
from scripts.freeze_audited_holdout import (
    CANDIDATES,
    COVERAGE,
    COVERAGE_PATH,
    FROZEN_REVISION,
    PRIMARY_EDITED,
    PRIMARY_PATH,
    PRIMARY_UNCHANGED,
    REJECTED,
    _accepted_source_path,
    build_splits,
)
from scripts.prepare_holdout_review import DEV


def _short(case_id: str) -> str:
    return case_id.removeprefix("holdout-")


def test_audited_partition_counts_and_unmodified_candidate_provenance() -> None:
    candidate_pool = load_candidates(CANDIDATES)
    primary, challenge = build_splits()
    candidate_by_id = {case.case_id: case for case in candidate_pool.cases}
    assert len(candidate_pool.cases) == 50
    assert len(PRIMARY_UNCHANGED) == 19
    assert len(PRIMARY_EDITED) == 15
    assert len(COVERAGE) == 5
    assert len(REJECTED) == 11
    assert primary.case_count == 34
    assert primary.answerable_count == 29
    assert primary.unanswerable_count == 5
    assert primary.multi_evidence_count == 8
    assert challenge.case_count == 5
    assert challenge.answerable_count == 5
    assert {_short(case.case_id) for case in challenge.cases} == COVERAGE
    assert {_short(case.case_id) for case in primary.cases} == (
        PRIMARY_UNCHANGED | PRIMARY_EDITED
    )
    assert not REJECTED.intersection(
        _short(case.case_id) for dataset in (primary, challenge)
        for case in dataset.cases
    )
    for case in primary.cases:
        if _short(case.case_id) in PRIMARY_UNCHANGED:
            original = candidate_by_id[case.case_id]
            for field, value in original.model_dump(mode="json").items():
                assert case.model_dump(mode="json")[field] == value
    assert candidate_pool.source_revision == FROZEN_REVISION
    assert primary.candidate_pool_hash == canonical_hash(candidate_pool)
    assert challenge.candidate_pool_hash == canonical_hash(candidate_pool)


def test_primary_policy_and_exact_category_counts() -> None:
    primary, challenge = build_splits()
    assert primary.category_counts == {
        "semantic_conceptual": 4,
        "exact_identifier": 4,
        "configuration_constants": 4,
        "filename_path": 2,
        "decorator_api_route": 3,
        "architecture": 2,
        "cross_module_behavior": 3,
        "multiple_required_evidence": 4,
        "difficult_near_matches": 3,
        "unanswerable_insufficient_context": 5,
    }
    assert Counter(case.primary_category for case in challenge.cases) == {
        "semantic_conceptual": 1,
        "filename_path": 2,
        "cross_module_behavior": 2,
    }
    for case in primary.cases:
        assert all(
            _accepted_source_path(span.file_path)
            for evidence in case.required_evidence
            for span in evidence.acceptable_spans
        )
    for case in challenge.cases:
        assert any(
            not _accepted_source_path(span.file_path)
            for evidence in case.required_evidence
            for span in evidence.acceptable_spans
        )


def test_audited_evidence_units_and_alternatives_remain_distinct() -> None:
    primary, challenge = build_splits()
    cases = {_short(case.case_id): case for case in primary.cases}
    assert len(cases["semantic-03"].required_evidence) == 1
    assert len(cases["semantic-03"].required_evidence[0].acceptable_spans) == 2
    assert len(cases["semantic-04"].required_evidence[0].acceptable_spans) == 2
    assert len(cases["route-03"].required_evidence[0].acceptable_spans) == 2
    assert cases["architecture-03"].primary_category == "semantic_conceptual"
    assert len(cases["architecture-03"].required_evidence[0].acceptable_spans) == 2
    assert len(cases["cross-04"].required_evidence) == 3
    assert len(cases["multi-02"].required_evidence) == 3
    assert len(cases["multi-03"].required_evidence) == 2
    assert len(cases["multi-03"].required_evidence[1].acceptable_spans) == 2
    assert len(cases["multi-04"].required_evidence) == 3
    assert len(cases["near-02"].required_evidence) == 1
    assert all(len(unit.acceptable_spans) == 2
               for unit in cases["near-05"].required_evidence)
    assert not cases["unanswerable-04"].source_answerable
    assert cases["unanswerable-04"].required_evidence == []
    covered = {_short(case.case_id): case for case in challenge.cases}
    assert len(covered["cross-03"].required_evidence) == 3
    assert len(covered["cross-05"].required_evidence) == 2


def test_frozen_files_match_audit_and_validate_at_exact_revision() -> None:
    from app.evaluation import EvaluationDataset  # Schema check only: no scoring.

    generated = build_splits()
    checked_in = (load_frozen(PRIMARY_PATH), load_frozen(COVERAGE_PATH))
    for expected, actual in zip(generated, checked_in, strict=True):
        assert actual.model_dump(mode="json") == expected.model_dump(mode="json")
        assert actual.source_revision == FROZEN_REVISION
        assert actual.dataset_status == "Human-reviewed, independently audited, frozen."
        assert actual.corpus.expected_chunk_count == 212
        assert len(validate_sources(actual, PROJECT_ROOT)) == actual.case_count
        assert EvaluationDataset.model_validate(actual.model_dump(mode="json")).cases


def test_frozen_hashes_reject_case_or_count_tampering() -> None:
    original = load_frozen(PRIMARY_PATH).model_dump(mode="json")
    bad_count = json.loads(json.dumps(original))
    bad_count["case_count"] += 1
    with pytest.raises(ValidationError, match="case count"):
        FrozenDataset.model_validate(bad_count)
    bad_label = json.loads(json.dumps(original))
    bad_label["cases"][0]["question"] += " changed"
    with pytest.raises(ValidationError, match="case-set hash"):
        FrozenDataset.model_validate(bad_label)
    bad_corpus = json.loads(json.dumps(original))
    bad_corpus["corpus"]["source_revision"] = "0" * 40
    with pytest.raises(ValidationError, match="corpus and case identities"):
        FrozenDataset.model_validate(bad_corpus)


def test_no_materially_duplicated_dev_question_and_no_scoring_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import rag, reranking, retrieval

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Freezing must not call retrieval, reranking, or a provider")

    monkeypatch.setattr(retrieval, "search_code", forbidden)
    monkeypatch.setattr(retrieval, "search_lexical", forbidden)
    monkeypatch.setattr(reranking, "rerank_hybrid", forbidden)
    monkeypatch.setattr(rag, "answer_question", forbidden)
    monkeypatch.setattr(rag, "OpenAI", forbidden)
    primary, challenge = build_splits()
    dev_cases = json.loads(DEV.read_text(encoding="utf-8"))["cases"]
    warnings = leakage_warnings(primary.cases, dev_cases)
    assert not [
        warning for flags in warnings.values() for warning in flags
        if warning.startswith(("Exact DEV question", "Normalised DEV question",
                               "Possible paraphrase"))
    ]
    assert primary.case_count == 34
    assert challenge.case_count == 5
