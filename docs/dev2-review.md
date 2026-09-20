# DEV2 candidates — independent audit required

Machine-prepared DEV2 candidate pending independent audit; not frozen or scored.
Frozen source: `7a3b7b05087793975ae0a84d85e7d691d9f3352e`. Candidate hash: `4ed6388ba299dbf7ae9dbbbca01d72cf46b4520dd26895605732d88463a872d6`.
DEV1 and the observed HOLDOUT remain unchanged. Do not score DEV2 before audit.

Oversize checks count tokenizer tokens including special tokens against the accepted 256-token embedding limit. They classify top-level Python symbol chunks; an unmarked config/companion span is not proven short.

## dev2-multi-01 — cross_module_behavior

Tags: multi_evidence, path_safety

Question: If the indexing root itself is a symlink, how does discovery treat it differently from symlinked entries inside the tree?

Answerable: yes

Expected-answer rubric: The requested root is resolved first; entries found during traversal are classified without following symlinks, so nested symlink entries are not descended or accepted as regular files.

Multi-evidence rationale (2 units): Root normalization and nested-entry traversal are separate decisions; neither span alone establishes the contrast.
One unit alone sufficient: no

Required `root-resolution`: Establishes that a symlink supplied as the root is resolved before traversal.

Acceptable source: `backend/app/services/repository_loader.py:31-39`

```text
31: def resolve_repository_root(repository_path: str | Path) -> Path:
… (intervening source lines omitted)
33:
34:     root = Path(repository_path).expanduser().resolve()
35:     if not root.exists():
… (intervening source lines omitted)
39:     return root
```

Required `entry-no-follow`: Establishes that nested entries are classified without following links.

Oversized accepted chunk: backend/app/services/repository_loader.py::discover_python_files: 392 tokens > 256; evidence begins near token 165

Acceptable source: `backend/app/services/repository_loader.py:85-101`

```text
85:     def visit(directory: Path) -> None:
… (intervening source lines omitted)
87:             try:
88:                 is_directory = entry.is_dir(follow_symlinks=False)
89:                 if is_directory:
… (intervening source lines omitted)
91:                         visit(Path(entry.path))
92:                 elif entry.is_file(follow_symlinks=False):
93:                     path = Path(entry.path)
… (intervening source lines omitted)
101:                         discovered.append(path)
```

DEV1 overlap: **LOW** — semantic-01: span overlap in backend/app/services/repository_loader.py; multi-01: span overlap in backend/app/services/repository_loader.py

HOLDOUT overlap: **LOW** — holdout-identifier-01: span overlap in backend/app/services/repository_loader.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-multi-02 — cross_module_behavior

Tags: multi_evidence, mixed_source

Question: Why can an indexed repository's Python-file count be smaller than its stored-row count when configuration files are present?

Answerable: yes

Expected-answer rubric: Discovery includes allowlisted config files; storage dispatches .py to the AST chunker and other discovered files to the config text chunker. The Python-file statistic counts only .py paths, while stored rows include config chunks and can include several chunks per Python file.

Multi-evidence rationale (3 units): The inclusion policy, dispatch decision, and statistic are three different facts needed for the complete answer.
One unit alone sufficient: no

Required `mixed-discovery`: Shows that the indexing path uses source discovery with configuration enabled.

Acceptable source: `backend/app/services/repository_loader.py:112-115`

```text
112: def discover_source_files(repository_path: str | Path) -> list[Path]:
… (intervening source lines omitted)
114:
115:     return discover_python_files(repository_path, include_config=True)
```

Required `chunker-dispatch`: Shows the distinct Python and config chunking branches.

Acceptable source: `backend/app/services/storage.py:36-43`

```text
36: def _load_chunks(root: Path, repository: str, files: list[Path]) -> list[SourceChunk]:
… (intervening source lines omitted)
39:         if file_path.suffix == ".py":
40:             chunks.extend(chunk_python_file(file_path, root, repository))
41:         else:
42:             chunks.extend(chunk_config_file(file_path, root, repository))
43:     return chunks
```

Required `python-only-counter`: Shows why the returned Python-file count excludes config paths even though their rows are stored.

Oversized accepted chunk: backend/app/services/storage.py::index_repository: 384 tokens > 256; evidence begins near token 331

Acceptable source: `backend/app/services/storage.py:84-89`

```text
84:     return IndexingStats(
85:         repository=repository,
86:         python_files_discovered=sum(path.suffix == ".py" for path in files),
87:         chunks_created=len(chunks),
… (intervening source lines omitted)
89:     )
```

DEV1 overlap: **LOW** — semantic-04: span overlap in backend/app/services/storage.py; multi-02: span overlap in backend/app/services/storage.py

HOLDOUT overlap: **LOW** — holdout-cross-02: span overlap in backend/app/services/storage.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-multi-03 — multiple_required_evidence

Tags: multi_evidence, module_fallback

Question: What happens to an assignment-only Python module between parsing and insertion into the vector table?

Answerable: yes

Expected-answer rubric: With no top-level function or class, the parser emits one whole-module fallback chunk. Storage embeds its content, copies its metadata and vector into CodeChunk, then publishes the rows.

Multi-evidence rationale (2 units): Fallback creation does not itself show embedding or persistence; storage does not explain why this source becomes a module chunk.
One unit alone sufficient: no

Required `assignment-fallback`: Establishes the special representation for a module without supported definitions.

Oversized accepted chunk: backend/app/services/chunker.py::chunk_python_file: 776 tokens > 256; evidence begins near token 293

Acceptable source: `backend/app/services/chunker.py:131-145`

```text
131:     source_lines = source.splitlines(keepends=True)
… (intervening source lines omitted)
134:
135:     if not symbol_nodes and tree.body and source.strip():
136:         return [
… (intervening source lines omitted)
139:                 file_path=relative_path,
140:                 symbol_type="module",
141:                 symbol_name=None,
… (intervening source lines omitted)
145:             )
```

Required `fallback-publication`: Establishes that prepared chunk text becomes a vector-backed stored row.

Oversized accepted chunk: backend/app/services/storage.py::index_repository: 384 tokens > 256; evidence begins near token 88

Acceptable source: `backend/app/services/storage.py:55-74`

```text
55:     files = discover_source_files(root)
56:     chunks = _load_chunks(root, repository, files)
57:     vectors = embed_texts([chunk.content for chunk in chunks])
58:
… (intervening source lines omitted)
70:             content=chunk.content,
71:             embedding=embedding,
72:         )
… (intervening source lines omitted)
74:     ]
```

DEV1 overlap: **LOW** — semantic-02: span overlap in backend/app/services/chunker.py; semantic-04: span overlap in backend/app/services/storage.py; multi-01: span overlap in backend/app/services/chunker.py; multi-02: span overlap in backend/app/services/storage.py

HOLDOUT overlap: **LOW** — holdout-cross-04: span overlap in backend/app/services/storage.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-multi-04 — multiple_required_evidence

Tags: multi_evidence, failure_boundary, long_chunk, early_source

Question: If embedding returns a different number of vectors than prepared chunks, can deletion occur before the error, and how does the index API report it?

Answerable: yes

Expected-answer rubric: No. Storage raises StorageError on the count mismatch before the later DELETE. The index route catches StorageError and returns a generic HTTP 500.

Multi-evidence rationale (2 units): The storage chunk establishes pre-delete failure; a separate API route chunk establishes the externally visible status.
One unit alone sufficient: no

Required `mismatch-before-delete`: Shows that the count mismatch raises before the later destructive statement.

