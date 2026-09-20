"""Apply the approved source-only audit decisions and freeze two dataset splits.

No database, retrieval, embedding, context, or provider code is imported here.
The original 50-case candidate JSON is never modified.
"""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from app.config import PROJECT_ROOT
from app.holdout import (
    Candidate,
    Evidence,
    FrozenDataset,
    HoldoutCandidates,
    Span,
    canonical_hash,
    freeze_dataset,
    leakage_warnings,
    load_candidates,
    load_frozen,
    validate_sources,
)
from app.services.repository_loader import (
    EXCLUDED_DIRECTORIES,
    SUPPORTED_CONFIG_FILENAMES,
    SUPPORTED_CONFIG_SUFFIXES,
)
from scripts.prepare_holdout_review import CANDIDATES, DEV


PRIMARY_UNCHANGED = frozenset("""
identifier-01 identifier-02 identifier-04 identifier-05
config-01 config-03 config-04 config-05
path-03 path-05 route-02 route-05
architecture-04 architecture-05 near-01
unanswerable-01 unanswerable-02 unanswerable-03 unanswerable-05
""".split())
PRIMARY_EDITED = frozenset("""
semantic-02 semantic-03 semantic-04 route-03 architecture-03
cross-01 cross-02 cross-04 multi-01 multi-02 multi-03 multi-04
near-02 near-05 unanswerable-04
""".split())
COVERAGE = frozenset("semantic-05 path-01 path-02 cross-03 cross-05".split())
REJECTED = frozenset("""
semantic-01 identifier-03 config-02 path-04 route-01 route-04
architecture-01 architecture-02 multi-05 near-03 near-04
""".split())

EXPECTED_CANDIDATE_HASH = (
    "4b43650c5d60643d197fe33005823ce9c8f9570746d958dce0b845bf12ea88e7"
)
FROZEN_REVISION = "7a3b7b05087793975ae0a84d85e7d691d9f3352e"
INDEX_MANIFEST = "86aa6028950355c88b68d57bb3fc027be3e414acfb5a3ea45e3d2b341d70995b"
CHUNKING_IDENTIFIER = "python-ast-symbols-companions-config-text-v2"
PRIMARY_PATH = (
    PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_holdout_v1.json"
)
COVERAGE_PATH = (
    PROJECT_ROOT
    / "backend/evaluation/datasets/codebase_qa_v2_source_coverage_challenge_v1.json"
)


def span(file_path: str, start: int, end: int, *anchors: str) -> Span:
    return Span(
        file_path=file_path, start_line=start, end_line=end,
        content_contains=list(anchors),
    )


def unit(evidence_id: str, why: str, *spans: Span) -> Evidence:
    return Evidence(
        evidence_id=evidence_id, why_required=why, acceptable_spans=list(spans)
    )


def edit(case: Candidate, **changes: object) -> Candidate:
    """Revalidate rather than trusting model_copy's unchecked updates."""

    return Candidate.model_validate(case.model_dump(mode="json") | changes)


