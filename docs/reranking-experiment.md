# Local cross-encoder reranking experiment

The accepted Batch 2A index and the same 40-case machine-prepared draft dataset
were held fixed. Case-set hash:
`97a85902564bdcfce9e5e85da38c0f1008cb3fc839296f2a3c4871e1f78a26af`.
The 212-row corpus manifest:
`86aa6028950355c88b68d57bb3fc027be3e414acfb5a3ea45e3d2b341d70995b`.
The previous dense, lexical, and hybrid reports reproduced exactly. The 50+50
scoped dense/lexical candidate union contained **40/40** evidence units, with
51–81 unique candidates per query (median 70). Evaluation was read-only on the
disposable database. Neither the normal index nor the serving default changed.

## Fixed method

The local model is
[`cross-encoder/ms-marco-MiniLM-L6-v2`](https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2),
pinned and resolved to revision
`233902d25c440f23af6f7d6e94d2946bac0bee0a`. It has 22,713,601
parameters and a 90.9 MB safetensors artifact. This environment's PyTorch build
is CPU-only. For each query, the two existing retrieval branches fetch 50 scoped
chunks in one repeatable-read snapshot. The reranker performs **no new search**:
it scores only the first 20 or first 50 deduplicated chunks in the existing RRF
order. Top 10 then flows through the unchanged production `build_context()`.
Run `python -m scripts.evaluate_retrieval --repository codebase-qa-v2 --mode rerank
--rerank-depth 20` (or 50) against the already prepared disposable corpus.

Each pair is the original question plus model-only repository/path/symbol metadata
and the **unchanged original source text**. Returned provenance remains the
original exact source slice. The model has a 512-token pair limit, including
special tokens; sentence-transformers uses `longest_first` truncation. The
evaluator records each pair's untruncated tokenizer length and truncation flag.
The reranker returns raw ranking scores, **not confidence probabilities**; they
are never added to cosine distance, PostgreSQL lexical score, or RRF score.
Equal scores keep the deterministic RRF order and source-metadata tie-breakers.

| Depth | Scored pairs | Pairs exceeding 512 | Maximum pair length |
|---|---:|---:|---:|
| 20 | 800 | 58/800 (7.25%) | 1,334 |
| 50 | 2,000 | 202/2,000 (10.10%) | 1,337 |

## Measured quality

There are 36 source-answerable cases and 40 required evidence units. Four
unanswerable cases are reported separately. Each metric shows its raw
numerator/denominator; full-precision percentages are in the JSON evaluator
reports.

| Metric | Dense | Hybrid RRF | Rerank 20 | Rerank 50 |
|---|---:|---:|---:|---:|
| Hit@1 | 9/36 | 14/36 | **18/36** | **18/36** |
| Hit@3 | 21/36 | 22/36 | **28/36** | 27/36 |
| Hit@5 | 25/36 | 28/36 | **31/36** | 30/36 |
| Hit@10 | 31/36 | 32/36 | **34/36** | **34/36** |
| MRR@10 | 15.5889/36 | 19.6262/36 | **23.2952/36** | 23.1845/36 |
| Macro evidence recall@1 | 8.5/36 | 13.5/36 | **17.5/36** | **17.5/36** |
| Macro evidence recall@3 | 20/36 | 21/36 | **27/36** | 26/36 |
| Macro evidence recall@5 | 23.5/36 | 26/36 | **29.5/36** | 29/36 |
| Macro evidence recall@10 | 29.5/36 | 31.5/36 | 33.5/36 | **34/36** |
| Micro evidence recall@1 | 9/40 | 14/40 | **18/40** | **18/40** |
| Micro evidence recall@3 | 21/40 | 22/40 | **28/40** | 27/40 |
| Micro evidence recall@5 | 25/40 | 28/40 | **32/40** | 31/40 |
| Micro evidence recall@10 | 31/40 | 35/40 | 37/40 | **38/40** |
| All evidence@1 | 8/36 | 13/36 | **17/36** | **17/36** |
| All evidence@3 | 19/36 | 20/36 | **26/36** | 25/36 |
| All evidence@5 | 22/36 | 24/36 | **28/36** | **28/36** |
| All evidence@10 | 28/36 | 31/36 | 33/36 | **34/36** |
| Final-context evidence | 31/40 | 34/40 | **37/40** | 36/40 |
| Context sufficiency | 28/36 | 30/36 | **33/36** | **33/36** |
| Selection loss | 0/31 | 1/35 | **0/37** | 2/38 |