Oversized accepted chunk: backend/app/services/storage.py::index_repository: 384 tokens > 256; evidence begins near token 88

Acceptable source: `backend/app/services/storage.py:55-82`

```text
55:     files = discover_source_files(root)
… (intervening source lines omitted)
58:
59:     if len(vectors) != len(chunks):
60:         raise StorageError("Embedding count does not match chunk count")
61:
… (intervening source lines omitted)
76:     try:
77:         db.execute(delete(CodeChunk).where(CodeChunk.repository == repository))
78:         db.add_all(rows)
… (intervening source lines omitted)
81:         db.rollback()
82:         raise StorageError(f"Could not store repository chunks: {exc}") from exc
```

Required `storage-http-error`: Shows the API translation of StorageError.

Oversized accepted chunk: backend/app/api/routes.py::index_local_repository: 288 tokens > 256; evidence begins near token 213

Acceptable source: `backend/app/api/routes.py:76-78`

```text
76:     except (EmbeddingError, StorageError) as exc:
77:         _log_internal_failure("Repository indexing failed", exc)
78:         raise HTTPException(status_code=500, detail="Repository indexing failed.") from exc
```

DEV1 overlap: **LOW** — semantic-04: span overlap in backend/app/services/storage.py; route-02: span overlap in backend/app/api/routes.py; cross-module-01: span overlap in backend/app/api/routes.py; multi-02: span overlap in backend/app/services/storage.py

HOLDOUT overlap: **LOW** — holdout-cross-04: span overlap in backend/app/services/storage.py; holdout-near-05: span overlap in backend/app/services/storage.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-multi-05 — cross_module_behavior

Tags: multi_evidence, configuration_use

Question: How does the configured application name become the title of the FastAPI app?

Answerable: yes

Expected-answer rubric: APP_NAME populates Settings.app_name, and main.py passes get_settings().app_name as FastAPI's title.

Multi-evidence rationale (2 units): A setting declaration alone does not show where it is consumed; app construction alone does not identify the environment alias.
One unit alone sufficient: no

Required `app-name-setting`: Defines the setting and environment alias.

Oversized accepted chunk: backend/app/config.py::Settings: 561 tokens > 256; evidence begins near token 148

Acceptable source: `backend/app/config.py:30-30`

```text
30:     app_name: str = Field(default="Codebase QA V2", validation_alias="APP_NAME")
```

Required `fastapi-title-use`: Shows the setting being consumed at app construction.

Acceptable source: `backend/app/main.py:8-10`

```text
8:
9: app = FastAPI(title=get_settings().app_name)
10: app.include_router(router)
```

DEV1 overlap: **LOW** — architecture-01: span overlap in backend/app/main.py; multi-04: span overlap in backend/app/config.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-multi-06 — multiple_required_evidence

Tags: multi_evidence, api_contract

Question: Which indexing statistics are calculated by storage and which of them does the HTTP response expose?

Answerable: yes

Expected-answer rubric: Storage returns repository, Python files discovered, chunks created, and rows stored; the response schema declares those same fields and the route constructs it from the returned stats.

Multi-evidence rationale (3 units): The storage calculation, declared HTTP schema, and route mapping each establish a separate part of the contract.
One unit alone sufficient: no

Required `stats-calculation`: Shows the values computed after publication.

Oversized accepted chunk: backend/app/services/storage.py::index_repository: 384 tokens > 256; evidence begins near token 331

Acceptable source: `backend/app/services/storage.py:84-89`

```text
84:     return IndexingStats(
85:         repository=repository,
… (intervening source lines omitted)
87:         chunks_created=len(chunks),
88:         rows_stored=len(rows),
89:     )
```

Required `index-response-fields`: Shows the public response shape independently of the storage record.

Acceptable source: `backend/app/schemas.py:28-32`

```text
28: class IndexRepositoryResponse(BaseModel):
29:     repository: str
30:     python_files_discovered: int
31:     chunks_created: int
32:     rows_stored: int
```

Required `route-stats-copy`: Shows the route copies storage's result into the response model.

Oversized accepted chunk: backend/app/api/routes.py::index_local_repository: 288 tokens > 256; evidence begins near token 213

Acceptable source: `backend/app/api/routes.py:76-79`

```text
76:     except (EmbeddingError, StorageError) as exc:
… (intervening source lines omitted)
78:         raise HTTPException(status_code=500, detail="Repository indexing failed.") from exc
79:     return IndexRepositoryResponse(**asdict(result))
```

DEV1 overlap: **LOW** — semantic-04: span overlap in backend/app/services/storage.py; route-02: span overlap in backend/app/api/routes.py; cross-module-01: span overlap in backend/app/api/routes.py; multi-02: span overlap in backend/app/services/storage.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-multi-07 — cross_module_behavior

Tags: multi_evidence, near_match, file_reading

Question: Does Python-source decoding follow the same screening path as allowlisted configuration files during indexing?

Answerable: yes

Expected-answer rubric: No. Discovery samples config candidates for NUL/UTF-8, while discovered Python files are passed to the Python chunker, whose full read_text UTF-8 operation raises SourceReadError on decoding failure.

Multi-evidence rationale (3 units): The sample check, its config-only dispatch branch, and the Python full-file read are distinct facts required for the contrast.
One unit alone sufficient: no

Required `config-sample-screen`: Shows the discovery-time screening applied to config candidates.

Acceptable source: `backend/app/services/repository_loader.py:49-63`

```text
49: def _is_utf8_text_file(path: Path) -> bool:
… (intervening source lines omitted)
53:         with path.open("rb") as source_file:
54:             sample = source_file.read(4096)
55:     except OSError as exc:
… (intervening source lines omitted)
59:     try:
60:         sample.decode("utf-8")
61:     except UnicodeDecodeError:
… (intervening source lines omitted)
63:     return True
```

Required `config-only-screen-branch`: Shows that the sample text check is confined to discovered non-Python config candidates.

Oversized accepted chunk: backend/app/services/repository_loader.py::discover_python_files: 392 tokens > 256; evidence begins near token 232

Acceptable source: `backend/app/services/repository_loader.py:92-101`

```text
92:                 elif entry.is_file(follow_symlinks=False):
93:                     path = Path(entry.path)
94:                     if entry.name.endswith(".py"):
95:                         discovered.append(path)
… (intervening source lines omitted)
98:                         and _is_supported_config_path(path)
99:                         and _is_utf8_text_file(path)
100:                     ):
101:                         discovered.append(path)
```

Required `python-full-read`: Shows the distinct full Python-source decoding and error boundary.

Oversized accepted chunk: backend/app/services/chunker.py::chunk_python_file: 776 tokens > 256; evidence begins near token 142

Acceptable source: `backend/app/services/chunker.py:116-121`

```text
116:     try:
117:         source = path.read_text(encoding="utf-8")
118:     except (OSError, UnicodeError) as exc:
119:         raise SourceReadError(
120:             f"Could not read Python source file {relative_path}: {exc}"
121:         ) from exc
```

DEV1 overlap: **LOW** — semantic-01: span overlap in backend/app/services/repository_loader.py; semantic-02: span overlap in backend/app/services/chunker.py; multi-01: span overlap in backend/app/services/chunker.py, backend/app/services/repository_loader.py

HOLDOUT overlap: **LOW** — holdout-multi-01: span overlap in backend/app/services/repository_loader.py; holdout-near-02: span overlap in backend/app/services/chunker.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-multi-08 — multiple_required_evidence

Tags: multi_evidence, failure_boundary, long_chunk, across_long_chunks