def audited_primary_edit(case: Candidate) -> Candidate:
    """Apply only the exact approved case edits, preserving stable IDs."""

    key = case.case_id.removeprefix("holdout-")
    if key == "semantic-02":
        return edit(
            case,
            question="How does the chunker find the opening line of a parenthesised decorator when the AST expression starts on a later line?",
            expected_answer="_decorator_start_line locates the decorator expression in the token stream, scans backward to the @ token, and returns that token's line.",
        )
    if key == "semantic-03":
        return edit(
            case,
            expected_answer="Consecutive top-level statements between supported definitions become a separate contiguous module_companion chunk, ending before the next supported definition.",
            required_evidence=[unit(
                "companion-flush",
                "Either the implementation or its source-slice test independently shows a separate contiguous companion region.",
                span("backend/app/services/chunker.py", 148, 194,
                     "companion_nodes.append(node)", "flush_companion()"),
                span("backend/tests/test_chunker.py", 111, 151,
                     '("module_companion", None, 8, 8)', "chunk.content =="),
            )],
        )
    if key == "semantic-04":
        return edit(
            case,
            expected_answer="chunk_config_file returns an empty chunk list when source.strip() is empty, so empty or whitespace-only files produce no searchable chunks.",
            required_evidence=[unit(
                "config-blank-guard",
                "Either the early return or its whitespace-only test establishes that no chunk is emitted.",
                span("backend/app/services/text_chunker.py", 46, 47,
                     "if not source.strip():", "return []"),
                span("backend/tests/test_text_chunker.py", 68, 72,
                     "chunk_config_file(path", "== []"),
            )],
        )
    if key == "route-03":
        return edit(
            case,
            required_evidence=[unit(
                "ask-provider-error-status",
                "Either the route branch or its HTTP test demonstrates status 502.",
                span("backend/app/api/routes.py", 113, 115,
                     "RAGGenerationError", "status_code=502"),
                span("backend/tests/test_api.py", 210, 224,
                     "RAGGenerationError", "response.status_code == 502"),
            )],
        )
    if key == "architecture-03":
        return edit(
            case,
            primary_category="semantic_conceptual",
            secondary_tags=["retrieval", "determinism", "tie-breaking"],
            expected_answer="Ordering uses cosine distance first, followed by repository, file path, start line, end line, symbol type, coalesced symbol name, and row ID. These secondary keys make ties deterministic for a fixed index snapshot.",
            required_evidence=[unit(
                "cosine-tie-order",
                "Either SQL ordering or its stable-order test proves the tie-breaking sequence.",
                span("backend/app/services/retrieval.py", 54, 63,
                     "distance,", "CodeChunk.file_path", "CodeChunk.id"),
                span("backend/tests/test_retrieval.py", 105, 125,
                     '"cosine_distance"', '"code_chunks.id"',
                     "assert positions == sorted(positions)"),
            )],
        )
    if key == "cross-01":
        return edit(
            case,
            question="Which environment variable and fallback URL configure the database engine, and how is the session factory connected to that engine?",
            expected_answer="Settings.database_url accepts DATABASE_URL, with fallback postgresql+psycopg://codebase_qa:codebase_qa@localhost:5432/codebase_qa. database.py passes the resolved setting to create_engine and binds SessionLocal to that engine.",
            required_evidence=[
                unit("database-url-setting", "Defines the alias and fallback URL.",
                     span("backend/app/config.py", 26, 29,
                          "DATABASE_URL", "postgresql+psycopg://codebase_qa:codebase_qa@localhost:5432/codebase_qa")),
                unit("database-engine-binding", "Shows the engine and session factory connection.",
                     span("backend/app/database.py", 11, 12,
                          "get_settings().database_url", "sessionmaker(bind=engine")),
            ],
        )
    if key == "cross-02":
        return edit(
            case,
            question="Which filename suffixes qualify as YAML configuration sources, and how does storage route those discovered files to the text chunker?",
            expected_answer=".yaml and .yml are in the configuration suffix allowlist. _load_chunks sends .py files to chunk_python_file and other discovered files, including these YAML files, to chunk_config_file.",
            required_evidence=[
                unit("yaml-allowlist", "Defines both YAML suffixes.",
                     span("backend/app/services/repository_loader.py", 19, 20,
                          '".yaml"', '".yml"')),
                unit("nonpython-dispatch", "Shows the Python versus config text dispatch.",
                     span("backend/app/services/storage.py", 36, 43,
                          'file_path.suffix == ".py"', "chunk_python_file", "chunk_config_file")),
            ],
        )
    if key == "cross-04":
        return edit(
            case,
            question="How are a chunk's path, line bounds, and source text represented in the parsed record and database model, and where does indexing copy them?",
            expected_answer="SourceChunk declares file_path and content as strings and start_line/end_line as integers. CodeChunk maps the corresponding fields to SQLAlchemy string, integer, and text columns. index_repository copies those values into each CodeChunk constructor.",
            required_evidence=[
                unit("parsed-provenance-fields", "Defines the parsed record types.",
                     span("backend/app/services/chunker.py", 21, 31,
                          "file_path: str", "start_line: int", "end_line: int", "content: str")),
                unit("orm-provenance-columns", "Defines corresponding persisted SQLAlchemy columns.",
                     span("backend/app/models.py", 12, 25,
                          "file_path:", "start_line:", "end_line:", "content:", "String", "Integer", "Text")),
                unit("row-provenance-copy", "Shows the parsed values copied into CodeChunk.",
                     span("backend/app/services/storage.py", 62, 74,
                          "file_path=chunk.file_path", "start_line=chunk.start_line",
                          "end_line=chunk.end_line", "content=chunk.content")),
            ],
        )
    return _audited_primary_edit_remaining(case, key)


