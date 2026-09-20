# Evaluation V2: initial blind primary-holdout result

This is the first frozen, question-level holdout comparison, run on 2026-09-20. It is an evaluation record, not a retrieval-configuration change. Do not tune on this holdout or edit its labels. The five-case source-coverage challenge was excluded.

## Frozen identity and method

- Primary dataset: `backend/evaluation/datasets/codebase_qa_v2_holdout_v1.json`, version `codebase-qa-v2-holdout-v1.0.0`, frozen dataset hash `3bb15dafe49667f5b53ab39215c3729fe2b71326d9775e095a05077ec6373c8a`, case-set hash `47ffd589172c5d916ade8d8e23d4a30be2dc005c427a97639af6ab51bc544375`.
- Frozen source revision: `7a3b7b05087793975ae0a84d85e7d691d9f3352e`. Application revision used: `895216c5cbd0445e50a92b1cd0998d4f98ca72d2` (clean before this note).
- 34 cases: 29 source-answerable, five absent-feature/unanswerable, eight genuinely multi-evidence; 40 required evidence units. Positive retrieval denominators exclude the five unanswerable cases.
- Disposable corpus: database `codebase_qa_eval_sc_20260919`, repository `codebase-qa-v2`, 212 chunks, manifest `86aa6028950355c88b68d57bb3fc027be3e414acfb5a3ea45e3d2b341d70995b`.
- Fixed candidate depth: 10 for scoring. Dense is exact MiniLM cosine search. Hybrid is the existing PostgreSQL lexical + dense RRF with 50 candidates per branch and constant 60. Rerank-20 scores the first 20 RRF candidates with `cross-encoder/ms-marco-MiniLM-L6-v2` at pinned revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`; it returns the best 10. Existing context selection uses 12,000 characters. No provider calls were made.
- Frozen identity and source anchors passed `python -m scripts.freeze_audited_holdout --check` before retrieval. The generic evaluator report's canonical dataset/case hashes omit freeze-only metadata, so they differ from the frozen-file hashes above; the frozen-file check is authoritative for identity.
- DEV figures below were loaded from prior recorded reports with matching DEV/corpus identities and unchanged retrieval implementation; they were not freshly recomputed in this batch.

## DEV versus blind holdout

Each entry is `DEV → holdout`; percentages use their own denominators (36 answerable/40 units on DEV; 29 answerable/40 units on holdout).

| Metric | Dense | Hybrid RRF | Hybrid + rerank-20 |
| --- | --- | --- | --- |
| Hit@1 | 9/36 25.0% → 10/29 34.5% | 14/36 38.9% → 13/29 44.8% | 18/36 50.0% → 12/29 41.4% |
| Hit@3 | 21/36 58.3% → 21/29 72.4% | 22/36 61.1% → 22/29 75.9% | 28/36 77.8% → 21/29 72.4% |
| Hit@5 | 25/36 69.4% → 24/29 82.8% | 28/36 77.8% → 22/29 75.9% | 31/36 86.1% → 22/29 75.9% |
| Hit@10 | 31/36 86.1% → 26/29 89.7% | 32/36 88.9% → 24/29 82.8% | 34/36 94.4% → 27/29 93.1% |
| MRR@10 | 15.589/36 43.3% → 15.978/29 55.1% | 19.626/36 54.5% → 17.292/29 59.6% | 23.295/36 64.7% → 16.721/29 57.7% |
| Macro evidence recall@10 | 29.5/36 81.9% → 25.167/29 86.8% | 31.5/36 87.5% → 23/29 79.3% | 33.5/36 93.1% → 24.333/29 83.9% |
| Micro evidence recall@10 | 31/40 77.5% → 32/40 80.0% | 35/40 87.5% → 28/40 70.0% | 37/40 92.5% → 31/40 77.5% |
| All evidence@10 | 28/36 77.8% → 24/29 82.8% | 31/36 86.1% → 22/29 75.9% | 33/36 91.7% → 22/29 75.9% |
| Final-context evidence | 31/40 77.5% → 32/40 80.0% | 34/40 85.0% → 28/40 70.0% | 37/40 92.5% → 30/40 75.0% |
| Context sufficiency | 28/36 77.8% → 24/29 82.8% | 30/36 83.3% → 22/29 75.9% | 33/36 91.7% → 21/29 72.4% |
| Selection loss | 0/31 → 0/32 | 1/35 → 0/28 | 0/37 → 1/31 |

Holdout index evidence coverage is 40/40 for all three. Hit@k counts cases with any required unit in top k; all-evidence@k requires every unit. MRR and macro recall have fractional numerators. No statistical significance is claimed.

## Category and multi-evidence diagnostics

Entries are dense / hybrid / rerank-20; the first triple is Hit@10 and the second is evidence units recovered@10. Small categories are descriptive only.

| Primary category | Cases | Hit@10 | Evidence units@10 |
| --- | ---: | --- | --- |
| Semantic/conceptual | 4 | 4/4 100% · 4/4 100% · 4/4 100% | 4/4 100% · 4/4 100% · 4/4 100% |
| Exact identifier | 4 | 3/4 75% · 3/4 75% · 3/4 75% | 3/4 75% · 3/4 75% · 3/4 75% |
| Configuration/constants | 4 | 4/4 100% · 4/4 100% · 4/4 100% | 4/4 100% · 4/4 100% · 4/4 100% |
| Filename/path | 2 | 2/2 100% · 1/2 50% · 1/2 50% | 2/2 100% · 1/2 50% · 1/2 50% |
| Decorator/API route | 3 | 3/3 100% · 3/3 100% · 3/3 100% | 3/3 100% · 3/3 100% · 3/3 100% |
| Architecture | 2 | 2/2 100% · 2/2 100% · 2/2 100% | 2/2 100% · 2/2 100% · 2/2 100% |
| Cross-module | 3 | 2/3 66.7% · 1/3 33.3% · 3/3 100% | 3/7 42.9% · 2/7 28.6% · 4/7 57.1% |
| Multiple required evidence | 4 | 4/4 100% · 4/4 100% · 4/4 100% | 9/10 90% · 7/10 70% · 7/10 70% |
| Difficult near matches | 3 | 2/3 66.7% · 2/3 66.7% · 3/3 100% | 2/4 50% · 2/4 50% · 3/4 75% |

Across the eight audited multi-evidence cases (`cross-01`, `cross-02`, `cross-04`, `multi-01`, `multi-02`, `multi-03`, `multi-04`, `near-05`), dense recovers 12/19 units and all evidence in 4/8 cases; hybrid 9/19 and 3/8; rerank-20 12/19 and 3/8. Final-context sufficiency is respectively 4/8, 3/8, 3/8. DEV's four multi-evidence cases had 3/8, 7/8, 7/8 units and 0/4, 3/4, 3/4 fully covered at top 10. Thus the strong DEV multi-evidence advantage did not generalise to this holdout.

| Holdout case | Dense units@10 | Hybrid units@10 | Rerank-20 units@10 |
| --- | ---: | ---: | ---: |
| `cross-01` | 2/2 | 2/2 | 2/2 |
| `cross-02` | 1/2 | 0/2 | 1/2 |
| `cross-04` | 0/3 | 0/3 | 1/3 |
| `multi-01` | 2/2 | 2/2 | 2/2 |
| `multi-02` | 3/3 | 2/3 | 1/3 |
| `multi-03` | 2/2 | 2/2 | 2/2 |
| `multi-04` | 2/3 | 1/3 | 2/3 |
| `near-05` | 0/2 | 0/2 | 1/2 |

At the evidence-unit level, dense → hybrid has no gains and four losses: `path-05` (3 → >10), `cross-02` YAML allowlist (3 → >10), `multi-02` request binding (3 → >10), and `multi-04` max-top-k constant (7 → >10). Hybrid → rerank-20 recovers units in `cross-02` (non-Python dispatch, RRF 17 → rerank 10), `cross-04` (parsed provenance, 15 → 6), `multi-04` (max-top-k constant, 16 → 7), and `near-05` (storage error, 18 → 7), but loses `multi-02` scope normalisation (1 → 15). Dense → rerank-20 has two unit gains (`cross-04`, `near-05`) and three unit losses (`path-05`, two in `multi-02`). All other answerable cases have unchanged unit counts, although individual ranks may move. No case with at least one hybrid top-10 unit becomes a complete top-10 miss under rerank-20.

## Candidate, window, and truncation diagnostics

The fixed 50+50 branch union contains 40/40 required holdout evidence units (0 absent); unique union sizes range from 53 to 78. This is a read-only candidate diagnostic, not a change to scoring. Evidence outside rerank-20's RRF scoring window includes `identifier-05` (RRF rank 26), `cross-02` YAML allowlist (28), `cross-04` ORM provenance (23), `multi-04` validated top-k setting (27), and `near-05` embedding error (38). Scored-but-below-top-10 units include `path-05` (reranker rank 18), `cross-04` row provenance copy (12), and `multi-02` scope normalisation (15) and request binding (11). These rankings point to ordering/window limitations, not a missing-index or missing-union problem.

Rerank-20's 512-token query-document input limit was exceeded by 71/680 scored pairs (maximum observed 1,345 tokens). The local MiniLM corpus has 35/212 chunks over its effective 256-token embedding input limit. Sixteen of 40 holdout gold units match at least one oversized chunk; 11/40 have only oversized matching chunks. Oversized matching chunks intersect some misses (`identifier-05`, `cross-04`, `multi-04`), while other misses have short evidence (`path-05`, `cross-02`, `near-05`). This is correlation, not causal proof. Rerank-20 lost one retrieved unit during the unchanged context-selection step: `config-03` at reranked position 9; dense and hybrid had zero holdout selection loss.

The five unanswerable cases are reported separately and excluded from positive recall denominators. Retrieval metrics do not establish whether an LLM would abstain; no provider call or answer-abstention evaluation occurred. The coverage challenge was not ranked or scored: its required frontend source paths are absent from the accepted primary index (although `frontend/vite.config.ts` is separately indexed under the existing allowlist).

## Local cost, conclusion, and next step

Warmed local CPU observations used two complete 34-question passes per mode (68 query timings, one warmup query per mode), with a fresh read-only session per query. Median/p95 total retrieval time was dense **6.2/7.4 ms**, hybrid **38.7/44.3 ms**, rerank-20 **465.7/489.0 ms**. These are local observations, not production benchmarks. The reranker ran on CPU; the loaded model reports 22,713,601 parameters.

**Conclusion: PARTIALLY GENERALISES.** Hybrid retains a holdout Hit@1/MRR advantage over dense, and rerank-20 improves hybrid Hit@10, but hybrid reduces top-10 evidence recall and rerank-20 does not recover dense's multi-evidence completeness or preserve its own DEV MRR advantage. Dense remains the serving default; no configuration was tuned. A next experiment should be pre-registered and developed on DEV or a new dataset, focused on multi-evidence candidate ordering/scoring-window behavior; this initial holdout must remain an untouched validation record, not a tuning set.

Verification: frozen/source check passed; 104 unit tests and five PostgreSQL integration tests passed (109/109 combined); compile check and `git diff --check` passed. No normal application repository reindex was run (its observed row count is 118); the disposable corpus manifest remained unchanged. No paid/provider API request occurred.
