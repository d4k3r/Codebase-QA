# Architecture

Codebase QA V2 is one modular, synchronous FastAPI backend. PostgreSQL is the system of record; pgvector adds the vector column type and cosine-distance operators.

The active chunking policy is the accepted Batch 2A source-coverage baseline. A later
bounded structural chunking policy was evaluated and rejected because its retrieval
regression outweighed its truncation reduction; it is retained only as an experiment
record in [`structural-chunking.md`](structural-chunking.md).

## Indexing flow

`POST /repositories/index` passes a local path to `storage.py`. The loader validates the directory, recursively discovers supported regular files, excludes generated/vendor directories, and sorts paths deterministically. Python chunking parses each file with `ast` and keeps top-level functions, async functions, and classes. When those symbols coexist with other meaningful top-level statements, contiguous uncovered statement regions become `module_companion` chunks. A module with meaningful source but no qualifying symbol remains one fallback chunk.

The deliberate non-Python allowlist is YAML/YML, SQL, `.env.example`, and the exact filename `vite.config.ts`. These files use a separate bounded config-text chunker, not AST semantics. `.env`, arbitrary TypeScript, Markdown, TOML, binary/non-UTF-8 files, and generated/vendor trees are excluded. Every emitted chunk contains an exact contiguous original-source slice with truthful line boundaries.

The embedding module lazily loads `sentence-transformers/all-MiniLM-L6-v2`, batches chunk text, normalizes the vectors, and enforces 384 dimensions. Storage then deletes existing rows with the same repository name and inserts the complete new set before one commit. Discovery, parsing, and embedding happen before the database replacement, so those failures leave the old rows untouched. A database failure rolls back the replacement transaction. Discovery prunes excluded directories before descent and surfaces traversal errors instead of accepting a partial file list.

## Query and retrieval flow

`POST /search` and `/ask` still default to exact dense pgvector cosine-distance retrieval. Lower distance means a closer match. An optional repository scope adds a SQL predicate before ordering and limiting; unknown scopes return no candidates, while omitted scope preserves global retrieval. Equal-distance results use stable source metadata and finally the row ID as deterministic tie-breakers for a fixed database snapshot. Repository scope is selection only, not authentication or authorization. No HNSW or IVFFlat index is present. The evaluator can explicitly compare PostgreSQL lexical `ts_rank_cd` (not BM25) and dense/lexical RRF without changing serving defaults; see [the measured experiment](retrieval-experiment.md). Hybrid branches share a short repeatable-read transaction.

## RAG flow

`POST /ask` validates LLM configuration, retrieves the nearest chunks, and builds a source-labelled context capped at 12,000 characters. Only complete chunks that fit are included, and only those chunks are returned as sources. `rag.py` rolls back the read-only retrieval transaction before waiting on the external request, explicitly closes the per-request OpenAI client, and applies configured timeout/retry limits. `LLM_BASE_URL` can point at an OpenAI-compatible endpoint; no local model server is installed by this project.

## Module responsibilities

- `main.py`: constructs FastAPI and includes the router.
- `config.py`: resolves the root `.env` deterministically and validates settings.
- `database.py`: owns the synchronous engine, session factory, and request dependency.
- `models.py`: defines persisted SQLAlchemy tables.
- `schemas.py`: defines validated HTTP request and response shapes.
- `api/routes.py`: translates HTTP calls and predictable service errors.
- `repository_loader.py`: validates a local directory and discovers allowlisted source files.
- `chunker.py`: turns Python source into AST-aware symbol, companion, or fallback chunks.
- `text_chunker.py`: creates bounded contiguous chunks for allowlisted config text.
- `embeddings.py`: lazily produces normalized 384-dimensional vectors.
- `storage.py`: orchestrates indexing and transactional replacement.
- `retrieval.py`: performs exact cosine-distance SQL retrieval.
- `lexical.py`: supplies code-aware query terms for experimental PostgreSQL lexical retrieval.
- `rag.py`: bounds context, constructs the prompt, and calls the LLM.
- `scripts/init_db.py`: creates MVP tables from SQLAlchemy metadata.
- `evaluation.py`: validates versioned datasets/manifests and reports source, index, retrieval, context-selection, and embedding-input diagnostics.
- `scripts/evaluate_retrieval.py`: performs manifest-validated, repository-scoped, read-only scoring without an LLM call.
- `scripts/prepare_evaluation_corpus.py`: explicitly write-enabled corpus preparation for an isolated/disposable evaluation database only.

## Evaluation flow and safety

The checked-in JSON dataset identifies one exact prepared corpus by repository name,
stable indexed-source hash, chunk count, source revision, and chunking identifier.
Default scoring starts a read-only PostgreSQL transaction, validates that manifest,
then searches only that repository. It does not index, create schema, clean up rows,
or call an answer provider. Corpus preparation is a separate command with an
explicit write confirmation because it invokes normal delete-and-replace indexing.

Each answerable case contains one or more required evidence units. A unit can list
alternative acceptable source spans, but it is counted once even if several spans
match. The evaluator reports source answerability, evidence present anywhere in the
index, ranked retrieval candidates, and evidence retained by the production
`build_context()` result. This separates absent indexed evidence from ranking misses
and from context-selection loss. Token lengths are measured with the local embedding
model tokenizer when available so chunks beyond the model input limit remain visible.

Metric denominators are explicit in the JSON report. Hit@k, MRR@10, macro evidence
recall@k, and all-evidence@k use answerable cases; micro evidence recall@k and index
or context evidence recall use required evidence units; context sufficiency uses
answerable cases; selection-loss rate uses retrieved evidence units. Unanswerable
cases are listed separately and are not counted as retrieval failures. Cosine
distance remains a ranking distance, not an answerability probability.

## Schema, model, PostgreSQL, and pgvector

Pydantic schemas validate data crossing the HTTP boundary. The SQLAlchemy `CodeChunk` model describes rows persisted in PostgreSQL. They are intentionally separate: an API response is not a database row.

PostgreSQL provides durable relational storage and transactions. The pgvector extension provides `VECTOR(384)` and cosine-distance SQL operations. The extension is enabled by the container initialization SQL; the table is created by the backend initialization script.

`Base.metadata.create_all()` is acceptable for this learning MVP because there is one new table. It is not a migration system and cannot safely evolve arbitrary production schemas.

## Main failure boundaries

- Invalid/missing repository path or invalid Python source: indexing returns a client error.
- Embedding model download/load/dimension failure: indexing or retrieval fails explicitly.
- PostgreSQL connection/query failure: storage rolls back or retrieval fails explicitly.
- Missing LLM API key/model: `/ask` returns a configuration error before retrieval.
- OpenAI-compatible request failure or empty answer: `/ask` returns an upstream-generation error while detailed diagnostics remain server-side.
- Retrieved context can be incomplete because some candidates may not fit the bound; the prompt requires the model to say so rather than invent behavior.