Question: If a provider returns a malformed completion rather than raising a transport error, how is that failure surfaced through /ask?

Answerable: yes

Expected-answer rubric: RAG raises RAGGenerationError for missing or empty answer content, and the ask route translates that class into HTTP 502 with a generic detail.

Multi-evidence rationale (2 units): The service establishes the failure class and the API establishes its status; neither source alone fully answers the transition.
One unit alone sufficient: no

Required `malformed-completion`: Shows the service-level error raised for a missing/empty answer.

Oversized accepted chunk: backend/app/services/rag.py::answer_question: 436 tokens > 256; evidence begins near token 350

Acceptable source: `backend/app/services/rag.py:136-142`

```text
136:     try:
… (intervening source lines omitted)
138:     except (AttributeError, IndexError) as exc:
139:         raise RAGGenerationError("LLM response did not contain an answer") from exc
140:     if not answer:
141:         raise RAGGenerationError("LLM returned an empty answer")
142:     return RAGResult(answer=answer, sources=context.included_chunks)
```

Required `generation-http-status`: Shows how the route translates the service error to HTTP.

Oversized accepted chunk: backend/app/api/routes.py::ask_repository: 283 tokens > 256; evidence begins near token 145

Acceptable source: `backend/app/api/routes.py:113-115`

```text
113:     except RAGGenerationError as exc:
114:         _log_internal_failure("LLM generation failed", exc)
115:         raise HTTPException(status_code=502, detail="LLM generation failed.") from exc
```

DEV1 overlap: **LOW** — route-04: span overlap in backend/app/api/routes.py; architecture-04: span overlap in backend/app/services/rag.py; cross-module-03: span overlap in backend/app/api/routes.py

HOLDOUT overlap: **LOW** — holdout-route-03: span overlap in backend/app/api/routes.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-architecture-01 — architecture

Tags: evaluation_safety, multi_evidence

Question: What separates the explicitly write-enabled evaluation-corpus preparation path from the default read-only scorer?

Answerable: yes

Expected-answer rubric: Preparation demands an exact --confirm-write literal and calls index_repository. The scorer opens a session, marks the transaction read-only, and calls evaluate_dataset without indexing.

Multi-evidence rationale (2 units): The two separate commands must both be inspected to distinguish their write permissions.
One unit alone sufficient: no

Required `write-gate`: Shows the explicit write confirmation and indexing call.

Acceptable source: `backend/scripts/prepare_evaluation_corpus.py:22-30`

```text
22:     args = parser.parse_args()
23:     if args.confirm_write != CONFIRMATION:
24:         parser.error(
… (intervening source lines omitted)
29:     with SessionLocal() as db:
30:         stats = index_repository(db, args.repository_path, args.repository)
```

Required `readonly-score`: Shows read-only transaction setup in the scorer.

Acceptable source: `backend/scripts/evaluate_retrieval.py:49-65`

```text
49: def run(
… (intervening source lines omitted)
57:     with SessionLocal() as db:
58:         db.execute(text("SET TRANSACTION READ ONLY"))
59:         return evaluate_dataset(
60:             db,
… (intervening source lines omitted)
65:         )
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-architecture-02 — architecture

Tags: reproducibility, index_identity

Question: Why can a prepared corpus keep the same manifest after row IDs change?

Answerable: yes

Expected-answer rubric: compute_index_manifest hashes repository/source metadata and content, explicitly excluding row IDs and vectors, so equivalent indexed source yields the same manifest.

Required `manifest-record-fields`: The manifest code shows exactly which fields participate.

Acceptable source: `backend/app/evaluation.py:205-224`

```text
205:
206: def compute_index_manifest(chunks: Sequence[IndexedChunk]) -> str:
207:     """Hash stable indexed source metadata/content, excluding row IDs and vectors."""
208:
… (intervening source lines omitted)
216:             "end_line": chunk.end_line,
217:             "content": chunk.content,
218:         }
… (intervening source lines omitted)
224:     return hashlib.sha256(canonical).hexdigest()
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-architecture-03 — architecture

Tags: reproducibility, failure_boundary

Question: Before evaluation scores any query, which prepared-corpus mismatches are rejected?

Answerable: yes

Expected-answer rubric: validate_corpus_manifest checks repository scope, nonempty rows, expected chunk count, index manifest hash, and chunking identifier; mismatches raise CorpusManifestMismatch.

Required `manifest-validation`: The validation branch lists the fail-closed corpus checks.

Oversized accepted chunk: backend/app/evaluation.py::validate_corpus_manifest: 368 tokens > 256; evidence begins near token 2

Acceptable source: `backend/app/evaluation.py:227-262`

```text
227: def validate_corpus_manifest(
… (intervening source lines omitted)
244:         )
245:     if len(chunks) != dataset.corpus.expected_chunk_count:
246:         raise CorpusManifestMismatch(
247:             "Prepared corpus chunk count mismatch: "
248:             f"expected {dataset.corpus.expected_chunk_count}, got {len(chunks)}"
249:         )
250:     actual_hash = compute_index_manifest(chunks)
251:     if actual_hash != dataset.corpus.index_manifest_sha256:
252:         raise CorpusManifestMismatch(
253:             "Prepared corpus manifest mismatch: "
254:             f"expected {dataset.corpus.index_manifest_sha256}, got {actual_hash}"
255:         )
256:     if dataset.corpus.chunking_identifier != CHUNKING_IDENTIFIER:
257:         raise CorpusManifestMismatch(
… (intervening source lines omitted)
259:             f"dataset={dataset.corpus.chunking_identifier}, "
260:             f"application={CHUNKING_IDENTIFIER}"
261:         )
262:     return actual_hash
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-architecture-04 — architecture

Tags: database_setup, multi_evidence

Question: Why are both Docker's initialization SQL and the backend table-initialization script needed for a fresh development database?

Answerable: yes

Expected-answer rubric: The Docker initialization SQL enables pgvector's vector extension. The backend init script separately creates SQLAlchemy tables from Base.metadata; neither operation substitutes for the other.

Multi-evidence rationale (2 units): Extension availability and table creation are separate setup responsibilities in separate files.
One unit alone sufficient: no

Required `vector-extension-init`: Shows the extension installation step.

Acceptable source: `docker/postgres/init.sql:1-1`

```text
1: CREATE EXTENSION IF NOT EXISTS vector;
```

Required `metadata-table-init`: Shows the independent table-creation step.

Acceptable source: `backend/scripts/init_db.py:7-11`

```text
7: def main() -> None:
… (intervening source lines omitted)
9:
10:     Base.metadata.create_all(bind=engine)
11:     print("Database tables initialized.")
```

DEV1 overlap: **LOW** — path-01: span overlap in docker/postgres/init.sql; path-03: span overlap in backend/scripts/init_db.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-architecture-05 — architecture

Tags: configuration, navigation

Question: Why does starting the backend from a different working directory not change where its .env file is sought?

Answerable: yes

Expected-answer rubric: PROJECT_ROOT is derived from config.py's own resolved path; ENV_FILE is PROJECT_ROOT/.env and is passed to the Settings configuration.

Required `env-file-location`: Shows file-relative location and Settings env_file use.

Acceptable source: `backend/app/config.py:11-23`

```text
11: PROJECT_ROOT = Path(__file__).resolve().parents[2]
12: ENV_FILE = PROJECT_ROOT / ".env"
… (intervening source lines omitted)
18:     model_config = SettingsConfigDict(
19:         env_file=ENV_FILE,
20:         env_file_encoding="utf-8",
… (intervening source lines omitted)
23:         extra="ignore",
```

DEV1 overlap: **LOW** — multi-04: span overlap in backend/app/config.py

HOLDOUT overlap: **LOW** — holdout-config-05: span overlap in backend/app/config.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-architecture-06 — architecture

Tags: repository_scope, evaluation_safety

Question: How does the evaluator prevent a case from silently searching a repository different from its declared corpus?

Answerable: yes

Expected-answer rubric: EvaluationDataset validation compares every case.repository with corpus.repository and rejects any mismatched case IDs.

Required `case-corpus-consistency`: The dataset model enforces matching repository identities.

Acceptable source: `backend/app/evaluation.py:95-109`

```text
95:     @model_validator(mode="after")
… (intervening source lines omitted)
102:             for case in self.cases
103:             if case.repository != self.corpus.repository
104:         ]
… (intervening source lines omitted)
106:             raise ValueError(
107:                 "Cases use a repository other than the corpus repository: "
108:                 + ", ".join(wrong_repository)
109:             )
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-semantic-01 — semantic_conceptual

