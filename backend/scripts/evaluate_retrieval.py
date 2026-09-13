"""Run a tiny transparent hit@k evaluation against a local repository."""

import argparse
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete

from app.database import SessionLocal
from app.models import CodeChunk
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


def _resolve_repository_identity(repository_name: str | None) -> tuple[str, bool]:
    """Return an explicit identity or a generated identity and cleanup flag."""

    if repository_name is not None:
        identity = repository_name.strip()
        if not identity:
            raise ValueError("--repository-name must not be blank")
        return identity, False
    return f"tiny-repo-evaluation-{uuid4().hex}", True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository_path", type=Path)
    parser.add_argument(
        "--repository-name",
        default=None,
        help="Optional persistent repository identity; generated identities are cleaned up.",
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    repository_name, cleanup_generated_identity = _resolve_repository_identity(
        args.repository_name
    )
    hits = 0
    db = SessionLocal()
    try:
        stats = index_repository(db, args.repository_path, repository_name)
        repository_name = stats.repository
        print(f"Indexed {stats.rows_stored} rows for {stats.repository}.")

        for case in CASES:
            results = search_code(db, case.question, args.top_k)
            hit = any(
                result.repository == repository_name
                and result.file_path == case.expected_file
                and result.symbol_name == case.expected_symbol
                for result in results
            )
            hits += int(hit)
            label = "HIT" if hit else "MISS"
            returned = [
                f"{item.repository}:{item.file_path}:{item.symbol_name}" for item in results
            ]
            print(f"{label}: {case.question}\n  returned={returned}")

        print(f"hit@{args.top_k}: {hits}/{len(CASES)} = {hits / len(CASES):.3f}")
    finally:
        try:
            if cleanup_generated_identity:
                db.rollback()
                db.execute(delete(CodeChunk).where(CodeChunk.repository == repository_name))
                db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    main()
