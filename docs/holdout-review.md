# Holdout candidates — human review required

Machine-prepared source-grounded holdout candidates pending human review.
Do **not** run retrieval/evaluation on these questions before review and freeze.
Source revision: `7a3b7b05087793975ae0a84d85e7d691d9f3352e`. Candidate hash: `4b43650c5d60643d197fe33005823ce9c8f9570746d958dce0b845bf12ea88e7`.

Choose ACCEPT, REJECT, or EDIT; record notes. No default acceptance is implied.

## holdout-semantic-01 — semantic_conceptual

**Question:** What causes a supported-looking configuration file to be skipped as binary or undecodable text?

**Answerable:** yes

**Expected-answer rubric:** The loader samples bytes, rejects NUL-containing files, and rejects samples that cannot decode as UTF-8.

**Required unit `config-text-guard`:** This guard decides whether config candidates are text before loading.

Acceptable source: `backend/app/services/repository_loader.py:49-63`

```text
49: def _is_utf8_text_file(path: Path) -> bool:
… (intervening source lines omitted)
59:     try:
60:         sample.decode("utf-8")
61:     except UnicodeDecodeError:
62:         return False
63:     return True
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-semantic-02 — semantic_conceptual

**Question:** Why can a parenthesised multi-line decorator still appear in a function's source provenance?

**Answerable:** yes

**Expected-answer rubric:** Token scanning walks back from the AST decorator expression to its @ token, which can precede the expression's own line.

**Required unit `decorator-at-token`:** The token scan establishes the true opening line.

Acceptable source: `backend/app/services/chunker.py:42-64`

```text
42: def _decorator_start_line(source: str, decorator: ast.expr) -> int:
… (intervening source lines omitted)
44:
45:     tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
46:     target_line = decorator.lineno
… (intervening source lines omitted)
61:     for token in reversed(tokens[: target_index + 1]):
62:         if token.type == tokenize.OP and token.string == "@":
63:             return token.start[0]
64:     return target_line
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-semantic-03 — semantic_conceptual

**Question:** What happens to imports or assignments between two top-level Python definitions?

**Answerable:** yes

**Expected-answer rubric:** The chunker gathers consecutive uncovered statements into a module_companion span and flushes it before each supported definition.

**Required unit `companion-flush`:** The loop and flush make those statements independently represented.

Acceptable source: `backend/app/services/chunker.py:148-194`

```text
148:     chunks: list[SourceChunk] = []
… (intervening source lines omitted)
150:
151:     def flush_companion() -> None:
152:         if not companion_nodes:
… (intervening source lines omitted)
172:         if not isinstance(node, supported_nodes):
173:             companion_nodes.append(node)
174:             continue
175:         flush_companion()
176:         if node.end_lineno is None:
… (intervening source lines omitted)
191:
192:     flush_companion()
193:
194:     return chunks
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-semantic-04 — semantic_conceptual

**Question:** How does config chunking avoid storing an empty file as a searchable chunk?

**Answerable:** yes

**Expected-answer rubric:** It returns no chunks for all-whitespace source and flushes only pending text with non-whitespace content.

**Required unit `config-blank-guard`:** Both the early return and flush guard determine emitted chunks.

Acceptable source: `backend/app/services/text_chunker.py:46-66`

```text
46:     if not source.strip():
47:         return []
… (intervening source lines omitted)
54:         nonlocal pending_size
55:         if pending and "".join(text for _, text in pending).strip():
56:             chunks.append(
… (intervening source lines omitted)
66:             )
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-semantic-05 — semantic_conceptual

**Question:** How is a generated answer displayed as Markdown without explicitly injecting raw HTML?

**Answerable:** yes

**Expected-answer rubric:** The Answer component passes answer text as children of ReactMarkdown; it does not call dangerouslySetInnerHTML or enable a raw-HTML plugin.

**Required unit `answer-markdown-component`:** The render path shows the Markdown component and original answer text.

Acceptable source: `frontend/src/components/Answer.tsx:7-17`

```text
7: export function Answer({ answer }: AnswerProps) {
… (intervening source lines omitted)
14:       <div className="answer-markdown">
15:         <ReactMarkdown>{answer}</ReactMarkdown>
16:       </div>
17:     </section>
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-identifier-01 — exact_identifier

**Question:** What validates that a requested local indexing root exists and is a directory before traversal?

**Answerable:** yes

**Expected-answer rubric:** resolve_repository_root resolves the path, then checks exists() and is_dir().

**Required unit `root-path-check`:** The named helper performs the pre-traversal path checks.

Acceptable source: `backend/app/services/repository_loader.py:31-39`

```text
31: def resolve_repository_root(repository_path: str | Path) -> Path:
32:     """Resolve and validate a local repository directory."""
… (intervening source lines omitted)
36:         raise RepositoryPathError(f"Repository path does not exist: {root}")
37:     if not root.is_dir():
38:         raise RepositoryPathError(f"Repository path is not a directory: {root}")
39:     return root
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-identifier-02 — exact_identifier

**Question:** What helper splits an unusually long single config line into bounded original-text pieces?

**Answerable:** yes

**Expected-answer rubric:** _bounded_line_pieces emits source-line-numbered slices, including pieces of long individual lines.

**Required unit `bounded-config-line-helper`:** The helper's offset loop defines how a long line is divided.

