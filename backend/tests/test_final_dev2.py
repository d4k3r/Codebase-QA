"""The audited DEV2 freeze is source-only; these tests never score retrieval."""

import hashlib
import re
from collections import Counter

import pytest
from pydantic import ValidationError

from app.config import PROJECT_ROOT
from app.dev2 import FinalDev2, load_dev2, load_final_dev2
from app.holdout import canonical_hash, validate_sources
from scripts.freeze_audited_dev2 import (
    ACCEPT, AUDIT, AUDIT_RAW_SHA256, CANDIDATES, CANDIDATE_HASH, FINAL, LONG,
    REJECT, SOURCE_REVISION, build_final, validate_accepted_chunk_containment,
)


def test_final_identity_counts_and_candidate_provenance() -> None:
    candidate = load_dev2(CANDIDATES)
    final = load_final_dev2(FINAL)
    assert canonical_hash(candidate) == CANDIDATE_HASH
    assert hashlib.sha256(CANDIDATES.read_bytes()).hexdigest() == (
        "14a0279b0cd149ddb4874e2609489fdd855fd2c1f244b2edd6cbe7888dc367a2"
    )
    assert hashlib.sha256(AUDIT.read_bytes()).hexdigest() == AUDIT_RAW_SHA256
    assert final.candidate_pool_hash == CANDIDATE_HASH
    assert final.source_revision == SOURCE_REVISION
    assert final.dataset_version == "codebase-qa-v2-dev2-v1.0.0"
    assert "NOT an independent generalisation benchmark" in final.dataset_status
    assert (final.case_count, final.answerable_count, final.unanswerable_count) == (38, 36, 2)
    assert (final.multi_evidence_count, final.long_chunk_count) == (16, 16)
    assert (final.required_evidence_unit_count, final.acceptable_span_count) == (60, 70)
    assert final.category_counts == {
        "semantic_conceptual": 15, "architecture": 3,
        "cross_module_behavior": 4, "configuration_constants": 6,
        "difficult_near_matches": 4, "multiple_required_evidence": 3,
        "exact_identifier": 1, "unanswerable_insufficient_context": 2,
    }
    assert final.dev1_overlap_counts == {"NONE": 18, "LOW": 20}
    assert final.holdout_overlap_counts == {"NONE": 23, "LOW": 15}
    assert not REJECT & {case.case_id for case in final.cases}
    assert not any("MATERIAL" in (case.dev1_overlap, case.holdout_overlap)
                   for case in final.cases)
    originals = {case.case_id: case for case in candidate.cases}
    for case in final.cases:
        if case.case_id in ACCEPT:
            assert case.model_dump(mode="json", exclude={"repository", "rationale"}) == (
                originals[case.case_id].model_dump(mode="json")
            )


def test_final_tag_and_long_position_annotations() -> None:
    final = load_final_dev2(FINAL)
    assert {case.case_id for case in final.cases
            if "long_chunk" in case.secondary_tags} == LONG
    assert {key: final.tag_counts[key] for key in (
        "multi_evidence", "long_chunk", "exact_token", "distractor",
        "failure_boundary", "later_source", "provider_config", "repository_scope",
        "mixed_semantic_exact", "context_selection", "evaluation_safety",
        "ordinary_developer_question", "reproducibility", "unanswerable",
    )} == {
        "multi_evidence": 16, "long_chunk": 16, "exact_token": 5,
        "distractor": 4, "failure_boundary": 4, "later_source": 3,
        "provider_config": 3, "repository_scope": 3, "mixed_semantic_exact": 2,
        "context_selection": 2, "evaluation_safety": 2,
        "ordinary_developer_question": 2, "reproducibility": 2,
        "unanswerable": 2,
    }
    assert sum(bool(case.oversized_evidence_ids) for case in final.cases) == 25
    assert sum(len(case.oversized_evidence_ids) for case in final.cases) == 32
    assert set(final.tag_counts) >= {"long_chunk", "multi_evidence"}
    assert all(("multi_evidence" in case.secondary_tags) ==
               (len(case.required_evidence) >= 2) for case in final.cases)
    assert all(case.one_unit_sufficient is False and case.multi_evidence_reason
               for case in final.cases if len(case.required_evidence) >= 2)
    assert all(not case.required_evidence and case.missing_reason
               for case in final.cases if not case.source_answerable)
    assert all(set(case.oversized_evidence_ids) <= {
        unit.evidence_id for unit in case.required_evidence
    } for case in final.cases)