Tags: context_selection, candidate_competition

Question: If the first retrieved chunk is too large for the answer context, can a later smaller chunk still be included?

Answerable: yes

Expected-answer rubric: Yes. build_context skips a chunk whose complete section exceeds the remaining character budget and continues iterating later candidates.

Required `context-skip-continue`: The loop uses continue rather than stopping at the first over-budget chunk.

Oversized accepted chunk: backend/tests/test_rag.py::test_build_context_enforces_bound_across_multiple_sources: 268 tokens > 256; evidence begins near token 2

Acceptable source: `backend/app/services/rag.py:49-62`

```text
49:     for chunk in chunks:
… (intervening source lines omitted)
57:         required = len(separator) + len(section)
58:         if used + required > MAX_CONTEXT_CHARACTERS:
59:             continue
60:         sections.append(section)
61:         included_chunks.append(chunk)
62:         used += required
```

Acceptable source: `backend/tests/test_rag.py:32-62`

```text
32: def test_build_context_enforces_bound_across_multiple_sources(
… (intervening source lines omitted)
59:     assert len(context.text) <= 300
60:     assert large_source not in context.included_chunks
61:     assert context.included_chunks == [small_source]
62:     assert "large.py" not in context.text
```

DEV1 overlap: **LOW** — identifier-04: span overlap in backend/app/services/rag.py; multi-03: span overlap in backend/app/services/rag.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-semantic-02 — semantic_conceptual

Tags: context_selection, empty_result

Question: What text does the answer-building path supply as repository context when no complete chunks fit?

Answerable: yes

Expected-answer rubric: build_context returns the fixed text 'No repository context was retrieved.' with an empty included-chunk list.

Required `empty-context-placeholder`: The return branch defines the no-context representation.

Acceptable source: `backend/app/services/rag.py:64-67`

```text
64:     return ContextBuild(
65:         text="\n\n".join(sections) if sections else "No repository context was retrieved.",
66:         included_chunks=included_chunks,
67:     )
```

DEV1 overlap: **LOW** — identifier-04: span overlap in backend/app/services/rag.py; multi-03: span overlap in backend/app/services/rag.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-semantic-03 — semantic_conceptual

Tags: determinism, discovery

Question: What makes source discovery's final file order stable even when filesystem enumeration order differs?

Answerable: yes

Expected-answer rubric: Entries are sorted by name within each directory, and the collected paths are sorted again by repository-relative POSIX path before return.

Required `relative-source-sort`: Shows both entry ordering and the final relative-path sort.

Oversized accepted chunk: backend/app/services/repository_loader.py::discover_python_files: 392 tokens > 256; evidence begins near token 79

Acceptable source: `backend/app/services/repository_loader.py:76-109`

```text
76:     def read_entries(directory: Path) -> list[os.DirEntry[str]]:
… (intervening source lines omitted)
78:             with os.scandir(directory) as entries:
79:                 return sorted(entries, key=lambda entry: entry.name)
80:         except OSError as exc:
… (intervening source lines omitted)
108:
109:     return sorted(discovered, key=lambda path: path.relative_to(root).as_posix())
```

DEV1 overlap: **LOW** — semantic-01: span overlap in backend/app/services/repository_loader.py; multi-01: span overlap in backend/app/services/repository_loader.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-semantic-04 — semantic_conceptual

Tags: embedding_validation, failure_boundary, multi_evidence

Question: What happens if the embedding encoder returns a vector with the wrong number of dimensions?

Answerable: yes

Expected-answer rubric: _validate_vectors checks every returned vector against EMBEDDING_DIMENSION and raises EmbeddingError before embed_texts returns the batch.

Multi-evidence rationale (2 units): The validator body defines the rule, while the separate embed_texts chunk proves that real batches pass through it.
One unit alone sufficient: no

Required `per-vector-dimension-check`: Shows validation of each encoded vector and the failure class.

Acceptable source: `backend/app/services/embeddings.py:39-46`

```text
39: def _validate_vectors(vectors: list[list[float]]) -> None:
40:     for index, vector in enumerate(vectors):
41:         if len(vector) != EMBEDDING_DIMENSION:
42:             raise EmbeddingError(
43:                 f"Embedding {index} has dimension {len(vector)}; "
… (intervening source lines omitted)
46:
```

Required `validator-called-before-return`: Shows embed_texts actually invokes vector validation before returning the batch.

Acceptable source: `backend/app/services/embeddings.py:63-68`

```text
63:         vectors = encoded.tolist()
… (intervening source lines omitted)
66:
67:     _validate_vectors(vectors)
68:     return vectors
```

DEV1 overlap: **LOW** — semantic-03: span overlap in backend/app/services/embeddings.py; multi-02: span overlap in backend/app/services/embeddings.py

HOLDOUT overlap: **LOW** — holdout-near-05: span overlap in backend/app/services/embeddings.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-semantic-05 — semantic_conceptual

Tags: source_coverage, edge_case

Question: Will a Python file containing only comments be emitted as a module fallback chunk?

Answerable: yes

Expected-answer rubric: No. The fallback requires a nonempty AST body as well as nonblank source; a comment-only file has no statements, so the returned chunk list is empty.

Required `fallback-body-guard`: The fallback's tree.body condition excludes comment-only modules.

Oversized accepted chunk: backend/app/services/chunker.py::chunk_python_file: 776 tokens > 256; evidence begins near token 293

Acceptable source: `backend/app/services/chunker.py:131-148`

```text
131:     source_lines = source.splitlines(keepends=True)
… (intervening source lines omitted)
134:
135:     if not symbol_nodes and tree.body and source.strip():
136:         return [
… (intervening source lines omitted)
147:
148:     chunks: list[SourceChunk] = []
```

DEV1 overlap: **LOW** — semantic-02: span overlap in backend/app/services/chunker.py; multi-01: span overlap in backend/app/services/chunker.py

HOLDOUT overlap: **LOW** — holdout-semantic-03: span overlap in backend/app/services/chunker.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-semantic-06 — semantic_conceptual

Tags: config_source, provenance

Question: When configuration text contains blank or comment lines next to values, does chunk creation reconstruct or omit those lines?

Answerable: yes

Expected-answer rubric: The config chunker joins pending pieces from the original lines and emits their exact text when that pending group contains non-whitespace; adjacent blank/comment lines remain in that source slice.

Required `pending-original-text`: The pending join and append retain original text rather than parsing configuration meaning.

