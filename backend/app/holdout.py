"""Source-only validation and review rendering for unfrozen holdout candidates.

This module deliberately imports no retrieval, embedding, database, or provider code.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Span(BaseModel):
    file_path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    content_contains: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_span(self) -> "Span":
        path = PurePosixPath(self.file_path)
        if (path.is_absolute() or ".." in path.parts or not self.file_path
                or self.file_path.startswith("-")):
            raise ValueError("Evidence paths must be safe repository-relative paths")
        if self.end_line < self.start_line:
            raise ValueError("Evidence lines are reversed")
        if any(not anchor.strip() for anchor in self.content_contains):
            raise ValueError("Evidence anchors must be non-empty")
        return self


class Evidence(BaseModel):
    evidence_id: str = Field(min_length=1)
    why_required: str = Field(min_length=1)
    acceptable_spans: list[Span] = Field(min_length=1)


Category = Literal[
    "semantic_conceptual", "exact_identifier", "configuration_constants",
    "filename_path", "decorator_api_route", "architecture",
    "cross_module_behavior", "multiple_required_evidence",
    "difficult_near_matches", "unanswerable_insufficient_context",
]


class Candidate(BaseModel):
    case_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    primary_category: Category
    secondary_tags: list[str] = Field(default_factory=list)
    source_answerable: bool
    expected_answer: str = Field(min_length=1)
    required_evidence: list[Evidence] = Field(default_factory=list)
    missing_reason: str | None = None

    @model_validator(mode="after")
    def valid_evidence(self) -> "Candidate":
        if self.source_answerable != bool(self.required_evidence):
            raise ValueError("Answerable cases need evidence; unanswerable cases need none")
        if not self.source_answerable and not self.missing_reason:
            raise ValueError("Unanswerable cases need a corpus-based reason")
        ids = [e.evidence_id for e in self.required_evidence]
        if len(ids) != len(set(ids)):
            raise ValueError("Evidence IDs must be unique within a case")
        if len({(s.file_path, s.start_line, s.end_line)
                for e in self.required_evidence for s in e.acceptable_spans}) != sum(
                    len(e.acceptable_spans) for e in self.required_evidence
                ):
            raise ValueError("Duplicate evidence spans in one case")
        return self


class HoldoutCandidates(BaseModel):
    format_version: Literal[1]
    dataset_version: str = Field(min_length=1)
    dataset_status: Literal[
        "Machine-prepared source-grounded holdout candidate pending human review; NOT FROZEN; NOT EVALUATED."
    ]
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    repository: str = Field(min_length=1)
    dev_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dev_case_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[Candidate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases(self) -> "HoldoutCandidates":
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("Candidate IDs must be unique")
        return self


class FrozenCase(Candidate):
    """Candidate label plus the fields expected by the later evaluator."""

    repository: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class FrozenCorpus(BaseModel):
    repository: str = Field(min_length=1)
    expected_chunk_count: int = Field(ge=1)
    index_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    chunking_identifier: str = Field(min_length=1)


class FrozenDataset(BaseModel):
    """An audited source-grounded split; hashes exclude only the two hash fields."""

    format_version: Literal[1]
    dataset_version: str = Field(min_length=1)
    dataset_status: Literal["Human-reviewed, independently audited, frozen."]
    cohort: Literal["primary", "source_coverage_challenge"]
    source_revision: str = Field(pattern=r"^[0-9a-f]{40}$")
    repository: str = Field(min_length=1)
    dev_dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dev_case_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidate_pool_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    index_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    corpus: FrozenCorpus
    case_count: int = Field(ge=1)
    answerable_count: int = Field(ge=0)
    unanswerable_count: int = Field(ge=0)
    multi_evidence_count: int = Field(ge=0)
    category_counts: dict[str, int]
    case_set_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    dataset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    cases: list[FrozenCase] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_freeze(self) -> "FrozenDataset":
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("Frozen case IDs must be unique")
        if (self.corpus.repository != self.repository
                or self.corpus.source_revision != self.source_revision
                or self.corpus.index_manifest_sha256 != self.index_manifest_sha256
                or any(case.repository != self.repository for case in self.cases)):
            raise ValueError("Frozen corpus and case identities do not match")
        if self.case_count != len(self.cases):
            raise ValueError("Frozen case count does not match cases")
        if self.answerable_count != sum(case.source_answerable for case in self.cases):
            raise ValueError("Frozen answerable count does not match cases")
        if self.unanswerable_count != self.case_count - self.answerable_count:
            raise ValueError("Frozen unanswerable count does not match cases")
        if self.multi_evidence_count != sum(
            len(case.required_evidence) >= 2 for case in self.cases
        ):
            raise ValueError("Frozen multi-evidence count does not match cases")
        if self.category_counts != dict(Counter(
            case.primary_category for case in self.cases
        )):
            raise ValueError("Frozen category counts do not match cases")
        if self.case_set_hash != _sha256_json([
            case.model_dump(mode="json") for case in self.cases
        ]):
            raise ValueError("Frozen case-set hash does not match cases")
        if self.dataset_hash != _sha256_json(
            self.model_dump(mode="json", exclude={"dataset_hash", "case_set_hash"})
        ):
            raise ValueError("Frozen dataset hash does not match payload")
        return self


def _sha256_json(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def canonical_hash(value: BaseModel) -> str:
    """Hash canonical validated JSON, independent of whitespace/key formatting."""

    return _sha256_json(value.model_dump(mode="json"))


def freeze_dataset(
    candidates: HoldoutCandidates,
    cases: list[Candidate],
    *,
    cohort: Literal["primary", "source_coverage_challenge"],
    dataset_version: str,
    index_manifest_sha256: str,
    expected_chunk_count: int,
    chunking_identifier: str,
) -> FrozenDataset:
    """Create a self-checking immutable-identity dataset from audited cases."""

    payload = {
        "format_version": 1,
        "dataset_version": dataset_version,
        "dataset_status": "Human-reviewed, independently audited, frozen.",
        "cohort": cohort,
        "source_revision": candidates.source_revision,
        "repository": candidates.repository,
        "dev_dataset_hash": candidates.dev_dataset_hash,
        "dev_case_set_hash": candidates.dev_case_set_hash,
        "candidate_pool_hash": canonical_hash(candidates),
        "index_manifest_sha256": index_manifest_sha256,
        "corpus": {
            "repository": candidates.repository,
            "expected_chunk_count": expected_chunk_count,
            "index_manifest_sha256": index_manifest_sha256,
            "source_revision": candidates.source_revision,
            "chunking_identifier": chunking_identifier,
        },
        "case_count": len(cases),
        "answerable_count": sum(case.source_answerable for case in cases),
        "unanswerable_count": sum(not case.source_answerable for case in cases),
        "multi_evidence_count": sum(len(case.required_evidence) >= 2 for case in cases),
        "category_counts": dict(Counter(case.primary_category for case in cases)),
        "cases": [
            case.model_dump(mode="json") | {
                "repository": candidates.repository,
                "rationale": case.expected_answer,
            }
            for case in cases
        ],
    }
    payload["case_set_hash"] = _sha256_json(payload["cases"])
    payload["dataset_hash"] = _sha256_json({
        key: value for key, value in payload.items() if key != "case_set_hash"
    })
    return FrozenDataset.model_validate(payload)


def load_frozen(path: Path) -> FrozenDataset:
    return FrozenDataset.model_validate_json(path.read_text(encoding="utf-8"))


def load_candidates(path: Path) -> HoldoutCandidates:
    return HoldoutCandidates.model_validate_json(path.read_text(encoding="utf-8"))


def _source_lines(root: Path, revision: str, file_path: str) -> list[str]:
    result = subprocess.run(
        ["git", "show", f"{revision}:{file_path}"], cwd=root,
        capture_output=True, check=False,
    )
    if result.returncode:
        raise ValueError(f"Source file missing at frozen revision: {file_path}")
    try:
        return result.stdout.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise ValueError(f"Source is not UTF-8: {file_path}") from exc


def validate_sources(
    dataset: HoldoutCandidates | FrozenDataset, root: Path
) -> dict[str, list[str]]:
    """Validate every gold alternative against the exact Git tree, without retrieval."""

    revision = subprocess.run(
        ["git", "rev-parse", "--verify", f"{dataset.source_revision}^{{commit}}"],
        cwd=root, capture_output=True, text=True, check=True,
    ).stdout.strip()
    if revision != dataset.source_revision:
        raise ValueError("Frozen source revision does not resolve exactly")
    cache: dict[str, list[str]] = {}
    excerpts: dict[str, list[str]] = {}
    for case in dataset.cases:
        excerpts[case.case_id] = []
        for evidence in case.required_evidence:
            for span in evidence.acceptable_spans:
                if span.file_path not in cache:
                    cache[span.file_path] = _source_lines(root, revision, span.file_path)
                lines = cache[span.file_path]
                if span.end_line > len(lines):
                    raise ValueError(f"Invalid lines: {case.case_id} {span.file_path}")
                selected = "\n".join(lines[span.start_line - 1:span.end_line])
                if not selected.strip() or any(
                    anchor not in selected for anchor in span.content_contains
                ):
                    raise ValueError(f"Missing source anchor: {case.case_id} {span.file_path}")
                display = {span.start_line, span.end_line}
                for anchor in span.content_contains:
                    for number in range(span.start_line, span.end_line + 1):
                        if anchor in lines[number - 1]:
                            display.update({number - 1, number, number + 1})
                numbers = sorted(number for number in display
                                 if span.start_line <= number <= span.end_line)
                excerpt_lines: list[str] = []
                previous = None
                for number in numbers:
                    if previous is not None and number > previous + 1:
                        excerpt_lines.append("… (intervening source lines omitted)")
                    source_line = lines[number - 1].rstrip()
                    excerpt_lines.append(
                        f"{number}: {source_line}" if source_line else f"{number}:"
                    )
                    previous = number
                excerpt = "\n".join(excerpt_lines)
                excerpts[case.case_id].append(excerpt)
    return excerpts


def _normalise(question: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", question.casefold()))


def leakage_warnings(cases: list[Candidate], dev_cases: list[dict]) -> dict[str, list[str]]:
    """Flag exact/near questions and overlapping gold; never auto-reject cases."""

    warnings: dict[str, list[str]] = {case.case_id: [] for case in cases}
    for case in cases:
        for dev in dev_cases:
            question = dev["question"]
            if case.question == question:
                warnings[case.case_id].append(f"Exact DEV question: {dev['case_id']}")
            elif _normalise(case.question) == _normalise(question):
                warnings[case.case_id].append(f"Normalised DEV question: {dev['case_id']}")
            elif SequenceMatcher(None, _normalise(case.question), _normalise(question)).ratio() >= .82:
                warnings[case.case_id].append(f"Possible paraphrase: {dev['case_id']}")
            for evidence in case.required_evidence:
                for span in evidence.acceptable_spans:
                    for old in dev.get("required_evidence", []):
                        for other in old["acceptable_spans"]:
                            shared_anchors = {
                                anchor for anchor in span.content_contains
                                if len(anchor) >= 8 and anchor in other.get("content_contains", [])
                            }
                            if shared_anchors:
                                warnings[case.case_id].append(
                                    f"DEV source-anchor overlap {dev['case_id']}: "
                                    + ", ".join(sorted(shared_anchors))
                                )
                            if span.file_path != other["file_path"]:
                                continue
                            overlap = min(span.end_line, other["end_line"]) - max(
                                span.start_line, other["start_line"]
                            ) + 1
                            if overlap > 0:
                                warnings[case.case_id].append(
                                    f"DEV span overlap {dev['case_id']}: {span.file_path} "
                                    f"lines {max(span.start_line, other['start_line'])}-"
                                    f"{min(span.end_line, other['end_line'])}"
                                )
    return {key: list(dict.fromkeys(value)) for key, value in warnings.items()}


def render_review(dataset: HoldoutCandidates, excerpts: dict[str, list[str]],
                  warnings: dict[str, list[str]]) -> str:
    """Make a review artifact, not a frozen/accepted evaluation dataset."""

    lines = [
        "# Holdout candidates — human review required", "",
        "Machine-prepared source-grounded holdout candidates pending human review.",
        "Do **not** run retrieval/evaluation on these questions before review and freeze.",
        f"Source revision: `{dataset.source_revision}`. Candidate hash: `{canonical_hash(dataset)}`.",
        "", "Choose ACCEPT, REJECT, or EDIT; record notes. No default acceptance is implied.", "",
    ]
    for case in dataset.cases:
        lines += [f"## {case.case_id} — {case.primary_category}", "",
                  f"**Question:** {case.question}", "",
                  f"**Answerable:** {'yes' if case.source_answerable else 'no'}", "",
                  f"**Expected-answer rubric:** {case.expected_answer}", ""]
        if case.missing_reason:
            lines += [f"**Why insufficient:** {case.missing_reason}", ""]
        excerpt_index = 0
        for evidence in case.required_evidence:
            lines += [f"**Required unit `{evidence.evidence_id}`:** {evidence.why_required}", ""]
            for span in evidence.acceptable_spans:
                lines += [f"Acceptable source: `{span.file_path}:{span.start_line}-{span.end_line}`", "",
                          "```text", excerpts[case.case_id][excerpt_index], "```", ""]
                excerpt_index += 1
        if warnings[case.case_id]:
            lines += ["**DEV leakage review flags:** " + "; ".join(warnings[case.case_id]), ""]
        else:
            lines += ["**DEV leakage review flags:** none detected automatically", ""]
        lines += ["Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT", "Notes: ____________________", ""]
    return "\n".join(lines)
