"""Warm local DEV-only retrieval/CE/fusion timings; not a production benchmark."""

import argparse
import json
import math
import statistics
from pathlib import Path
from time import perf_counter

from sqlalchemy import text

from app.database import SessionLocal
from app.evaluation import load_dataset, load_indexed_chunks, validate_corpus_manifest
from app.services.embeddings import get_embedding_model
from app.services.reranking import (
    fuse_reranker_ranks, get_reranker_model, rerank_candidates,
)
from app.services.retrieval import hybrid_candidate_pool, search_code
from scripts.analyse_signal_ranking import DATASETS


def _summary(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    return {
        "observations": len(ordered),
        "median_ms": round(statistics.median(ordered) * 1000, 2),
        "p95_ms": round(ordered[math.ceil(.95 * len(ordered)) - 1] * 1000, 2),
    }


def measure(db: object, cohort: str, query_count: int, repeats: int) -> dict:
    if cohort not in DATASETS:
        raise ValueError("Only DEV1 and DEV2 may be timed")
    dataset, _ = load_dataset(DATASETS[cohort])
    validate_corpus_manifest(
        dataset, dataset.corpus.repository,
        load_indexed_chunks(db, dataset.corpus.repository),
    )
    questions = [case.question for case in dataset.cases if case.source_answerable][:query_count]
    if not questions or repeats < 1:
        raise ValueError("Need answerable DEV questions and at least one repetition")
    get_embedding_model()
    model = get_reranker_model()
    # Warm both model paths and PostgreSQL statements outside timed observations.
    q = questions[0]
    search_code(db, q, 10, dataset.corpus.repository)
    ordered, union_size = hybrid_candidate_pool(db, q, dataset.corpus.repository)
    rerank_candidates(q, ordered, union_size=union_size, top_k=10, depth=20)

    samples: dict[str, list[float]] = {key: [] for key in (
        "dense", "hybrid_retrieval", "cross_encoder", "rrf_ce_fusion_overhead",
        "three_signal_fusion_overhead", "rerank20_total", "rrf_ce_total",
        "three_signal_total",
    )}
    pair_counts = []
    for _ in range(repeats):
        for question in questions:
            t0 = perf_counter()
            search_code(db, question, 10, dataset.corpus.repository)
            t1 = perf_counter()
            ordered, union_size = hybrid_candidate_pool(db, question, dataset.corpus.repository)
            t2 = perf_counter()
            reranked = rerank_candidates(
                question, ordered, union_size=union_size, top_k=10, depth=20
            )
            t3 = perf_counter()
            fuse_reranker_ranks(reranked, top_k=10, mode="rrf_ce")
            t4 = perf_counter()
            fuse_reranker_ranks(reranked, top_k=10, mode="three_signal")
            t5 = perf_counter()
            pair_counts.append(reranked.scored_candidates)
            for key, duration in (
                ("dense", t1 - t0), ("hybrid_retrieval", t2 - t1),
                ("cross_encoder", t3 - t2), ("rrf_ce_fusion_overhead", t4 - t3),
                ("three_signal_fusion_overhead", t5 - t4),
                ("rerank20_total", t3 - t1), ("rrf_ce_total", t4 - t1),
                ("three_signal_total", t3 - t1 + t5 - t4),
            ):
                samples[key].append(duration)
    return {
        "cohort": cohort,
        "query_count": len(questions),
        "repeats": repeats,
        "device": str(model.device),
        "model_revision": reranked.model_revision,
        "model_parameters": reranked.model_parameters,
        "candidate_pairs_per_query": sorted(set(pair_counts)),
        "timings": {key: _summary(values) for key, values in samples.items()},
        "note": "Warm sequential local observations, not a production benchmark.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", choices=tuple(DATASETS), required=True)
    parser.add_argument("--queries", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        result = measure(db, args.cohort, args.queries, args.repeats)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{args.cohort}: {result['query_count']} questions x {result['repeats']} repeats; "
          f"wrote {args.output}")


if __name__ == "__main__":
    main()