Oversized accepted chunk: backend/app/services/text_chunker.py::chunk_config_file: 449 tokens > 256; evidence begins near token 221

Acceptable source: `backend/app/services/text_chunker.py:49-75`

```text
49:     chunks: list[SourceChunk] = []
… (intervening source lines omitted)
63:                     end_line=pending[-1][0],
64:                     content="".join(text for _, text in pending),
65:                 )
… (intervening source lines omitted)
69:
70:     for line_number, text in _bounded_line_pieces(source):
71:         if pending and pending_size + len(text) > MAX_CONFIG_CHUNK_CHARACTERS:
… (intervening source lines omitted)
75:     flush()
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-exact-01 — configuration_constants

Tags: exact_token, embedding_batch, multi_evidence

Question: Which batch-size setting reaches the local encoder when several chunks are embedded together?

Answerable: yes

Expected-answer rubric: DEFAULT_BATCH_SIZE is 32 and embed_texts passes it as the model.encode batch_size argument.

Multi-evidence rationale (2 units): The declaration provides the value; the encoder call proves where it is consumed.
One unit alone sufficient: no

Required `batch-size-definition`: Defines the constant's value.

Acceptable source: `backend/app/services/embeddings.py:9-10`

```text
9: EMBEDDING_DIMENSION = 384
10: DEFAULT_BATCH_SIZE = 32
```

Required `batch-size-use`: Shows it is actually passed to model.encode.

Acceptable source: `backend/app/services/embeddings.py:54-62`

```text
54:     model = get_embedding_model()
55:     try:
56:         encoded = model.encode(
57:             list(texts),
58:             batch_size=DEFAULT_BATCH_SIZE,
59:             normalize_embeddings=True,
… (intervening source lines omitted)
62:         )
```

DEV1 overlap: **LOW** — semantic-03: span overlap in backend/app/services/embeddings.py; config-01: span overlap in backend/app/services/embeddings.py; multi-02: span overlap in backend/app/services/embeddings.py

HOLDOUT overlap: **LOW** — holdout-near-05: span overlap in backend/app/services/embeddings.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-exact-02 — configuration_constants

Tags: exact_token, database_session

Question: How is the synchronous session factory configured with respect to autoflush and autocommit?

Answerable: yes

Expected-answer rubric: SessionLocal binds to engine with autoflush=False and autocommit=False.

Required `sessionmaker-options`: The factory declaration carries both options.

Acceptable source: `backend/app/database.py:11-12`

```text
11: engine = create_engine(get_settings().database_url, pool_pre_ping=True)
12: SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **LOW** — holdout-config-01: span overlap in backend/app/database.py; holdout-cross-01: span overlap in backend/app/database.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-exact-03 — configuration_constants

Tags: exact_token, database_setup

Question: What local command does the Compose database healthcheck run before reporting the PostgreSQL service ready?

Answerable: yes

Expected-answer rubric: The healthcheck invokes pg_isready with the configured POSTGRES_USER and POSTGRES_DB, at five-second intervals with ten retries.

Required `postgres-healthcheck`: The Compose healthcheck lists its command and timing.

Acceptable source: `docker-compose.yml:13-17`

```text
13:     healthcheck:
14:       test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
15:       interval: 5s
16:       timeout: 5s
17:       retries: 10
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-exact-04 — configuration_constants

Tags: exact_token, provider_config

Question: How many retries can configuration permit for the answer provider, even if the default is lower?

Answerable: yes

Expected-answer rubric: llm_max_retries defaults to 2 and Settings validation caps it at 5.

Required `retry-setting-bounds`: Shows both default and upper validation bound.

Oversized accepted chunk: backend/app/config.py::Settings: 561 tokens > 256; evidence begins near token 395

Acceptable source: `backend/app/config.py:45-50`

```text
45:     llm_max_retries: int = Field(
46:         default=2,
47:         ge=0,
48:         le=5,
49:         validation_alias="LLM_MAX_RETRIES",
50:     )
```

DEV1 overlap: **LOW** — multi-04: span overlap in backend/app/config.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-exact-05 — exact_identifier

Tags: exact_token, chunk_identity

Question: What structural label does the Python chunker give an async top-level function, rather than a regular function or class?

Answerable: yes

Expected-answer rubric: _symbol_type returns async_function for ast.AsyncFunctionDef, function for FunctionDef, and class otherwise.

Required `async-symbol-label`: The dispatch shows the distinct structural labels.

Acceptable source: `backend/app/services/chunker.py:34-39`

```text
34: def _symbol_type(node: ast.AST) -> str:
35:     if isinstance(node, ast.AsyncFunctionDef):
36:         return "async_function"
37:     if isinstance(node, ast.FunctionDef):
38:         return "function"
39:     return "class"
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-near-01 — difficult_near_matches

Tags: distractor, module_structure

Question: How does a module with no top-level definitions differ from uncovered statements in a module that does have a definition?

Answerable: yes

Expected-answer rubric: A source module with statements but no supported definitions gets a whole-file module fallback; otherwise uncovered consecutive statements become module_companion chunks beside function/class chunks.

Required `module-vs-companion`: The same implementation chunk contains both branches needed for the contrast.

Oversized accepted chunk: backend/app/services/chunker.py::chunk_python_file: 776 tokens > 256; evidence begins near token 293

Acceptable source: `backend/app/services/chunker.py:131-175`

```text
131:     source_lines = source.splitlines(keepends=True)
… (intervening source lines omitted)
134:
135:     if not symbol_nodes and tree.body and source.strip():
136:         return [
… (intervening source lines omitted)
139:                 file_path=relative_path,
140:                 symbol_type="module",
141:                 symbol_name=None,
… (intervening source lines omitted)
162:                 source_lines=source_lines,
163:                 symbol_type="module_companion",
164:                 symbol_name=None,
… (intervening source lines omitted)
175:         flush_companion()
```

DEV1 overlap: **LOW** — semantic-02: span overlap in backend/app/services/chunker.py; multi-01: span overlap in backend/app/services/chunker.py

HOLDOUT overlap: **LOW** — holdout-semantic-03: span overlap in backend/app/services/chunker.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-near-02 — difficult_near_matches

Tags: distractor, error_boundary

Question: Does the config chunker use the same error for a path outside the repository as for an unreadable file inside it?

Answerable: yes

Expected-answer rubric: No. A path failing relative_to raises SourceFileError, while read_text failures raise the more specific SourceReadError.

Required `config-path-versus-read`: The adjacent exception branches distinguish provenance validation from reading.

Oversized accepted chunk: backend/app/services/text_chunker.py::chunk_config_file: 449 tokens > 256; evidence begins near token 68

Acceptable source: `backend/app/services/text_chunker.py:32-44`

