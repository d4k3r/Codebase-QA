"""Source-only DEV2 candidate validation and review diagnostics.

No retrieval, database, embedding inference, or provider calls belong here.
"""

from __future__ import annotations

import ast
import re
import subprocess
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel, Field, model_validator

from app.holdout import Candidate, Span, canonical_hash, validate_sources


OverlapLevel = Literal["NONE", "LOW", "MATERIAL"]


class Dev2Candidate(Candidate):
    """A source-grounded draft with explicit review and diagnostic fields."""

    dev1_overlap: OverlapLevel
    holdout_overlap: OverlapLevel
    multi_evidence_reason: str | None = None
    one_unit_sufficient: bool | None = None
    oversized_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_dev2_metadata(self) -> "Dev2Candidate":
        multi = len(self.required_evidence) >= 2
        if multi != bool(self.multi_evidence_reason):
            raise ValueError("Multi-evidence rationale must match evidence-unit count")
        if self.one_unit_sufficient is not (False if multi else None):
            raise ValueError("Multi-evidence cases must say one unit is insufficient")
        ids = {unit.evidence_id for unit in self.required_evidence}
        if len(self.oversized_evidence_ids) != len(set(self.oversized_evidence_ids)):
            raise ValueError("Oversized evidence IDs must be unique")
        if not set(self.oversized_evidence_ids) <= ids:
            raise ValueError("Oversized evidence IDs must name required evidence")
        return self


class Dev2Candidates(BaseModel):
    format_version: Literal[1]
    dataset_version: Literal["codebase-qa-v2-dev2-candidates-v1.0.0"]
    dataset_status: Literal[
        "Machine-prepared DEV2 candidate pending independent audit; NOT FROZEN; NOT SCORED."
    ]
    source_revision: Literal["7a3b7b05087793975ae0a84d85e7d691d9f3352e"]
    repository: Literal["codebase-qa-v2"]
    embedding_model: Literal["sentence-transformers/all-MiniLM-L6-v2"]
    effective_input_limit: Literal[256]
    cases: list[Dev2Candidate] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_cases(self) -> "Dev2Candidates":
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("DEV2 candidate IDs must be unique")
        return self


def load_dev2(path: Path) -> Dev2Candidates:
    return Dev2Candidates.model_validate_json(path.read_text(encoding="utf-8"))


