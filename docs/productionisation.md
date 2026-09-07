# Productionisation options — not implemented

Everything in this document is future design discussion. None of these capabilities is implemented in Codebase QA V2 today.

## Ingestion and service boundaries

- **Incremental indexing:** add content hashes and repository revisions when full delete-and-replace indexing becomes too costly or loses useful history.
- **Background ingestion:** move long-running parsing and embedding outside HTTP request lifetimes when repositories become large.
- **Worker/queue architecture:** introduce durable jobs only when retries, concurrency control, and independent worker scaling are concrete requirements.
- **Modular monolith to service boundary:** keep modules in one deployable unit until ingestion and query workloads have independently measurable scaling or ownership needs.

## Retrieval quality and scale

- **BM25 lexical retrieval:** add keyword matching when exact identifiers and rare terms are poorly served by semantic embeddings.
- **Hybrid lexical/vector retrieval:** combine lexical and semantic candidates when evaluations show complementary recall.
- **Reranking:** apply a more expensive model to a small candidate set when first-stage ordering limits answer quality.
- **ANN vector indexes:** add HNSW or IVFFlat only when exact search latency is unacceptable at measured data volume; both trade exactness and operational tuning for speed.

## Platform concerns

- **Authentication and authorization:** add identities and repository permissions before accepting untrusted or multi-user traffic.
- **Observability:** add structured logs, metrics, traces, and request correlation when operating the system beyond local development.
- **Managed PostgreSQL/RDS:** use managed backups, patching, failover, and monitoring when operational reliability matters; verify pgvector version support first.
- **Container orchestration:** consider an orchestrator only when multiple deployed workloads, scaling, health management, or rollout requirements justify it.

## Evaluation

- **Retrieval evaluation:** grow the transparent hit@k fixture into a versioned question/source dataset and track recall by query class.
- **Answer evaluation:** separately assess factual grounding, citation/source support, insufficiency handling, latency, and cost. Good retrieval does not guarantee a good answer, and answer quality should not hide retrieval misses.
