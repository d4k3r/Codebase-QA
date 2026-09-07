# Codebase QA V2

Codebase QA V2 is a small, learning-oriented backend that indexes local Python repositories and answers questions using AST-aware chunks, local sentence-transformer embeddings, PostgreSQL/pgvector retrieval, and an OpenAI-compatible LLM.

Implemented now: recursive Python discovery, top-level function/class/module chunking, normalized 384-dimensional embeddings, transactional repository replacement, exact cosine-distance search, `/health`, `/repositories/index`, `/search`, and `/ask`.

It remains one synchronous FastAPI application. See [architecture](docs/architecture.md) for the concrete flows and [productionisation options](docs/productionisation.md) for ideas that are explicitly not implemented.

## Local setup

From the repository root:

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

Start PostgreSQL and enable pgvector through the first-run container script:

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
  -d '{"query":"Where is configuration loaded?","top_k":5}'
```

To use `/ask`, configure `LLM_API_KEY` and `LLM_MODEL_NAME` in the root `.env`. Set `LLM_BASE_URL` to use another OpenAI-compatible endpoint. No LLM server is installed by this project.

## Tests and retrieval evaluation

```bash
cd backend
source .venv/bin/activate
pytest
RUN_DATABASE_TESTS=1 pytest -m integration
python -m scripts.evaluate_retrieval tests/fixtures/tiny_repo --top-k 3
```

The default test run skips the real PostgreSQL/model integration test. The evaluation utility indexes the tiny fixture and reports transparent hit@k results independently of LLM answer quality.

## Deliberate limits

Only local Python repositories are supported. Re-indexing replaces all rows for a repository name. Search is exact vector search. There is no Git cloning, incremental indexing, background work, authentication, frontend, ANN index, hybrid search, reranking, agent loop, or deployment automation.
