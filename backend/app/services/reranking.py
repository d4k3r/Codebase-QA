"""Experimental local cross-encoder ordering of an existing hybrid candidate pool."""

import math
import tempfile
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path

import torch
from sentence_transformers import CrossEncoder
from sqlalchemy.orm import Session

from app.services.retrieval import (
    MAX_TOP_K,
    RRF_BRANCH_DEPTH,
    RRF_CONSTANT,
    RetrievedChunk,
    _identity,
    hybrid_candidate_pool,
)


RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L6-v2"
RERANKER_REVISION = "233902d25c440f23af6f7d6e94d2946bac0bee0a"
RERANKER_MAX_TOKENS = 512
RERANKER_BATCH_SIZE = 16
RERANK_DEPTHS = (20, 50)


@dataclass(frozen=True, slots=True)
class RerankResult:
    candidates: list[RetrievedChunk]
    pre_rerank_candidates: list[RetrievedChunk]
    ranked_candidates: list[RetrievedChunk]
    union_size: int
    scored_candidates: int
    truncated_inputs: int
    maximum_input_tokens: int
    model_input_limit: int
    device: str
    model_revision: str | None
    model_parameters: int | None
    signal_ranked_candidates: list[RetrievedChunk] | None = None


def reranker_document(chunk: RetrievedChunk) -> str:
    """Supply source metadata as model-only context, not displayed source text."""

    return (
        f"Repository: {chunk.repository}\n"
        f"File: {chunk.file_path}\n"
        f"Symbol: {chunk.symbol_type} {chunk.symbol_name or '<module>'}\n"
        f"Source:\n{chunk.content}"
    )


@lru_cache(maxsize=1)
def get_reranker_model() -> CrossEncoder:
    """Load one pinned public artifact lazily; never contact an LLM provider."""

    cache = Path(tempfile.gettempdir()) / "codebase-qa-v2-reranker-cache"
    return CrossEncoder(
        RERANKER_MODEL,
        revision=RERANKER_REVISION,
        max_length=RERANKER_MAX_TOKENS,
        device="cuda" if torch.cuda.is_available() else "cpu",
        cache_folder=str(cache),
    )


def rerank_candidates(
    question: str,
    ordered_union: list[RetrievedChunk],
    *,
    union_size: int,
    top_k: int,
    depth: int,
) -> RerankResult:
    """Score only the first ``depth`` RRF candidates; retain original provenance."""

    if depth not in RERANK_DEPTHS or not 1 <= top_k <= MAX_TOP_K or top_k > depth:
        raise ValueError("Invalid reranking depth or top_k")
    selected = ordered_union[:depth]
    model = get_reranker_model()
    limit = int(model.max_seq_length)
    pairs = [(question, reranker_document(chunk)) for chunk in selected]
    lengths = [
        len(model.tokenizer(
            query, document, add_special_tokens=True,
            truncation=False, verbose=False,
        )["input_ids"])
        for query, document in pairs
    ]
    scores = model.predict(
        pairs, batch_size=RERANKER_BATCH_SIZE, show_progress_bar=False,
        convert_to_numpy=True,
    ) if pairs else []
    if len(scores) != len(selected):
        raise RuntimeError("Reranker returned the wrong number of scores")
    ranked: list[RetrievedChunk] = []
    for chunk, score, length in zip(selected, scores, lengths, strict=True):
        value = float(score)
        if not math.isfinite(value):
            raise RuntimeError("Reranker returned a non-finite score")
        ranked.append(replace(
            chunk,
            reranker_score=value,
            reranker_input_tokens=length,
            reranker_input_truncated=length > limit,
        ))
    ranked.sort(key=lambda chunk: (
        -float(chunk.reranker_score),
        chunk.fusion_rank if chunk.fusion_rank is not None else MAX_TOP_K + 1,
        chunk.repository, chunk.file_path, chunk.start_line, chunk.end_line,
        chunk.symbol_type, chunk.symbol_name or "", chunk.row_id or 0,
    ))
    ranked = [replace(chunk, reranker_rank=rank) for rank, chunk in enumerate(ranked, 1)]
    chosen = ranked[:top_k]
    config = getattr(getattr(model, "model", None), "config", None)
    revision = getattr(config, "_commit_hash", None)
    parameters = (
        sum(parameter.numel() for parameter in model.model.parameters())
        if hasattr(getattr(model, "model", None), "parameters") else None
    )
    return RerankResult(
        candidates=chosen,
        pre_rerank_candidates=ordered_union,
        ranked_candidates=ranked,
        union_size=union_size,
        scored_candidates=len(selected),
        truncated_inputs=sum(length > limit for length in lengths),
        maximum_input_tokens=max(lengths, default=0),
        model_input_limit=limit,
        device=str(model.device),
        model_revision=revision,
        model_parameters=parameters,
    )


