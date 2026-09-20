"""Validate source-only holdout candidates and generate a human-review document.

This command never opens a database or invokes retrieval, embedding, or a provider.
"""

import argparse
import hashlib
import json
from pathlib import Path

from app.config import PROJECT_ROOT
from app.holdout import (
    canonical_hash,
    leakage_warnings,
    load_candidates,
    render_review,
    validate_sources,
)


DEV = PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_v1.json"
CANDIDATES = (
    PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_holdout_candidates_v1.json"
)
REVIEW = PROJECT_ROOT / "docs/holdout-review.md"
DEV_RAW_SHA256 = "098017b14aed9a4433051ddc92812292ee8d2cdec0268ea94c7c47404e193b17"


def prepare(dataset_path: Path, dev_path: Path, root: Path) -> tuple[str, dict[str, list[str]]]:
    """Return review Markdown and warnings only after all checks pass."""

    dataset = load_candidates(dataset_path)
    if hashlib.sha256(dev_path.read_bytes()).hexdigest() != DEV_RAW_SHA256:
        raise ValueError("DEV dataset changed; review its identity before preparing holdout")
    dev = json.loads(dev_path.read_text(encoding="utf-8"))
    if len(dev["cases"]) != 40 or dataset.dev_dataset_hash != (
        "eb095d8701955216171ad3463f6cfb2d7ce2ce44cf8aef47ceaf00c41edd2a8b"
    ) or dataset.dev_case_set_hash != (
        "97a85902564bdcfce9e5e85da38c0f1008cb3fc839296f2a3c4871e1f78a26af"
    ):
        raise ValueError("DEV dataset/case-set identity mismatch")
    excerpts = validate_sources(dataset, root)
    warnings = leakage_warnings(dataset.cases, dev["cases"])
    return render_review(dataset, excerpts, warnings), warnings


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--dev", type=Path, default=DEV)
    parser.add_argument("--output", type=Path, default=REVIEW)
    args = parser.parse_args()
    review, warnings = prepare(args.candidates, args.dev, PROJECT_ROOT)
    args.output.write_text(review, encoding="utf-8")
    dataset = load_candidates(args.candidates)
    flagged = sum(bool(flags) for flags in warnings.values())
    print(
        f"Validated {len(dataset.cases)} source-grounded candidates; "
        f"{flagged} have DEV overlap warnings; "
        f"candidate hash {canonical_hash(dataset)}; review: {args.output}"
    )


if __name__ == "__main__":
    main()
