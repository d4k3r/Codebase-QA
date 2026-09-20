# Signal-preserving rank fusion — DEV-only experiment

Decision: **REJECT / REVISE as a replacement for current rerank20**. Keep dense
as the serving default and all reranking/fusion modes experimental. The two
new rank-only policies fix two destructive CE demotions on DEV2, but neither
consistently improves DEV1 and DEV2 top-10 evidence recovery. This is
development-set evidence, not new generalisation validation.

## Fixed identities and method

- DEV1: 40 cases, canonical evaluator dataset hash
  `eb095d8701955216171ad3463f6cfb2d7ce2ce44cf8aef47ceaf00c41edd2a8b`.
  Its repeatedly used DEV case-set hash is
  `97a85902564bdcfce9e5e85da38c0f1008cb3fc839296f2a3c4871e1f78a26af`.
- DEV2: 38 independently audited development cases; full audited dataset hash
  `9b24fdf2a80c3135143f2a62f98cd5f792b1a921f71fbb858cfce2da7e067cae`,
  full audited case-set hash
  `f835c2f4e4179c559d4dcaaba1d30df31569b5b4fa348f3c69708a5e7125eab1`.
  The evaluator's narrower schema projection has a different report hash;
  the full audited identity was checked separately before the first run.
- Frozen source revision `7a3b7b05087793975ae0a84d85e7d691d9f3352e`;
  disposable corpus `codebase_qa_eval_sc_20260919`, repository
  `codebase-qa-v2`, 212 rows, manifest
  `86aa6028950355c88b68d57bb3fc027be3e414acfb5a3ea45e3d2b341d70995b`.
- Accepted Batch 2A chunker, normalized 384-dimensional
  `sentence-transformers/all-MiniLM-L6-v2` (resolved local model revision
  `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`), exact dense cosine;
  unchanged PostgreSQL lexical branch; 50 candidates per branch; RRF `c=60`;
  candidate evaluation depth 10; existing 12,000-character complete-chunk
  context selector.
- Cross-encoder `cross-encoder/ms-marco-MiniLM-L6-v2`, pinned/resolved
  revision `233902d25c440f23af6f7d6e94d2946bac0bee0a`, CPU, 512-token
  input limit, first 20 RRF candidates, existing input formatting/truncation.
  No new model, retriever, or input transformation was used.

The four DEV2 baselines (dense, lexical, hybrid, current rerank20) were run
**before** implementing rank fusion. DEV1's recorded dense/hybrid/rerank20
baselines reproduced exactly. All runs were read-only on the disposable
database. No provider calls, normal application reindexing, HOLDOUT run,
HOLDOUT tuning, or HOLDOUT file edits occurred.

## Ranking policies

Let `r_D`, `r_L`, `r_H`, `r_C` be dense, lexical, existing hybrid/RRF, and
cross-encoder ranks. Missing ranks contribute **zero**. CE ranks exist only
for the first 20 RRF candidates; candidates outside that window are retained
with their available non-CE ranks. All policies start with the same 50+50
scoped candidate union and deterministic stable chunk identity.

- Hybrid baseline: `H = 1/(60+r_D) + 1/(60+r_L)` for available branches.
- Current rerank20: CE raw score orders only the first 20 RRF candidates;
  this order replaces their RRF order. Raw CE scores are not probabilities.
- Two-signal `rerank_rrf_ce`: `F2 = 1/(60+r_H) + 1/(60+r_C)` when CE-scored;
  otherwise only `1/(60+r_H)`.
- Three-signal `rerank_three_signal`:
  `F3 = 1/(60+r_D) + 1/(60+r_L) + 1/(60+r_C)` for available ranks.

Higher fused score wins. Equal scores fall back to original RRF rank, then
stable repository/path/line/symbol/row identity. Cosine distance, PostgreSQL
lexical score, original RRF score/rank, CE raw score/rank, and final
experimental fusion score/rank remain separate fields. No raw scores from
different systems are numerically added.

## DEV1 metrics — 36 answerable cases, 40 required units

`H1/H3/H5/H10` are case Hit@k. `Micro` and `Context` count evidence units.
`All` and `Sufficient` count cases with every required unit. MRR and macro
recall have 36-case denominators; unanswerable cases are excluded.

