"""Read-only, source-grounded retrieval and context-selection evaluation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Literal, Sequence

from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, get_settings
from app.models import CodeChunk
from app.services.chunker import CHUNKING_IDENTIFIER
from app.services.embeddings import EMBEDDING_DIMENSION, get_embedding_model
from app.services.rag import MAX_CONTEXT_CHARACTERS, build_context
from app.services.reranking import (
    RERANKER_MODEL,
    RERANKER_REVISION,
    RERANK_DEPTHS,
    rerank_hybrid,
    rerank_hybrid_fused,
)
from app.services.retrieval import (
    MAX_TOP_K,
    RRF_BRANCH_DEPTH,
    RRF_CONSTANT,
    RetrievedChunk,
    retrieve_code,
    search_code,
)


METRIC_DEPTHS = (1, 3, 5, 10)
DATASET_FORMAT_VERSION = 1
EvaluationMode = Literal[
    "dense", "lexical", "hybrid", "rerank", "rerank_rrf_ce", "rerank_three_signal"
]


class EvaluationError(RuntimeError):
    """Raised when evaluation cannot run reproducibly."""


class CorpusManifestMismatch(EvaluationError):
    """Raised when the prepared index differs from the dataset corpus manifest."""


class EvidenceSpan(BaseModel):
    file_path: str = Field(min_length=1)
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    symbol_type: str | None = None
    symbol_name: str | None = None
    content_contains: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_lines(self) -> "EvidenceSpan":
        if self.end_line < self.start_line:
            raise ValueError("Evidence end_line must be >= start_line")
        return self


class EvidenceUnit(BaseModel):
    evidence_id: str = Field(min_length=1)
    acceptable_spans: list[EvidenceSpan] = Field(min_length=1)


class EvaluationCase(BaseModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    primary_category: str = Field(min_length=1)
    secondary_tags: list[str] = Field(default_factory=list)
    repository: str = Field(min_length=1)
    source_answerable: bool
    required_evidence: list[EvidenceUnit] = Field(default_factory=list)
    distractors: list[EvidenceSpan] = Field(default_factory=list)
    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> "EvaluationCase":
        if self.source_answerable and not self.required_evidence:
            raise ValueError("Answerable cases require at least one evidence unit")
        if not self.source_answerable and self.required_evidence:
            raise ValueError("Unanswerable cases must not define required evidence")
        evidence_ids = [unit.evidence_id for unit in self.required_evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("Evidence IDs must be unique within a case")
        return self


class CorpusManifest(BaseModel):
    repository: str = Field(min_length=1)
    expected_chunk_count: int = Field(ge=1)
    index_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_revision: str | None = None
    chunking_identifier: str = Field(min_length=1)


class EvaluationDataset(BaseModel):
    format_version: Literal[1]
    dataset_version: str = Field(min_length=1)
    dataset_status: str = Field(min_length=1)
    corpus: CorpusManifest
    cases: list[EvaluationCase] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_cases(self) -> "EvaluationDataset":
        case_ids = [case.case_id for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Evaluation case IDs must be unique")
        wrong_repository = [
            case.case_id
            for case in self.cases
            if case.repository != self.corpus.repository
        ]
        if wrong_repository:
            raise ValueError(
                "Cases use a repository other than the corpus repository: "
                + ", ".join(wrong_repository)
            )
        return self


@dataclass(frozen=True, slots=True)
class IndexedChunk:
    row_id: int
    repository: str
    file_path: str
    symbol_type: str
    symbol_name: str | None
    start_line: int
    end_line: int
    content: str


@dataclass(frozen=True, slots=True)
class CaseOutcome:
    case_id: str
    source_answerable: bool
    required_evidence_ids: frozenset[str]
    indexed_evidence_ids: frozenset[str]
    candidate_evidence_by_rank: tuple[frozenset[str], ...]
    context_evidence_ids: frozenset[str]

    def retrieved_at(self, depth: int) -> frozenset[str]:
        recovered: set[str] = set()
        for matches in self.candidate_evidence_by_rank[:depth]:
            recovered.update(matches)
        return frozenset(recovered)


def load_dataset(path: Path) -> tuple[EvaluationDataset, str]:
    """Load and hash one versioned JSON dataset."""

    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"Invalid evaluation dataset JSON: {exc}") from exc
    dataset = EvaluationDataset.model_validate(payload)
    canonical = json.dumps(
        dataset.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return dataset, hashlib.sha256(canonical).hexdigest()


def compute_case_set_hash(dataset: EvaluationDataset) -> str:
    """Hash questions and gold labels independently from the corpus manifest."""

    canonical = json.dumps(
        [case.model_dump(mode="json") for case in dataset.cases],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _source_identifier(chunk: IndexedChunk | RetrievedChunk) -> str:
    symbol = chunk.symbol_name or "<module>"
    return (
        f"{chunk.repository}:{chunk.file_path}:{chunk.symbol_type}:{symbol}:"
        f"{chunk.start_line}-{chunk.end_line}"
    )


def load_indexed_chunks(db: Session, repository: str) -> list[IndexedChunk]:
    """Load one repository's index using stable source ordering."""

    statement = (
        select(CodeChunk)
        .where(CodeChunk.repository == repository)
        .order_by(
            CodeChunk.file_path,
            CodeChunk.start_line,
            CodeChunk.end_line,
            CodeChunk.symbol_type,
            CodeChunk.symbol_name,
            CodeChunk.id,
        )
    )
    chunks = db.scalars(statement).all()
    return [
        IndexedChunk(
            row_id=chunk.id,
            repository=chunk.repository,
            file_path=chunk.file_path,
            symbol_type=chunk.symbol_type,
            symbol_name=chunk.symbol_name,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
            content=chunk.content,
        )
        for chunk in chunks
    ]


