# Dense, PostgreSQL lexical, and RRF retrieval experiment

## Controlled setup

The accepted Batch 2A chunker and the checked-in 40-case, machine-prepared
source-grounded draft dataset were held fixed. Case-set SHA-256 is
`97a85902564bdcfce9e5e85da38c0f1008cb3fc839296f2a3c4871e1f78a26af`;
the 212-row corpus manifest is
`86aa6028950355c88b68d57bb3fc027be3e414acfb5a3ea45e3d2b341d70995b`.
The disposable database was scored with a read-only repeatable-read transaction;
the normal application database was not reindexed. No LLM answer was requested.

Dense remains exact pgvector cosine-distance retrieval and the `/search` and `/ask`
serving default. The evaluator alone selects `dense`, `lexical`, or `hybrid` with
`--mode`; all three return the top 10 to the unchanged complete-chunk context
builder. Hybrid draws 50 scoped candidates from each branch before fusion.

Lexical search uses PostgreSQL `simple` full-text search over weighted existing
columns: symbol and file path have weight A, original content weight D. Both original
spelling and underscore/camel/path-separated forms enter an on-the-fly `tsvector`;
question terms are ORed after dropping a small fixed list of ordinary question glue.
Complete code-shaped identifiers are retained alongside parts. Exact symbol/path/
basename matches receive small lexical-only additions of 0.10/0.10/0.05. No
production table, generated column, or index was added. `ts_rank_cd` is a PostgreSQL
cover-density rank, **not BM25**, and is not numerically combined with cosine
distance. A lexical-only hit has no cosine distance.

Hybrid deduplicates by repository plus row ID and scores each candidate as
`1/(60 + dense_rank) + 1/(60 + lexical_rank)` for branches where it appears.
The evaluator exposes `--rrf-constant` (default 60) and `--branch-depth`
(default 50); this comparison used those defaults without a parameter sweep.
Stable repository/path/line/symbol/row-ID fields break exact fusion ties. The two
queries run in one short repeatable-read snapshot, so they cannot observe different
repository replacements. The evaluator's transaction is read-only; `/ask` still
releases its dense read transaction before external generation.

## Measured results

Each cell is numerator/denominator (percentage). The 36 answerable cases contain
40 required evidence units; four unanswerable cases are reported separately.

| Metric | Dense | Lexical | Hybrid RRF |
|---|---:|---:|---:|
| Hit@1 | 9/36 (25.00%) | 10/36 (27.78%) | 14/36 (38.89%) |
| Hit@3 | 21/36 (58.33%) | 16/36 (44.44%) | 22/36 (61.11%) |
| Hit@5 | 25/36 (69.44%) | 21/36 (58.33%) | 28/36 (77.78%) |
| Hit@10 | 31/36 (86.11%) | 25/36 (69.44%) | 32/36 (88.89%) |
| MRR@10 | 15.5889/36 (43.30%) | 13.8694/36 (38.53%) | 19.6262/36 (54.52%) |
| Macro evidence recall@1 | 8.5/36 (23.61%) | 9/36 (25.00%) | 13.5/36 (37.50%) |
| Macro evidence recall@3 | 20/36 (55.56%) | 15/36 (41.67%) | 21/36 (58.33%) |
| Macro evidence recall@5 | 23.5/36 (65.28%) | 20.5/36 (56.94%) | 26/36 (72.22%) |
| Macro evidence recall@10 | 29.5/36 (81.94%) | 24.5/36 (68.06%) | 31.5/36 (87.50%) |
| Micro evidence recall@1 | 9/40 (22.50%) | 10/40 (25.00%) | 14/40 (35.00%) |
| Micro evidence recall@3 | 21/40 (52.50%) | 16/40 (40.00%) | 22/40 (55.00%) |
| Micro evidence recall@5 | 25/40 (62.50%) | 22/40 (55.00%) | 28/40 (70.00%) |
| Micro evidence recall@10 | 31/40 (77.50%) | 27/40 (67.50%) | 35/40 (87.50%) |
| All evidence@1 | 8/36 (22.22%) | 8/36 (22.22%) | 13/36 (36.11%) |
| All evidence@3 | 19/36 (52.78%) | 14/36 (38.89%) | 20/36 (55.56%) |
| All evidence@5 | 22/36 (61.11%) | 20/36 (55.56%) | 24/36 (66.67%) |
| All evidence@10 | 28/36 (77.78%) | 24/36 (66.67%) | 31/36 (86.11%) |
| Final-context evidence | 31/40 (77.50%) | 25/40 (62.50%) | 34/40 (85.00%) |
| Context sufficiency | 28/36 (77.78%) | 23/36 (63.89%) | 30/36 (83.33%) |
| Selection loss | 0/31 (0%) | 2/27 (7.41%) | 1/35 (2.86%) |

