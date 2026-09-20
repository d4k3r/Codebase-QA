"""Read-only DEV1/DEV2 per-case ranking diagnostics from fixed report files.

Never accepts HOLDOUT. Candidate-union coverage is measured from the same
scoped dense/lexical branches at depth 50, not inferred from reranker top-20.
"""

import argparse
import json
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal
from app.dev2 import load_final_dev2
from app.evaluation import (
    evidence_matches, load_dataset, load_indexed_chunks, validate_corpus_manifest,
)
from app.services.retrieval import search_code, search_lexical
from app.services.embeddings import get_embedding_model


DATASETS = {
    "dev1": Path(__file__).resolve().parents[1] / "evaluation/datasets/codebase_qa_v2_v1.json",
    "dev2": Path(__file__).resolve().parents[1] / "evaluation/datasets/codebase_qa_v2_dev2_v1.json",
}
MODES = ("dense", "lexical", "hybrid", "rerank", "rerank_rrf_ce", "rerank_three_signal")


def _report_path(directory: Path, cohort: str, mode: str) -> Path:
    kind = "experimental" if mode.startswith("rerank_") else "baseline"
    return directory / f"codebase-qa-{cohort}-{kind}-{mode}.json"


def _unit_ranks(case: object, chunks: list[object]) -> dict[str, int | None]:
    ids = [unit.evidence_id for unit in case.required_evidence]
    return {evidence_id: next(
        (rank for rank, chunk in enumerate(chunks, 1)
         if evidence_id in evidence_matches(case, [chunk])), None
    ) for evidence_id in ids}


def _long_positions(indexed: list, dataset_path: Path) -> dict:
    """Approximate tokenizer positions in exact accepted source chunks."""

    final = load_final_dev2(dataset_path)
    tokenizer = get_embedding_model().tokenizer
    result = {}
    for case in final.cases:
        if "long_chunk" not in case.secondary_tags:
            continue
        units = {}
        for unit in case.required_evidence:
            alternatives = []
            for span in unit.acceptable_spans:
                for chunk in indexed:
                    if (chunk.file_path != span.file_path
                            or chunk.start_line > span.start_line
                            or span.end_line > chunk.end_line
                            or not all(anchor in chunk.content for anchor in span.content_contains)):
                        continue
                    lines = chunk.content.splitlines(keepends=True)
                    begin = span.start_line - chunk.start_line
                    end = span.end_line - chunk.start_line + 1
                    token_length = lambda source: len(tokenizer(
                        source, add_special_tokens=True, truncation=False,
                        verbose=False,
                    )["input_ids"])
                    total = token_length(chunk.content)
                    start_token = token_length("".join(lines[:begin])) - 2
                    end_token = token_length("".join(lines[:end])) - 2
                    alternatives.append({
                        "file_path": span.file_path,
                        "chunk_start_line": chunk.start_line,
                        "chunk_end_line": chunk.end_line,
                        "chunk_tokens_including_special": total,
                        "evidence_start_content_token_approx": start_token,
                        "evidence_end_content_token_approx": end_token,
                        "extends_beyond_254_content_tokens": end_token > 254,
                        "complete_short_alternative": total <= 256,
                    })
            units[unit.evidence_id] = alternatives
        result[case.case_id] = units
    return result


