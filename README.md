# Codebase QA V2

Codebase QA V2 is a small, learning-oriented backend that indexes local Python repositories and answers questions using AST-aware chunks, local sentence-transformer embeddings, PostgreSQL/pgvector retrieval, and an OpenAI-compatible LLM.

Implemented now: recursive Python discovery, top-level function/class/module chunking, normalized 384-dimensional embeddings, transactional repository replacement, exact cosine-distance search, `/health`, `/repositories/index`, `/search`, and `/ask`.

It remains one synchronous FastAPI application. See [architecture](docs/architecture.md) for the concrete flows and [productionisation options](docs/productionisation.md) for ideas that are explicitly not implemented.

## Local setup

Run these setup commands from the repository root:

```bash
cp .env.example .env
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# CPU-only PyTorch avoids downloading CUDA packages for this local MVP.
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev]"
cd ..
```

The first sentence-transformer use downloads `sentence-transformers/all-MiniLM-L6-v2`. It is a simple reproducible MVP choice, not a claim that it is the optimal source-code embedding model.

## Database

Start PostgreSQL from the repository root. Compose reads the PostgreSQL settings from the root `.env` when it exists; the application reads the same file and uses `DATABASE_URL` to connect from WSL:

```bash
docker compose up -d postgres
docker compose ps
docker compose exec postgres psql -U codebase_qa -d codebase_qa \
  -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Create the application table:

```bash
cd backend
source .venv/bin/activate
python -m scripts.init_db
```

`create_all()` is intentionally used for this MVP. It creates missing tables but is not a migration system; use a real migration tool before evolving a production schema.

## Run and use the API

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Index a local Python repository:

```bash
curl -X POST http://127.0.0.1:8000/repositories/index \
  -H 'Content-Type: application/json' \
  -d '{"repository_path":"/absolute/path/to/python-repo","repository_name":"example"}'
```

Search it:

```bash
curl -X POST http://127.0.0.1:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"Where is configuration loaded?","top_k":5,"repository":"example"}'
```

`repository` is optional on both `/search` and `/ask`. When supplied, filtering is
performed in PostgreSQL before ordering and limiting; an unknown repository returns
no candidates and never falls back to global search. Omitting it preserves global
search across all indexed repositories. This scope is retrieval selection, not an
authentication or authorization boundary.

To use `/ask`, configure `LLM_API_KEY` and `LLM_MODEL_NAME` in the root `.env`. Set `LLM_BASE_URL` to use another OpenAI-compatible endpoint. No LLM server is installed by this project.

Example request and response shape:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Where is configuration loaded?","top_k":3,"repository":"example"}'
```

```json
{
  "answer": "...",
  "sources": [
    {
      "repository": "example",
      "file_path": "app/config.py",
      "symbol_type": "module",
      "symbol_name": null,
      "start_line": 1,
      "end_line": 20,
      "content": "...",
      "cosine_distance": 0.12
    }
  ]
}
```

Only complete chunks that fit the bounded model context are returned as `/ask` sources. Configure `LLM_TIMEOUT_SECONDS` and `LLM_MAX_RETRIES` for the deliberate external-request policy.

## Tests and retrieval evaluation

```bash
cd backend
source .venv/bin/activate
pytest
RUN_DATABASE_TESTS=1 pytest -m integration
python -m scripts.evaluate_retrieval \
  --repository codebase-qa-v2 \
  --candidate-depth 10 \
  --output /tmp/codebase-qa-v2-evaluation.json
```

The default test run skips the real PostgreSQL/model integration tests. The default
evaluation command is read-only: it requires an explicit repository identity,
validates the checked-in corpus manifest, performs scoped retrieval, reuses the
production context selector, and never indexes, cleans up rows, creates schema, or
calls an LLM. Its versioned 40-case JSON dataset is a machine-prepared,
source-grounded draft pending human review.

Corpus preparation is deliberately separate and write-enabled. Run
`python -m scripts.prepare_evaluation_corpus --help` only against an explicitly
isolated/disposable evaluation database: preparation uses the normal replacement
semantics and can delete existing rows sharing the selected repository identity.

The report keeps pipeline failures distinct: source answerability is a dataset
label; index evidence coverage measures required evidence represented anywhere in
the validated index; retrieval metrics measure that evidence in ranked candidates;
and context metrics measure evidence retained by the real bounded `build_context()`.
Hit@k, MRR@10, macro/micro evidence recall, all-evidence@k, context sufficiency, and
selection loss all include raw numerators and denominators. Unanswerable cases are
reported separately and are not treated as retrieval misses.

## Frontend

The interview/demo frontend is a small React + TypeScript + Vite application in `frontend/`. It calls only the backend `/ask` endpoint; the OpenAI key remains server-side and is never sent to the browser.

Prerequisites: Node.js 20+ and npm.

Install dependencies from `frontend/`:

```bash
cd frontend
npm install
```

Start the FastAPI backend from `backend/` in one terminal:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

Start the Vite frontend from `frontend/` in another terminal:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`. The frontend calls `/ask` with a relative URL. During development, Vite proxies that path to `http://127.0.0.1:8000`, where FastAPI is expected to be running. The backend remains responsible for retrieval, context construction, and the LLM request.

Build the frontend from `frontend/` with:

```bash
npm run build
```

## Deliberate limits

Only local Python repositories are supported. Re-indexing replaces all rows for a repository name. Search is exact vector search. There is no Git cloning, incremental indexing, background work, authentication, ANN index, hybrid search, reranking, agent loop, or deployment automation. The existing frontend is intentionally only a small `/ask` demonstration UI.