def test_audited_alternatives_and_complementary_units() -> None:
    by_id = {case.case_id: case for case in load_final_dev2(FINAL).cases}
    assert len(by_id["dev2-multi-04"].required_evidence) == 2
    assert len(by_id["dev2-multi-04"].required_evidence[1].acceptable_spans) == 2
    assert [unit.evidence_id for unit in by_id["dev2-architecture-05"].required_evidence] == [
        "env-path-definition", "settings-env-path",
    ]
    assert len(by_id["dev2-architecture-05"].required_evidence[1].acceptable_spans) == 2
    assert len(by_id["dev2-multi-07"].required_evidence) == 4
    assert len(by_id["dev2-near-03"].required_evidence) == 4
    assert len(by_id["dev2-mixed-03"].required_evidence) == 5
    assert [unit.evidence_id for unit in by_id["dev2-multi-02"].required_evidence] == [
        "index-count-semantics",
    ]
    assert "No." not in by_id["dev2-near-03"].expected_answer
    assert by_id["dev2-near-03"].expected_answer.startswith("Yes.")


def test_audit_decision_table_matches_final_categories_and_overlaps() -> None:
    category = {
        "S": "semantic_conceptual", "A": "architecture",
        "X": "cross_module_behavior", "C": "configuration_constants",
        "M": "multiple_required_evidence", "N": "difficult_near_matches",
        "I": "exact_identifier", "U": "unanswerable_insufficient_context",
    }
    overlap = {"N": "NONE", "L": "LOW", "M": "MATERIAL"}
    table = {}
    for line in AUDIT.read_text(encoding="utf-8").split("**Exact proposed corrections**")[0].splitlines():
        if re.match(r"^\| (multi|architecture|semantic|exact|near|long|mixed|ordinary|unanswerable)-\d+ \|", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            table[f"dev2-{cells[0]}"] = cells
    assert len(table) == 45
    final = load_final_dev2(FINAL)
    for case in final.cases:
        cells = table[case.case_id]
        assert cells[2] == "**EDIT**" or cells[2] == "**ACCEPT**"
        assert case.primary_category == category[cells[1].split("→")[-1]]
        assert case.dev1_overlap == overlap[cells[5]]
        assert case.holdout_overlap == overlap[cells[6]]


def test_frozen_sources_and_accepted_chunks_validate_without_retrieval() -> None:
    final = load_final_dev2(FINAL)
    excerpts = validate_sources(final, PROJECT_ROOT)
    assert len(excerpts) == 38
    assert sum(map(len, excerpts.values())) == 70
    validate_accepted_chunk_containment(final.cases)
    assert len({span.file_path for case in final.cases for unit in case.required_evidence
                for span in unit.acceptable_spans}) == 24


def test_self_recorded_hashes_and_counts_reject_tampering() -> None:
    final = load_final_dev2(FINAL)
    altered = final.model_dump(mode="json")
    altered["cases"][0]["question"] += " changed"
    with pytest.raises(ValidationError, match="case-set hash"):
        FinalDev2.model_validate(altered)
    altered = final.model_dump(mode="json")
    altered["dev1_overlap_counts"] = {"NONE": 19, "LOW": 19}
    with pytest.raises(ValidationError, match="dev1_overlap_counts"):
        FinalDev2.model_validate(altered)
    altered = final.model_dump(mode="json")
    altered["cases"][0]["dev1_overlap"] = "MATERIAL"
    with pytest.raises(ValidationError, match="MATERIAL overlap"):
        FinalDev2.model_validate(altered)


def test_checked_in_final_rebuilds_without_scoring_or_provider_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import embeddings, rag, reranking, retrieval

    def forbidden(*args: object, **kwargs: object) -> None:
        pytest.fail("DEV2 finalisation must not invoke retrieval or provider")

    monkeypatch.setattr(retrieval, "search_code", forbidden)
    monkeypatch.setattr(retrieval, "search_lexical", forbidden)
    monkeypatch.setattr(reranking, "rerank_hybrid", forbidden)
    monkeypatch.setattr(embeddings, "embed_texts", forbidden)
    monkeypatch.setattr(rag, "answer_question", forbidden)
    monkeypatch.setattr(rag, "OpenAI", forbidden)
    rebuilt = build_final()
    checked = load_final_dev2(FINAL)
    assert rebuilt.dataset_hash == checked.dataset_hash
    assert rebuilt.case_set_hash == checked.case_set_hash


def test_final_can_be_loaded_by_existing_evaluation_schema_without_scoring() -> None:
    from app.evaluation import EvaluationDataset

    final = load_final_dev2(FINAL)
    evaluation_shape = EvaluationDataset.model_validate(final.model_dump(mode="json"))
    assert len(evaluation_shape.cases) == 38
    assert evaluation_shape.corpus.expected_chunk_count == 212
    assert Counter(case.repository for case in evaluation_shape.cases) == {
        "codebase-qa-v2": 38,
    }