```text
32:     root = Path(repository_root).resolve()
… (intervening source lines omitted)
36:     except ValueError as exc:
37:         raise SourceFileError(f"Source file is outside repository root: {path}") from exc
38:
… (intervening source lines omitted)
41:     except (OSError, UnicodeError) as exc:
42:         raise SourceReadError(
43:             f"Could not read config source file {relative_path}: {exc}"
44:         ) from exc
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **LOW** — holdout-multi-01: span overlap in backend/app/services/text_chunker.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-near-03 — difficult_near_matches

Tags: distractor, input_validation, multi_evidence

Question: Can a search request containing only spaces reach a different validation boundary from an empty query string?

Answerable: yes

Expected-answer rubric: No. SearchRequest's min_length=1 rejects an empty string, but whitespace satisfies that field length; embed_query later strips and rejects a whitespace-only query.

Multi-evidence rationale (2 units): The schema and embedding helper enforce different notions of emptiness, requiring both sources to explain the contrast.
One unit alone sufficient: no

Required `search-schema-min-length`: Shows the HTTP-level minimum length, which is not a whitespace trim.

Acceptable source: `backend/app/schemas.py:35-40`

```text
35: class SearchRequest(BaseModel):
36:     query: str = Field(min_length=1)
37:     top_k: int | None = Field(default=None, ge=1, le=50)
… (intervening source lines omitted)
40:     _validate_repository = field_validator("repository")(_normalise_repository_scope)
```

Required `embedding-whitespace-guard`: Shows the direct service check applied after stripping whitespace.

Acceptable source: `backend/app/services/embeddings.py:71-76`

```text
71: def embed_query(query: str) -> list[float]:
… (intervening source lines omitted)
73:
74:     if not query.strip():
75:         raise ValueError("Query must not be empty")
76:     return embed_texts([query])[0]
```

DEV1 overlap: **LOW** — identifier-03: span overlap in backend/app/services/embeddings.py; near-match-03: span overlap in backend/app/services/embeddings.py

HOLDOUT overlap: **LOW** — holdout-multi-02: span overlap in backend/app/schemas.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-near-04 — difficult_near_matches

Tags: distractor, http_error

Question: If repository traversal fails, does the indexing API use the same client-facing error message as a Python source read failure?

Answerable: yes

Expected-answer rubric: No. RepositoryReadError produces 'Could not safely read the repository directories.'; SourceReadError produces 'Could not safely read the repository source files.' Both use HTTP 400.

Required `distinct-read-http-details`: The route has separate branches and stable details.

Oversized accepted chunk: backend/app/api/routes.py::index_local_repository: 288 tokens > 256; evidence begins near token 105

Acceptable source: `backend/app/api/routes.py:64-73`

```text
64:     except RepositoryReadError:
65:         raise HTTPException(
66:             status_code=400,
67:             detail="Could not safely read the repository directories.",
68:         )
69:     except SourceReadError:
70:         raise HTTPException(
71:             status_code=400,
72:             detail="Could not safely read the repository source files.",
73:         )
```

DEV1 overlap: **LOW** — route-02: span overlap in backend/app/api/routes.py; cross-module-01: span overlap in backend/app/api/routes.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-near-05 — difficult_near_matches

Tags: distractor, database_model

Question: Are repository and file path optional on stored code chunks in the same way symbol name is?

Answerable: yes

Expected-answer rubric: No. repository and file_path are required non-null strings; only symbol_name is nullable.

Required `nullable-vs-required-columns`: The ORM column declarations show different nullability.

Acceptable source: `backend/app/models.py:17-25`

```text
17:     id: Mapped[int] = mapped_column(Integer, primary_key=True)
18:     repository: Mapped[str] = mapped_column(String, nullable=False)
19:     file_path: Mapped[str] = mapped_column(String, nullable=False)
20:     symbol_type: Mapped[str] = mapped_column(String, nullable=False)
21:     symbol_name: Mapped[str | None] = mapped_column(String, nullable=True)
22:     start_line: Mapped[int] = mapped_column(Integer, nullable=False)
… (intervening source lines omitted)
25:     embedding: Mapped[list[float]] = mapped_column(VECTOR(384), nullable=False)
```

DEV1 overlap: **LOW** — identifier-02: span overlap in backend/app/models.py

HOLDOUT overlap: **LOW** — holdout-cross-04: span overlap in backend/app/models.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-long-01 — semantic_conceptual

Tags: long_chunk, later_source, ast_metadata

Question: What happens if the AST reports no end-line location for a supported top-level symbol during chunking?

Answerable: yes

Expected-answer rubric: chunk_python_file raises SourceFileError rather than emitting a chunk with an invented end boundary.

Required `symbol-endline-guard`: The supported-symbol branch explicitly checks end_lineno before slicing source.

Oversized accepted chunk: backend/app/services/chunker.py::chunk_python_file: 776 tokens > 256; evidence begins near token 644

Acceptable source: `backend/app/services/chunker.py:175-188`

```text
175:         flush_companion()
176:         if node.end_lineno is None:
177:             raise SourceFileError(f"Missing end-line metadata for {relative_path}")
178:
… (intervening source lines omitted)
188:                 end_line=node.end_lineno,
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **LOW** — holdout-semantic-03: span overlap in backend/app/services/chunker.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-long-02 — semantic_conceptual

Tags: long_chunk, later_source, provider_boundary

Question: How does answer generation treat a completion with no choice compared with one whose message content is empty?

Answerable: yes

Expected-answer rubric: Missing choices/message content shape raises RAGGenerationError for a response without an answer; empty answer content raises RAGGenerationError with a separate empty-answer message.

Required `completion-shape-and-empty`: The late response-validation branch distinguishes malformed structure from empty content.

Oversized accepted chunk: backend/app/services/rag.py::answer_question: 436 tokens > 256; evidence begins near token 350

Acceptable source: `backend/app/services/rag.py:136-142`

```text
136:     try:
137:         answer = completion.choices[0].message.content
138:     except (AttributeError, IndexError) as exc:
139:         raise RAGGenerationError("LLM response did not contain an answer") from exc
140:     if not answer:
141:         raise RAGGenerationError("LLM returned an empty answer")
142:     return RAGResult(answer=answer, sources=context.included_chunks)
```

DEV1 overlap: **LOW** — architecture-04: span overlap in backend/app/services/rag.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-long-03 — semantic_conceptual

Tags: long_chunk, later_source, fail_closed_discovery

Question: How does discovery handle an OS error while classifying an individual directory entry, after the directory has already opened?

Answerable: yes

Expected-answer rubric: The entry-classification try block catches OSError and raises RepositoryReadError, so discovery fails instead of silently returning a partial file list.

Required `entry-classification-error`: The late traversal branch handles individual DirEntry failures.

Oversized accepted chunk: backend/app/services/repository_loader.py::discover_python_files: 392 tokens > 256; evidence begins near token 325

Acceptable source: `backend/app/services/repository_loader.py:102-105`

```text
102:             except OSError as exc:
103:                 raise RepositoryReadError(
104:                     f"Could not classify repository entry {entry.path}: {exc}"
105:                 ) from exc
```

DEV1 overlap: **LOW** — semantic-01: span overlap in backend/app/services/repository_loader.py; multi-01: span overlap in backend/app/services/repository_loader.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-long-04 — configuration_constants

Tags: long_chunk, later_source, provider_config

Question: What upper bound applies to an operator-supplied LLM request timeout?

Answerable: yes

Expected-answer rubric: Settings.llm_timeout_seconds defaults to 30.0 seconds, must be positive, and cannot exceed 300 seconds.

Required `timeout-upper-bound`: The Settings field declares its default and validation limit.

Oversized accepted chunk: backend/app/config.py::Settings: 561 tokens > 256; evidence begins near token 354

Acceptable source: `backend/app/config.py:39-44`

```text
39:     llm_timeout_seconds: float = Field(
40:         default=30.0,
41:         gt=0,
42:         le=300,
43:         validation_alias="LLM_TIMEOUT_SECONDS",
44:     )
```

DEV1 overlap: **LOW** — multi-04: span overlap in backend/app/config.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-long-05 — architecture

Tags: long_chunk, later_source, evaluation_metadata

Question: What reproducibility details does the evaluator attach to its report after scoring cases?

Answerable: yes

Expected-answer rubric: The report records dataset and case-set hashes, corpus manifest and source revision, Git revision/dirty flag, model identity and limit, chunking identifier, candidate depth, context budget and package versions.

