"""Apply the independent DEV2 audit to the unchanged candidate pool.

This is source-only dataset preparation: no database, retrieval, inference, or
provider calls. Run with --check to compare the checked-in final dataset.
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from app.config import PROJECT_ROOT
from app.dev2 import (
    Dev2Candidate, FinalDev2, _hash_json, _symbol_source, load_dev2,
    load_final_dev2,
)
from app.holdout import Evidence, Span, canonical_hash, validate_sources
from app.services.chunker import chunk_python_file
from app.services.repository_loader import SUPPORTED_CONFIG_FILENAMES, SUPPORTED_CONFIG_SUFFIXES
from app.services.text_chunker import chunk_config_file


CANDIDATES = PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_dev2_candidates_v1.json"
FINAL = PROJECT_ROOT / "backend/evaluation/datasets/codebase_qa_v2_dev2_v1.json"
AUDIT = PROJECT_ROOT / "docs/dev2-audit.md"
SOURCE_REVISION = "7a3b7b05087793975ae0a84d85e7d691d9f3352e"
CANDIDATE_HASH = "4ed6388ba299dbf7ae9dbbbca01d72cf46b4520dd26895605732d88463a872d6"
AUDIT_RAW_SHA256 = "cca706bd0b1fbf1688eff6e2a2c34ae07b2d3078a24aac08430dfea31c4dfca4"
INDEX_MANIFEST = "86aa6028950355c88b68d57bb3fc027be3e414acfb5a3ea45e3d2b341d70995b"
CHUNKING_IDENTIFIER = "python-ast-symbols-companions-config-text-v2"
ACCEPT = frozenset("dev2-semantic-01 dev2-long-04 dev2-mixed-01".split())
REJECT = frozenset("""dev2-multi-06 dev2-architecture-04 dev2-near-01
dev2-long-02 dev2-long-03 dev2-mixed-02 dev2-ordinary-03""".split())
LONG = frozenset("""dev2-multi-02 dev2-multi-03 dev2-multi-04 dev2-multi-07
dev2-multi-08 dev2-architecture-03 dev2-semantic-02 dev2-semantic-03
dev2-semantic-05 dev2-semantic-06 dev2-exact-04 dev2-long-01 dev2-long-04
dev2-long-05 dev2-mixed-03 dev2-mixed-05""".split())
DEV1_NONE = frozenset("""dev2-multi-01 dev2-architecture-01 dev2-architecture-02
dev2-architecture-03 dev2-architecture-05 dev2-architecture-06 dev2-semantic-03
dev2-semantic-06 dev2-exact-01 dev2-exact-02 dev2-exact-03 dev2-exact-05
dev2-near-05 dev2-long-01 dev2-long-05 dev2-mixed-04 dev2-ordinary-02
dev2-unanswerable-01""".split())
HOLDOUT_NONE = frozenset("""dev2-multi-05 dev2-architecture-01
dev2-architecture-02 dev2-architecture-03 dev2-architecture-05
dev2-architecture-06 dev2-semantic-01 dev2-semantic-02 dev2-semantic-03
dev2-semantic-06 dev2-exact-01 dev2-exact-02
dev2-exact-03 dev2-exact-04 dev2-exact-05 dev2-near-04 dev2-long-01
dev2-long-04 dev2-long-05 dev2-mixed-01 dev2-mixed-04 dev2-ordinary-02
dev2-unanswerable-02""".split())

L = "backend/app/services/repository_loader.py"
C = "backend/app/services/chunker.py"
T = "backend/app/services/text_chunker.py"
S = "backend/app/services/storage.py"
B = "backend/app/services/embeddings.py"
G = "backend/app/services/rag.py"
R = "backend/app/services/retrieval.py"
CFG = "backend/app/config.py"
API = "backend/app/api/routes.py"
SCH = "backend/app/schemas.py"
EV = "backend/app/evaluation.py"


def span(path: str, start: int, end: int, *anchors: str) -> dict:
    return Span(file_path=path, start_line=start, end_line=end,
                content_contains=list(anchors)).model_dump(mode="json")


def unit(evidence_id: str, why: str, *spans: dict) -> dict:
    return Evidence(evidence_id=evidence_id, why_required=why,
                    acceptable_spans=[Span.model_validate(s) for s in spans]).model_dump(mode="json")


def existing(raw: dict, evidence_id: str) -> dict:
    return next(e for e in raw["required_evidence"] if e["evidence_id"] == evidence_id)


def relocate(raw: dict, evidence_id: str, path: str, start: int, end: int,
             *anchors: str, alternative: dict | None = None) -> None:
    evidence = existing(raw, evidence_id)
    evidence["acceptable_spans"] = [span(path, start, end, *anchors)]
    if alternative is not None:
        evidence["acceptable_spans"].append(alternative)


def _edit(raw: dict) -> None:
    """Exact per-case edits from docs/dev2-audit.md; unmentioned fields stay put."""

    key = raw["case_id"]
    if key == "dev2-multi-01":
        raw["primary_category"] = "semantic_conceptual"
        relocate(raw, "entry-no-follow", L, 73, 109,
                 "resolve_repository_root(repository_path)",
                 "is_dir(follow_symlinks=False)", "is_file(follow_symlinks=False)",
                 "visit(root)")
    elif key == "dev2-multi-02":
        raw["question"] = "Do `python_files_discovered` and `rows_stored` count the same thing when indexing includes configuration files?"
        raw["expected_answer"] = "No. `python_files_discovered` counts discovered paths whose suffix is `.py`. `rows_stored` counts prepared database rows, with one row constructed per prepared chunk, including chunks from configuration sources. Neither statistic is a count of all discovered files."
        raw["primary_category"] = "semantic_conceptual"
        raw["required_evidence"] = [unit("index-count-semantics",
            "The row-building loop and both counters establish their distinct meanings.",
            span(S, 55, 89, "for chunk, embedding in zip(chunks, vectors, strict=True)",
                 "python_files_discovered=sum", "rows_stored=len(rows)"))]
    elif key == "dev2-multi-03":
        relocate(raw, "assignment-fallback", C, 131, 146,
                 "if not symbol_nodes and tree.body", 'symbol_type="module"')
        relocate(raw, "fallback-publication", S, 55, 79,
                 "embed_texts([chunk.content for chunk in chunks])", "embedding=embedding", "db.commit()")
    elif key == "dev2-multi-04":
        relocate(raw, "storage-http-error", API, 76, 78,
                 "StorageError", "status_code=500",
                 alternative=span("backend/tests/test_api.py", 136, 155,
                                  "StorageError", "response.status_code == 500"))
        raw["secondary_tags"] = ["boundary_crossing" if tag == "early_source" else tag
                                 for tag in raw["secondary_tags"]]
    elif key == "dev2-multi-05":
        raw["question"] = "Which environment variable controls the FastAPI title, and where is that setting applied?"
        raw["expected_answer"] = "`APP_NAME` populates `Settings.app_name`; `main.py` passes `get_settings().app_name` as the FastAPI title."
        relocate(raw, "app-name-setting", CFG, 30, 30, 'validation_alias="APP_NAME"',
                 alternative=span(".env.example", 4, 5, "APP_NAME=Codebase QA V2"))
    elif key == "dev2-multi-07":
        raw["required_evidence"].append(unit("python-chunker-dispatch",
            "Storage dispatches admitted .py paths to the Python chunker, not the config chunker.",
            span(S, 36, 43, 'file_path.suffix == ".py"', "chunk_python_file")))
    elif key == "dev2-multi-08":
        raw["question"] = "If a completion has no choices or empty answer content, how does `/ask` report the failure?"
        raw["expected_answer"] = "An empty choices list triggers the missing-answer `RAGGenerationError`; falsy message content triggers the separate empty-answer `RAGGenerationError`. The `/ask` route translates either into HTTP 502 with the generic detail `LLM generation failed.`"
        relocate(raw, "generation-http-status", API, 113, 115,
                 "RAGGenerationError", "status_code=502",
                 alternative=span("backend/tests/test_api.py", 210, 224,
                                  "RAGGenerationError", "response.status_code == 502"))
        raw["secondary_tags"].remove("across_long_chunks")
    elif key == "dev2-architecture-01":
        raw["expected_answer"] = "Preparation requires `--confirm-write`, compares it with the expected confirmation constant, and rejects a mismatch before calling `index_repository`. The scorer marks its transaction read-only before calling `evaluate_dataset`."
        relocate(raw, "write-gate", "backend/scripts/prepare_evaluation_corpus.py", 13, 30,
                 "--confirm-write", "args.confirm_write != CONFIRMATION", "index_repository")
    elif key == "dev2-architecture-02":
        raw["primary_category"] = "semantic_conceptual"
        raw["expected_answer"] = "For the same ordered source records, `compute_index_manifest` hashes repository, path, symbol metadata, line bounds and content, while excluding row IDs and vectors. Changing only those excluded values leaves the manifest unchanged."
        relocate(raw, "manifest-record-fields", EV, 206, 224,
                 '"repository": chunk.repository', '"content": chunk.content')
    elif key == "dev2-architecture-03":
        raw["expected_answer"] = "Before iterating over cases and calling search, evaluation validates repository scope, nonempty corpus rows, expected chunk count, manifest hash and chunking identifier. Blank corpus scope raises `EvaluationError`; the listed corpus mismatches raise `CorpusManifestMismatch`."
        raw["required_evidence"].append(unit("evaluation-preflight-order",
            "The caller validates the corpus before entering the search loop.",
            span(EV, 529, 544, "validate_corpus_manifest", "for case in dataset.cases", "search_code")))
    elif key == "dev2-architecture-05":
        raw["primary_category"] = "configuration_constants"
        raw["required_evidence"] = [
            unit("env-path-definition", "Defines the project-relative .env path.",
                 span(CFG, 11, 12, "Path(__file__).resolve().parents[2]", "ENV_FILE")),
            unit("settings-env-path", "Settings uses that resolved path, independent of cwd.",
                 span(CFG, 18, 24, "env_file=ENV_FILE"),
                 span("backend/tests/test_config.py", 9, 13, "ENV_FILE")),
        ]
    elif key == "dev2-architecture-06":
        raw["question"] = "How does dataset validation reject cases assigned to a different repository from the declared corpus?"
        raw["expected_answer"] = "`EvaluationDataset.validate_cases` compares each case's repository with the corpus repository and raises `ValueError` listing mismatched case IDs."
        raw["primary_category"] = "semantic_conceptual"
    elif key == "dev2-semantic-02":
        raw["question"] = "When no retrieved chunk fits the context budget, does answer generation stop or still call the provider, and with what context?"
        raw["expected_answer"] = "With valid configuration and successful retrieval, `build_context` returns `No repository context was retrieved.` and an empty included-chunk list. `answer_question` still constructs the prompt and calls the provider; there is no early return for this no-fitting-context condition."
        raw["primary_category"] = "architecture"
        raw["required_evidence"] = [
            unit("empty-context-construction", "Shows the placeholder and empty included set.",
                 span(G, 42, 67, "No repository context was retrieved.", "included_chunks=included_chunks")),
            unit("provider-continuation", "Shows prompt/client call continues after context building.",
                 span(G, 119, 130, "build_context", "client.chat.completions.create")),
        ]
    elif key == "dev2-semantic-03":
        raw["question"] = "How does discovery guarantee repository-relative POSIX path ordering, rather than merely the order produced by walking each directory?"
        raw["expected_answer"] = "After traversal, it sorts the collected paths using `path.relative_to(root).as_posix()` as the key."
        relocate(raw, "relative-source-sort", L, 107, 109,
                 "path.relative_to(root).as_posix()")
    elif key == "dev2-semantic-04":
        raw["question"] = "Where is each encoded vector checked for dimensionality, and how is that check enforced before batch embeddings are returned?"
        raw["expected_answer"] = "`_validate_vectors` checks every vector against `EMBEDDING_DIMENSION` and raises `EmbeddingError` on a mismatch. `embed_texts` invokes this validator before returning the encoded batch."
        relocate(raw, "validator-called-before-return", B, 48, 68,
                 "_validate_vectors(vectors)", "return vectors")
    elif key == "dev2-semantic-05":
        relocate(raw, "fallback-body-guard", C, 131, 194,
                 "if not symbol_nodes and tree.body and source.strip():", "return chunks")
    elif key == "dev2-semantic-06":
        raw["question"] = "How does config chunking preserve original blank/comment lines, and when can a whitespace-only group be dropped?"
        raw["expected_answer"] = "Line pieces preserve original characters, including line endings, and emitted groups join those pieces without reconstructing text. Comments are non-whitespace and are retained in emitted groups. An entirely whitespace-only file produces no chunks, and a pending group containing only whitespace is discarded when flushed; therefore not every blank character is guaranteed to survive independently of chunk boundaries."
        raw["required_evidence"] = [
            unit("original-line-pieces", "Shows exact line characters and line endings are retained.",
                 span(T, 11, 22, "splitlines(keepends=True)", "line")),
            unit("whitespace-group-flush", "Shows blank-file and pending-group filtering, plus original-text join.",
                 span(T, 46, 76, "if not source.strip():", "content=\"\".join",
                      'if pending and "".join(text for _, text in pending).strip()')),
        ]
    elif key == "dev2-exact-01":
        raw["question"] = "Which constant controls the `batch_size` passed to `model.encode`, and what is its value?"
        raw["expected_answer"] = "`DEFAULT_BATCH_SIZE` is 32, and `embed_texts` supplies that constant as `model.encode`'s `batch_size`."
        relocate(raw, "batch-size-definition", B, 9, 10, "DEFAULT_BATCH_SIZE = 32",
                 alternative=span("backend/tests/test_embeddings.py", 26, 35, "batch_size"))
    elif key == "dev2-exact-02":
        pass  # HOLDOUT overlap corrected below.
    elif key == "dev2-exact-03":
        raw["question"] = "What command is configured under Compose's `healthcheck.test`, and which database/user does it probe?"
        raw["expected_answer"] = "The `CMD-SHELL` healthcheck invokes `pg_isready` using the configured `POSTGRES_USER` and `POSTGRES_DB`."
        relocate(raw, "postgres-healthcheck", "docker-compose.yml", 13, 17,
                 "CMD-SHELL", "pg_isready", "POSTGRES_USER", "POSTGRES_DB")
    elif key == "dev2-exact-04":
        raw["question"] = "What values does Settings allow for `LLM_MAX_RETRIES`, including the default and maximum?"
        raw["expected_answer"] = "An integer from 0 through 5 inclusive; the default is 2."
    elif key == "dev2-exact-05":
        raw["expected_answer"] = "An async top-level function receives the structural label `async_function`."
        relocate(raw, "async-symbol-label", C, 34, 39,
                 "ast.AsyncFunctionDef", 'return "async_function"',
                 alternative=span("backend/tests/test_chunker.py", 36, 45,
                                  "async_function"))
    elif key == "dev2-near-02":
        pass  # DEV1 overlap corrected below.
    elif key == "dev2-near-03":
        raw["expected_answer"] = "Yes. With an otherwise valid request, an empty query fails `SearchRequest`'s minimum-length constraint. A whitespace-only query satisfies that length constraint, is forwarded through the search route and `search_code`, and is rejected when `embed_query` strips it."
        raw["required_evidence"] = [
            unit("search-schema-min-length", "An empty string fails HTTP request validation.",
                 span(SCH, 35, 40, "query: str = Field(min_length=1)")),
            unit("search-route-forwarding", "The route forwards the query to the service.",
                 span(API, 82, 90, "search_code", "request.query")),
            unit("search-service-embedding", "The service passes query text to embedding after scope checks.",
                 span(R, 33, 49, "embed_query", "query")),
            unit("embedding-whitespace-guard", "The embedder strips and rejects whitespace-only text.",
                 span(B, 71, 76, "if not query.strip()", "Query must not be empty")),
        ]
    elif key == "dev2-near-04":
        relocate(raw, "distinct-read-http-details", API, 64, 73,
                 "RepositoryReadError", "SourceReadError", "repository directories.",
                 "repository source files.",
                 alternative=span("backend/tests/test_api.py", 158, 190,
                                  "repository directories.", "repository source files.",
                                  "status_code"))
    elif key == "dev2-near-05":
        pass  # DEV1 overlap corrected below.
    elif key == "dev2-long-01":
        pass  # HOLDOUT overlap corrected below.
    elif key == "dev2-long-05":
        raw["question"] = "What metadata can I use to reproduce an evaluation run and identify its source/model configuration?"
        raw["expected_answer"] = "The report records dataset identity/status and hashes, case-set hash, corpus manifest and pinned source revision, repository, application Git revision/dirty status, embedding identity/dimension, resolved model revision and effective limit when available, chunking identifier, candidate depth, context budget and package versions."
        raw["primary_category"] = "semantic_conceptual"
        relocate(raw, "report-reproducibility-fields", EV, 612, 634,
                 '"reproducibility"', '"case_set_sha256"', '"chunking_identifier"')
    elif key == "dev2-mixed-03":
        raw["question"] = "For an unauthenticated local OpenAI-compatible server, how does `LLM_API_KEY` get from the documented placeholder setting into the created client?"
        raw["expected_answer"] = "The example instructs the operator to use the placeholder accepted by that server. `LLM_API_KEY` populates `Settings.llm_api_key`; `_required_llm_config` extracts and strips it; `answer_question` passes the resulting key to `_create_client`; that helper supplies it as the OpenAI client's `api_key` option."
        raw["required_evidence"] = [
            unit("placeholder-key-guidance", "Documents the local-server placeholder instruction.",
                 span(".env.example", 9, 13, "placeholder API key", "LLM_API_KEY=")),
            unit("llm-api-key-setting", "Maps LLM_API_KEY into Settings.",
                 span(CFG, 37, 37, 'validation_alias="LLM_API_KEY"')),
            unit("required-key-extraction", "Validates and strips the key.",
                 span(G, 70, 82, "settings.llm_api_key", "api_key")),
            unit("client-handoff", "Passes the extracted key to _create_client.",
                 span(G, 107, 122, "api_key", "_create_client")),
            unit("client-key-option", "Supplies the key as the OpenAI client option.",
                 span(G, 85, 93, '"api_key": api_key', "OpenAI(**options)")),
        ]
    elif key == "dev2-mixed-04":
        raw["secondary_tags"].remove("mixed_semantic_exact")
    elif key == "dev2-mixed-05":
        raw["expected_answer"] = "A supplied nonblank repository becomes a SQL equality predicate. The service executes that scoped query and returns its rows; zero matching rows do not trigger an unscoped retry."
        relocate(raw, "scoped-sql-predicate", R, 45, 82,
                 "statement.where(CodeChunk.repository == scope)", "db.execute(statement)",
                 alternative=span("backend/tests/test_retrieval.py", 67, 78,
                                  "unknown", "assert"))
        raw["secondary_tags"].remove("mixed_semantic_exact")
    elif key == "dev2-ordinary-01":
        raw["expected_answer"] = "No. The accepted policy emits top-level classes as class chunks; their methods remain inside those class chunks rather than becoming separate chunks."
        relocate(raw, "top-level-only-loop", C, 131, 190,
                 "tree.body", "ast.ClassDef", "symbol_type=_symbol_type(node)",
                 alternative=span("backend/tests/test_chunker.py", 10, 33,
                                  '"def multiply" in chunks[2].content',
                                  'chunk.symbol_name != "multiply"'))
    elif key == "dev2-ordinary-02":
        pass  # DEV1 overlap corrected below.
    elif key == "dev2-unanswerable-01":
        pass  # HOLDOUT overlap corrected below.
    elif key == "dev2-unanswerable-02":
        pass  # DEV1 overlap corrected below.
    else:
        raise ValueError(f"Audit edit missing for {key}")


MULTI_RATIONALES = {
    "dev2-multi-01": "Root normalization and the caller's no-follow entry classification establish different halves of the contrast; neither alone suffices.",
    "dev2-multi-03": "Chunker's fallback representation and storage's committed publication are separate necessary steps.",
    "dev2-multi-04": "Storage's before-delete mismatch guard and the HTTP translation answer different halves of the question.",
    "dev2-multi-05": "The environment alias and FastAPI construction are independently needed to connect configuration to title.",
    "dev2-multi-07": "Sampling, config-only admission, Python dispatch, and complete Python reading establish the two paths together.",
    "dev2-multi-08": "Completion-shape failure creation and HTTP translation are separate required facts.",
    "dev2-architecture-01": "The write-gated preparer and read-only scorer are separate entry points with different database permissions.",
    "dev2-architecture-03": "The validator's checks and its invocation before the case-search loop are both necessary.",
    "dev2-architecture-05": "The project-relative path definition and its use by Settings are separate accepted source chunks.",
    "dev2-semantic-02": "The no-fitting-context return and the later provider-call continuation are separate necessary facts.",
    "dev2-semantic-04": "The dimension guard and embed_texts calling it before return are separate necessary facts.",
    "dev2-semantic-06": "Line-piece preservation and group-level whitespace filtering jointly answer the qualified behaviour.",
    "dev2-exact-01": "The constant's value and its separate use in model.encode are both needed.",
    "dev2-near-03": "Schema, route, service, and embedder stages together establish the contrasting validation boundaries.",
    "dev2-mixed-01": "Request declaration, route forwarding, and RAG service forwarding all establish scope propagation.",
    "dev2-mixed-03": "Documentation, Settings binding, validation, handoff, and client construction each supply a distinct step.",
}


def audited_cases() -> tuple[dict, list[Dev2Candidate]]:
    source = load_dev2(CANDIDATES)
    if canonical_hash(source) != CANDIDATE_HASH or source.source_revision != SOURCE_REVISION:
        raise ValueError("Original DEV2 candidate identity changed")
    if not AUDIT.is_file() or hashlib.sha256(AUDIT.read_bytes()).hexdigest() != AUDIT_RAW_SHA256:
        raise ValueError("Independent DEV2 audit report identity changed")
    ids = {case.case_id for case in source.cases}
    if len(ids) != 45 or not ACCEPT <= ids or not REJECT <= ids:
        raise ValueError("Audited candidate decision list does not match source")
    cases: list[Dev2Candidate] = []
    for case in source.cases:
        if case.case_id in REJECT:
            continue
        raw = case.model_dump(mode="json")
        if case.case_id not in ACCEPT:
            _edit(raw)
            raw["dev1_overlap"] = "NONE" if case.case_id in DEV1_NONE else "LOW"
            raw["holdout_overlap"] = "NONE" if case.case_id in HOLDOUT_NONE else "LOW"
            tags = [tag for tag in raw["secondary_tags"] if tag not in {"multi_evidence", "long_chunk"}]
            if len(raw["required_evidence"]) >= 2:
                tags.append("multi_evidence")
                raw["multi_evidence_reason"] = MULTI_RATIONALES[case.case_id]
                raw["one_unit_sufficient"] = False
            else:
                raw["multi_evidence_reason"] = None
                raw["one_unit_sufficient"] = None
            if case.case_id in LONG:
                tags.append("long_chunk")
            raw["secondary_tags"] = tags
            # Recomputed below from the frozen source; distinct from the
            # audit's meaningful-late `long_chunk` judgement.
            raw["oversized_evidence_ids"] = []
        cases.append(Dev2Candidate.model_validate(raw))
    if len(cases) != 38 or set(MULTI_RATIONALES) != {
        case.case_id for case in cases if len(case.required_evidence) >= 2
    }:
        raise ValueError("Audited DEV2 case/multi-evidence decisions disagree")
    return source.model_dump(mode="json", exclude={"cases"}), cases


def _annotate_physical_oversize(cases: list[Dev2Candidate]) -> list[Dev2Candidate]:
    """Offline tokenizer/source check only; no embedding inference."""
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(
        "sentence-transformers/all-MiniLM-L6-v2", local_files_only=True
    )
    frozen_sources: dict[str, str] = {}
    result: list[Dev2Candidate] = []
    for case in cases:
        oversized: list[str] = []
        for evidence in case.required_evidence:
            for alternative in evidence.acceptable_spans:
                path = alternative.file_path
                if path not in frozen_sources:
                    frozen_sources[path] = subprocess.run(
                        ["git", "show", f"{SOURCE_REVISION}:{path}"], cwd=PROJECT_ROOT,
                        check=True, capture_output=True,
                    ).stdout.decode("utf-8")
                symbol = _symbol_source(alternative, frozen_sources[path])
                if symbol and len(tokenizer(symbol[1], add_special_tokens=True,
                                            truncation=False, verbose=False)["input_ids"]) > 256:
                    oversized.append(evidence.evidence_id)
                    break
        raw = case.model_dump(mode="json")
        raw["oversized_evidence_ids"] = oversized
        result.append(Dev2Candidate.model_validate(raw))
    return result


def validate_accepted_chunk_containment(cases: list[Dev2Candidate]) -> None:
    """Check every alternative against the actual accepted Batch 2A chunkers.

    Only frozen Git source is staged in a temporary directory. No indexing,
    embedding, database write, or retrieval is performed.
    """

    paths = {span.file_path for case in cases for evidence in case.required_evidence
             for span in evidence.acceptable_spans}
    with tempfile.TemporaryDirectory(prefix="dev2-frozen-source-") as directory:
        root = Path(directory)
        chunks_by_path = {}
        lines_by_path = {}
        for relative in sorted(paths):
            name = Path(relative)
            if not (relative.endswith(".py") or name.name in SUPPORTED_CONFIG_FILENAMES
                    or name.suffix.lower() in SUPPORTED_CONFIG_SUFFIXES):
                raise ValueError(f"Unsupported accepted source type: {relative}")
            source = subprocess.run(
                ["git", "show", f"{SOURCE_REVISION}:{relative}"], cwd=PROJECT_ROOT,
                check=True, capture_output=True,
            ).stdout
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(source)
            lines_by_path[relative] = source.decode("utf-8").splitlines()
            chunks_by_path[relative] = (
                chunk_python_file(path, root, "codebase-qa-v2") if relative.endswith(".py")
                else chunk_config_file(path, root, "codebase-qa-v2")
            )
        for case in cases:
            for evidence in case.required_evidence:
                for alternative in evidence.acceptable_spans:
                    lines = lines_by_path[alternative.file_path]
                    first, last = alternative.start_line, alternative.end_line
                    while first <= last and not lines[first - 1].strip():
                        first += 1
                    while last >= first and not lines[last - 1].strip():
                        last -= 1
                    if not any(
                        chunk.start_line <= first
                        and last <= chunk.end_line
                        for chunk in chunks_by_path[alternative.file_path]
                    ):
                        raise ValueError(
                            f"Evidence crosses or misses accepted chunk: "
                            f"{case.case_id}/{evidence.evidence_id}/"
                            f"{alternative.file_path}:{alternative.start_line}-{alternative.end_line}"
                        )


def build_final() -> FinalDev2:
    header, cases = audited_cases()
    cases = _annotate_physical_oversize(cases)
    raw_cases = [case.model_dump(mode="json") | {
        "repository": "codebase-qa-v2", "rationale": case.expected_answer,
    } for case in cases]
    payload = {
        **header,
        "dataset_version": "codebase-qa-v2-dev2-v1.0.0",
        "dataset_status": "Independently audited development set; for tuning, NOT an independent generalisation benchmark.",
        "candidate_pool_hash": CANDIDATE_HASH,
        "corpus": {
            "repository": "codebase-qa-v2",
            "expected_chunk_count": 212,
            "index_manifest_sha256": INDEX_MANIFEST,
            "source_revision": SOURCE_REVISION,
            "chunking_identifier": CHUNKING_IDENTIFIER,
        },
        "case_count": len(cases),
        "answerable_count": sum(case.source_answerable for case in cases),
        "unanswerable_count": sum(not case.source_answerable for case in cases),
        "multi_evidence_count": sum(len(case.required_evidence) >= 2 for case in cases),
        "long_chunk_count": sum("long_chunk" in case.secondary_tags for case in cases),
        "required_evidence_unit_count": sum(len(case.required_evidence) for case in cases),
        "acceptable_span_count": sum(len(u.acceptable_spans) for case in cases
                                     for u in case.required_evidence),
        "category_counts": dict(Counter(case.primary_category for case in cases)),
        "tag_counts": dict(Counter(tag for case in cases for tag in case.secondary_tags)),
        "dev1_overlap_counts": dict(Counter(case.dev1_overlap for case in cases)),
        "holdout_overlap_counts": dict(Counter(case.holdout_overlap for case in cases)),
        "case_set_hash": _hash_json(raw_cases),
        "cases": raw_cases,
    }
    payload["dataset_hash"] = _hash_json(payload)
    final = FinalDev2.model_validate(payload)
    validate_sources(final, PROJECT_ROOT)
    validate_accepted_chunk_containment(final.cases)
    expected = {
        "case_count": 38, "answerable_count": 36, "unanswerable_count": 2,
        "multi_evidence_count": 16, "long_chunk_count": 16,
        "required_evidence_unit_count": 60, "acceptable_span_count": 70,
    }
    if any(getattr(final, key) != value for key, value in expected.items()):
        raise ValueError("Final DEV2 counts disagree with independent audit")
    if final.dev1_overlap_counts != {"NONE": 18, "LOW": 20} or final.holdout_overlap_counts != {"NONE": 23, "LOW": 15}:
        raise ValueError("Final DEV2 overlap counts disagree with independent audit")
    if {case.case_id for case in final.cases} & REJECT:
        raise ValueError("Rejected audit cases survived in final DEV2")
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without writing")
    args = parser.parse_args()
    final = build_final()
    if args.check:
        checked = load_final_dev2(FINAL)
        if checked.dataset_hash != final.dataset_hash:
            raise ValueError("Checked-in final DEV2 differs from audited source-only build")
    else:
        FINAL.write_text(final.model_dump_json(indent=2) + "\n", encoding="utf-8")
    print(f"DEV2 {len(final.cases)} cases; hash {final.dataset_hash}; "
          f"case-set {final.case_set_hash}; source spans validated")


if __name__ == "__main__":
    main()
