"""Run a tiny transparent hit@k evaluation against a local repository."""

import argparse
from dataclasses import dataclass
from pathlib import Path

from app.database import SessionLocal
from app.services.retrieval import search_code
from app.services.storage import index_repository


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    question: str
    expected_file: str
    expected_symbol: str | None


CASES = (
    EvaluationCase("Which function adds two numbers?", "calculator.py", "add"),
    EvaluationCase(
        "What class exposes arithmetic operations?", "calculator.py", "Calculator"
    ),
    EvaluationCase(
        "Where is a friendly welcome message built?", "nested/greetings.py", "greet"
    ),
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository_path", type=Path)
    parser.add_argument("--repository-name", default="tiny-repo-evaluation")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    hits = 0
    with SessionLocal() as db:
        stats = index_repository(db, args.repository_path, args.repository_name)
        print(f"Indexed {stats.rows_stored} rows for {stats.repository}.")

        for case in CASES:
            results = search_code(db, case.question, args.top_k)
            hit = any(
                result.file_path == case.expected_file
                and result.symbol_name == case.expected_symbol
                for result in results
            )
            hits += int(hit)
            label = "HIT" if hit else "MISS"
            returned = [f"{item.file_path}:{item.symbol_name}" for item in results]
            print(f"{label}: {case.question}\n  returned={returned}")

    print(f"hit@{args.top_k}: {hits}/{len(CASES)} = {hits / len(CASES):.3f}")


if __name__ == "__main__":
    main()