def rerank_hybrid(
    db: Session,
    question: str,
    top_k: int,
    repository: str,
    *,
    depth: int = 20,
    branch_depth: int = RRF_BRANCH_DEPTH,
    rrf_constant: int = RRF_CONSTANT,
) -> RerankResult:
    """Rerank the already scoped RRF pool without performing another search."""

    if depth not in RERANK_DEPTHS or not 1 <= top_k <= depth:
        raise ValueError("Invalid reranking depth or top_k")
    ordered, union_size = hybrid_candidate_pool(
        db, question, repository, branch_depth, rrf_constant, MAX_TOP_K
    )
    return rerank_candidates(
        question, ordered, union_size=union_size, top_k=top_k, depth=depth
    )


def fuse_reranker_ranks(
    result: RerankResult,
    *,
    top_k: int,
    mode: str,
    constant: int = RRF_CONSTANT,
) -> RerankResult:
    """Add bounded CE rank to existing ranks, without combining raw scores.

    ``rrf_ce``: 1/(c + RRF rank) + 1/(c + CE rank, if scored).
    ``three_signal``: available dense, lexical, and CE reciprocal ranks.
    Missing branch/CE ranks contribute zero. Unscored candidates keep their
    original branch ranks and are never assigned a fabricated CE rank.
    """

    if mode not in {"rrf_ce", "three_signal"} or constant < 1:
        raise ValueError("Invalid signal-fusion mode or constant")
    if not 1 <= top_k <= 20 or result.scored_candidates > 20:
        raise ValueError("Signal fusion requires the bounded 20-candidate window")
    scored = {_identity(chunk): chunk for chunk in result.ranked_candidates}
    seen: set[tuple[object, ...]] = set()
    ranked: list[RetrievedChunk] = []
    for original in result.pre_rerank_candidates:
        key = _identity(original)
        if key in seen:
            continue
        seen.add(key)
        ce = scored.get(key)
        ce_rank = ce.reranker_rank if ce else None
        if mode == "rrf_ce":
            if original.fusion_rank is None:
                raise ValueError("RRF rank is required for rrf_ce fusion")
            value = 1 / (constant + original.fusion_rank)
        else:
            value = sum(
                1 / (constant + rank)
                for rank in (original.dense_rank, original.lexical_rank)
                if rank is not None
            )
        if ce_rank is not None:
            value += 1 / (constant + ce_rank)
        ranked.append(replace(
            original,
            reranker_score=ce.reranker_score if ce else None,
            reranker_rank=ce_rank,
            reranker_input_tokens=ce.reranker_input_tokens if ce else None,
            reranker_input_truncated=ce.reranker_input_truncated if ce else None,
            signal_fusion_score=value,
        ))
    ranked.sort(key=lambda chunk: (
        -float(chunk.signal_fusion_score),
        chunk.fusion_rank if chunk.fusion_rank is not None else MAX_TOP_K + 1,
        chunk.repository, chunk.file_path, chunk.start_line, chunk.end_line,
        chunk.symbol_type, chunk.symbol_name or "", chunk.row_id or 0,
    ))
    ranked = [replace(chunk, signal_fusion_rank=rank)
              for rank, chunk in enumerate(ranked, 1)]
    return replace(result, candidates=ranked[:top_k], signal_ranked_candidates=ranked)


def rerank_hybrid_fused(
    db: Session,
    question: str,
    top_k: int,
    repository: str,
    *,
    mode: str,
    branch_depth: int = RRF_BRANCH_DEPTH,
    rrf_constant: int = RRF_CONSTANT,
) -> RerankResult:
    """One scoped 50+50 snapshot, 20 scored pairs, then rank-only fusion."""

    if mode not in {"rrf_ce", "three_signal"}:
        raise ValueError("Unknown signal-fusion mode")
    base = rerank_hybrid(
        db, question, top_k, repository,
        depth=20, branch_depth=branch_depth, rrf_constant=rrf_constant,
    )
    return fuse_reranker_ranks(
        base, top_k=top_k, mode=mode, constant=rrf_constant
    )