Top-10 evidence recovery by category (four units each, except eight for
multiple-required-evidence):

| Category | Dense | Hybrid | Rerank 20 | Rerank 50 |
|---|---:|---:|---:|---:|
| Semantic/conceptual | 3/4 | 3/4 | 3/4 | 3/4 |
| Exact identifier | 4/4 | 4/4 | 4/4 | 4/4 |
| Configuration/constants | 3/4 | 2/4 | **4/4** | **4/4** |
| Filename/path | 3/4 | 3/4 | 3/4 | **4/4** |
| Decorator/API route | 4/4 | 4/4 | 4/4 | 4/4 |
| Architecture | 4/4 | 4/4 | 4/4 | 4/4 |
| Cross-module | 3/4 | 4/4 | **4/4** | 3/4 |
| Multiple evidence | 3/8 | 7/8 | 7/8 | **8/8** |
| Difficult near matches | 4/4 | 4/4 | 4/4 | 4/4 |

Depth 20 gained `config-01` and `config-02` versus hybrid and lost no case's
top-10 evidence (34 answerable cases unchanged in count). Depth 50 gained
`config-01`, `config-02`, `path-04`, and the second unit of `multi-04`, but lost
`cross-module-02` (31 unchanged). Depth 50 retrieved both `multi-03` units yet
the unchanged complete-chunk context selector excluded both. Depth 20 retained
both in context. Consequently the deeper policy had *less* final-context evidence.

The five hybrid top-10 misses had these ranks in the existing RRF order and
after reranking. “Not scored” means outside the bounded 20-candidate input,
not absent from the 50+50 union.

| Evidence | RRF | Rerank 20 | Rerank 50 | Pair >512? |
|---|---:|---:|---:|---|
| `semantic-03` normalized embeddings | 30 | not scored | 12 | no (215 tokens) |
| `config-01` embedding dimension | 13 | **4** | 4 | no (111) |
| `config-02` excluded directories | 15 | **3** | 4 | no (199) |
| `path-04` `.env.example` settings | 33 | not scored | **6** | no (283) |
| `multi-04` LLM settings | 29 | not scored | **7** | yes (613) |

The new depth-50 miss `cross-module-02` moved from RRF rank 2 to reranker rank
12, with an untruncated 231-token pair. Depth 20 kept it at rank 7. In
`multi-03`, the context/retrieval units became ranks 5/6 at depth 20 and 6/7
at depth 50; the changed ordering and unchanged complete-chunk context budget
excluded both in that deeper run.

For every answerable query, each cell below is **first relevant rank / number
of required units present by rank 10**; “—” is a top-10 miss.