def _audited_primary_edit_remaining(case: Candidate, key: str) -> Candidate:
    if key == "multi-01":
        return edit(
            case,
            question="Can a YAML file pass discovery's text check and still fail UTF-8 loading, and what part of the file does discovery screen for NUL bytes?",
            expected_answer="Discovery checks only the first 4,096 bytes for NUL bytes and UTF-8 decodability. Passing that sample does not ensure the rest of the file is valid UTF-8. The config chunker reads the complete file as UTF-8 and raises SourceReadError on decoding failure. NUL screening does not extend beyond the sample.",
            required_evidence=[
                unit("config-binary-screen", "Shows the sample-only NUL and UTF-8 checks.",
                     span("backend/app/services/repository_loader.py", 49, 63,
                          "read(4096)", 'b"\\x00"', 'sample.decode("utf-8")')),
                unit("config-text-read", "Shows the full-file UTF-8 read and failure class.",
                     span("backend/app/services/text_chunker.py", 39, 47,
                          'read_text(encoding="utf-8")', "SourceReadError")),
            ],
        )
    if key == "multi-02":
        return edit(
            case,
            question="How do HTTP search requests and direct search_code calls each handle a supplied whitespace-only repository scope, compared with omitting it?",
            expected_answer="SearchRequest binds repository to _normalise_repository_scope. The helper permits None, strips supplied strings, and rejects a blank result. search_code independently rejects supplied blank scope before embedding or SQL. Omitted scope remains None, so no repository predicate is added.",
            required_evidence=[
                unit("scope-normalisation", "Defines None-versus-blank behaviour.",
                     span("backend/app/schemas.py", 8, 14,
                          "if value is None:", "scope = value.strip()", "raise ValueError")),
                unit("search-request-binding", "Shows HTTP SearchRequest uses the helper.",
                     span("backend/app/schemas.py", 35, 40,
                          'field_validator("repository")', "_normalise_repository_scope")),
                unit("service-scope-filter", "Shows direct-call guard and conditional SQL predicate.",
                     span("backend/app/services/retrieval.py", 45, 53,
                          "Repository scope must not be blank", "if scope is not None:",
                          "CodeChunk.repository == scope")),
            ],
        )
    if key == "multi-03":
        return edit(
            case,
            question="Where are a missing LLM API key or model setting detected, and what HTTP status does /ask return?",
            expected_answer="The RAG configuration check requires both API key and model setting and raises LLMConfigurationError when either is missing. The ask route translates that exception into HTTP 503.",
            required_evidence=[
                unit("llm-required-config-check", "Detects missing required provider configuration.",
                     span("backend/app/services/rag.py", 70, 82,
                          "LLM_API_KEY", "LLM_MODEL_NAME", "LLMConfigurationError")),
                unit("llm-config-http-status", "Either route or HTTP test proves the 503 translation.",
                     span("backend/app/api/routes.py", 111, 112,
                          "LLMConfigurationError", "status_code=503"),
                     span("backend/tests/test_api.py", 121, 133,
                          "LLMConfigurationError", "response.status_code == 503")),
            ],
        )
    if key == "multi-04":
        return edit(
            case,
            question="What is the default search result count, and where are the configured default and an explicit top_k checked against the supported range?",
            expected_answer="DEFAULT_TOP_K falls back to 5 and settings validation restricts it to 1–50. search_code uses that default when top_k is omitted, otherwise the supplied value. It checks the resulting count against MAX_TOP_K=50 before embedding or SQL.",
            required_evidence=[
                unit("validated-top-k-setting", "Defines default 5 and settings range 1–50.",
                     span("backend/app/config.py", 35, 35,
                          "default=5", "ge=1", "le=50")),
                unit("max-top-k-service", "Defines the service maximum.",
                     span("backend/app/services/retrieval.py", 14, 14,
                          "MAX_TOP_K = 50")),
                unit("retrieval-default-and-limit", "Consumes/checks either configured or explicit count before embedding.",
                     span("backend/app/services/retrieval.py", 41, 49,
                          "get_settings().default_top_k", "top_k is None",
                          "not 1 <= limit <= MAX_TOP_K", "query_vector = embed_query")),
            ],
        )
    if key == "near-02":
        return edit(
            case,
            required_evidence=[unit(
                "source-path-versus-syntax",
                "One function shows the distinct path-safety and AST syntax failure branches.",
                span("backend/app/services/chunker.py", 109, 129,
                     "path.relative_to(root)", "outside repository root",
                     "ast.parse", "Invalid Python syntax"),
            )],
        )
    if key == "near-05":
        return edit(
            case,
            required_evidence=[
                unit("embedding-error-role", "Either declaration or embed call shows vector failure.",
                     span("backend/app/services/embeddings.py", 13, 14,
                          "class EmbeddingError", "expected embeddings"),
                     span("backend/app/services/embeddings.py", 48, 68,
                          "raise EmbeddingError", "model.encode")),
                unit("storage-error-role", "Either declaration or transaction failure shows storage failure.",
                     span("backend/app/services/storage.py", 17, 18,
                          "class StorageError", "cannot be stored"),
                     span("backend/app/services/storage.py", 76, 82,
                          "db.commit()", "raise StorageError")),
            ],
        )
    if key == "unanswerable-04":
        return edit(
            case,
            question="Where is a maximum indexed size per repository configured and enforced?",
            expected_answer="The frozen repository defines no per-repository byte, chunk-count, or storage-size quota or enforcement mechanism. top_k and the per-config-chunk character cap are not repository storage quotas.",
            missing_reason="No per-repository byte, chunk-count, or storage-size quota is configured or enforced in the frozen source; retrieval top_k and config chunk size are different limits.",
            secondary_tags=["quotas", "indexing", "not-implemented"],
        )
    raise ValueError(f"No audited primary edit for {key}")