Required `report-reproducibility-fields`: The late result-construction branch enumerates report metadata.

Oversized accepted chunk: backend/app/evaluation.py::evaluate_dataset: 1282 tokens > 256; evidence begins near token 891

Acceptable source: `backend/app/evaluation.py:609-643`

```text
609:     revision, dirty = _git_revision()
… (intervening source lines omitted)
611:     return {
612:         "reproducibility": {
613:             "dataset_version": dataset.dataset_version,
… (intervening source lines omitted)
615:             "dataset_sha256": dataset_hash,
616:             "case_set_sha256": compute_case_set_hash(dataset),
617:             "corpus_manifest_sha256": actual_manifest,
… (intervening source lines omitted)
629:             ),
630:             "chunking_identifier": CHUNKING_IDENTIFIER,
631:             "candidate_depth": candidate_depth,
… (intervening source lines omitted)
643:     }
```

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-mixed-01 — cross_module_behavior

Tags: mixed_semantic_exact, multi_evidence, repository_scope

Question: When /ask receives a repository selection, through which request and service fields does it reach retrieval?

Answerable: yes

Expected-answer rubric: AskRequest carries an optional repository field; the route passes it to answer_question, which passes it into search_code.

Multi-evidence rationale (3 units): The request field, route mapping, and RAG retrieval call form three distinct handoffs.
One unit alone sufficient: no

Required `ask-request-scope`: Shows the incoming field on the ask request model.

Acceptable source: `backend/app/schemas.py:58-63`

```text
58: class AskRequest(BaseModel):
59:     question: str = Field(min_length=1)
60:     top_k: int | None = Field(default=None, ge=1, le=50)
61:     repository: str | None = None
62:
63:     _validate_repository = field_validator("repository")(_normalise_repository_scope)
```

Required `ask-route-forwarding`: Shows the HTTP-to-service handoff.

Oversized accepted chunk: backend/app/api/routes.py::ask_repository: 283 tokens > 256; evidence begins near token 2

Acceptable source: `backend/app/api/routes.py:97-108`

```text
97: @router.post("/ask", response_model=AskResponse)
… (intervening source lines omitted)
102:     try:
103:         result = answer_question(
104:             db,
… (intervening source lines omitted)
106:             request.top_k,
107:             request.repository,
108:         )
```

Required `rag-retrieval-forwarding`: Shows the service-to-retriever handoff.

Oversized accepted chunk: backend/app/services/rag.py::answer_question: 436 tokens > 256; evidence begins near token 2

Acceptable source: `backend/app/services/rag.py:96-110`

```text
96: def answer_question(
… (intervening source lines omitted)
99:     top_k: int | None = None,
100:     repository: str | None = None,
101: ) -> RAGResult:
… (intervening source lines omitted)
109:     try:
110:         retrieval_candidates = search_code(db, question, top_k, repository)
```

DEV1 overlap: **LOW** — route-04: span overlap in backend/app/api/routes.py; architecture-04: span overlap in backend/app/services/rag.py; cross-module-03: span overlap in backend/app/api/routes.py; near-match-02: span overlap in backend/app/schemas.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-mixed-02 — cross_module_behavior

Tags: mixed_semantic_exact, multi_evidence, configuration_use

Question: How does the example Postgres port setting relate to Compose's published port, and what must the local DATABASE_URL target?

Answerable: yes

Expected-answer rubric: .env.example declares POSTGRES_PORT and a localhost:5432 DATABASE_URL; Compose uses POSTGRES_PORT for the host-side loopback binding. If the port changes, DATABASE_URL must target the chosen host port.

Multi-evidence rationale (2 units): The example file establishes both application URL and configured host port; the separate Compose file establishes how that port is published.
One unit alone sufficient: no

Required `example-url-and-port`: Shows the backend URL and the configured Compose host port together in the example file.

Acceptable source: `.env.example:1-21`

```text
1: # PostgreSQL connection used by the locally-run FastAPI application.
2: DATABASE_URL=postgresql+psycopg://codebase_qa:codebase_qa@localhost:5432/codebase_qa
3:
… (intervening source lines omitted)
20: POSTGRES_PASSWORD=codebase_qa
21: POSTGRES_PORT=5432
```

Required `compose-port-substitution`: Shows where Compose consumes the port setting.

Acceptable source: `docker-compose.yml:8-9`

```text
8:     ports:
9:       - "127.0.0.1:${POSTGRES_PORT:-5432}:5432"
```

DEV1 overlap: **LOW** — path-04: span overlap in .env.example

HOLDOUT overlap: **LOW** — holdout-config-03: span overlap in docker-compose.yml

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-mixed-03 — cross_module_behavior

Tags: mixed_semantic_exact, multi_evidence, provider_config

Question: For a local OpenAI-compatible server, how does the documented placeholder API-key setting reach the created client?

Answerable: yes

Expected-answer rubric: The example says to use the local server's accepted placeholder API key; _create_client passes the configured API key into the OpenAI client options.

Multi-evidence rationale (2 units): Documentation explains the local-server value; client construction establishes its runtime use.
One unit alone sufficient: no

Required `placeholder-key-guidance`: Shows the documented local-server configuration expectation.

Acceptable source: `.env.example:9-13`

```text
9: # LLM settings used by POST /ask. Base URL is optional for the normal OpenAI endpoint.
10: # For an unauthenticated local compatible server, set its accepted placeholder API key.
11: LLM_BASE_URL=
12: LLM_API_KEY=
13: LLM_MODEL_NAME=
```

Required `client-key-option`: Shows the runtime client receives that setting.

Acceptable source: `backend/app/services/rag.py:85-93`

```text
85: def _create_client(settings: Settings, api_key: str) -> OpenAI:
86:     options: dict[str, object] = {
87:         "api_key": api_key,
88:         "timeout": settings.llm_timeout_seconds,
… (intervening source lines omitted)
92:         options["base_url"] = settings.llm_base_url.strip()
93:     return OpenAI(**options)
```

DEV1 overlap: **LOW** — path-04: span overlap in .env.example; multi-04: span overlap in backend/app/services/rag.py

HOLDOUT overlap: **LOW** — holdout-path-03: span overlap in backend/app/services/rag.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-mixed-04 — semantic_conceptual

Tags: mixed_semantic_exact, context_provenance

Question: What source identity is shown for a chunk without a symbol name in the model context?

Answerable: yes

Expected-answer rubric: build_context substitutes <module> for a missing symbol name and includes repository/file path, symbol type and line range in its source header.

Required `module-context-header`: The header construction shows the fallback label and provenance fields.

Acceptable source: `backend/app/services/rag.py:49-54`

```text
49:     for chunk in chunks:
50:         symbol = chunk.symbol_name or "<module>"
51:         header = (
52:             f"--- {chunk.repository}/{chunk.file_path} "
53:             f"[{chunk.symbol_type} {symbol}, lines {chunk.start_line}-{chunk.end_line}] ---\n"
54:         )
```

DEV1 overlap: **LOW** — identifier-04: span overlap in backend/app/services/rag.py; multi-03: span overlap in backend/app/services/rag.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-mixed-05 — semantic_conceptual

Tags: mixed_semantic_exact, repository_scope

Question: Why does a valid but unknown repository name produce no scoped semantic hits instead of switching to a global search?

Answerable: yes

Expected-answer rubric: A supplied nonblank repository is used as a SQL equality predicate before ordering and limiting; there is no fallback branch when it matches zero rows.

