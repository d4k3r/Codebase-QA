"""Explicitly index a corpus into an isolated/disposable evaluation database."""

import argparse
from pathlib import Path

from app.database import SessionLocal
from app.services.storage import index_repository


CONFIRMATION = "I_UNDERSTAND_THIS_REPLACES_REPOSITORY_ROWS"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository_path", type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument(
        "--confirm-write",
        required=True,
        help=f"Required literal confirmation: {CONFIRMATION}",
    )
    args = parser.parse_args()
    if args.confirm_write != CONFIRMATION:
        parser.error(
            "Corpus preparation is write-enabled and requires the exact confirmation "
            f"{CONFIRMATION!r}"
        )

    with SessionLocal() as db:
        stats = index_repository(db, args.repository_path, args.repository)
    print(
        f"Prepared {stats.repository}: {stats.python_files_discovered} Python files, "
        f"{stats.rows_stored} rows."
    )


if __name__ == "__main__":
    main()