Acceptable source: `backend/app/services/text_chunker.py:11-22`

```text
11: def _bounded_line_pieces(source: str) -> list[tuple[int, str]]:
12:     """Split source into bounded pieces while retaining original characters."""
… (intervening source lines omitted)
17:             continue
18:         for offset in range(0, len(line), MAX_CONFIG_CHUNK_CHARACTERS):
19:             pieces.append(
… (intervening source lines omitted)
22:     return pieces
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-identifier-03 — exact_identifier

**Question:** Which retrieval function rejects an out-of-range result count before querying the vector column?

**Answerable:** yes

**Expected-answer rubric:** search_code validates top_k against MAX_TOP_K before calling embed_query and building its SQL statement.

**Required unit `search-limit-validator`:** The function contains the result-count guard before embedding and SQL.

Acceptable source: `backend/app/services/retrieval.py:33-50`

```text
33: def search_code(
34:     db: Session,
… (intervening source lines omitted)
41:     limit = get_settings().default_top_k if top_k is None else top_k
42:     if not 1 <= limit <= MAX_TOP_K:
43:         raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
… (intervening source lines omitted)
50:     distance = CodeChunk.embedding.cosine_distance(query_vector).label("cosine_distance")
```

**DEV leakage review flags:** DEV span overlap architecture-03: backend/app/services/retrieval.py lines 33-50; DEV span overlap multi-03: backend/app/services/retrieval.py lines 33-50

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-identifier-04 — exact_identifier

**Question:** Which helper chooses an explicit repository name or falls back to the root directory name?

**Answerable:** yes

**Expected-answer rubric:** storage._resolve_repository_name strips an explicit name or uses root.name, then rejects empty names.

**Required unit `repository-name-helper`:** The helper implements name choice before indexing.

Acceptable source: `backend/app/services/storage.py:29-33`

```text
29: def _resolve_repository_name(root: Path, repository_name: str | None) -> str:
30:     name = repository_name.strip() if repository_name is not None else root.name
31:     if not name:
… (intervening source lines omitted)
33:     return name
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-identifier-05 — exact_identifier

**Question:** What validator rejects an LLM endpoint setting that is not an absolute HTTP(S) URL?

**Answerable:** yes

**Expected-answer rubric:** Settings.validate_llm_base_url uses urlparse and checks scheme and netloc.

**Required unit `llm-base-url-validator`:** The decorator and method identify the validation boundary.

Acceptable source: `backend/app/config.py:52-60`

```text
52:     @field_validator("llm_base_url")
53:     @classmethod
54:     def validate_llm_base_url(cls, value: str | None) -> str | None:
55:         if value is None:
… (intervening source lines omitted)
57:         parsed = urlparse(value)
58:         if parsed.scheme not in {"http", "https"} or not parsed.netloc:
59:             raise ValueError("LLM_BASE_URL must be an absolute http(s) URL")
60:         return value.rstrip("/")
```

**DEV leakage review flags:** DEV span overlap multi-04: backend/app/config.py lines 52-60

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-config-01 — configuration_constants

**Question:** What database-engine option checks pooled connections before using them?

**Answerable:** yes

**Expected-answer rubric:** The engine is created with pool_pre_ping=True.

**Required unit `engine-pre-ping`:** The engine constructor contains the option.

Acceptable source: `backend/app/database.py:10-12`

```text
10:
11: engine = create_engine(get_settings().database_url, pool_pre_ping=True)
12: SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-config-02 — configuration_constants

**Question:** What maximum requested result count does the dense search service permit?

**Answerable:** yes

**Expected-answer rubric:** MAX_TOP_K is 50 and search_code rejects limits outside 1 to 50.

**Required unit `dense-result-cap`:** The constant defines the service's maximum.

Acceptable source: `backend/app/services/retrieval.py:14-14`

```text
14: MAX_TOP_K = 50
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-config-03 — configuration_constants

**Question:** How is the development database port kept off non-loopback host interfaces?

**Answerable:** yes

**Expected-answer rubric:** Compose publishes the configurable host port bound to 127.0.0.1 only.

**Required unit `compose-loopback-binding`:** The published port string contains the loopback host address.

Acceptable source: `docker-compose.yml:8-9`

```text
8:     ports:
9:       - "127.0.0.1:${POSTGRES_PORT:-5432}:5432"
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-config-04 — configuration_constants

**Question:** What size cap controls config-text chunks in the accepted source policy?

**Answerable:** yes

**Expected-answer rubric:** MAX_CONFIG_CHUNK_CHARACTERS is 4,000 characters; this is not a tokenizer-token guarantee.

**Required unit `config-character-cap`:** The config chunker declares its bound explicitly.

Acceptable source: `backend/app/services/text_chunker.py:8-8`

```text
8: MAX_CONFIG_CHUNK_CHARACTERS = 4_000
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-config-05 — configuration_constants

**Question:** What settings-file policy ignores empty environment values and unknown keys?

**Answerable:** yes

**Expected-answer rubric:** The Settings model uses env_ignore_empty=True and extra='ignore'.

**Required unit `settings-env-policy`:** The model configuration sets both behaviours.

Acceptable source: `backend/app/config.py:18-24`

```text
18:     model_config = SettingsConfigDict(
… (intervening source lines omitted)
20:         env_file_encoding="utf-8",
21:         env_ignore_empty=True,
22:         case_sensitive=False,
23:         extra="ignore",
24:     )
```

**DEV leakage review flags:** DEV span overlap multi-04: backend/app/config.py lines 18-24

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-path-01 — filename_path

**Question:** Where does the browser-side code send its JSON question request?

**Answerable:** yes

**Expected-answer rubric:** frontend/src/api.ts calls fetch('/ask') with POST and JSON headers/body.

**Required unit `browser-ask-fetch`:** The browser transport path and method are present in one file.

Acceptable source: `frontend/src/api.ts:40-48`

```text
40: export async function askQuestion(request: AskRequest): Promise<AskResponse> {
… (intervening source lines omitted)
43:   try {
44:     response = await fetch("/ask", {
45:       method: "POST",
46:       headers: { "Content-Type": "application/json" },
47:       body: JSON.stringify(request),
48:     });
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-path-02 — filename_path

**Question:** Which frontend file displays retrieved source line numbers beside a file path?

**Answerable:** yes

**Expected-answer rubric:** frontend/src/components/SourceList.tsx displays repository/file_path and start/end line range.

**Required unit `source-card-provenance`:** The source card renders path and line provenance.

Acceptable source: `frontend/src/components/SourceList.tsx:17-26`

```text
17:           return (
18:             <article className="source-card" key={`${source.file_path}-${source.start_line}-${index}`}>
19:               <div className="source-card-header">
… (intervening source lines omitted)
21:                   <p className="source-path">
22:                     {source.repository}/{source.file_path}
23:                   </p>
24:                   <p className="source-symbol">
25:                     {source.symbol_type}: {symbol} · lines {source.start_line}–{source.end_line}
26:                   </p>
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-path-03 — filename_path

**Question:** Where is the OpenAI-compatible client's optional base URL applied?

**Answerable:** yes

**Expected-answer rubric:** backend/app/services/rag.py applies llm_base_url inside _create_client.

**Required unit `provider-base-url-location`:** The client factory conditionally supplies base_url.

Acceptable source: `backend/app/services/rag.py:85-93`

```text
85: def _create_client(settings: Settings, api_key: str) -> OpenAI:
… (intervening source lines omitted)
91:     if settings.llm_base_url and settings.llm_base_url.strip():
92:         options["base_url"] = settings.llm_base_url.strip()
93:     return OpenAI(**options)
```

**DEV leakage review flags:** DEV span overlap multi-04: backend/app/services/rag.py lines 85-93

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-path-04 — filename_path

**Question:** Which separate loader handles allowlisted non-Python source as text rather than Python AST?

**Answerable:** yes

**Expected-answer rubric:** backend/app/services/text_chunker.py provides chunk_config_file.

**Required unit `config-loader-location`:** The named function is the non-AST text path.

Acceptable source: `backend/app/services/text_chunker.py:25-30`

```text
25: def chunk_config_file(
26:     file_path: str | Path,
… (intervening source lines omitted)
29: ) -> list[SourceChunk]:
30:     """Chunk one supported UTF-8 config file without applying Python semantics."""
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-path-05 — filename_path

**Question:** Where is the narrow allowlist for non-Python repository files declared?

**Answerable:** yes

**Expected-answer rubric:** repository_loader.py declares SQL/YAML suffixes plus .env.example and vite.config.ts filenames.

**Required unit `config-allowlist-location`:** The declarations specify the supported paths.

Acceptable source: `backend/app/services/repository_loader.py:19-20`

```text
19: SUPPORTED_CONFIG_SUFFIXES = frozenset({".sql", ".yaml", ".yml"})
20: SUPPORTED_CONFIG_FILENAMES = frozenset({".env.example", "vite.config.ts"})
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-route-01 — decorator_api_route

**Question:** Which HTTP handler returns a 201 status when local indexing succeeds?

**Answerable:** yes

**Expected-answer rubric:** index_local_repository is decorated with POST /repositories/index and HTTP_201_CREATED.

**Required unit `index-status-decorator`:** The decorator defines its status code.

Acceptable source: `backend/app/api/routes.py:53-61`

```text
53: @router.post(
… (intervening source lines omitted)
55:     response_model=IndexRepositoryResponse,
56:     status_code=status.HTTP_201_CREATED,
57: )
58: def index_local_repository(
59:     request: IndexRepositoryRequest,
… (intervening source lines omitted)
61: ) -> IndexRepositoryResponse:
```

**DEV leakage review flags:** DEV span overlap route-02: backend/app/api/routes.py lines 53-61; DEV span overlap cross-module-01: backend/app/api/routes.py lines 53-61

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-route-02 — decorator_api_route

**Question:** What client-facing status does the search route use when embedding or retrieval fails internally?

**Answerable:** yes

**Expected-answer rubric:** The /search handler responds with HTTP 500 and a generic Semantic search failed detail.

**Required unit `search-internal-error-status`:** The route maps the internal failure classes to HTTP 500.

Acceptable source: `backend/app/api/routes.py:82-94`

```text
82: @router.post("/search", response_model=SearchResponse)
… (intervening source lines omitted)
92:         _log_internal_failure("Semantic search failed", exc)
93:         raise HTTPException(status_code=500, detail="Semantic search failed.") from exc
94:     return SearchResponse(results=[_chunk_response(chunk) for chunk in results])
```

**DEV leakage review flags:** DEV span overlap route-03: backend/app/api/routes.py lines 82-94; DEV span overlap cross-module-02: backend/app/api/routes.py lines 82-94

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-route-03 — decorator_api_route

**Question:** What status is returned when the answer provider fails after retrieval?

**Answerable:** yes

**Expected-answer rubric:** The /ask route maps RAGGenerationError to HTTP 502.

**Required unit `ask-provider-error-status`:** The handler has the provider-error exception branch.

Acceptable source: `backend/app/api/routes.py:109-118`

```text
109:     except ValueError as exc:
… (intervening source lines omitted)
112:         raise HTTPException(status_code=503, detail=str(exc)) from exc
113:     except RAGGenerationError as exc:
114:         _log_internal_failure("LLM generation failed", exc)
115:         raise HTTPException(status_code=502, detail="LLM generation failed.") from exc
116:     except (EmbeddingError, RetrievalError) as exc:
… (intervening source lines omitted)
118:         raise HTTPException(status_code=500, detail="RAG retrieval failed.") from exc
```

**DEV leakage review flags:** DEV span overlap route-04: backend/app/api/routes.py lines 109-117; DEV span overlap cross-module-03: backend/app/api/routes.py lines 109-117

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-route-04 — decorator_api_route

**Question:** Which decorator applies repository-scope normalisation to a request body?

**Answerable:** yes

**Expected-answer rubric:** field_validator('repository') applies _normalise_repository_scope; either SearchRequest or AskRequest demonstrates the same fact.

**Required unit `request-scope-validator`:** Either request-model declaration independently demonstrates the shared validator.

Acceptable source: `backend/app/schemas.py:35-40`

```text
35: class SearchRequest(BaseModel):
… (intervening source lines omitted)
39:
40:     _validate_repository = field_validator("repository")(_normalise_repository_scope)
```

Acceptable source: `backend/app/schemas.py:58-63`

```text
58: class AskRequest(BaseModel):
… (intervening source lines omitted)
62:
63:     _validate_repository = field_validator("repository")(_normalise_repository_scope)
```

**DEV leakage review flags:** DEV span overlap near-match-02: backend/app/schemas.py lines 58-63

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-route-05 — decorator_api_route

**Question:** What decorator makes embedding-model construction lazy and cached?

**Answerable:** yes

**Expected-answer rubric:** @lru_cache(maxsize=1) decorates get_embedding_model.

**Required unit `embedding-cache-decorator`:** The decorator and function signature establish caching.

Acceptable source: `backend/app/services/embeddings.py:17-20`

```text
17: @lru_cache(maxsize=1)
18: def get_embedding_model() -> Any:
19:     """Load and cache the single MVP embedding model on first use."""
20:
```

**DEV leakage review flags:** DEV span overlap cross-module-04: backend/app/services/embeddings.py lines 17-20

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-architecture-01 — architecture

**Question:** How are database table definitions made available to the explicit first-run initializer?

**Answerable:** yes

**Expected-answer rubric:** Models share the SQLAlchemy declarative Base; the initializer imports that Base and calls Base.metadata.create_all(bind=engine).

**Required unit `declarative-base-definition`:** Defines the metadata-owning declarative base.

Acceptable source: `backend/app/models.py:8-9`

```text
8: class Base(DeclarativeBase):
9:     """Base class for SQLAlchemy declarative models."""
```

**Required unit `initial-metadata-create`:** Shows the initializer using that metadata.

Acceptable source: `backend/scripts/init_db.py:5-12`

```text
5:
… (intervening source lines omitted)
9:
10:     Base.metadata.create_all(bind=engine)
11:     print("Database tables initialized.")
12:
```

**DEV leakage review flags:** DEV source-anchor overlap path-03: Base.metadata.create_all; DEV span overlap path-03: backend/scripts/init_db.py lines 7-11

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-architecture-02 — architecture

**Question:** Where does indexing decide between AST-based Python chunking and config-text chunking?

**Answerable:** yes

**Expected-answer rubric:** storage._load_chunks branches on the .py suffix and calls chunk_python_file or chunk_config_file.

**Required unit `storage-chunker-dispatch`:** This is the central file-type dispatch.

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

**DEV leakage review flags:** DEV span overlap semantic-04: backend/app/services/storage.py lines 42-43; DEV span overlap multi-02: backend/app/services/storage.py lines 42-43

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-architecture-03 — architecture

**Question:** How are exact cosine-distance ties made reproducible for a fixed index snapshot?

**Answerable:** yes

**Expected-answer rubric:** SQL ordering follows distance with repository, path, line range, symbol metadata, then row ID.

**Required unit `cosine-tie-order`:** The query's order_by establishes deterministic tie-breakers.

Acceptable source: `backend/app/services/retrieval.py:54-63`

```text
54:     statement = statement.order_by(
… (intervening source lines omitted)
56:         CodeChunk.repository,
57:         CodeChunk.file_path,
58:         CodeChunk.start_line,
… (intervening source lines omitted)
61:         func.coalesce(CodeChunk.symbol_name, ""),
62:         CodeChunk.id,
63:     ).limit(limit)
```

**DEV leakage review flags:** DEV span overlap architecture-03: backend/app/services/retrieval.py lines 54-63; DEV span overlap multi-03: backend/app/services/retrieval.py lines 54-63

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-architecture-04 — architecture

**Question:** What ensures the per-answer provider client is closed after a request failure?

**Answerable:** yes

**Expected-answer rubric:** The chat completion call is wrapped in a try/finally whose finally closes the client.

**Required unit `provider-client-finally`:** The finally clause covers success and provider-error paths.

Acceptable source: `backend/app/services/rag.py:122-135`

```text
122:     client = _create_client(settings, api_key)
… (intervening source lines omitted)
132:         raise RAGGenerationError(f"LLM request failed: {exc}") from exc
133:     finally:
134:         client.close()
135:
```

**DEV leakage review flags:** DEV span overlap architecture-04: backend/app/services/rag.py lines 122-135

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-architecture-05 — architecture

**Question:** How does the API avoid placing raw internal exception text in its diagnostic log entry?

**Answerable:** yes

**Expected-answer rubric:** The route logger records a stable message and exception class name rather than formatting or serializing the exception itself.

**Required unit `route-safe-error-log`:** The logging helper determines the diagnostic payload.

Acceptable source: `backend/app/api/routes.py:36-39`

```text
36: def _log_internal_failure(message: str, error: Exception) -> None:
… (intervening source lines omitted)
38:
39:     logger.error("%s (%s)", message, type(error).__name__)
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-cross-01 — cross_module_behavior

**Question:** How does the configured database URL become the connection target for request sessions?

**Answerable:** yes

**Expected-answer rubric:** Settings supplies database_url; database.py passes it to create_engine and binds SessionLocal to that engine.

**Required unit `database-url-setting`:** Defines the configurable connection URL.

Acceptable source: `backend/app/config.py:26-29`

```text
26:     database_url: str = Field(
27:         default="postgresql+psycopg://codebase_qa:codebase_qa@localhost:5432/codebase_qa",
28:         validation_alias="DATABASE_URL",
29:     )
```

**Required unit `database-engine-binding`:** Shows the setting consumed by engine and session factory.

Acceptable source: `backend/app/database.py:10-12`

```text
10:
11: engine = create_engine(get_settings().database_url, pool_pre_ping=True)
12: SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
```

**DEV leakage review flags:** DEV span overlap multi-04: backend/app/config.py lines 26-29

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-cross-02 — cross_module_behavior

**Question:** How does an allowlisted YAML file reach a text chunker instead of the Python parser?

**Answerable:** yes

**Expected-answer rubric:** Discovery allows .yaml/.yml and includes config sources; storage dispatches non-.py files to chunk_config_file.

**Required unit `yaml-allowlist`:** Shows YAML is among discoverable config sources.

Acceptable source: `backend/app/services/repository_loader.py:19-20`

```text
19: SUPPORTED_CONFIG_SUFFIXES = frozenset({".sql", ".yaml", ".yml"})
20: SUPPORTED_CONFIG_FILENAMES = frozenset({".env.example", "vite.config.ts"})
```

**Required unit `nonpython-dispatch`:** Shows non-Python files are routed to the text chunker.

Acceptable source: `backend/app/services/storage.py:36-43`

```text
36: def _load_chunks(root: Path, repository: str, files: list[Path]) -> list[SourceChunk]:
… (intervening source lines omitted)
38:     for file_path in files:
39:         if file_path.suffix == ".py":
40:             chunks.extend(chunk_python_file(file_path, root, repository))
41:         else:
42:             chunks.extend(chunk_config_file(file_path, root, repository))
43:     return chunks
```

**DEV leakage review flags:** DEV span overlap semantic-04: backend/app/services/storage.py lines 42-43; DEV span overlap multi-02: backend/app/services/storage.py lines 42-43

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-cross-03 — cross_module_behavior

**Question:** What must the backend include in an answer source for the browser to accept the response?

**Answerable:** yes

**Expected-answer rubric:** AskResponse contains answer plus RetrievedChunkResponse sources; the browser verifies each source's provenance/content and numeric cosine_distance.

**Required unit `backend-ask-contract`:** Defines the backend response and source fields.

Acceptable source: `backend/app/schemas.py:43-51`

```text
43: class RetrievedChunkResponse(BaseModel):
44:     repository: str
45:     file_path: str
46:     symbol_type: str
… (intervening source lines omitted)
50:     content: str
51:     cosine_distance: float
```

**Required unit `browser-source-guard`:** Shows browser-side field checks.

Acceptable source: `frontend/src/api.ts:7-21`

```text
7: function isRetrievedSource(value: unknown): value is RetrievedSource {
… (intervening source lines omitted)
13:     typeof value.repository === "string" &&
14:     typeof value.file_path === "string" &&
15:     typeof value.symbol_type === "string" &&
… (intervening source lines omitted)
19:     typeof value.content === "string" &&
20:     typeof value.cosine_distance === "number"
21:   );
```

**DEV leakage review flags:** DEV source-anchor overlap architecture-03: cosine_distance; DEV source-anchor overlap multi-03: cosine_distance; DEV source-anchor overlap near-match-04: cosine_distance

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-cross-04 — cross_module_behavior

**Question:** How do parsed source line ranges become persistent row provenance during indexing?

**Answerable:** yes

**Expected-answer rubric:** SourceChunk carries file_path/start/end/content, and storage copies those fields into CodeChunk rows before one transaction publishes them.

**Required unit `parsed-provenance-fields`:** Defines the parser's source-provenance record.

Acceptable source: `backend/app/services/chunker.py:21-31`

```text
21: @dataclass(frozen=True, slots=True)
… (intervening source lines omitted)
28:     symbol_name: str | None
29:     start_line: int
30:     end_line: int
31:     content: str
```

**Required unit `row-provenance-copy`:** Shows the fields transferred to the ORM row.

Acceptable source: `backend/app/services/storage.py:62-74`

```text
62:     rows = [
… (intervening source lines omitted)
67:             symbol_name=chunk.symbol_name,
68:             start_line=chunk.start_line,
69:             end_line=chunk.end_line,
70:             content=chunk.content,
71:             embedding=embedding,
… (intervening source lines omitted)
74:     ]
```

**DEV leakage review flags:** DEV span overlap semantic-04: backend/app/services/storage.py lines 62-74; DEV span overlap multi-02: backend/app/services/storage.py lines 62-74

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-cross-05 — cross_module_behavior

**Question:** How do the question form and page together prevent submitting blank text or a duplicate in-flight request?

**Answerable:** yes

**Expected-answer rubric:** QuestionForm checks trimmed emptiness/loading before submit and disables the button; App.handleAsk repeats the trimmed/loading guard.

**Required unit `form-submit-guard`:** The form prevents and disables invalid/in-flight submission.

Acceptable source: `frontend/src/components/QuestionForm.tsx:16-22`

```text
16:   const isEmpty = question.trim().length === 0;
17:
… (intervening source lines omitted)
19:     event.preventDefault();
20:     if (!isLoading && !isEmpty) {
21:       onSubmit();
22:     }
```

**Required unit `app-submit-guard`:** The handler independently rejects whitespace and in-flight calls.

Acceptable source: `frontend/src/App.tsx:15-19`

```text
15:   async function handleAsk() {
16:     const trimmedQuestion = question.trim();
17:     if (!trimmedQuestion || isLoading) {
18:       return;
19:     }
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-multi-01 — multiple_required_evidence

**Question:** For a YAML candidate, what two checks and transformations prevent binary input from becoming a stored config chunk?

**Answerable:** yes

**Expected-answer rubric:** Discovery admits YAML but rejects NUL/non-UTF8 samples; the config chunker then reads UTF-8 text and only emits nonblank pieces.

**Required unit `config-binary-screen`:** Establishes the discovery-time binary/text distinction.

Acceptable source: `backend/app/services/repository_loader.py:49-63`

```text
49: def _is_utf8_text_file(path: Path) -> bool:
… (intervening source lines omitted)
57:     if b"\x00" in sample:
58:         return False
59:     try:
60:         sample.decode("utf-8")
61:     except UnicodeDecodeError:
62:         return False
63:     return True
```

**Required unit `config-text-read`:** Establishes the later UTF-8 read and no-blank-chunk rule.

Acceptable source: `backend/app/services/text_chunker.py:39-47`

```text
39:     try:
40:         source = path.read_text(encoding="utf-8")
41:     except (OSError, UnicodeError) as exc:
… (intervening source lines omitted)
45:
46:     if not source.strip():
47:         return []
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-multi-02 — multiple_required_evidence

**Question:** How is a whitespace-only repository selector rejected before a query could return global results?

**Answerable:** yes

**Expected-answer rubric:** Request validation strips/rejects blank scope, and search_code independently rejects supplied blank scope before applying a repository SQL predicate.

**Required unit `scope-request-validation`:** Covers the HTTP input boundary.

Acceptable source: `backend/app/schemas.py:8-14`

```text
8: def _normalise_repository_scope(value: str | None) -> str | None:
… (intervening source lines omitted)
10:         return None
11:     scope = value.strip()
12:     if not scope:
13:         raise ValueError("Repository scope must not be blank")
14:     return scope
```

**Required unit `scope-sql-safety`:** Covers the service boundary and scoped SQL semantics.

Acceptable source: `backend/app/services/retrieval.py:45-53`

```text
45:     scope = repository.strip() if repository is not None else None
46:     if repository is not None and not scope:
47:         raise ValueError("Repository scope must not be blank")
48:
… (intervening source lines omitted)
52:     if scope is not None:
53:         statement = statement.where(CodeChunk.repository == scope)
```

**DEV leakage review flags:** DEV span overlap architecture-03: backend/app/services/retrieval.py lines 45-53; DEV span overlap multi-03: backend/app/services/retrieval.py lines 45-53

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-multi-03 — multiple_required_evidence

**Question:** When LLM credentials are absent, where is the problem detected and how is it reported over HTTP?

**Answerable:** yes

**Expected-answer rubric:** RAG checks API key/model and raises LLMConfigurationError; the /ask route translates that to HTTP 503.

**Required unit `llm-required-config-check`:** Shows missing credentials/model are diagnosed.

Acceptable source: `backend/app/services/rag.py:70-82`

```text
70: def _required_llm_config(settings: Settings) -> tuple[str, str]:
… (intervening source lines omitted)
74:         name
75:         for name, value in (("LLM_API_KEY", api_key), ("LLM_MODEL_NAME", model))
76:         if not value
… (intervening source lines omitted)
78:     if missing:
79:         raise LLMConfigurationError(
80:             f"Missing required LLM configuration: {', '.join(missing)}"
… (intervening source lines omitted)
82:     return api_key, model
```

**Required unit `llm-config-http-status`:** Shows the corresponding HTTP response.

Acceptable source: `backend/app/api/routes.py:109-115`

```text
109:     except ValueError as exc:
110:         raise HTTPException(status_code=400, detail=str(exc)) from exc
111:     except LLMConfigurationError as exc:
112:         raise HTTPException(status_code=503, detail=str(exc)) from exc
113:     except RAGGenerationError as exc:
… (intervening source lines omitted)
115:         raise HTTPException(status_code=502, detail="LLM generation failed.") from exc
```

**DEV leakage review flags:** DEV span overlap route-04: backend/app/api/routes.py lines 109-115; DEV span overlap cross-module-03: backend/app/api/routes.py lines 109-115

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-multi-04 — multiple_required_evidence

**Question:** How is the configured default result count constrained before dense retrieval executes?

**Answerable:** yes

**Expected-answer rubric:** Settings declares DEFAULT_TOP_K with a 1–50 validation range; search_code uses that default when top_k is absent and independently checks against MAX_TOP_K.

**Required unit `validated-top-k-setting`:** Defines the configuration default and its allowed range.

Acceptable source: `backend/app/config.py:35-35`

```text
35:     default_top_k: int = Field(default=5, ge=1, le=50, validation_alias="DEFAULT_TOP_K")
```

**Required unit `retrieval-default-and-limit`:** Shows the service consumes and checks the configured limit.

Acceptable source: `backend/app/services/retrieval.py:41-43`

```text
41:     limit = get_settings().default_top_k if top_k is None else top_k
42:     if not 1 <= limit <= MAX_TOP_K:
43:         raise ValueError(f"top_k must be between 1 and {MAX_TOP_K}")
```

**DEV leakage review flags:** DEV span overlap architecture-03: backend/app/services/retrieval.py lines 41-43; DEV span overlap multi-03: backend/app/services/retrieval.py lines 41-43; DEV span overlap multi-04: backend/app/config.py lines 35-35

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-multi-05 — multiple_required_evidence

**Question:** What path does a browser question take through the development proxy to the backend ask handler?

**Answerable:** yes

**Expected-answer rubric:** The browser posts JSON to relative /ask; Vite proxies /ask to local port 8000; FastAPI's /ask handler accepts that request.

**Required unit `browser-relative-ask`:** Shows the page invokes the browser ask transport.

Acceptable source: `frontend/src/App.tsx:25-27`

```text
25:     try {
26:       const response = await askQuestion({ question: trimmedQuestion });
27:       setResult(response);
```

**Required unit `vite-ask-proxy`:** Shows the development forwarding target.

Acceptable source: `frontend/vite.config.ts:7-12`

```text
7:     proxy: {
8:       "/ask": {
9:         target: "http://127.0.0.1:8000",
10:         changeOrigin: true,
… (intervening source lines omitted)
12:     },
```

**Required unit `backend-ask-handler`:** Shows the backend destination.

Acceptable source: `backend/app/api/routes.py:97-101`

```text
97: @router.post("/ask", response_model=AskResponse)
98: def ask_repository(
99:     request: AskRequest,
… (intervening source lines omitted)
101: ) -> AskResponse:
```

**DEV leakage review flags:** DEV span overlap path-02: frontend/vite.config.ts lines 7-12; DEV source-anchor overlap route-04: @router.post("/ask"; DEV span overlap route-04: backend/app/api/routes.py lines 97-101; DEV span overlap cross-module-03: backend/app/api/routes.py lines 97-101

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-near-01 — difficult_near_matches

**Question:** Which repository error represents a traversal/read failure rather than a path that simply does not exist?

**Answerable:** yes

**Expected-answer rubric:** RepositoryReadError is the traversal/read subclass; RepositoryPathError is the general invalid-path base.

**Required unit `repository-read-error-distinction`:** The two adjacent exception declarations establish their relationship.

Acceptable source: `backend/app/services/repository_loader.py:23-28`

```text
23: class RepositoryPathError(ValueError):
… (intervening source lines omitted)
26:
27: class RepositoryReadError(RepositoryPathError):
28:     """Raised when repository traversal cannot safely complete."""
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-near-02 — difficult_near_matches

**Question:** Does a Python file outside the repository root fail for the same reason as a syntax-invalid file inside it?

**Answerable:** yes

**Expected-answer rubric:** No. Path.relative_to failure raises SourceFileError for outside-root input; ast.parse failure raises SourceFileError with an invalid-syntax location.

**Required unit `outside-root-path-failure`:** Shows the path-safety branch.

Acceptable source: `backend/app/services/chunker.py:109-114`

```text
109:     root = Path(repository_root).resolve()
… (intervening source lines omitted)
111:     try:
112:         relative_path = path.relative_to(root).as_posix()
113:     except ValueError as exc:
114:         raise SourceFileError(f"Source file is outside repository root: {path}") from exc
```

**Required unit `syntax-parse-failure`:** Shows the distinct parse-failure branch.

Acceptable source: `backend/app/services/chunker.py:123-129`

```text
123:     try:
124:         tree = ast.parse(source, filename=relative_path)
125:     except SyntaxError as exc:
… (intervening source lines omitted)
127:         raise SourceFileError(
128:             f"Invalid Python syntax in {relative_path} at {location}: {exc.msg}"
129:         ) from exc
```

**DEV leakage review flags:** DEV span overlap semantic-02: backend/app/services/chunker.py lines 109-114; DEV source-anchor overlap semantic-02: ast.parse; DEV span overlap semantic-02: backend/app/services/chunker.py lines 123-129; DEV span overlap multi-01: backend/app/services/chunker.py lines 109-114; DEV source-anchor overlap multi-01: ast.parse; DEV span overlap multi-01: backend/app/services/chunker.py lines 123-129

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-near-03 — difficult_near_matches

**Question:** What distinguishes a missing provider setting from a provider request that failed after configuration?

**Answerable:** yes

**Expected-answer rubric:** LLMConfigurationError means required settings are absent; RAGGenerationError means generation failed.

**Required unit `llm-error-types`:** The adjacent exception types state their separate meanings.

Acceptable source: `backend/app/services/rag.py:20-25`

```text
20: class LLMConfigurationError(RuntimeError):
21:     """Raised when required LLM configuration is absent."""
… (intervening source lines omitted)
23:
24: class RAGGenerationError(RuntimeError):
25:     """Raised when the configured LLM cannot generate an answer."""
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-near-04 — difficult_near_matches

**Question:** Is the stored embedding vector the same value as the cosine distance returned for a search hit?

**Answerable:** yes

**Expected-answer rubric:** No. CodeChunk stores a 384-dimensional embedding; search_code computes a scalar cosine distance and places it on RetrievedChunk.

**Required unit `stored-vector`:** Shows the persisted vector field and dimension.

Acceptable source: `backend/app/models.py:24-25`

```text
24:     content: Mapped[str] = mapped_column(Text, nullable=False)
25:     embedding: Mapped[list[float]] = mapped_column(VECTOR(384), nullable=False)
```

**Required unit `computed-distance`:** Shows the scalar distance computed from the vector in a query.

Acceptable source: `backend/app/services/retrieval.py:49-53`

```text
49:     query_vector = embed_query(query)
50:     distance = CodeChunk.embedding.cosine_distance(query_vector).label("cosine_distance")
51:     statement = select(CodeChunk, distance)
… (intervening source lines omitted)
53:         statement = statement.where(CodeChunk.repository == scope)
```

**DEV leakage review flags:** DEV source-anchor overlap identifier-02: VECTOR(384); DEV span overlap identifier-02: backend/app/models.py lines 24-25; DEV source-anchor overlap architecture-03: cosine_distance; DEV span overlap architecture-03: backend/app/services/retrieval.py lines 49-53; DEV source-anchor overlap multi-03: cosine_distance; DEV span overlap multi-03: backend/app/services/retrieval.py lines 49-53; DEV source-anchor overlap near-match-04: cosine_distance

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-near-05 — difficult_near_matches

**Question:** Which failure class means local vectors could not be produced, and which means prepared rows could not be stored?

**Answerable:** yes

**Expected-answer rubric:** EmbeddingError describes model/vector creation failure; StorageError describes chunk-storage failure.

**Required unit `embedding-error-role`:** Names the vector-generation failure class.

Acceptable source: `backend/app/services/embeddings.py:13-14`

```text
13: class EmbeddingError(RuntimeError):
14:     """Raised when the configured model cannot produce expected embeddings."""
```

**Required unit `storage-error-role`:** Names the storage failure class.

Acceptable source: `backend/app/services/storage.py:17-18`

```text
17: class StorageError(RuntimeError):
18:     """Raised when indexed chunks cannot be stored."""
```

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-unanswerable-01 — unanswerable_insufficient_context

**Question:** Which endpoint streams partial answer tokens to the browser as server-sent events?

**Answerable:** no

**Expected-answer rubric:** The frozen corpus does not define a streaming/SSE answer endpoint.

**Why insufficient:** The defined ask route returns a complete AskResponse; no streaming route or SSE transport is present.

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-unanswerable-02 — unanswerable_insufficient_context

**Question:** Where is a nightly scheduled task configured to refresh indexed repositories automatically?

**Answerable:** no

**Expected-answer rubric:** No nightly refresh schedule or worker is defined in the frozen source.

**Why insufficient:** Indexing is initiated by the explicit HTTP route; there is no scheduler configuration.

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-unanswerable-03 — unanswerable_insufficient_context

**Question:** How are repository files deleted incrementally from the vector index without reindexing the whole repository?

**Answerable:** no

**Expected-answer rubric:** No incremental file-deletion mechanism is implemented.

**Why insufficient:** The storage path replaces all rows for one repository in a transaction.

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-unanswerable-04 — unanswerable_insufficient_context

**Question:** What per-repository storage quota blocks an indexing request before a tenant reaches its limit?

**Answerable:** no

**Expected-answer rubric:** The frozen source defines no per-repository tenant quota.

**Why insufficient:** There is no tenant/account or quota configuration in the backend or database model.

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________

## holdout-unanswerable-05 — unanswerable_insufficient_context

**Question:** Which source file defines an automatic retry policy for indexing a repository after a failed database commit?

**Answerable:** no

**Expected-answer rubric:** There is no automatic commit-retry policy for indexing.

**Why insufficient:** The storage path rolls back SQLAlchemy failures and raises StorageError; it does not schedule or perform a retry.

**DEV leakage review flags:** none detected automatically

Review: [ ] ACCEPT  [ ] REJECT  [ ] EDIT
Notes: ____________________