Required `scoped-sql-predicate`: The search statement applies repository filtering prior to ranking and limiting.

Oversized accepted chunk: backend/app/services/retrieval.py::search_code: 458 tokens > 256; evidence begins near token 127

Acceptable source: `backend/app/services/retrieval.py:45-65`

```text
45:     scope = repository.strip() if repository is not None else None
… (intervening source lines omitted)
52:     if scope is not None:
53:         statement = statement.where(CodeChunk.repository == scope)
54:     statement = statement.order_by(
… (intervening source lines omitted)
62:         CodeChunk.id,
63:     ).limit(limit)
64:
65:     try:
```

DEV1 overlap: **LOW** — architecture-03: span overlap in backend/app/services/retrieval.py; multi-03: span overlap in backend/app/services/retrieval.py

HOLDOUT overlap: **LOW** — holdout-architecture-03: span overlap in backend/app/services/retrieval.py; holdout-multi-02: span overlap in backend/app/services/retrieval.py; holdout-multi-04: span overlap in backend/app/services/retrieval.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-ordinary-01 — semantic_conceptual

Tags: ordinary_developer_question, chunk_structure

Question: Are methods inside a Python class emitted as separate chunks by the accepted AST policy?

Answerable: yes

Expected-answer rubric: No. The loop selects only top-level FunctionDef, AsyncFunctionDef and ClassDef nodes from tree.body, emitting the whole class node as a class chunk rather than visiting each method.

Required `top-level-only-loop`: The top-level node selection and chunk append show the class granularity.

Oversized accepted chunk: backend/app/services/chunker.py::chunk_python_file: 776 tokens > 256; evidence begins near token 293

Acceptable source: `backend/app/services/chunker.py:131-190`

```text
131:     source_lines = source.splitlines(keepends=True)
132:     supported_nodes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
133:     symbol_nodes = [node for node in tree.body if isinstance(node, supported_nodes)]
134:
135:     if not symbol_nodes and tree.body and source.strip():
136:         return [
… (intervening source lines omitted)
170:
171:     for node in tree.body:
172:         if not isinstance(node, supported_nodes):
… (intervening source lines omitted)
184:                 source_lines=source_lines,
185:                 symbol_type=_symbol_type(node),
186:                 symbol_name=node.name,
… (intervening source lines omitted)
190:         )
```

DEV1 overlap: **LOW** — semantic-02: span overlap in backend/app/services/chunker.py; multi-01: span overlap in backend/app/services/chunker.py

HOLDOUT overlap: **LOW** — holdout-semantic-03: span overlap in backend/app/services/chunker.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-ordinary-02 — semantic_conceptual

Tags: ordinary_developer_question, grounding

Question: What instruction tells the answer provider to acknowledge insufficient repository evidence?

Answerable: yes

Expected-answer rubric: SYSTEM_PROMPT tells the model to answer from supplied repository context, avoid invented behavior, and say clearly when context is insufficient.

Required `insufficient-context-instruction`: The fixed system prompt carries the grounding instruction.

Acceptable source: `backend/app/services/rag.py:13-17`

```text
13: MAX_CONTEXT_CHARACTERS = 12_000
… (intervening source lines omitted)
15: Do not invent repository behavior that is not supported by the context.
16: If the supplied context is insufficient, say so clearly.
17: When useful, refer to source file paths and line ranges from the context."""
```

DEV1 overlap: **LOW** — config-03: span overlap in backend/app/services/rag.py

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-ordinary-03 — semantic_conceptual

Tags: ordinary_developer_question, source_errors

Question: What location detail does a Python syntax-error message include when AST parsing fails?

Answerable: yes

Expected-answer rubric: chunk_python_file reports the relative file path, line number if available, and parser message in SourceFileError.

Required `syntax-error-location`: The ast.parse exception branch formats the source error location.

Oversized accepted chunk: backend/app/services/chunker.py::chunk_python_file: 776 tokens > 256; evidence begins near token 204

Acceptable source: `backend/app/services/chunker.py:123-129`

```text
123:     try:
… (intervening source lines omitted)
125:     except SyntaxError as exc:
126:         location = f"line {exc.lineno}" if exc.lineno is not None else "unknown line"
127:         raise SourceFileError(
128:             f"Invalid Python syntax in {relative_path} at {location}: {exc.msg}"
129:         ) from exc
```

DEV1 overlap: **LOW** — semantic-02: span overlap in backend/app/services/chunker.py; multi-01: span overlap in backend/app/services/chunker.py

HOLDOUT overlap: **LOW** — holdout-near-02: span overlap in backend/app/services/chunker.py

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-unanswerable-01 — unanswerable_insufficient_context

Tags: unanswerable, file_size_policy

Question: Where does indexing enforce a maximum byte size for each individual Python source file before embedding it?

Answerable: no

Expected-answer rubric: No per-Python-file byte limit is configured or enforced by the frozen source. The config-chunk character cap is a chunking limit, not a Python-file ingestion limit.

Why insufficient: The frozen discovery/chunking/indexing path has no maximum byte size for an individual Python file.

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## dev2-unanswerable-02 — unanswerable_insufficient_context

Tags: unanswerable, citation_validation

Question: Where does the backend verify that file-path citations written in an LLM answer refer to the returned source list?

Answerable: no

Expected-answer rubric: The frozen backend has no post-generation citation validator. It returns generated text and the supplied context's sources, but does not parse or check citations in the answer text.

Why insufficient: There is no answer-text citation parser or validator in the frozen RAG/API path.

DEV1 overlap: **NONE** — none detected

HOLDOUT overlap: **NONE** — none detected

Review: [ ] ACCEPT  [ ] EDIT  [ ] REJECT
Notes: ____________________

## Candidate summary

Cases: 45; answerable: 43; multi-evidence: 16; oversized-tagged: 26.
Categories: {'cross_module_behavior': 7, 'multiple_required_evidence': 4, 'architecture': 7, 'semantic_conceptual': 14, 'configuration_constants': 5, 'exact_identifier': 1, 'difficult_near_matches': 5, 'unanswerable_insufficient_context': 2}

Tags: {'multi_evidence': 16, 'path_safety': 1, 'mixed_source': 1, 'module_fallback': 1, 'failure_boundary': 4, 'long_chunk': 7, 'early_source': 1, 'configuration_use': 2, 'api_contract': 1, 'near_match': 1, 'file_reading': 1, 'across_long_chunks': 1, 'evaluation_safety': 2, 'reproducibility': 2, 'index_identity': 1, 'database_setup': 2, 'configuration': 1, 'navigation': 1, 'repository_scope': 3, 'context_selection': 2, 'candidate_competition': 1, 'empty_result': 1, 'determinism': 1, 'discovery': 1, 'embedding_validation': 1, 'source_coverage': 1, 'edge_case': 1, 'config_source': 1, 'provenance': 1, 'exact_token': 5, 'embedding_batch': 1, 'database_session': 1, 'provider_config': 3, 'chunk_identity': 1, 'distractor': 5, 'module_structure': 1, 'error_boundary': 1, 'input_validation': 1, 'http_error': 1, 'database_model': 1, 'later_source': 5, 'ast_metadata': 1, 'provider_boundary': 1, 'fail_closed_discovery': 1, 'evaluation_metadata': 1, 'mixed_semantic_exact': 5, 'context_provenance': 1, 'ordinary_developer_question': 3, 'chunk_structure': 1, 'grounding': 1, 'source_errors': 1, 'unanswerable': 2, 'file_size_policy': 1, 'citation_validation': 1}
