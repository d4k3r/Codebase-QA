"""Validate DEV2 candidates from frozen source and generate an audit package.

This command does not connect to a database or invoke retrieval, embedding
inference, reranking, evaluation metrics, or an answer provider.
"""

import argparse
import hashlib
import json
from pathlib import Path

from app.config import PROJECT_ROOT
from app.dev2 import load_dev2, validate_and_render
from app.holdout import canonical_hash, load_frozen


CANDIDATES = (
    PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_dev2_candidates_v1.json"
)
DEV1 = PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_v1.json"
HOLDOUT = PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_holdout_v1.json"
REVIEW = PROJECT_ROOT / "docs/dev2-review.md"
DEV1_RAW_SHA256 = "098017b14aed9a4433051ddc92812292ee8d2cdec0268ea94c7c47404e193b17"
HOLDOUT_DATASET_SHA256 = "3bb15dafe49667f5b53ab39215c3729fe2b71326d9775e095a05077ec6373c8a"


def prepare(
    candidates_path: Path = CANDIDATES,
    dev1_path: Path = DEV1,
    holdout_path: Path = HOLDOUT,
    root: Path = PROJECT_ROOT,
    token_count=None,
) -> tuple[str, dict]:
    """Return Markdown and overlap diagnostics after source-only checks."""

    if hashlib.sha256(dev1_path.read_bytes()).hexdigest() != DEV1_RAW_SHA256:
        raise ValueError("DEV1 changed; abort DEV2 preparation")
    holdout = load_frozen(holdout_path)
    if holdout.dataset_hash != HOLDOUT_DATASET_SHA256 or holdout.cohort != "primary":
        raise ValueError("Frozen HOLDOUT identity changed; abort DEV2 preparation")
    dataset = load_dev2(candidates_path)
    dev1 = json.loads(dev1_path.read_text(encoding="utf-8"))
    if token_count is None:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(
            dataset.embedding_model, local_files_only=True
        )
        token_count = lambda source: len(
            tokenizer(source, add_special_tokens=True, truncation=False)["input_ids"]
        )
    return validate_and_render(dataset, root, dev1["cases"], [
        case.model_dump(mode="json") for case in holdout.cases
    ], token_count)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--output", type=Path, default=REVIEW)
    args = parser.parse_args()
    review, overlaps = prepare(args.candidates)
    args.output.write_text(review, encoding="utf-8")
    dataset = load_dev2(args.candidates)
    print(
        f"Validated {len(dataset.cases)} DEV2 candidates; "
        f"hash {canonical_hash(dataset)}; "
        f"DEV1 overlap {sum(bool(v[1]) for v in overlaps['DEV1'].values())}; "
        f"HOLDOUT overlap {sum(bool(v[1]) for v in overlaps['HOLDOUT'].values())}; "
        f"review {args.output}"
    )


if __name__ == "__main__":
    main()
