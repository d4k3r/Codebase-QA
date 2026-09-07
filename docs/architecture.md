# Architecture

Codebase QA V2 is one modular, synchronous FastAPI backend. PostgreSQL is the system of record; pgvector adds the vector column type and cosine-distance operators.

## Indexing flow

`POST /repositories/index` passes a local path to `storage.py`. The loader validates the directory, recursively discovers Python files, excludes generated directories, and sorts paths deterministically. The chunker parses each file with Python `ast` and extracts top-level functions, async functions, and classes. A module with meaningful source but no qualifying symbol becomes one fallback chunk.

The embedding module lazily loads `sentence-transformers/all-MiniLM-L6-v2`, batches chunk text, normalizes the vectors, and enforces 384 dimensions. Storage then deletes existing rows with the same repository name and inserts the complete new set before one commit. Discovery, parsing, and embedding happen before the database replacement, so those failures leave the old rows untouched. A database failure rolls back the replacement transaction.

## Query and retrieval flow

`POST /search` embeds the query and issues one SQLAlchemy query ordered by pgvector cosine distance. Lower distance means a closer match. Retrieval is exact: every stored vector is eligible for comparison, and no HNSW or IVFFlat index is present.

## RAG flow

`POST /ask` validates LLM configuration, retrieves the nearest chunks, and builds a source-labelled context capped at 12,000 characters. `rag.py` sends one request through the official OpenAI Python client using the Chat Completions interface. `LLM_BASE_URL` can point at an OpenAI-compatible endpoint; no local model server is installed by this project. The answer is returned with the same retrieved source metadata.

## Module responsibilities

- `main.py`: constructs FastAPI and includes the router.
- `config.py`: resolves the root `.env` deterministically and validates settings.
- `database.py`: owns the synchronous engine, session factory, and request dependency.
- `models.py`: defines persisted SQLAlchemy tables.
- `schemas.py`: defines validated HTTP request and response shapes.
- `api/routes.py`: translates HTTP calls and predictable service errors.
- `repository_loader.py`: validates a local directory and discovers Python files.
- `chunker.py`: turns source files into AST-aware domain chunks.
- `embeddings.py`: lazily produces normalized 384-dimensional vectors.
- `storage.py`: orchestrates indexing and transactional replacement.
- `retrieval.py`: performs exact cosine-distance SQL retrieval.
- `rag.py`: bounds context, constructs the prompt, and calls the LLM.
- `scripts/init_db.py`: creates MVP tables from SQLAlchemy metadata.
- `scripts/evaluate_retrieval.py`: reports hit@k for three explicit questions.

## Schema, model, PostgreSQL, and pgvector

Pydantic schemas validate data crossing the HTTP boundary. The SQLAlchemy `CodeChunk` model describes rows persisted in PostgreSQL. They are intentionally separate: an API response is not a database row.

PostgreSQL provides durable relational storage and transactions. The pgvector extension provides `VECTOR(384)` and cosine-distance SQL operations. The extension is enabled by the container initialization SQL; the table is created by the backend initialization script.

`Base.metadata.create_all()` is acceptable for this learning MVP because there is one new table. It is not a migration system and cannot safely evolve arbitrary production schemas.

## Main failure boundaries

- Invalid/missing repository path or invalid Python source: indexing returns a client error.
- Embedding model download/load/dimension failure: indexing or retrieval fails explicitly.
- PostgreSQL connection/query failure: storage rolls back or retrieval fails explicitly.
- Missing LLM API key/model: `/ask` returns a configuration error before retrieval.
- OpenAI-compatible request failure or empty answer: `/ask` returns an upstream-generation error.
- Retrieved context can be incomplete; the prompt requires the model to say so rather than invent behavior.