Category-level top-10 evidence units (four cases each, except multiple evidence
has eight units):

| Category | Dense | Lexical | Hybrid |
|---|---:|---:|---:|
| Semantic/conceptual | 3/4 | 2/4 | 3/4 |
| Exact identifier | 4/4 | 4/4 | 4/4 |
| Configuration/constants | 3/4 | 1/4 | 2/4 |
| Filename/path | 3/4 | 2/4 | 3/4 |
| Decorator/API route | 4/4 | 4/4 | 4/4 |
| Architecture | 4/4 | 3/4 | 4/4 |
| Cross-module | 3/4 | 3/4 | 4/4 |
| Multiple evidence | 3/8 | 5/8 | 7/8 |
| Difficult near matches | 4/4 | 3/4 | 4/4 |

Against dense at depth 10, lexical gained `cross-module-03`, `multi-01`,
`multi-03`, `multi-04`, but lost `semantic-01`, `config-01`, `config-03`,
`path-03`, `architecture-02`, `cross-module-01`, `multi-02`, and
`near-match-02`. Hybrid gained `cross-module-03`, `multi-01`, `multi-02`,
and `multi-03`; it lost `config-01`. The other 31 answerable cases were unchanged
in evidence-unit count. Relative to lexical, hybrid gained eight cases and lost
`multi-04` (its `llm-settings` evidence moved from lexical rank 1 to hybrid rank 29).

The nine original dense top-10 evidence misses had these ranks at depth 50
(`>50` means absent from that branch's first 50):

| Case / evidence | Dense | Lexical | Hybrid |
|---|---:|---:|---:|
| `semantic-03` normalized embeddings | 12 | >50 | 30 |
| `config-02` excluded directories | 11 | 30 | 15 |
| `path-04` `.env.example` settings | >50 | 14 | 33 |
| `cross-module-03` ask sources | 13 | 3 | 4 |
| `multi-01` discovery stage | 22 | 1 | 6 |
| `multi-02` embedding stage | 12 | 13 | 5 |
| `multi-03` context stage | 20 | 6 | 5 |
| `multi-03` retrieval stage | 16 | 15 | 10 |
| `multi-04` LLM settings | >50 | 1 | 29 |

At branch depth 50, the dense-plus-lexical union contains all **40/40** evidence
units and all evidence for **36/36** answerable cases. Hybrid top 10 contains
35/40 units and all evidence for 31/36 cases; its bounded context retains 34/40.
This is candidate ordering/context-budget headroom, not missing source coverage.
`multi-03` has both units in hybrid top 10 but loses the retrieval-stage chunk at
context selection. Dense selection loss remained zero; the changed ordering made
one loss visible without changing context policy.

Three warmed local passes over all 40 questions (120 timings per mode, excluding
model load and report diagnostics) yielded approximate median/p95 retrieval-only
times: dense 4.94/6.00 ms, lexical 23.85/28.96 ms, hybrid 36.49/43.61 ms.
These are local observations, not a production benchmark.

## Decision: PARTIALLY ADOPT

Keep hybrid as an explicit evaluator/service experiment, **not** the serving
default. RRF improves several measured ranks, especially multi-evidence recovery,
but regresses `config-01`, is slower with on-the-fly SQL vectors, and introduces a
context loss. Lexical alone harms some semantic/paraphrased queries. The draft set
is small and pending human review, so tiny aggregate differences are not statistical
claims. BM25 was not implemented: this first comparison already establishes signal
complementarity, while lexical tokenization/ranking and question wording both need
review before attributing misses to the rank formula. A later reranker experiment is
plausible because the 50+50 union contains every required unit, but no reranker or
structure-aware routing is part of this batch. The accepted Batch 2A chunking policy
still leaves 35/212 embeddings beyond MiniLM's 256-token effective input length.