def compute_index_manifest(chunks: Sequence[IndexedChunk]) -> str:
    """Hash stable indexed source metadata/content, excluding row IDs and vectors."""

    records = [
        {
            "repository": chunk.repository,
            "file_path": chunk.file_path,
            "symbol_type": chunk.symbol_type,
            "symbol_name": chunk.symbol_name,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "content": chunk.content,
        }
        for chunk in chunks
    ]
    canonical = json.dumps(records, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(canonical).hexdigest()


def validate_corpus_manifest(
    dataset: EvaluationDataset,
    repository: str,
    chunks: Sequence[IndexedChunk],
) -> str:
    """Fail if repository identity, chunk count, or stable index hash differs."""

    scope = repository.strip()
    if not scope:
        raise EvaluationError("Repository scope must not be blank")
    if scope != dataset.corpus.repository:
        raise CorpusManifestMismatch(
            f"Dataset expects repository {dataset.corpus.repository!r}; got {scope!r}"
        )
    if not chunks:
        raise CorpusManifestMismatch(
            f"Prepared corpus {scope!r} is missing from the index"
        )
    if len(chunks) != dataset.corpus.expected_chunk_count:
        raise CorpusManifestMismatch(
            "Prepared corpus chunk count mismatch: "
            f"expected {dataset.corpus.expected_chunk_count}, got {len(chunks)}"
        )
    actual_hash = compute_index_manifest(chunks)
    if actual_hash != dataset.corpus.index_manifest_sha256:
        raise CorpusManifestMismatch(
            "Prepared corpus manifest mismatch: "
            f"expected {dataset.corpus.index_manifest_sha256}, got {actual_hash}"
        )
    if dataset.corpus.chunking_identifier != CHUNKING_IDENTIFIER:
        raise CorpusManifestMismatch(
            "Chunking identifier mismatch: "
            f"dataset={dataset.corpus.chunking_identifier}, "
            f"application={CHUNKING_IDENTIFIER}"
        )
    return actual_hash


def _span_matches_chunk(
    span: EvidenceSpan,
    chunk: IndexedChunk | RetrievedChunk,
) -> bool:
    if chunk.file_path != span.file_path:
        return False
    if span.symbol_type is not None and chunk.symbol_type != span.symbol_type:
        return False
    if span.symbol_name is not None and chunk.symbol_name != span.symbol_name:
        return False
    if chunk.start_line > span.end_line or chunk.end_line < span.start_line:
        return False
    return all(text in chunk.content for text in span.content_contains)


def evidence_matches(
    case: EvaluationCase,
    chunks: Sequence[IndexedChunk | RetrievedChunk],
) -> frozenset[str]:
    """Return unique evidence facts represented by any acceptable span."""

    matched: set[str] = set()
    for unit in case.required_evidence:
        if any(
            _span_matches_chunk(span, chunk)
            for span in unit.acceptable_spans
            for chunk in chunks
        ):
            matched.add(unit.evidence_id)
    return frozenset(matched)


def _candidate_match_sets(
    case: EvaluationCase,
    candidates: Sequence[RetrievedChunk],
) -> tuple[frozenset[str], ...]:
    return tuple(evidence_matches(case, [candidate]) for candidate in candidates)


def _ratio(numerator: float, denominator: int) -> dict[str, float | int | None]:
    value = numerator / denominator if denominator else None
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": value,
        "percentage": value * 100 if value is not None else None,
    }