| Mode | H1 | H3 | H5 | H10 | MRR@10 | Macro@10 | Micro@10 | All@10 | Context | Sufficient | Selection loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dense | 9/36 | 21/36 | 25/36 | 31/36 | .433 | 29.5/36 | 31/40 | 28/36 | 31/40 | 28/36 | 0/31 |
| Lexical | 10/36 | 16/36 | 21/36 | 25/36 | .385 | 24.5/36 | 27/40 | 24/36 | 25/40 | 23/36 | 2/27 |
| Hybrid RRF | 14/36 | 22/36 | 28/36 | 32/36 | .545 | 31.5/36 | 35/40 | 31/36 | 34/40 | 30/36 | 1/35 |
| Rerank20 | 18/36 | 28/36 | 31/36 | 34/36 | .647 | 33.5/36 | 37/40 | 33/36 | 37/40 | 33/36 | 0/37 |
| RRF + CE rank | 16/36 | 29/36 | 31/36 | 34/36 | .616 | 33.5/36 | 37/40 | 33/36 | 37/40 | 33/36 | 0/37 |
| Dense + lexical + CE rank | 17/36 | 26/36 | 31/36 | 33/36 | .616 | 32.5/36 | 36/40 | 32/36 | 36/40 | 32/36 | 0/36 |

## DEV2 metrics — first baselines and experiment

DEV2 has 36 answerable cases, 60 required units, two unanswerable cases. It
was not scored before this batch. Its audited 16 multi-evidence cases and 16
meaningful long-position cases are not interchangeable with primary-category
counts.

| Mode | H1 | H3 | H5 | H10 | MRR@10 | Macro@10 | Micro@10 | All@10 | Context | Sufficient | Selection loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Dense | 13/36 | 22/36 | 26/36 | 30/36 | .520 | 28.05/36 | 48/60 | 25/36 | 48/60 | 25/36 | 0/48 |
| Lexical | 13/36 | 22/36 | 29/36 | 33/36 | .531 | 28.183/36 | 44/60 | 23/36 | 40/60 | 19/36 | 4/44 |
| Hybrid RRF | 21/36 | 28/36 | 30/36 | 31/36 | .682 | 28.967/36 | 49/60 | 26/36 | 47/60 | 25/36 | 2/49 |
| Rerank20 | 21/36 | 28/36 | 34/36 | 35/36 | .709 | 32.75/36 | 53/60 | 30/36 | 53/60 | 30/36 | 0/53 |
| RRF + CE rank | 22/36 | 28/36 | 31/36 | 33/36 | .717 | 31.3/36 | 52/60 | 29/36 | 52/60 | 29/36 | 0/52 |
| Dense + lexical + CE rank | 22/36 | 28/36 | 30/36 | 33/36 | .708 | 31.3/36 | 52/60 | 29/36 | 51/60 | 28/36 | 1/52 |

The five DEV1 and two DEV2 unanswerable cases are not positive-retrieval
recall denominators; no answer-abstention/provider evaluation was done.

### Descriptive pooled totals (not a substitute for separate DEV results)

Across 72 answerable cases and 100 evidence units, dense / hybrid / current
rerank20 / RRF+CE / three-signal have respectively: Hit@10
`61/72, 63/72, 69/72, 67/72, 66/72`; micro evidence recall@10
`79/100, 84/100, 90/100, 89/100, 88/100`; final-context evidence
`79/100, 81/100, 90/100, 89/100, 87/100`. Pooled Hit@1 is
`22/72, 35/72, 39/72, 38/72, 39/72`; MRR@10 is
`.477, .614, .678, .666, .662`. These are descriptive counts from two
development sets, not independent validation.

## Failure taxonomy and candidate union

The exact 50+50 dense/lexical union contains **DEV1 40/40** and **DEV2
60/60** gold units. It is a strong candidate generator on these two sets, not
proof of general candidate coverage. The per-case read-only diagnostics are
reproducible with `scripts.analyse_signal_ranking` and distinguish candidate
generation, top-10 ordering, rerank window, CE ordering, destructive RRF
demotion, context loss, multi-evidence competition, long-chunk association,
and near-match/distractor association. Classes can overlap; long-chunk
association is not causal attribution.

