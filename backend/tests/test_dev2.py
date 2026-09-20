"""DEV2 preparation tests: source evidence and labels, never retrieval scores."""

import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import PROJECT_ROOT
from app.dev2 import (
    Dev2Candidate,
    Dev2Candidates,
    load_dev2,
    overlap_diagnostics,
    render_review,
    validate_overlap,
    validate_oversized,
)
from app.holdout import canonical_hash, load_frozen, validate_sources
from scripts.prepare_dev2_review import CANDIDATES, DEV1, HOLDOUT, prepare


def _references() -> tuple[list[dict], list[dict]]:
    dev1 = json.loads(DEV1.read_text(encoding="utf-8"))["cases"]
    holdout = [
        case.model_dump(mode="json") for case in load_frozen(HOLDOUT).cases
    ]
    return dev1, holdout


def test_checked_in_candidate_identity_and_source_anchors(tmp_path: Path) -> None:
    dataset = load_dev2(CANDIDATES)
    assert dataset.source_revision == "7a3b7b05087793975ae0a84d85e7d691d9f3352e"
    assert len(dataset.cases) == 45
    assert sum(case.source_answerable for case in dataset.cases) == 43
    assert sum(len(case.required_evidence) >= 2 for case in dataset.cases) == 16
    assert sum(bool(case.oversized_evidence_ids) for case in dataset.cases) >= 5
    assert dataset.dataset_status.startswith("Machine-prepared DEV2 candidate")
    excerpts = validate_sources(dataset, PROJECT_ROOT)
    assert len(excerpts) == 45
    assert all(len(excerpts[case.case_id]) == sum(
        len(unit.acceptable_spans) for unit in case.required_evidence
    ) for case in dataset.cases)
    reordered = tmp_path / "reordered.json"
    reordered.write_text(
        json.dumps(dataset.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    assert canonical_hash(dataset) == canonical_hash(load_dev2(reordered))
    with pytest.raises(ValidationError, match="dataset_version"):
        Dev2Candidates.model_validate(
            dataset.model_dump(mode="json") | {"dataset_version": "wrong-version"}
        )


def test_schema_rejects_bad_multi_and_unanswerable_metadata() -> None:
    dataset = load_dev2(CANDIDATES)
    multi = dataset.cases[0].model_dump(mode="json")
    with pytest.raises(ValidationError, match="one unit is insufficient"):
        Dev2Candidate.model_validate(multi | {"one_unit_sufficient": True})
    with pytest.raises(ValidationError, match="Oversized evidence IDs must name"):
        Dev2Candidate.model_validate(multi | {"oversized_evidence_ids": ["not-gold"]})
    with pytest.raises(ValidationError, match="Multi-evidence rationale"):
        Dev2Candidate.model_validate(multi | {"multi_evidence_reason": None})
    negative = next(case for case in dataset.cases if not case.source_answerable)
    with pytest.raises(ValidationError, match="Unanswerable cases need"):
        Dev2Candidate.model_validate(
            negative.model_dump(mode="json") | {"missing_reason": None}
        )
    with pytest.raises(ValidationError, match="DEV2 candidate IDs must be unique"):
        Dev2Candidates.model_validate(
            dataset.model_dump(mode="json") | {"cases": [multi, multi]}
        )


def test_source_validation_checks_alternatives_and_rejects_bad_anchor() -> None:
    dataset = load_dev2(CANDIDATES)
    case = next(case for case in dataset.cases if case.case_id == "dev2-semantic-01")
    assert len(case.required_evidence[0].acceptable_spans) == 2
    excerpts = validate_sources(dataset, PROJECT_ROOT)[case.case_id]
    assert len(excerpts) == 2
    bad = dataset.model_dump(mode="json")
    target = next(item for item in bad["cases"] if item["case_id"] == case.case_id)
    target["required_evidence"][0]["acceptable_spans"][1]["content_contains"] = [
        "not-in-frozen-source"
    ]
    with pytest.raises(ValueError, match="Missing source anchor"):
        validate_sources(Dev2Candidates.model_validate(bad), PROJECT_ROOT)


def test_dev1_holdout_overlap_and_candidate_duplicate_detection() -> None:
    dataset = load_dev2(CANDIDATES)
    dev1, holdout = _references()
    diagnostics = validate_overlap(dataset, dev1, holdout)
    assert Counter(value[0] for value in diagnostics["DEV1"].values()) == {
        "LOW": 32, "NONE": 13,
    }
    assert Counter(value[0] for value in diagnostics["HOLDOUT"].values()) == {
        "LOW": 21, "NONE": 24,
    }
    exact = dataset.cases[0].model_copy(update={"question": dev1[0]["question"]})
    assert overlap_diagnostics([exact], dev1)[exact.case_id][0] == "MATERIAL"
    normalised = dataset.cases[0].model_copy(
        update={"question": holdout[0]["question"].upper() + "!"}
    )
    assert overlap_diagnostics([normalised], holdout)[normalised.case_id][0] == "MATERIAL"
    duplicate = dataset.cases[0].model_copy(update={"case_id": "duplicate-intent"})
    with pytest.raises(ValueError, match="duplicate DEV2 candidate intent"):
        validate_overlap(
            dataset.model_copy(update={"cases": [dataset.cases[0], duplicate]}),
            dev1, holdout,
        )


def test_oversized_annotation_uses_token_count_of_frozen_symbol() -> None:
    dataset = load_dev2(CANDIDATES)
    case = next(case for case in dataset.cases if case.case_id == "dev2-long-01")
    one = dataset.model_copy(update={"cases": [case]})
    diagnostic = validate_oversized(one, PROJECT_ROOT, lambda source: 300)
    assert "symbol-endline-guard" in diagnostic[case.case_id]
    with pytest.raises(ValueError, match="annotation does not match"):
        validate_oversized(one, PROJECT_ROOT, lambda source: 100)


def test_review_renders_every_case_and_separate_overlap_warnings() -> None:
    dataset = load_dev2(CANDIDATES)
    dev1, holdout = _references()
    overlaps = validate_overlap(dataset, dev1, holdout)
    excerpts = validate_sources(dataset, PROJECT_ROOT)
    oversized = {case.case_id: {
        evidence_id: ["tokenizer-verified diagnostic"]
        for evidence_id in case.oversized_evidence_ids
    } for case in dataset.cases}
    review = render_review(dataset, excerpts, overlaps, oversized)
    assert review.count("Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT") == 45
    assert "DEV1 overlap: **LOW**" in review
    assert "HOLDOUT overlap: **LOW**" in review
    assert "One unit alone sufficient: no" in review
    assert "not frozen or scored" in review
    assert "an unmarked config/companion span is not proven short" in review
    assert "dev2-unanswerable-02" in review


def test_preparation_never_calls_retrieval_or_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app import dev2
    from app.services import embeddings, rag, reranking, retrieval

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("DEV2 source preparation must not invoke retrieval or provider")

    monkeypatch.setattr(retrieval, "search_code", forbidden)
    monkeypatch.setattr(retrieval, "search_lexical", forbidden)
    monkeypatch.setattr(reranking, "rerank_hybrid", forbidden)
    monkeypatch.setattr(embeddings, "embed_texts", forbidden)
    monkeypatch.setattr(rag, "answer_question", forbidden)
    monkeypatch.setattr(rag, "OpenAI", forbidden)
    monkeypatch.setattr(dev2, "validate_oversized", lambda *args: {
        case.case_id: {} for case in load_dev2(CANDIDATES).cases
    })
    review, _ = prepare(token_count=lambda source: 1)
    assert "dev2-multi-01" in review


def test_reference_identity_change_aborts_preparation(tmp_path: Path) -> None:
    altered = tmp_path / "dev1.json"
    altered.write_text(DEV1.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="DEV1 changed"):
        prepare(dev1_path=altered, token_count=lambda source: 1)