def analyse(db: object, cohort: str, report_directory: Path) -> dict:
    if cohort not in DATASETS:
        raise ValueError("Only DEV1 and DEV2 may be analysed")
    dataset, _ = load_dataset(DATASETS[cohort])
    repository = dataset.corpus.repository
    indexed = load_indexed_chunks(db, repository)
    validate_corpus_manifest(dataset, repository, indexed)
    reports = {mode: json.loads(_report_path(report_directory, cohort, mode).read_text(
        encoding="utf-8"
    )) for mode in MODES}
    expected_ids = [case.case_id for case in dataset.cases]
    for mode, report in reports.items():
        if ([case["case_id"] for case in report["cases"]] != expected_ids
                or report["reproducibility"]["dataset_version"] != dataset.dataset_version
                or report["reproducibility"]["corpus_manifest_sha256"]
                != dataset.corpus.index_manifest_sha256
                or report["reproducibility"]["retrieval_mode"] != mode):
            raise ValueError(f"Incompatible {cohort}/{mode} report")
    case_reports = {mode: {case["case_id"]: case for case in report["cases"]}
                    for mode, report in reports.items()}
    cases = []
    for case in dataset.cases:
        dense = search_code(db, case.question, 50, repository)
        lexical = search_lexical(db, case.question, 50, repository)
        union = {(chunk.repository, chunk.row_id): chunk for chunk in [*dense, *lexical]}
        required = {unit.evidence_id for unit in case.required_evidence}
        union_found = evidence_matches(case, list(union.values()))
        rerank_ranks = case_reports["rerank"][case.case_id]["rerank_evidence_ranks"] or {}
        per_mode = {}
        for mode in MODES:
            report_case = case_reports[mode][case.case_id]
            top10 = set(report_case["retrieved_evidence_at_depth"])
            context = set(report_case["context_evidence_ids"])
            ranking_miss = sorted(union_found - top10)
            window_miss = []
            ce_ordering_miss = []
            rrf_demotion = []
            if mode.startswith("rerank"):
                for evidence_id in ranking_miss:
                    ranks = rerank_ranks.get(evidence_id, {})
                    rrf = ranks.get("rrf_rank")
                    ce = ranks.get("reranker_rank")
                    if rrf is None or rrf > 20:
                        window_miss.append(evidence_id)
                    elif ce is not None and ce > 10:
                        ce_ordering_miss.append(evidence_id)
                        if rrf <= 10:
                            rrf_demotion.append(evidence_id)
            context_loss = sorted(top10 - context)
            multi_competition = len(required) > 1 and bool(top10) and top10 != required
            classes = [
                label for label, present in (
                    ("candidate_generation", bool(required - union_found)),
                    ("fusion_or_ranking", bool(ranking_miss)),
                    ("reranking_window", bool(window_miss)),
                    ("reranker_ordering", mode == "rerank" and bool(ce_ordering_miss)),
                    ("rrf_preservation", mode == "rerank" and bool(rrf_demotion)),
                    ("context_selection", bool(context_loss)),
                    ("multi_evidence_competition", multi_competition),
                    ("truncation_associated", "long_chunk" in case.secondary_tags and bool(ranking_miss)),
                    ("near_match_distractor", "distractor" in case.secondary_tags and bool(ranking_miss)),
                ) if present
            ]
            if (required - context) and not classes:
                classes.append("other")
            per_mode[mode] = {
                "top10_evidence": sorted(top10),
                "context_evidence": sorted(context),
                "candidate_generation_missing": sorted(required - union_found),
                "ranking_missing": ranking_miss,
                "rerank_window_missing": window_miss,
                "ce_ordering_missing": ce_ordering_miss,
                "strong_rrf_demoted_by_ce": rrf_demotion,
                "context_selection_missing": context_loss,
                "multi_evidence_competition": multi_competition,
                "failure_classes": classes,
                "ranks_at_top10": {
                    evidence_id: next(
                        (candidate["rank"] for candidate in report_case["candidates"]
                         if evidence_id in candidate["matched_evidence_ids"]), None
                    ) for evidence_id in sorted(required)
                },
                "rerank_ranks": report_case["rerank_evidence_ranks"],
            }
        cases.append({
            "case_id": case.case_id,
            "category": case.primary_category,
            "tags": case.secondary_tags,
            "source_answerable": case.source_answerable,
            "required_evidence": sorted(required),
            "candidate_union_size": len(union),
            "candidate_union_evidence": sorted(union_found),
            "dense_rank_50": _unit_ranks(case, dense),
            "lexical_rank_50": _unit_ranks(case, lexical),
            "modes": per_mode,
        })
    answerable = [case for case in cases if case["source_answerable"]]
    return {
        "cohort": cohort,
        "dataset_version": dataset.dataset_version,
        "corpus_manifest": dataset.corpus.index_manifest_sha256,
        "answerable_cases": len(answerable),
        "gold_units": sum(len(case["required_evidence"]) for case in answerable),
        "candidate_union_found": sum(len(case["candidate_union_evidence"]) for case in answerable),
        "audited_long_positions": (
            _long_positions(indexed, DATASETS[cohort]) if cohort == "dev2" else None
        ),
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", required=True, choices=tuple(DATASETS))
    parser.add_argument("--reports", type=Path, default=Path("/tmp"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        result = analyse(db, args.cohort, args.reports)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{args.cohort}: candidate union {result['candidate_union_found']}/{result['gold_units']}; "
          f"wrote {args.output}")


if __name__ == "__main__":
    main()