| Case | Dense | Hybrid | Rerank 20 | Rerank 50 |
|---|---:|---:|---:|---:|
| semantic-01 | 3 / 1 | 8 / 1 | 2 / 1 | 2 / 1 |
| semantic-02 | 3 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| semantic-03 | — / 0 | — / 0 | — / 0 | — / 0 |
| semantic-04 | 9 / 1 | 2 / 1 | 7 / 1 | 7 / 1 |
| identifier-01 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| identifier-02 | 2 / 1 | 2 / 1 | 1 / 1 | 1 / 1 |
| identifier-03 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| identifier-04 | 4 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| config-01 | 10 / 1 | — / 0 | 4 / 1 | 4 / 1 |
| config-02 | — / 0 | — / 0 | 3 / 1 | 4 / 1 |
| config-03 | 1 / 1 | 7 / 1 | 1 / 1 | 1 / 1 |
| config-04 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| path-01 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| path-02 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| path-03 | 2 / 1 | 4 / 1 | 3 / 1 | 3 / 1 |
| path-04 | — / 0 | — / 0 | — / 0 | 6 / 1 |
| route-01 | 2 / 1 | 3 / 1 | 2 / 1 | 2 / 1 |
| route-02 | 3 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| route-03 | 8 / 1 | 2 / 1 | 3 / 1 | 3 / 1 |
| route-04 | 3 / 1 | 2 / 1 | 1 / 1 | 1 / 1 |
| architecture-01 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| architecture-02 | 2 / 1 | 4 / 1 | 2 / 1 | 2 / 1 |
| architecture-03 | 2 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| architecture-04 | 9 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| cross-module-01 | 8 / 1 | 6 / 1 | 3 / 1 | 3 / 1 |
| cross-module-02 | 6 / 1 | 2 / 1 | 7 / 1 | — / 0 |
| cross-module-03 | — / 0 | 4 / 1 | 2 / 1 | 2 / 1 |
| cross-module-04 | 3 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| multi-01 | 5 / 1 | 3 / 2 | 4 / 2 | 4 / 2 |
| multi-02 | 3 / 1 | 5 / 2 | 2 / 2 | 2 / 2 |
| multi-03 | — / 0 | 5 / 2 | 5 / 2 | 6 / 2 |
| multi-04 | 1 / 1 | 1 / 1 | 1 / 1 | 1 / 2 |
| near-match-01 | 1 / 1 | 2 / 1 | 1 / 1 | 1 / 1 |
| near-match-02 | 5 / 1 | 8 / 1 | 7 / 1 | 8 / 1 |
| near-match-03 | 2 / 1 | 1 / 1 | 1 / 1 | 1 / 1 |
| near-match-04 | 5 / 1 | 4 / 1 | 3 / 1 | 3 / 1 |

## Local cost and decision

Three warmed passes over all 40 questions (120 timings per depth), excluding
model load and manifest diagnostics, separated 50+50 retrieval and reranking.
These CPU measurements are local observations, not production benchmarks:

| Depth | Retrieval median/p95 | Reranking median/p95 | Total median/p95 |
|---|---:|---:|---:|
| 20 | 38.95 / 46.99 ms | 416.46 / 466.30 ms | 456.64 / 513.29 ms |
| 50 | 38.67 / 45.61 ms | 723.19 / 871.44 ms | 760.53 / 915.83 ms |

Peak process RSS was about 889 MB with both local models loaded; that is **not**
standalone reranker memory. GPU memory is not applicable.

**Decision: PARTIALLY ADOPT.** Keep depth-20 reranking as an explicit evaluator/
service experiment, not the serving default. It recovered two of hybrid's five
top-10 misses, improved final-context recovery by three units, and had no
case-level evidence regression. But CPU latency is roughly an order of magnitude
above hybrid retrieval and this draft dataset awaits human review. Depth 50
scored 2.5 times as many pairs yet produced lower final-context recovery and a
cross-module regression; it is not justified as a default.

The remaining depth-20 misses are `semantic-03`, `path-04`, and the LLM-settings
unit of `multi-04`: all were RRF ranks 29–33 and thus never scored. At depth 50,
`semantic-03` and `cross-module-02` were scored without tokenizer truncation but
placed at rank 12—reranker-ordering errors. The truncated `multi-04` settings
pair still reached rank 7. Depth-50 `multi-03` loss is a separate context
selection effect. MiniLM still truncates 35/212 indexed chunks, but that is not
proven to cause these particular residual errors.

An embedding-model bake-off is **not the most direct next experiment** while
the 50+50 union already covers every evidence unit. First have humans review the
draft labels and compare code-oriented reranker/input/context trade-offs on a
larger held-out set. An embedding bake-off remains a sensible later test for
dense ranking and its 256-token limit, not an inferred fix for measured
reranker-ordering failures.