def calculate_metrics(outcomes: Sequence[CaseOutcome]) -> dict[str, object]:
    """Calculate retrieval, coverage, and production-context metrics."""

    answerable = [outcome for outcome in outcomes if outcome.source_answerable]
    unanswerable = [outcome for outcome in outcomes if not outcome.source_answerable]
    metrics: dict[str, object] = {
        "source_answerability": _ratio(len(answerable), len(outcomes)),
        "unanswerable_cases": {
            "count": len(unanswerable),
            "total_cases": len(outcomes),
            "case_ids": [outcome.case_id for outcome in unanswerable],
        },
    }

    total_evidence = sum(len(outcome.required_evidence_ids) for outcome in answerable)
    indexed_evidence = sum(len(outcome.indexed_evidence_ids) for outcome in answerable)
    metrics["index_evidence_coverage"] = _ratio(indexed_evidence, total_evidence)
    metrics["all_evidence_indexed"] = _ratio(
        sum(
            outcome.indexed_evidence_ids == outcome.required_evidence_ids
            for outcome in answerable
        ),
        len(answerable),
    )

    for depth in METRIC_DEPTHS:
        recovered_by_case = [outcome.retrieved_at(depth) for outcome in answerable]
        recovered_units = sum(len(recovered) for recovered in recovered_by_case)
        macro_sum = sum(
            len(recovered) / len(outcome.required_evidence_ids)
            for outcome, recovered in zip(answerable, recovered_by_case, strict=True)
        )
        metrics[f"hit_at_{depth}"] = _ratio(
            sum(bool(recovered) for recovered in recovered_by_case), len(answerable)
        )
        metrics[f"macro_evidence_recall_at_{depth}"] = _ratio(
            macro_sum, len(answerable)
        )
        metrics[f"micro_evidence_recall_at_{depth}"] = _ratio(
            recovered_units, total_evidence
        )
        metrics[f"all_evidence_at_{depth}"] = _ratio(
            sum(
                recovered == outcome.required_evidence_ids
                for outcome, recovered in zip(
                    answerable, recovered_by_case, strict=True
                )
            ),
            len(answerable),
        )

    reciprocal_rank_sum = 0.0
    for outcome in answerable:
        first_rank = next(
            (
                rank
                for rank, matches in enumerate(
                    outcome.candidate_evidence_by_rank[:10], start=1
                )
                if matches
            ),
            None,
        )
        if first_rank is not None:
            reciprocal_rank_sum += 1 / first_rank
    metrics["mrr_at_10"] = _ratio(reciprocal_rank_sum, len(answerable))

    context_units = sum(len(outcome.context_evidence_ids) for outcome in answerable)
    metrics["final_context_evidence_recall"] = _ratio(
        context_units, total_evidence
    )
    context_sufficiency = _ratio(
        sum(
            outcome.context_evidence_ids == outcome.required_evidence_ids
            for outcome in answerable
        ),
        len(answerable),
    )
    metrics["all_evidence_in_context"] = context_sufficiency
    metrics["context_sufficiency"] = context_sufficiency
    retrieved_units = 0
    selection_losses = 0
    for outcome in answerable:
        retrieved = outcome.retrieved_at(len(outcome.candidate_evidence_by_rank))
        retrieved_units += len(retrieved)
        selection_losses += len(retrieved - outcome.context_evidence_ids)
    metrics["selection_loss_rate"] = _ratio(selection_losses, retrieved_units)
    return metrics


def _package_versions() -> dict[str, str | None]:
    packages = (
        "fastapi",
        "pgvector",
        "psycopg",
        "sentence-transformers",
        "sqlalchemy",
        "torch",
        "transformers",
    )
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return versions