def _normalise(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def overlap_diagnostics(
    cases: list[Dev2Candidate], reference: list[dict[str, object]]
) -> dict[str, tuple[OverlapLevel, list[str]]]:
    """Flag likely duplication; shared files alone are not overlap."""

    result: dict[str, tuple[OverlapLevel, list[str]]] = {}
    for case in cases:
        level: OverlapLevel = "NONE"
        warnings: list[str] = []
        for old in reference:
            old_question = str(old["question"])
            similarity = SequenceMatcher(
                None, _normalise(case.question), _normalise(old_question)
            ).ratio()
            matching_spans = []
            for unit in case.required_evidence:
                for span in unit.acceptable_spans:
                    for old_unit in old.get("required_evidence", []):
                        for old_span in old_unit["acceptable_spans"]:
                            if span.file_path != old_span["file_path"]:
                                continue
                            if min(span.end_line, old_span["end_line"]) >= max(
                                span.start_line, old_span["start_line"]
                            ):
                                matching_spans.append(span.file_path)
            exact = _normalise(case.question) == _normalise(old_question)
            if exact or similarity >= 0.90 or (matching_spans and similarity >= 0.75):
                level = "MATERIAL"
                warnings.append(
                    f"{old['case_id']}: likely same question/intent"
                    + (f"; overlapping {', '.join(sorted(set(matching_spans)))}" if matching_spans else "")
                )
            elif matching_spans or similarity >= 0.70:
                if level == "NONE":
                    level = "LOW"
                warnings.append(
                    f"{old['case_id']}: "
                    + (f"span overlap in {', '.join(sorted(set(matching_spans)))}" if matching_spans else f"question similarity {similarity:.2f}")
                )
        result[case.case_id] = level, warnings
    return result


def validate_overlap(
    dataset: Dev2Candidates, dev1: list[dict[str, object]], holdout: list[dict[str, object]]
) -> dict[str, dict[str, tuple[OverlapLevel, list[str]]]]:
    """Check recorded levels against both references and detect DEV2 duplicates."""

    diagnostics = {
        "DEV1": overlap_diagnostics(dataset.cases, dev1),
        "HOLDOUT": overlap_diagnostics(dataset.cases, holdout),
    }
    for case in dataset.cases:
        if case.dev1_overlap != diagnostics["DEV1"][case.case_id][0]:
            raise ValueError(f"DEV1 overlap classification mismatch: {case.case_id}")
        if case.holdout_overlap != diagnostics["HOLDOUT"][case.case_id][0]:
            raise ValueError(f"HOLDOUT overlap classification mismatch: {case.case_id}")
    for index, case in enumerate(dataset.cases):
        other = overlap_diagnostics([case], [
            previous.model_dump(mode="json") for previous in dataset.cases[:index]
        ])[case.case_id]
        if other[0] == "MATERIAL":
            raise ValueError(f"Likely duplicate DEV2 candidate intent: {case.case_id}")
    return diagnostics


def _source_text(root: Path, revision: str, file_path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{revision}:{file_path}"], cwd=root,
        capture_output=True, check=True,
    )
    return result.stdout.decode("utf-8")


def _symbol_source(span: Span, source: str) -> tuple[str, str, int] | None:
    """Locate a top-level accepted symbol containing an evidence span."""

    if not span.file_path.endswith(".py"):
        return None
    lines = source.splitlines(keepends=True)
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        if start <= span.start_line and node.end_lineno is not None and span.end_line <= node.end_lineno:
            return node.name, "".join(lines[start - 1 : node.end_lineno]), start
    return None


def validate_oversized(
    dataset: Dev2Candidates,
    root: Path,
    token_count: Callable[[str], int],
) -> dict[str, dict[str, list[str]]]:
    """Compare declared oversized units with frozen top-level symbol lengths.

    Config and module-companion spans cannot be classified by this symbol-only
    diagnostic; an unmarked unit containing those spans is not a shortness claim.
    """

    cache: dict[str, str] = {}
    result: dict[str, dict[str, list[str]]] = {}
    for case in dataset.cases:
        result[case.case_id] = {}
        for unit in case.required_evidence:
            descriptions: list[str] = []
            for span in unit.acceptable_spans:
                if span.file_path not in cache:
                    cache[span.file_path] = _source_text(
                        root, dataset.source_revision, span.file_path
                    )
                symbol = _symbol_source(span, cache[span.file_path])
                if symbol is None:
                    continue
                name, content, chunk_start = symbol
                count = token_count(content)
                if count > dataset.effective_input_limit:
                    prefix = "".join(
                        cache[span.file_path].splitlines(keepends=True)[
                            chunk_start - 1 : span.start_line - 1
                        ]
                    )
                    start_token = token_count(prefix)
                    descriptions.append(
                        f"{span.file_path}::{name}: {count} tokens "
                        f"> {dataset.effective_input_limit}; evidence begins near "
                        f"token {start_token}"
                    )
            if bool(descriptions) != (unit.evidence_id in case.oversized_evidence_ids):
                raise ValueError(
                    f"Oversized evidence annotation does not match frozen source: "
                    f"{case.case_id}/{unit.evidence_id}"
                )
            if descriptions:
                result[case.case_id][unit.evidence_id] = descriptions
    return result


def render_review(
    dataset: Dev2Candidates,
    excerpts: dict[str, list[str]],
    overlaps: dict[str, dict[str, tuple[OverlapLevel, list[str]]]],
    oversized: dict[str, dict[str, list[str]]],
) -> str:
    lines = [
        "# DEV2 candidates — independent audit required", "",
        "Machine-prepared DEV2 candidate pending independent audit; not frozen or scored.",
        f"Frozen source: `{dataset.source_revision}`. Candidate hash: `{canonical_hash(dataset)}`.",
        "DEV1 and the observed HOLDOUT remain unchanged. Do not score DEV2 before audit.", "",
        "Oversize checks count tokenizer tokens including special tokens against the accepted "
        "256-token embedding limit. They classify top-level Python symbol chunks; "
        "an unmarked config/companion span is not proven short.", "",
    ]
    for case in dataset.cases:
        lines += [
            f"## {case.case_id} — {case.primary_category}", "",
            f"Tags: {', '.join(case.secondary_tags) or 'none'}", "",
            f"Question: {case.question}", "",
            f"Answerable: {'yes' if case.source_answerable else 'no'}", "",
            f"Expected-answer rubric: {case.expected_answer}", "",
        ]
        if case.missing_reason:
            lines += [f"Why insufficient: {case.missing_reason}", ""]
        if case.multi_evidence_reason:
            lines += [
                f"Multi-evidence rationale ({len(case.required_evidence)} units): "
                f"{case.multi_evidence_reason}",
                "One unit alone sufficient: no", "",
            ]
        excerpt_index = 0
        for unit in case.required_evidence:
            lines += [f"Required `{unit.evidence_id}`: {unit.why_required}", ""]
            if unit.evidence_id in oversized[case.case_id]:
                lines += [
                    "Oversized accepted chunk: "
                    + "; ".join(oversized[case.case_id][unit.evidence_id]), "",
                ]
            for span in unit.acceptable_spans:
                lines += [
                    f"Acceptable source: `{span.file_path}:{span.start_line}-{span.end_line}`",
                    "", "```text", excerpts[case.case_id][excerpt_index], "```", "",
                ]
                excerpt_index += 1
        for cohort in ("DEV1", "HOLDOUT"):
            level, warnings = overlaps[cohort][case.case_id]
            lines += [
                f"{cohort} overlap: **{level}**"
                + (" — " + "; ".join(warnings) if warnings else " — none detected"),
                "",
            ]
        lines += ["Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT", "Notes: ____________________", ""]
    lines += [
        "## Candidate summary", "",
        f"Cases: {len(dataset.cases)}; answerable: {sum(c.source_answerable for c in dataset.cases)}; "
        f"multi-evidence: {sum(len(c.required_evidence) >= 2 for c in dataset.cases)}; "
        f"oversized-tagged: {sum(bool(c.oversized_evidence_ids) for c in dataset.cases)}.",
        f"Categories: {dict(Counter(c.primary_category for c in dataset.cases))}", "",
        f"Tags: {dict(Counter(tag for c in dataset.cases for tag in c.secondary_tags))}", "",
    ]
    return "\n".join(lines)


def validate_and_render(
    dataset: Dev2Candidates,
    root: Path,
    dev1: list[dict[str, object]],
    holdout: list[dict[str, object]],
    token_count: Callable[[str], int],
) -> tuple[str, dict[str, dict[str, tuple[OverlapLevel, list[str]]]]]:
    excerpts = validate_sources(dataset, root)
    overlaps = validate_overlap(dataset, dev1, holdout)
    oversized = validate_oversized(dataset, root, token_count)
    return render_review(dataset, excerpts, overlaps, oversized), overlaps
