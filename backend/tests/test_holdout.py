"""Source-only holdout preparation; no retrieval or model evaluation."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import PROJECT_ROOT
from app.holdout import (
    Candidate,
    Evidence,
    HoldoutCandidates,
    Span,
    canonical_hash,
    leakage_warnings,
    load_candidates,
    render_review,
    validate_sources,
)
from scripts.prepare_holdout_review import CANDIDATES, DEV, prepare


def test_schema_enforces_answerability_and_unique_facts() -> None:
    span = Span(file_path="backend/app/config.py", start_line=11, end_line=12,
                content_contains=["ENV_FILE"])
    evidence = Evidence(evidence_id="one", why_required="A fact", acceptable_spans=[span])
    with pytest.raises(ValidationError, match="Answerable cases need evidence"):
        Candidate(case_id="bad", question="Q?", primary_category="semantic_conceptual",
                  source_answerable=True, expected_answer="A")
    with pytest.raises(ValidationError, match="unanswerable cases need none"):
        Candidate(case_id="bad", question="Q?", primary_category="semantic_conceptual",
                  source_answerable=False, expected_answer="A",
                  missing_reason="Absent", required_evidence=[evidence])
    with pytest.raises(ValidationError, match="Duplicate evidence spans"):
        Candidate(case_id="bad", question="Q?", primary_category="semantic_conceptual",
                  source_answerable=True, expected_answer="A",
                  required_evidence=[evidence, evidence.model_copy(update={"evidence_id": "two"})])
    with pytest.raises(ValidationError, match="safe repository-relative"):
        Span(file_path="../.env", start_line=1, end_line=1, content_contains=["secret"])
    with pytest.raises(ValidationError, match="Evidence lines are reversed"):
        Span(file_path="a.py", start_line=3, end_line=2, content_contains=["x"])
    with pytest.raises(ValidationError, match="Candidate IDs must be unique"):
        d = load_candidates(CANDIDATES)
        HoldoutCandidates.model_validate(d.model_dump() | {"cases": [d.cases[0], d.cases[0]]})
    with pytest.raises(ValidationError, match="format_version"):
        HoldoutCandidates.model_validate(d.model_dump() | {"format_version": 2})
    with pytest.raises(ValidationError, match="dataset_status"):
        HoldoutCandidates.model_validate(d.model_dump() | {"dataset_status": "human-reviewed"})


def test_alternative_spans_and_exact_source_anchors() -> None:
    dataset = load_candidates(CANDIDATES)
    # The two request models are genuine alternatives for the same validation fact.
    case = next(c for c in dataset.cases if c.case_id == "holdout-route-04")
    assert len(case.required_evidence[0].acceptable_spans) == 2
    assert len(validate_sources(dataset.model_copy(update={"cases": [case]}), PROJECT_ROOT)[case.case_id]) == 2
    bad_span = case.required_evidence[0].acceptable_spans[0].model_copy(
        update={"content_contains": ["not-an-actual-source-anchor"]}
    )
    bad_evidence = case.required_evidence[0].model_copy(update={"acceptable_spans": [bad_span]})
    bad_case = case.model_copy(update={"required_evidence": [bad_evidence]})
    with pytest.raises(ValueError, match="Missing source anchor"):
        validate_sources(dataset.model_copy(update={"cases": [bad_case]}), PROJECT_ROOT)
    outside = bad_span.model_copy(update={"file_path": "missing.py"})
    outside_case = case.model_copy(update={"required_evidence": [
        bad_evidence.model_copy(update={"acceptable_spans": [outside]})
    ]})
    with pytest.raises(ValueError, match="Source file missing"):
        validate_sources(dataset.model_copy(update={"cases": [outside_case]}), PROJECT_ROOT)


def test_dev_leakage_flags_exact_normalised_paraphrase_and_span_overlap() -> None:
    dataset = load_candidates(CANDIDATES)
    case = dataset.cases[0]
    span = case.required_evidence[0].acceptable_spans[0]
    dev = [
        {"case_id": "exact", "question": case.question, "required_evidence": []},
        {"case_id": "normal", "question": case.question.upper() + "!", "required_evidence": []},
        {"case_id": "similar", "question": case.question + " in this project?",
         "required_evidence": []},
        {"case_id": "span", "question": "Unrelated words", "required_evidence": [
            {"acceptable_spans": [{"file_path": span.file_path, "start_line": span.start_line,
                                    "end_line": span.end_line,
                                    "content_contains": span.content_contains}]}
        ]},
    ]
    warnings = leakage_warnings([case], dev)[case.case_id]
    assert any("Exact DEV question" in warning for warning in warnings)
    assert any("Normalised DEV question" in warning for warning in warnings)
    assert any("Possible paraphrase" in warning for warning in warnings)
    assert any("DEV span overlap" in warning for warning in warnings)
    assert any("DEV source-anchor overlap" in warning for warning in warnings)


def test_canonical_hash_is_format_independent_and_review_is_actionable(tmp_path: Path) -> None:
    dataset = load_candidates(CANDIDATES)
    reordered = tmp_path / "candidate.json"
    reordered.write_text(json.dumps(dataset.model_dump(mode="json"), sort_keys=True),
                         encoding="utf-8")
    assert canonical_hash(load_candidates(reordered)) == canonical_hash(dataset)
    markdown, warnings = prepare(CANDIDATES, DEV, PROJECT_ROOT)
    assert "Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT" in markdown
    assert "holdout-unanswerable-01" in markdown
    assert "Missing source anchor" not in markdown
    assert any(warnings.values())
    assert markdown == render_review(
        dataset, validate_sources(dataset, PROJECT_ROOT), warnings
    )


def test_preparation_does_not_call_retrieval_or_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import rag, reranking, retrieval

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("Holdout preparation must not call retrieval or provider APIs")

    monkeypatch.setattr(retrieval, "search_code", forbidden)
    monkeypatch.setattr(retrieval, "search_lexical", forbidden)
    monkeypatch.setattr(reranking, "rerank_hybrid", forbidden)
    monkeypatch.setattr(rag, "answer_question", forbidden)
    monkeypatch.setattr(rag, "OpenAI", forbidden)
    markdown, _ = prepare(CANDIDATES, DEV, PROJECT_ROOT)
    assert "Machine-prepared" in markdown


def test_checked_in_holdout_candidate_identity_and_source_validation() -> None:
    dataset = load_candidates(CANDIDATES)
    assert len(dataset.cases) == 50
    assert dataset.source_revision == "7a3b7b05087793975ae0a84d85e7d691d9f3352e"
    assert dataset.dataset_status.startswith("Machine-prepared")
    assert sum(c.source_answerable for c in dataset.cases) == 45
    excerpts = validate_sources(dataset, PROJECT_ROOT)
    assert len(excerpts) == 50
    for case in dataset.cases:
        spans = [span for evidence in case.required_evidence
                 for span in evidence.acceptable_spans]
        for span, excerpt in zip(spans, excerpts[case.case_id], strict=True):
            assert all(anchor in excerpt for anchor in span.content_contains)
    assert json.loads(DEV.read_text(encoding="utf-8"))["dataset_version"] == "codebase-qa-v2-v1.1.0"


def test_changed_dev_file_is_rejected_before_review(tmp_path: Path) -> None:
    changed = tmp_path / "dev.json"
    changed.write_text(DEV.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="DEV dataset changed"):
        prepare(CANDIDATES, changed, PROJECT_ROOT)