| Cohort/mode | Union-absent units | Top-10-missing units | Of misses: outside CE top-20 | Scored but CE rank >10 | Strong RRF top-10 demoted by CE | Context-lost units |
|---|---:|---:|---:|---:|---:|---:|
| DEV1 dense | 0 | 9 | — | — | — | 0 |
| DEV1 lexical | 0 | 13 | — | — | — | 2 |
| DEV1 hybrid | 0 | 5 | — | — | — | 1 |
| DEV1 rerank20 | 0 | 3 | 3 | 0 | 0 | 0 |
| DEV1 RRF+CE | 0 | 3 | 3 | 0 | 0 | 0 |
| DEV1 three-signal | 0 | 4 | 3 | 0 | 0 | 0 |
| DEV2 dense | 0 | 12 | — | — | — | 0 |
| DEV2 lexical | 0 | 16 | — | — | — | 4 |
| DEV2 hybrid | 0 | 11 | — | — | — | 2 |
| DEV2 rerank20 | 0 | 7 | 2 | 5 | 2 | 0 |
| DEV2 RRF+CE | 0 | 8 | 2 | 3 CE-low among misses | 0 | 0 |
| DEV2 three-signal | 0 | 8 | 2 | 3 CE-low among misses | 0 | 1 |

The two DEV2 rerank-window misses are `dev2-multi-03`'s publication unit
(in the union but outside the retained top-50 RRF report) and
`dev2-multi-04`'s HTTP error unit (RRF rank 24). DEV1's three remaining
rerank20 misses are all window misses at RRF ranks 29, 30 and 33. Scored
but poorly ordered DEV2 units include `dev2-multi-07`'s sampling and
dispatch evidence and `dev2-near-05`'s stored-column evidence. Context loss
is small and is not the dominant bottleneck.

### DEV2 audited slices, units recovered at top 10

| Slice | Cases / units | Union | Dense | Hybrid | Rerank20 | RRF+CE | Three-signal |
|---|---:|---:|---:|---:|---:|---:|---:|
| Genuine multi-evidence | 16 / 40 | 40/40 | 33/40 | 34/40 | 34/40 | 35/40 | 35/40 |
| Meaningfully long-position | 16 / 29 | 29/29 | 20/29 | 23/29 | 25/29 | 23/29 | 23/29 |
| Mixed semantic + exact | 2 / 8 | 8/8 | 7/8 | 6/8 | 8/8 | 7/8 | 7/8 |
| Distractor | 4 / 7 | 7/7 | 6/7 | 6/7 | 5/7 | 6/7 | 6/7 |
| Cross-module | 4 / 14 | 14/14 | 11/14 | 10/14 | 12/14 | 11/14 | 11/14 |
| Architecture | 3 / 6 | 6/6 | 5/6 | 6/6 | 6/6 | 6/6 | 6/6 |
| Configuration/constants | 6 / 8 | 8/8 | 7/8 | 6/8 | 8/8 | 6/8 | 6/8 |
| Ordinary developer questions | 2 / 2 | 2/2 | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 |

Multi-evidence all-units@10 / final-context-sufficient cases are DEV1:
hybrid `3/4 / 3/4`, rerank20 `3/4 / 3/4`, both rank fusions `3/4 / 3/4`;
DEV2: dense `10/16 / 10/16`, hybrid `11/16 / 10/16`, rerank20
`11/16 / 11/16`, both rank fusions `12/16 / 12/16`. All multi-evidence
gold units are in the branch union (`8/8` DEV1, `40/40` DEV2).

All multi-evidence cases below use `required/union`, then units recovered at
top 10 by hybrid/current CE/RRF+CE, then RRF+CE final-context units. Each
`unit:R/C/F` entry gives the evidence unit's original RRF, CE, and RRF+CE
rank. `—` means outside the retained RRF top 50 or unscored; every listed
unit was nevertheless found in the full 50+50 branch union. All-evidence
success and context sufficiency mean the corresponding count equals
`required` in that row. The three-signal unit counts match RRF+CE on these
20 cases, although individual ranks can differ.