def _git_revision() -> tuple[str | None, bool | None]:
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return revision, dirty
    except (OSError, subprocess.CalledProcessError):
        return None, None


def collect_embedding_diagnostics(
    chunks: Sequence[IndexedChunk],
) -> tuple[dict[str, dict[str, int | bool | None]], dict[str, object]]:
    """Measure tokenizer lengths without changing embedding behavior."""

    diagnostics: dict[str, dict[str, int | bool | None]] = {}
    metadata: dict[str, object] = {
        "effective_input_limit": None,
        "resolved_model_revision": None,
        "token_lengths_available": False,
    }
    try:
        model = get_embedding_model()
        tokenizer = getattr(model, "tokenizer", None)
        input_limit = getattr(model, "max_seq_length", None)
        metadata["effective_input_limit"] = input_limit
        first_module = model._first_module() if hasattr(model, "_first_module") else None
        auto_model = getattr(first_module, "auto_model", None)
        config = getattr(auto_model, "config", None)
        metadata["resolved_model_revision"] = getattr(config, "_commit_hash", None)
        if tokenizer is None:
            raise AttributeError("Embedding tokenizer is unavailable")
        for chunk in chunks:
            encoded = tokenizer(
                chunk.content,
                add_special_tokens=True,
                truncation=False,
            )
            token_count = len(encoded["input_ids"])
            diagnostics[_source_identifier(chunk)] = {
                "token_count": token_count,
                "input_limit": input_limit,
                "exceeds_input_limit": (
                    token_count > input_limit if isinstance(input_limit, int) else None
                ),
            }
        metadata["token_lengths_available"] = True
    except Exception as exc:
        metadata["diagnostic_error"] = type(exc).__name__
        for chunk in chunks:
            diagnostics[_source_identifier(chunk)] = {
                "token_count": None,
                "input_limit": metadata["effective_input_limit"],
                "exceeds_input_limit": None,
            }
    return diagnostics, metadata


def _embedding_summary(
    diagnostics: dict[str, dict[str, int | bool | None]],
) -> dict[str, object]:
    measured = [
        (source_id, item["token_count"])
        for source_id, item in diagnostics.items()
        if isinstance(item["token_count"], int)
    ]
    over_limit = [
        source_id
        for source_id, item in diagnostics.items()
        if item["exceeds_input_limit"] is True
    ]
    return {
        "indexed_chunks": len(diagnostics),
        "measured_chunks": len(measured),
        "chunks_exceeding_input_limit": len(over_limit),
        "maximum_token_count": max((count for _, count in measured), default=None),
        "exceeding_source_ids": over_limit,
    }