def audited_coverage_edit(case: Candidate) -> Candidate:
    key = case.case_id.removeprefix("holdout-")
    if key == "semantic-05":
        return edit(
            case,
            question="How does the Answer component render answer text as Markdown?",
            expected_answer="It imports ReactMarkdown and passes answer as its children. The component does not explicitly inject raw HTML; this is not a broad sanitization guarantee.",
            required_evidence=[unit(
                "answer-markdown-component", "Shows the import and rendering path.",
                span("frontend/src/components/Answer.tsx", 1, 19,
                     'import ReactMarkdown from "react-markdown"', "<ReactMarkdown>{answer}</ReactMarkdown>"),
            )],
        )
    if key == "path-01":
        return edit(
            case,
            question="Which frontend source file issues the JSON POST /ask request?",
            expected_answer="frontend/src/api.ts, inside askQuestion, uses fetch('/ask') with POST, JSON content type, and a serialized request body.",
            required_evidence=[unit(
                "browser-ask-fetch", "The browser transport has the path, method, header, and JSON body.",
                span("frontend/src/api.ts", 40, 48,
                     'fetch("/ask"', 'method: "POST"', "application/json",
                     "JSON.stringify(request)"),
            )],
        )
    if key == "path-02":
        return case
    if key == "cross-03":
        return edit(
            case,
            question="How does the backend's declared /ask response schema compare with the browser's runtime checks for answer and source fields?",
            expected_answer="AskResponse declares an answer string and RetrievedChunkResponse sources. The browser checks the envelope and source fields, including nullable symbol name and numeric line/distance values. Browser numeric checks do not establish integer lines or valid line ordering.",
            required_evidence=[
                unit("backend-source-contract", "Declares the source record fields.",
                     span("backend/app/schemas.py", 43, 51,
                          "class RetrievedChunkResponse", "symbol_name: str | None",
                          "start_line: int", "cosine_distance: float")),
                unit("backend-answer-contract", "Declares answer plus source list.",
                     span("backend/app/schemas.py", 66, 68,
                          "class AskResponse", "sources: list[RetrievedChunkResponse]")),
                unit("browser-runtime-guard", "Shows browser runtime checks and their numeric-only limit.",
                     span("frontend/src/api.ts", 3, 31,
                          "isRetrievedSource", "typeof value.start_line === \"number\"",
                          "typeof value.cosine_distance === \"number\"",
                          "value.sources.every")),
            ],
        )
    if key == "cross-05":
        return edit(
            case,
            question="What checks do the form and page use to block blank submissions and submissions while a request is marked as loading?",
            expected_answer="The form checks trimmed emptiness/loading before invoking submission and disables its button. The page rechecks trimmed text/loading and sets loading before awaiting the request. This does not prove an unconditional concurrency guarantee.",
            required_evidence=[
                unit("form-submit-guard", "Shows the form checks and disabled state.",
                     span("frontend/src/components/QuestionForm.tsx", 16, 40,
                          "question.trim()", "!isLoading && !isEmpty",
                          "disabled={isLoading || isEmpty}")),
                unit("page-submit-guard", "Shows the page rechecks and sets loading.",
                     span("frontend/src/App.tsx", 15, 54,
                          "question.trim()", "isLoading", "setIsLoading(true)",
                          "await askQuestion")),
            ],
        )
    raise ValueError(f"No audited coverage edit for {key}")


def _accepted_source_path(file_path: str) -> bool:
    path = Path(file_path)
    if any(part in EXCLUDED_DIRECTORIES for part in path.parts):
        return False
    return (
        path.suffix == ".py"
        or path.suffix.lower() in SUPPORTED_CONFIG_SUFFIXES
        or path.name in SUPPORTED_CONFIG_FILENAMES
    ) and path.name != ".env"