| Case | Required/union | Hybrid / CE / RRF+CE / context | Evidence-unit ranks R/C/F |
|---|---:|---:|---|
| DEV1 `multi-01` | 2/2 | 2/2/2/2 | chunking-stage 3/7/4; discovery-stage 6/4/5 |
| DEV1 `multi-02` | 2/2 | 2/2/2/2 | embedding-stage 5/4/3; storage-stage 6/2/2 |
| DEV1 `multi-03` | 2/2 | 2/2/2/2 | context-stage 5/5/3; retrieval-stage 10/6/7 |
| DEV1 `multi-04` | 2/2 | 1/1/1/1 | client-options 1/1/1; llm-settings 29/—/29 |
| `dev2-multi-01` | 2/2 | 2/1/2/2 | entry-no-follow 2/1/1; root-resolution 1/15/6 |
| `dev2-multi-03` | 2/2 | 1/1/1/1 | assignment-fallback 9/1/4; fallback-publication —/—/— |
| `dev2-multi-04` | 2/2 | 1/1/1/1 | mismatch-before-delete 1/1/1; storage-http-error 24/—/24 |
| `dev2-multi-05` | 2/2 | 2/2/2/2 | app-name-setting 7/2/4; fastapi-title-use 1/1/1 |
| `dev2-multi-07` | 4/4 | 2/2/2/2 | config-only-screen-branch 1/3/2; config-sample-screen 16/14/17; python-chunker-dispatch 20/15/18; python-full-read 4/5/4 |
| `dev2-multi-08` | 2/2 | 2/2/2/2 | generation-http-status 2/3/2; malformed-completion 1/1/1 |
| `dev2-architecture-01` | 2/2 | 2/2/2/2 | readonly-score 10/3/6; write-gate 3/2/2 |
| `dev2-architecture-03` | 2/2 | 2/2/2/2 | evaluation-preflight-order 4/5/5; manifest-validation 1/3/2 |
| `dev2-architecture-05` | 2/2 | 2/2/2/2 | env-path-definition 4/2/3; settings-env-path 1/1/1 |
| `dev2-semantic-02` | 2/2 | 2/2/2/2 | empty-context-construction 1/1/1; provider-continuation 4/2/2 |
| `dev2-semantic-04` | 2/2 | 2/2/2/2 | per-vector-dimension-check 3/5/4; validator-called-before-return 2/2/1 |
| `dev2-semantic-06` | 2/2 | 2/2/2/2 | original-line-pieces 10/4/6; whitespace-group-flush 4/5/5 |
| `dev2-exact-01` | 2/2 | 2/2/2/2 | batch-size-definition 1/2/1; batch-size-use 4/1/2 |
| `dev2-near-03` | 4/4 | 4/3/4/4 | embedding-whitespace-guard 1/1/1; search-route-forwarding 2/3/2; search-schema-min-length 3/15/9; search-service-embedding 4/7/4 |
| `dev2-mixed-01` | 3/3 | 2/3/3/3 | ask-request-scope 3/5/2; ask-route-forwarding 1/2/1; rag-retrieval-forwarding 11/1/3 |
| `dev2-mixed-03` | 5/5 | 4/5/4/4 | client-handoff 7/2/5; client-key-option 3/3/3; llm-api-key-setting 14/10/13; placeholder-key-guidance 4/1/1; required-key-extraction 1/5/2 |

### Important per-case rank changes

| Case / evidence | RRF rank | CE rank | RRF+CE / three-signal rank | Effect vs current rerank20 |
|---|---:|---:|---:|---|
| `dev2-multi-01` root resolution | 1 | 15 | 6 / 2 | Both fusions restore the second required unit. |
| `dev2-near-03` search schema minimum | 3 | 15 | 9 / 7 | Both restore the fourth required unit. |
| `dev2-exact-03` healthcheck | 20 | 5 | 12 / 19 | Both lose a current CE success. |
| `dev2-long-04` timeout bound | 20 | 5 | 13 / 20 | Both lose a CE success; its CE input exceeded 512 tokens. |
| `dev2-mixed-03` API-key setting | 14 | 10 | 13 / 13 | Both lose one of five units; its CE input exceeded 512 tokens. |
| DEV1 `config-02` excluded-directories constant | 15 | 3 | 8 / 11 | Three-signal alone loses a current CE success. |