def evaluate_dataset(
    db: Session,
    dataset: EvaluationDataset,
    dataset_hash: str,
    repository: str,
    candidate_depth: int = 10,
    mode: EvaluationMode = "dense",
    branch_depth: int = RRF_BRANCH_DEPTH,
    rrf_constant: int = RRF_CONSTANT,
    rerank_depth: int = 20,
) -> dict[str, object]:
    """Evaluate one prepared corpus using scoped retrieval and production context."""

    if not 10 <= candidate_depth <= MAX_TOP_K:
        raise EvaluationError(
            f"candidate_depth must be between 10 and {MAX_TOP_K}"
        )
    scope = repository.strip()
    if not scope:
        raise EvaluationError("Repository scope must not be blank")
    indexed_chunks = load_indexed_chunks(db, scope)
    actual_manifest = validate_corpus_manifest(dataset, scope, indexed_chunks)
    token_diagnostics, model_metadata = collect_embedding_diagnostics(indexed_chunks)
    if mode == "rerank" and rerank_depth not in RERANK_DEPTHS:
        raise EvaluationError("rerank_depth must be 20 or 50")
    if mode in {"rerank_rrf_ce", "rerank_three_signal"} and rerank_depth != 20:
        raise EvaluationError("Signal-fusion experiments require rerank_depth=20")

    outcomes: list[CaseOutcome] = []
    case_reports: list[dict[str, object]] = []
    rerank_results = []
    for case in dataset.cases:
        rerank_result = None
        if mode == "dense":
            candidates = search_code(
                db, case.question, top_k=candidate_depth, repository=scope
            )
        elif mode == "rerank":
            rerank_result = rerank_hybrid(
                db, case.question, candidate_depth, scope,
                depth=rerank_depth, branch_depth=branch_depth,
                rrf_constant=rrf_constant,
            )
            candidates = rerank_result.candidates
            rerank_results.append(rerank_result)
        elif mode in {"rerank_rrf_ce", "rerank_three_signal"}:
            rerank_result = rerank_hybrid_fused(
                db, case.question, candidate_depth, scope,
                mode="rrf_ce" if mode == "rerank_rrf_ce" else "three_signal",
                branch_depth=branch_depth, rrf_constant=rrf_constant,
            )
            candidates = rerank_result.candidates
            rerank_results.append(rerank_result)
        else:
            candidates = retrieve_code(
                db,
                case.question,
                top_k=candidate_depth,
                repository=scope,
                mode=mode,
                branch_depth=branch_depth,
                rrf_constant=rrf_constant,
            )
        context = build_context(candidates)
        indexed_evidence = evidence_matches(case, indexed_chunks)
        candidate_matches = _candidate_match_sets(case, candidates)
        context_evidence = evidence_matches(case, context.included_chunks)
        required_ids = frozenset(
            unit.evidence_id for unit in case.required_evidence
        )
        outcome = CaseOutcome(
            case_id=case.case_id,
            source_answerable=case.source_answerable,
            required_evidence_ids=required_ids,
            indexed_evidence_ids=indexed_evidence,
            candidate_evidence_by_rank=candidate_matches,
            context_evidence_ids=context_evidence,
        )
        outcomes.append(outcome)
        retrieved_all = outcome.retrieved_at(candidate_depth)
        evidence_ranks = None
        if rerank_result is not None:
            evidence_ranks = {}
            for evidence_id in sorted(required_ids):
                def matching_chunk(pool: list[RetrievedChunk]) -> RetrievedChunk | None:
                    return next(
                        (
                            chunk
                            for chunk in pool
                            if evidence_id in evidence_matches(case, [chunk])
                        ),
                        None,
                    )
                pre_chunk = matching_chunk(rerank_result.pre_rerank_candidates)
                scored_chunk = matching_chunk(rerank_result.ranked_candidates)
                fused_chunk = matching_chunk(rerank_result.signal_ranked_candidates or [])
                evidence_ranks[evidence_id] = {
                    "rrf_rank": pre_chunk.fusion_rank if pre_chunk else None,
                    "reranker_rank": (
                        scored_chunk.reranker_rank if scored_chunk else None
                    ),
                    "signal_fusion_rank": (
                        fused_chunk.signal_fusion_rank if fused_chunk else None
                    ),
                    "reranker_input_tokens": (
                        scored_chunk.reranker_input_tokens if scored_chunk else None
                    ),
                    "reranker_input_truncated": (
                        scored_chunk.reranker_input_truncated if scored_chunk else None
                    ),
                }
        case_reports.append(
            {
                "case_id": case.case_id,
                "question": case.question,
                "primary_category": case.primary_category,
                "secondary_tags": case.secondary_tags,
                "source_answerable": case.source_answerable,
                "required_evidence_ids": sorted(required_ids),
                "indexed_evidence_ids": sorted(indexed_evidence),
                "evidence_absent_from_index": sorted(required_ids - indexed_evidence),
                "retrieved_evidence_at_depth": sorted(retrieved_all),
                "retrieval_misses": sorted(indexed_evidence - retrieved_all),
                "context_evidence_ids": sorted(context_evidence),
                "selection_losses": sorted(retrieved_all - context_evidence),
                "context_size_characters": len(context.text),
                "candidate_union_size": (
                    rerank_result.union_size if rerank_result else None
                ),
                "reranked_candidates": (
                    rerank_result.scored_candidates if rerank_result else None
                ),
                "reranker_truncated_inputs": (
                    rerank_result.truncated_inputs if rerank_result else None
                ),
                "rerank_evidence_ranks": evidence_ranks,
                "context_source_ids": [
                    _source_identifier(chunk) for chunk in context.included_chunks
                ],
                "candidates": [
                    {
                        "rank": rank,
                        "source_id": _source_identifier(candidate),
                        "repository": candidate.repository,
                        "file_path": candidate.file_path,
                        "symbol_type": candidate.symbol_type,
                        "symbol_name": candidate.symbol_name,
                        "start_line": candidate.start_line,
                        "end_line": candidate.end_line,
                        "cosine_distance": candidate.cosine_distance,
                        "lexical_score": candidate.lexical_score,
                        "dense_rank": candidate.dense_rank,
                        "lexical_rank": candidate.lexical_rank,
                        "fusion_score": candidate.fusion_score,
                        "fusion_rank": candidate.fusion_rank,
                        "reranker_score": candidate.reranker_score,
                        "reranker_rank": candidate.reranker_rank,
                        "reranker_input_tokens": candidate.reranker_input_tokens,
                        "reranker_input_truncated": candidate.reranker_input_truncated,
                        "signal_fusion_score": candidate.signal_fusion_score,
                        "signal_fusion_rank": candidate.signal_fusion_rank,
                        "matched_evidence_ids": sorted(candidate_matches[rank - 1]),
                        "embedding_input": token_diagnostics.get(
                            _source_identifier(candidate),
                            {
                                "token_count": None,
                                "input_limit": model_metadata.get(
                                    "effective_input_limit"
                                ),
                                "exceeds_input_limit": None,
                            },
                        ),
                    }
                    for rank, candidate in enumerate(candidates, start=1)
                ],
                "rationale": case.rationale,
            }
        )

    revision, dirty = _git_revision()
    settings = get_settings()
    return {
        "reproducibility": {
            "dataset_version": dataset.dataset_version,
            "dataset_status": dataset.dataset_status,
            "dataset_sha256": dataset_hash,
            "case_set_sha256": compute_case_set_hash(dataset),
            "corpus_manifest_sha256": actual_manifest,
            "corpus_source_revision": dataset.corpus.source_revision,
            "repository": scope,
            "application_git_revision": revision,
            "application_git_dirty": dirty,
            "embedding_model_name": settings.embedding_model_name,
            "resolved_model_revision": model_metadata.get(
                "resolved_model_revision"
            ),
            "embedding_dimension": EMBEDDING_DIMENSION,
            "effective_model_input_limit": model_metadata.get(
                "effective_input_limit"
            ),
            "chunking_identifier": CHUNKING_IDENTIFIER,
            "candidate_depth": candidate_depth,
            "retrieval_mode": mode,
            "rrf_constant": rrf_constant if mode in {"hybrid", "rerank", "rerank_rrf_ce", "rerank_three_signal"} else None,
            "rrf_branch_depth": branch_depth if mode in {"hybrid", "rerank", "rerank_rrf_ce", "rerank_three_signal"} else None,
            "reranker_model": RERANKER_MODEL if mode in {"rerank", "rerank_rrf_ce", "rerank_three_signal"} else None,
            "reranker_requested_revision": (
                RERANKER_REVISION if mode in {"rerank", "rerank_rrf_ce", "rerank_three_signal"} else None
            ),
            "reranker_revision": (
                rerank_results[0].model_revision if rerank_results else None
            ),
            "reranker_depth": rerank_depth if mode in {"rerank", "rerank_rrf_ce", "rerank_three_signal"} else None,
            "reranker_device": (
                rerank_results[0].device if rerank_results else None
            ),
            "reranker_model_input_limit": (
                rerank_results[0].model_input_limit if rerank_results else None
            ),
            "reranker_model_parameters": (
                rerank_results[0].model_parameters if rerank_results else None
            ),
            "context_budget_characters": MAX_CONTEXT_CHARACTERS,
            "package_versions": _package_versions(),
        },
        "corpus": {
            "expected_chunk_count": dataset.corpus.expected_chunk_count,
            "actual_chunk_count": len(indexed_chunks),
            "embedding_input_diagnostics": _embedding_summary(token_diagnostics),
            "embedding_diagnostic_metadata": model_metadata,
            "reranker_diagnostics": (
                {
                    "candidate_pairs_scored": sum(
                        result.scored_candidates for result in rerank_results
                    ),
                    "candidate_pairs_exceeding_input_limit": sum(
                        result.truncated_inputs for result in rerank_results
                    ),
                    "maximum_input_tokens": max(
                        (result.maximum_input_tokens for result in rerank_results),
                        default=None,
                    ),
                    "candidate_union_sizes": [
                        result.union_size for result in rerank_results
                    ],
                } if rerank_results else None
            ),
        },
        "metrics": calculate_metrics(outcomes),
        "cases": case_reports,
    }