def build_splits() -> tuple[FrozenDataset, FrozenDataset]:
    """Reproduce the exact audited split, then source-validate both cohorts."""

    candidates: HoldoutCandidates = load_candidates(CANDIDATES)
    if (canonical_hash(candidates) != EXPECTED_CANDIDATE_HASH
            or candidates.source_revision != FROZEN_REVISION):
        raise ValueError("Candidate pool identity or source revision changed")
    if hashlib.sha256(DEV.read_bytes()).hexdigest() != (
        "098017b14aed9a4433051ddc92812292ee8d2cdec0268ea94c7c47404e193b17"
    ):
        raise ValueError("DEV dataset changed")
    all_decisions = PRIMARY_UNCHANGED | PRIMARY_EDITED | COVERAGE | REJECTED
    if sum(map(len, (PRIMARY_UNCHANGED, PRIMARY_EDITED, COVERAGE, REJECTED))) != 50:
        raise ValueError("Audit decisions overlap")
    if {case.case_id.removeprefix("holdout-") for case in candidates.cases} != all_decisions:
        raise ValueError("Audit decisions do not partition candidate pool")

    primary_cases: list[Candidate] = []
    coverage_cases: list[Candidate] = []
    for case in candidates.cases:
        key = case.case_id.removeprefix("holdout-")
        if key in PRIMARY_UNCHANGED:
            primary_cases.append(case)
        elif key in PRIMARY_EDITED:
            primary_cases.append(audited_primary_edit(case))
        elif key in COVERAGE:
            coverage_cases.append(audited_coverage_edit(case))

    if len(primary_cases) != 34 or len(coverage_cases) != 5:
        raise ValueError("Incorrect audited split size")
    if sum(case.source_answerable for case in primary_cases) != 29:
        raise ValueError("Primary answerability differs from audit")
    if sum(len(case.required_evidence) >= 2 for case in primary_cases) != 8:
        raise ValueError("Primary multi-evidence count differs from audit")
    for case in primary_cases:
        if not all(
            _accepted_source_path(span.file_path)
            for evidence in case.required_evidence
            for span in evidence.acceptable_spans
        ):
            raise ValueError(f"Unsupported primary source: {case.case_id}")
    for case in coverage_cases:
        if not any(
            not _accepted_source_path(span.file_path)
            for evidence in case.required_evidence
            for span in evidence.acceptable_spans
        ):
            raise ValueError(f"Coverage case lacks unsupported source: {case.case_id}")

    dev_cases = json.loads(DEV.read_text(encoding="utf-8"))["cases"]
    warnings = leakage_warnings(primary_cases, dev_cases)
    if any(
        warning.startswith(("Exact DEV question", "Normalised DEV question", "Possible paraphrase"))
        for flags in warnings.values() for warning in flags
    ):
        raise ValueError("A primary question appears to duplicate DEV")
    # Broader span/anchor warnings on accepted cases were reviewed by the
    # independent audit. They are not silently converted to automatic rejects.

    primary = freeze_dataset(
        candidates, primary_cases, cohort="primary",
        dataset_version="codebase-qa-v2-holdout-v1.0.0",
        index_manifest_sha256=INDEX_MANIFEST,
        expected_chunk_count=212,
        chunking_identifier=CHUNKING_IDENTIFIER,
    )
    coverage = freeze_dataset(
        candidates, coverage_cases, cohort="source_coverage_challenge",
        dataset_version="codebase-qa-v2-source-coverage-challenge-v1.0.0",
        index_manifest_sha256=INDEX_MANIFEST,
        expected_chunk_count=212,
        chunking_identifier=CHUNKING_IDENTIFIER,
    )
    validate_sources(primary, PROJECT_ROOT)
    validate_sources(coverage, PROJECT_ROOT)
    return primary, coverage


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Validate checked-in frozen files without writing them.",
    )
    args = parser.parse_args()
    primary, coverage = build_splits()
    for path, dataset in ((PRIMARY_PATH, primary), (COVERAGE_PATH, coverage)):
        if args.check:
            existing = load_frozen(path)
            if existing.model_dump(mode="json") != dataset.model_dump(mode="json"):
                parser.error(f"Frozen dataset differs from audited decisions: {path}")
        else:
            path.write_text(dataset.model_dump_json(indent=2) + "\n", encoding="utf-8")
        print(
            f"{dataset.cohort}: {dataset.case_count} cases, "
            f"hash {dataset.dataset_hash}, case-set {dataset.case_set_hash}: {path}"
        )


if __name__ == "__main__":
    main()
