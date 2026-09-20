"""Score an already prepared repository index without database or LLM writes."""

import argparse
import json
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal
from app.evaluation import EvaluationError, EvaluationMode, evaluate_dataset, load_dataset
from app.services.retrieval import RRF_BRANCH_DEPTH, RRF_CONSTANT


DEFAULT_DATASET = (
    Path(__file__).resolve().parents[1]
    / "evaluation"
    / "datasets"
    / "codebase_qa_v2_v1.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="Versioned JSON dataset (defaults to the Codebase QA V2 draft set).",
    )
    parser.add_argument(
        "--repository",
        required=True,
        help="Exact prepared repository identity to search; this is selection, not authorization.",
    )
    parser.add_argument(
        "--candidate-depth",
        type=int,
        default=10,
        help="Scoped candidate depth, from 10 to 50.",
    )
    parser.add_argument(
        "--mode",
        choices=("dense", "lexical", "hybrid", "rerank", "rerank_rrf_ce", "rerank_three_signal"),
        default="dense",
        help="Explicit retrieval experiment mode; dense remains the default.",
    )
    parser.add_argument(
        "--branch-depth", type=int, default=RRF_BRANCH_DEPTH,
        help="Candidates per branch in hybrid mode (default: 50).",
    )
    parser.add_argument(
        "--rrf-constant", type=int, default=RRF_CONSTANT,
        help="Positive RRF rank constant in hybrid mode (default: 60).",
    )
    parser.add_argument(
        "--rerank-depth", type=int, choices=(20, 50), default=20,
        help="RRF-ordered candidates scored by the local reranker (20 or 50).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON report path; stdout is used by default.",
    )
    return parser


def run(
    dataset_path: Path,
    repository: str,
    candidate_depth: int,
    mode: EvaluationMode = "dense",
    branch_depth: int = RRF_BRANCH_DEPTH,
    rrf_constant: int = RRF_CONSTANT,
    rerank_depth: int = 20,
) -> dict[str, object]:
    """Run read-only scoring against an existing compatible corpus."""

    dataset, dataset_hash = load_dataset(dataset_path)
    with SessionLocal() as db:
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        return evaluate_dataset(
            db,
            dataset,
            dataset_hash,
            repository,
            candidate_depth,
            mode=mode,
            branch_depth=branch_depth,
            rrf_constant=rrf_constant,
            rerank_depth=rerank_depth,
        )


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        report = run(
            args.dataset,
            args.repository,
            args.candidate_depth,
            args.mode,
            args.branch_depth,
            args.rrf_constant,
            args.rerank_depth,
        )
    except (EvaluationError, OSError, ValueError) as exc:
        parser.error(str(exc))

    rendered = json.dumps(report, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote evaluation report to {args.output}")


if __name__ == "__main__":
    main()