Thus the two-signal policy removes the two **observed** DEV2 destructive
demotions of strong RRF top-10 evidence, but creates three different top-10
losses. It does not solve `dev2-multi-03`, `dev2-multi-04`, or
`dev2-multi-07`; their complementary evidence remains displaced or outside
the reranking window. Both DEV datasets have complete candidate-union recall,
so the residual measured problem is rank/window/selection, not missing source
representation in the candidate union.

### Long source positions and truncation association

The accepted MiniLM input limit is 256 tokens including two special tokens
(about 254 content tokens). The accepted corpus has 35/212 chunks over that
limit. DEV2's 16 audited `long_chunk` cases cover 29 required units; offline
tokenizer-position checks found 18 units with at least one acceptable span
extending beyond the ~254-content-token boundary. `dev2-mixed-05` has a
complete short test alternative despite its late implementation span.
The per-unit positions are in the machine diagnostic output; they are
approximate because tokenization of a prefix can differ at the boundary.
Current rerank20 gets 25/29 long-slice units, versus hybrid 23/29 and both
new fusions 23/29. This correlation does **not** establish that MiniLM
truncation caused a particular ranking miss. The existing CE policy measured
58/800 DEV1 and 81/760 DEV2 query-document pairs above its 512-token input
limit (maximum observed 1,334 and 1,345 tokens respectively); no input
policy changed in this experiment.

## Warm local latency and resource cost

Eight answerable questions from each DEV set, three warmed sequential repeats
each (24 observations per cohort), measured directly around dense search,
hybrid candidate generation, CE scoring, and rank fusion. Median/p95 ms:

| Cohort | Dense | Hybrid retrieval | CE scoring | Rerank20 total | RRF+CE fusion overhead / total | Three-signal overhead / total |
|---|---:|---:|---:|---:|---:|---:|
| DEV1 | 6.88/8.28 | 38.04/42.41 | 429.93/444.20 | 467.21/483.22 | .41/.72 / 467.59/483.63 | .39/.43 / 467.56/483.57 |
| DEV2 | 7.45/8.57 | 40.68/46.15 | 444.99/476.95 | 487.09/518.82 | .41/.48 / 487.47/519.29 | .40/.52 / 487.49/519.28 |

The 22,713,601-parameter CE ran on CPU and scored exactly 20 pairs/query.
Fusion is negligible next to CE inference; latency is not the reason to
reject these variants. These are local observations, not production SLOs.

## Interpretation and next step

DEV2 repeats DEV1's broad finding that hybrid improves early dense ranking and
reranking improves top-10 evidence recovery, but its larger multi-evidence
and long-position slices expose more complementary-evidence competition.
Lexical-only DEV2 Hit@10 is higher than dense (33/36 vs 30/36) while its
micro evidence recall and context sufficiency are lower (44/60 vs 48/60;
19/36 vs 25/36): one relevant hit is not the same as all required evidence.

RRF+CE rank fusion is a **mixed diagnostic** but **REJECT / REVISE as the
next default ranking policy**: DEV1 top-10 evidence ties current rerank20
while Hit@1/MRR fall; DEV2 gains one multi-evidence unit but loses two net
top-10 case hits and one net evidence unit, with regressions on configuration,
long-position and cross-module slices. Three-signal fusion is weaker still.
Do not use the already-observed HOLDOUT to break this tie. Keep the serving
default dense and current rerank20 available as the stronger experimental
baseline. A controlled **multi-evidence/complementary-selection** experiment
is better justified next than another simple rank-addition policy: the union
already contains every DEV gold unit, while required complementary units
compete for top-10/context positions. An embedding-model bake-off remains a
separate plausible follow-up for measured long-source truncation, not a fix
implemented here.

Reproduce report files with `scripts.evaluate_retrieval` for each DEV dataset
and mode, then use `scripts.analyse_signal_ranking` for full per-case union,
rank and failure-class diagnostics and `scripts.benchmark_signal_ranking` for
local timings. Both helper scripts accept only DEV1/DEV2 and use a read-only
transaction. Neither performs answer generation or provider calls.
